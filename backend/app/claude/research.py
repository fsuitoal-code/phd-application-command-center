"""Program-research contract.

Given a program name and the official program/department URL the user pasted,
gather PUBLIC facts (program details, faculty, deadlines, requirements) via the
Agent SDK's WebFetch tool, restricted to that institution's domain.

Rule 3 is enforced structurally, not just by prompt: a ``can_use_tool`` callback
DENIES any tool that is not a WebFetch within the seed URL's registrable domain
(so no general web search, no Google Scholar, no off-domain fetches). Rule 8:
everything comes back as ``researched`` / ``needs_human_verification``. Rule 7
spirit: the model is told never to invent facts — unknown fields stay null.
"""

from __future__ import annotations

import json
from urllib.parse import quote as urlquote, urlparse

from pydantic import BaseModel, Field, field_validator

from app.config import ClaudeTask, settings

# ── Structured result shape ────────────────────────────────────────────────
class ResearchedFaculty(BaseModel):
    name: str
    research_areas: str | None = None
    homepage_url: str | None = None


class ResearchedDeadline(BaseModel):
    type: str = "other"  # application | funding | rec_letters_by | test_scores_by | other
    date: str  # ISO YYYY-MM-DD
    notes: str | None = None


class ResearchedRequirement(BaseModel):
    kind: str = "other"  # gre | toefl | app_fee | fee_waiver | app_cost | rec_letters | essay_type | other
    value: str | None = None


class ResearchedNote(BaseModel):
    """One cited fact. Stored as its own row (ProgramNote), not assembled
    into markdown -- each note is individually confirmable (Rule 8)."""

    text: str
    quote: str
    source_url: str
    source_label: str | None = None


#: Text fragments stop matching well past a sentence or two, and a very long
#: one is more likely to differ from the page by a stray character.
_MAX_QUOTE_CHARS = 240


def quote_fragment_url(url: str, quote: str) -> str:
    """Point ``url`` at ``quote`` using a scroll-to-text fragment.

    ``page#:~:text=...`` makes the browser scroll to that text and highlight
    it, so clicking a citation lands on the sentence rather than the top of a
    long admissions page. Unsupported browsers, and quotes that do not match
    the page exactly, simply open the page as before -- which is what these
    links did anyway, so the failure mode is the old behaviour.

    Two details the syntax demands: a URL that already has a fragment takes
    ``:~:`` appended to it rather than a second ``#``, and ``-`` and ``,``
    delimit the fragment's own grammar, so they must survive as escapes.
    """
    snippet = " ".join(quote.split())[:_MAX_QUOTE_CHARS].strip()
    if not snippet:
        return url
    # quote() leaves "-" alone as an unreserved character, but a literal "-"
    # inside the snippet would read as the prefix/suffix delimiter.
    encoded = urlquote(snippet, safe="").replace("-", "%2D")
    separator = ":~:" if "#" in url else "#:~:"
    return f"{url}{separator}text={encoded}"


def _render_note(item: dict) -> str | None:
    """One structured note -> one markdown bullet, with its quote beneath."""
    text = str(item.get("text") or "").strip().lstrip("-*•").strip()
    quote = str(item.get("quote") or "").strip().strip('"').strip()
    url = str(item.get("source_url") or "").strip()
    if not text or not quote or not url:
        return None

    label = str(item.get("source_label") or "").strip() or _label_for(url)
    bullet = f"- {text} ([{label}]({quote_fragment_url(url, quote)}))"
    # The quote goes on its own line so the reader can check the claim against
    # the source's own words without leaving the page.
    return f"{bullet}\n> {quote}"


def _label_for(url: str) -> str:
    """A short link label when the model did not supply one."""
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    if segments:
        return segments[-1].rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    return (parsed.hostname or url).replace("www.", "")


