"""The per-faculty dossier: one researched, cited profile of one person.

A faculty row starts as a name and a line of research areas. That is enough to
list someone and nothing like enough to decide whether to spend an application
on them. This contract produces what the applicant actually needs to read --
what the person works on *now*, who is in the group and where they went, how
students are funded, where the career stage leaves them, what to open an email
with, and what to ask -- as a set of named sections whose every claim carries
the sentence it came from.

WEB SCOPE (Rule 3 -- read this before widening it further)
----------------------------------------------------------
Program research (``app.claude.research``) is locked to the institution's own
domain. This pass is deliberately wider, because the facts it wants are not all
on the university's site: a lab runs at its own address, a grant is recorded by
the funder, a group's output is announced by a news office.

So the tool boundary here allows WebSearch, and allows WebFetch on any host
EXCEPT a deny-list. What the deny-list keeps out:

- **Google Scholar**, which Rule 3 names explicitly. Search may surface a
  Scholar link; this makes it unfetchable, so it cannot become a source.
- **Search-engine result pages.** Searching goes through WebSearch, which is
  the supported path. Fetching a results page is scraping a search engine.

Everything else that keeps this honest is unchanged: no scraping library is
introduced (WebFetch is the SDK's own tool and honours robots.txt itself), and
every sentence in the output must quote the page it came from or it is dropped
(Rule 8). Anti-fabrication and ``needs_human_verification`` per Rule 7.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.claude.research import _extract_json, _explain_sdk_failure, _render_note
from app.config import ClaudeTask, settings

#: Brands WebFetch may never touch, whatever a search result says.
_DENIED_BRANDS = (
    "google",
    "googleusercontent",
    "bing",
    "duckduckgo",
    "yahoo",
    "baidu",
    "yandex",
)

#: A denied host is one of those brands followed by nothing but a public
#: suffix: ``google.com``, ``scholar.google.co.uk``, ``www.bing.com``.
#:
#: Matching the last two labels instead (the approximation
#: ``research.registrable_domain`` makes) silently misses
#: ``scholar.google.co.uk``, which resolves to ``co.uk`` -- the exact host Rule
#: 3 names. Requiring only short TLD-ish labels after the brand is also what
#: keeps a person out of the blast radius: ``bing.li.university.edu`` is
#: somebody's homepage, not a search engine, and it does not match.
_DENIED_HOST = re.compile(
    r"(?:^|\.)(?:" + "|".join(_DENIED_BRANDS) + r")(?:\.[a-z]{2,4}){1,2}$"
)

#: The sections asked for, in the order they are written. Modelled on the
#: reference dossiers: what the person does, who they do it with, who pays,
#: where they are in a career, what to be glad or wary about, who else to name,
#: what to open with, and what to ask.
_SECTIONS = (
    "Research",
    "Lab & students",
    "Funding",
    "Career stage",
    "Signals",
    "Adjacent faculty",
    "Outreach hooks",
    "To ask",
)

_ANTIFAB = (
    "ANTI-FABRICATION (critical): every claim must come from a page you "
    "actually fetched, and must quote it. Never invent a paper, a grant, a "
    "student, a title, or a shared history. Never guess whether someone is "
    "recruiting. If you could not establish something, say that you could not "
    "-- an honest 'not stated publicly' is worth more here than a plausible "
    "sentence, because the applicant will act on this."
)


# ── Output shape ───────────────────────────────────────────────────────────
class DossierNote(BaseModel):
    """One claim, and the sentence on the page that establishes it."""

    text: str
    quote: str
    source_url: str
    source_label: str


class DossierSection(BaseModel):
    heading: str
    items: list[DossierNote] = Field(default_factory=list)


class FacultyDossier(BaseModel):
    summary: str | None = None
    research_areas: str | None = None
    homepage_url: str | None = None
    sections: list[DossierSection] = Field(default_factory=list)
    needs_human_verification: bool = True

    def to_markdown(self) -> str:
        """Render as the same bullet-and-quote markdown program notes use.

        One renderer serves both: ``## heading`` opens a section, each claim is
        a bullet whose link jumps to the quoted sentence, and the quote sits
        underneath it. A section whose items all failed the quote/URL check is
        dropped rather than printed empty -- an empty "Funding" heading reads
        as "no funding", which is not what it means.

        "Bottom line" leads, and is the one part written as a plain paragraph
        rather than quoted bullets: it is the model's own read of what it
        found, and it should not be able to pass for a sourced fact. Every
        other section looks different on the page precisely because it is.
        """
        blocks: list[str] = []
        summary = (self.summary or "").strip()
        if summary:
            # One line: a paragraph break here would render as two paragraphs.
            blocks.append("## Bottom line\n" + " ".join(summary.split()))
        for section in self.sections:
            rendered = [
                note
                for note in (_render_note(i.model_dump()) for i in section.items)
                if note
            ]
            if not rendered:
                continue
            heading = section.heading.strip().lstrip("#").strip()
            blocks.append(f"## {heading}\n" + "\n".join(rendered))
        return "\n\n".join(blocks)


# ── Tool boundary ──────────────────────────────────────────────────────────
def is_denied(url: str) -> bool:
    """True for a host this pass must not fetch, whatever surfaced it.

    Scholar is the one Rule 3 names; it is blocked by way of blocking google
    entirely, since no google host is a primary source for any of this.
    """
    host = (urlparse(url).hostname or "").lower().strip(".")
    return bool(_DENIED_HOST.search(host))


def _make_permission_callback():
    """Allow WebSearch, allow WebFetch off the deny-list, deny everything else.

    Note WebSearch and WebFetch are deliberately kept OUT of ``allowed_tools``
    at the call site: an allow-list entry auto-approves a tool and SHADOWS this
    callback, which would leave the deny-list unenforced. The same trap is
    documented in ``app.claude.research``.
    """
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    async def can_use_tool(tool_name: str, tool_input: dict, _context):
        if tool_name == "WebSearch":
            return PermissionResultAllow()
        if tool_name != "WebFetch":
            return PermissionResultDeny(
                message=(
                    f"Only WebSearch and WebFetch are permitted; "
                    f"'{tool_name}' is blocked."
                ),
            )
        url = str(tool_input.get("url", ""))
        if is_denied(url):
            return PermissionResultDeny(
                message=(
                    f"Fetch of {url!r} blocked: search engines and Google "
                    "Scholar are not sources. Search with "
                    "WebSearch and fetch the primary page it points to."
                ),
            )
        return PermissionResultAllow()

    return can_use_tool


# ── Prompt ─────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are researching ONE faculty member for a prospective \
PhD applicant's private notes. The applicant will decide whether to spend an \
application, and an email, on this person based on what you write.

{antifab}

HOW TO WORK
- Use WebSearch to find pages, then WebFetch to read them. You may fetch any \
site EXCEPT search engines and Google Scholar, which are blocked -- search \
results are for finding primary pages, not for citing.
- Read widely before writing: the faculty page, the lab or group site, the \
group/people page, the department's PhD admissions page, funder pages, and \
recent news. Prefer the lab's own current site over a personal page, which is \
often years stale, and say so if they disagree.
- Prefer CURRENT work. A representative paper from a decade ago explains the \
through-line; it is not what this person does now, and an email written from \
it reads as such. If the group has visibly repositioned, that is the single \
most useful thing you can report.

WHAT TO WRITE
Return these sections, in this order, omitting any you could not source: \
{sections}.
- Research: what they work on NOW, what kind of work it is (experimental, \
computational, ethnographic, design), and the live threads.
- Lab & students: who is in the group, whether students first-author, where \
alumni went, group size, and whether they are said to be recruiting.
- Funding: grants, and -- most important -- whether student funding is \
attached to the advisor or guaranteed by the department.
- Career stage: rank, trajectory, training, and what that implies for \
availability and resources.
- Signals: what is genuinely reassuring, and what is an open concern. Concerns \
are welcome; a page of praise is useless.
- Adjacent faculty: others worth naming, and why.
- Outreach hooks: the specific, current things an email could open with.
- To ask: the questions this research could NOT answer.

EVERY CLAIM IS CITED
Each section is a list of items. One fact per item, and no line breaks inside \
any string. Each item is exactly:
  {{"text": str, "quote": str, "source_url": str, "source_label": str}}
- "text" is your own one-sentence summary, written for the applicant.
- "quote" is the EXACT sentence from the page that establishes it, copied \
character for character -- not paraphrased, not stitched together from two \
places, not trimmed mid-word. It is checked against the page. Keep it under \
240 characters; if the supporting sentence is longer, take the clause that \
carries the fact.
- "source_url" is the page you fetched and that the quote appears on. \
"source_label" is 2-4 words naming it, e.g. "lab people page".
- An item missing any of the four is DISCARDED. There is no uncited claim. If \
you cannot quote a sentence for it, leave it out or move it to "To ask".

ALSO RETURN
- "summary": 2-4 sentences, the bottom line. This one field is your own \
judgement rather than a quote, so keep it to a read of what you found -- what \
matters most about this person for this applicant, and the decisive open \
question. Never put a fact here that appears nowhere else.
- "research_areas": one short line (under 120 chars) naming what they work on, \
for the collapsed list row.
- "homepage_url": their best current page -- the lab site if there is one.

Output ONLY a single JSON object (no prose, no markdown fences):
{{"summary": str|null, "research_areas": str|null, "homepage_url": str|null, \
"needs_human_verification": true, \
"sections": [{{"heading": str, "items": [{{"text": str, "quote": str, \
"source_url": str, "source_label": str}}]}}]}}
"""


def _prompt(profile, faculty, program) -> str:
    return (
        f"FACULTY MEMBER: {faculty.name}\n"
        f"AT: {program.university}"
        f"{' — ' + program.department if program.department else ''}"
        f"{' (' + program.degree + ')' if program.degree else ''}\n"
        f"Known page: {faculty.homepage_url or '(none recorded — find it)'}\n"
        f"Recorded research areas: {faculty.research_areas or '(none recorded)'}\n"
        f"Program site: {program.portal_url or '(none recorded)'}\n\n"
        "THE APPLICANT (for judging relevance and outreach hooks only — never "
        "attribute any of this to the faculty member):\n"
        f"Target degree: {profile.target_degree or '(unspecified)'}\n"
        f"Research interests: {profile.research_interests or '(none given)'}\n"
        f"Keywords: {profile.keywords or '(none)'}\n"
        f"Background: {profile.background_summary or '(none given)'}\n\n"
        "Research this person and return the JSON object."
    )


async def research_faculty(profile, faculty, program) -> FacultyDossier:
    """Run the dossier pass for one faculty member.

    Raises RuntimeError if the SDK/CLI is unavailable or the pass dies (Rule 1:
    no API-key fallback), ValueError if the output will not parse.
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

    options = ClaudeAgentOptions(
        model=settings.model_for(ClaudeTask.FACULTY_DOSSIER),
        system_prompt=_SYSTEM_PROMPT.format(
            antifab=_ANTIFAB, sections=", ".join(_SECTIONS)
        ),
        # Neither web tool is allow-listed; see _make_permission_callback.
        can_use_tool=_make_permission_callback(),
    )

    final_text = ""
    try:
        prompt = _prompt(profile, faculty, program)
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
        # As in research.py: a pass that dies has already spent real money, so
        # re-raise with the CLI's own reason rather than letting a bare 500
        # reach the user.
        raise RuntimeError(_explain_sdk_failure(exc)) from exc

    return FacultyDossier.model_validate(_extract_json(final_text))