class ResearchedProgram(BaseModel):
    university: str
    department: str | None = None
    degree: str | None = None
    portal_url: str | None = None
    #: Each item becomes its own ProgramNote row (Rule 8: source=researched,
    #: needs_human_verification=True) in the router, not assembled markdown.
    notes: list[ResearchedNote] = Field(default_factory=list)
    faculty: list[ResearchedFaculty] = Field(default_factory=list)
    deadlines: list[ResearchedDeadline] = Field(default_factory=list)
    requirements: list[ResearchedRequirement] = Field(default_factory=list)

    @field_validator("faculty", mode="after")
    @classmethod
    def _cap_faculty(cls, value: list[ResearchedFaculty]) -> list[ResearchedFaculty]:
        """Keep at most ``max_faculty_per_program``, however many came back.

        The prompt asks for a shortlist, but a prompt is a request. A pass that
        returned an entire Industrial Engineering directory -- 53 names,
        adjuncts and online-program instructors included, every research_areas
        empty -- is what made this cap exist, and an instruction alone would not
        have stopped it. The model is asked to put the most relevant first, so
        truncating from the front keeps its own ranking.
        """
        return value[: settings.max_faculty_per_program]

    @field_validator("notes", mode="before")
    @classmethod
    def _drop_uncited_notes(cls, value: object) -> list[dict]:
        """Keep only fully-cited items -- each carries the sentence it is
        claiming, the page it came from, and the EXACT quote from that page.
        An item missing the quote or the URL is dropped rather than kept: an
        uncitable note is the kind that turned out to be commentary on the
        app's own other fields ("the portal did not list these dates"), which
        is noise next to a Deadlines section that has the dates. Requiring a
        quote removes that whole category by construction -- no page
        sentence says what the model failed to find. A non-list value (a
        model that free-styles outside the schema) yields no notes rather
        than guessing at its shape.
        """
        if not isinstance(value, list):
            return []
        items: list[dict] = []
        for item in value:
            if isinstance(item, ResearchedNote):
                # Already validated (e.g. constructed directly in tests) --
                # its required fields guarantee it is fully cited.
                items.append(item.model_dump())
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip().lstrip("-*•").strip()
            quote = str(item.get("quote") or "").strip().strip('"').strip()
            url = str(item.get("source_url") or "").strip()
            if not text or not quote or not url:
                continue
            label = str(item.get("source_label") or "").strip() or _label_for(url)
            items.append(
                {"text": text, "quote": quote, "source_url": url, "source_label": label}
            )
        return items


def registrable_domain(url: str) -> str:
    """Approximate eTLD+1 from a URL host (last two labels).

    Good enough for the common ``dept.university.edu`` case; multi-part public
    suffixes like ``ac.uk`` are not special-cased (documented limitation).
    """
    host = (urlparse(url).hostname or "").lower().strip(".")
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _host_in_domain(url: str, domain: str) -> bool:
    host = (urlparse(url).hostname or "").lower().strip(".")
    return host == domain or host.endswith("." + domain)


_SYSTEM_PROMPT = """You are a meticulous research assistant gathering PUBLIC \
facts about a graduate program for an applicant's tracker.

HARD RULES (do not violate):
- Use ONLY the WebFetch tool, and ONLY on pages within the institution's own \
domain: {domain}. Start at the URL given and follow same-domain links \
(department page, faculty directory, admissions/deadlines, requirements).
- NEVER fetch Google Scholar or any other domain. If information is not on the \
institution's site, leave the field null rather than guessing.
- Do NOT invent facts. Every field must be grounded in a page you actually \
fetched. Unknown values are null. Include ALL deadlines and requirements \
you find (do not omit) — but never fabricate to fill gaps.
- Actively look for these six requirement facts, since every program is \
tracked against them: GRE, TOEFL, application fee, fee waiver availability, \
number of recommendation letters required, and the required essay type \
(statement of purpose, personal statement, statement of objectives, video \
essay, etc.). Leave any you can't confirm off the list rather than guessing \
— the tracker already shows them as unverified until you fill one in.

FACULTY (the "faculty" field) -- a SHORTLIST, not the directory:
- Return AT MOST {max_faculty} people, ordered most relevant first. \
Returning fewer is correct when fewer genuinely fit; returning the whole \
directory is not. Anything past {max_faculty} is discarded, so spend the \
effort choosing rather than listing.
- Relevance follows the department's own emphasis: order by what the \
department itself presents as its main research thrusts, and prefer faculty \
whose current work is described in the most detail.
- Include only research/tenure-track faculty who advise doctoral \
students. Skip adjuncts, teaching-track faculty and professors of \
practice, emeriti, visiting and affiliate staff, and anyone who appears \
only on an online or professional-masters page -- those names are the \
bulk of a directory and none of them take PhD students.
- Fill in "research_areas" for every person you return, in your own words \
from the page you read. A name with no research areas is not a shortlist \
entry: if you cannot say what someone works on, leave them out and return \
fewer.

NOTES FORMAT (the "notes" field):
- "notes" is a JSON ARRAY OF OBJECTS, never one block of text. One fact per \
object, and no line breaks inside any string. Each object is exactly:
  {{"text": str, "quote": str, "source_url": str, "source_label": str}}
- "text" is your own one-sentence summary of the fact, written for the \
applicant. Cover only what they would want at a glance and that has no \
dedicated field of its own (funding and stipend terms, cohort size, advising \
or rotation structure, application components, caveats).
- "quote" is the EXACT sentence from the page that establishes the fact, \
copied character for character -- not paraphrased, not stitched together from \
two places, not trimmed mid-word. It is checked against the page, so an \
approximation is worse than no note at all. Keep it under 240 characters; if \
the supporting sentence is longer, choose the clause that carries the fact.
- "source_url" is the {domain} page you actually fetched and that the quote \
appears on. "source_label" is 2-4 words naming that page, e.g. "funding page".
- EVERY object needs all four fields. If you cannot quote a sentence that \
states the fact, do not write the note. There is no uncited note.
- Never write a note ABOUT this app's other fields. "The portal did not list \
the dates" is not a note -- the deadlines you found are already in \
"deadlines", and the reader can see them. Neither is "the faculty directory \
gave no research areas": that belongs in the faculty entries being null. \
Notes are facts about the PROGRAM, each backed by a sentence on a page.
- Write for the applicant, not as a log of your own research. "Fully funded \
for five years" is a note; "the catalog page did not list this, so I checked \
another page" is not.
- If there is nothing worth saying, notes is an empty array.

When done, output ONLY a single JSON object (no prose, no markdown fences) with \
this shape:
{{"university": str, "department": str|null, "degree": str|null, \
"portal_url": str|null, \
"notes": [{{"text": str, "quote": str, "source_url": str, "source_label": str}}], \
"faculty": [{{"name": str, "research_areas": str|null, "homepage_url": str|null}}], \
"deadlines": [{{"type": "application|funding|rec_letters_by|test_scores_by|other", \
"date": "YYYY-MM-DD", "notes": str|null}}], \
"requirements": [{{"kind": "gre|toefl|app_fee|fee_waiver|app_cost|rec_letters|essay_type|other", \
"value": str|null}}]}}
"""


def _make_permission_callback(domain: str):
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    async def can_use_tool(tool_name: str, tool_input: dict, _context):
        # Rule 3 enforcement at the tool boundary.
        if tool_name != "WebFetch":
            return PermissionResultDeny(
                message=f"Only WebFetch is permitted; '{tool_name}' is blocked.",
            )
        url = str(tool_input.get("url", ""))
        if not _host_in_domain(url, domain):
            return PermissionResultDeny(
                message=f"Fetch of {url!r} blocked: outside allowed domain {domain}.",
            )
        return PermissionResultAllow()

    return can_use_tool


def _explain_sdk_failure(exc: Exception) -> str:
    """Turn an Agent SDK failure into something worth showing the user.

    A pass that dies has already spent real money, so "HTTP 500" is the worst
    possible answer. The CLI reports *why* it stopped in the terminal result
    frame, which the SDK hands over on ``ResultError``.
    """
    status = getattr(exc, "api_error_status", None)
    if getattr(exc, "terminal_reason", None) == "api_error" or status:
        return f"the Claude API returned an error{f' (status {status})' if status else ''}. Nothing was saved."
    return f"{type(exc).__name__}: {exc}"


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in research output.")
    # strict=False tolerates literal control characters (e.g. raw newlines inside
    # a multi-line string value like an email body) that models often emit.
    return json.loads(text[start : end + 1], strict=False)


async def research_program(query: str, official_url: str) -> ResearchedProgram:
    """Run the research pass and return structured, researched facts.

    The faculty shortlist holds at most ``settings.max_faculty_per_program``
    people, ranked by the department's own emphasis (see the prompt).

    Raises RuntimeError if the SDK/CLI is unavailable (Rule 1: no API-key
    fallback), or ValueError if the model returns unparseable output.
    """
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKError,
            ResultMessage,
            TextBlock,
            query as sdk_query,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "claude-agent-sdk unavailable. Install it and run `claude /login`."
        ) from exc

    domain = registrable_domain(official_url)
    if not domain:
        raise ValueError("Could not determine a domain from the official URL.")

    options = ClaudeAgentOptions(
        model=settings.model_for(ClaudeTask.RESEARCH_SYNTHESIS),
        system_prompt=_SYSTEM_PROMPT.format(
            domain=domain,
            max_faculty=settings.max_faculty_per_program,
        ),
        # Do NOT put WebFetch in allowed_tools: an allow-list entry auto-approves
        # the tool and SHADOWS can_use_tool, defeating the domain guard. Leaving
        # it out routes every tool call through the callback, which allow-lists
        # only in-domain WebFetch and denies everything else (Rule 3).
        disallowed_tools=["WebSearch"],
        can_use_tool=_make_permission_callback(domain),
    )

    prompt = (
        f"Research this program: {query}\n"
        f"Official site to start from: {official_url}\n"
        f"Fetch that page and follow same-domain links to collect the facts."
    )

    final_text = ""
    try:
        async for message in sdk_query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                parts = [b.text for b in message.content if isinstance(b, TextBlock)]
                if parts:
                    final_text = "".join(parts)
            elif isinstance(message, ResultMessage):
                result = getattr(message, "result", None)
                if isinstance(result, str) and result.strip():
                    final_text = result
    except ClaudeSDKError as exc:
        # ClaudeSDKError descends from Exception, not RuntimeError, so without
        # this it escapes the router's (RuntimeError, ValueError) handler and
        # the user gets a bare HTTP 500 after a pass that has already spent
        # real money. Re-raise as RuntimeError so
        # the router answers 502 with a reason worth reading.
        raise RuntimeError(_explain_sdk_failure(exc)) from exc

    data = _extract_json(final_text)
    return ResearchedProgram.model_validate(data)
