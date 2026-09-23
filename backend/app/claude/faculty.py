"""Web-grounded faculty suggestions.

Contract:
- suggest_faculty uses domain-restricted WebFetch (reuses program research's
  tool-boundary guard); it may only surface people found on fetched pages, and
  returns a shortlist, never the directory.

Every contract carries an explicit anti-fabrication instruction and a
needs_human_verification escape hatch (Rule 7).
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field, ValidationError

from app.claude.research import (
    _extract_json,
    _make_permission_callback,
    registrable_domain,
)
from app.config import ClaudeTask, settings

_ANTIFAB = (
    "ANTI-FABRICATION (critical): use ONLY the facts provided below (and, when "
    "web access is granted, pages you actually fetched). Never invent the "
    "applicant's experience, degrees, or publications, and never invent a "
    "faculty member's work, papers, or a shared history. If something is "
    "unknown, say so or leave it out — do not guess."
)


# ── Output shapes ──────────────────────────────────────────────────────────
class SuggestedFaculty(BaseModel):
    name: str
    research_areas: str | None = None
    homepage_url: str | None = None


class _SuggestList(BaseModel):
    faculty: list[SuggestedFaculty] = Field(default_factory=list)


class SuggestResult(BaseModel):
    """What a suggest pass hands back: the new people, plus who it found but
    dropped because they were already listed -- so an empty result can say
    "all already on your list" rather than "nobody found"."""

    faculty: list[SuggestedFaculty] = Field(default_factory=list)
    already_listed: list[str] = Field(default_factory=list)


# ── SDK helpers ────────────────────────────────────────────────────────────
def _import_sdk():
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            query,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "claude-agent-sdk unavailable. Install it and run `claude /login`."
        ) from exc
    return query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock


async def _run_text(prompt: str, options) -> str:
    """Stream a query and return the final assistant/result text."""
    query, _, AssistantMessage, ResultMessage, TextBlock = _import_sdk()
    final = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            parts = [b.text for b in message.content if isinstance(b, TextBlock)]
            if parts:
                final = "".join(parts)
        elif isinstance(message, ResultMessage):
            result = getattr(message, "result", None)
            if isinstance(result, str) and result.strip():
                final = result
    return final


def _name_key(name: str) -> str:
    """Compare names the way a person would: accents, case, punctuation and
    spacing don't make "Özlem Ergun" someone other than "Ozlem  ergun"."""
    decomposed = unicodedata.normalize("NFKD", name)
    letters = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", letters).casefold().split())


def _drop_existing(found: list[SuggestedFaculty], existing: list[str]) -> SuggestResult:
    """Remove anyone already on the program's list, and repeats within `found`.

    The prompt names who to skip, but — as with the shortlist cap — a prompt
    alone isn't trusted to hold it: a suggestion you already have is a wasted
    slot in a billed pass. Who was dropped is kept, by the program's own
    spelling, so the UI can say so.
    """
    listed = {_name_key(n): n for n in existing}
    seen = set(listed)
    result = SuggestResult()
    for s in found:
        key = _name_key(s.name)
        if key in listed:
            if listed[key] not in result.already_listed:
                result.already_listed.append(listed[key])
        elif key and key not in seen:
            seen.add(key)
            result.faculty.append(s)
    return result


# ── Contracts ──────────────────────────────────────────────────────────────
async def suggest_faculty(program, official_url: str) -> SuggestResult:
    _, ClaudeAgentOptions, *_ = _import_sdk()
    domain = registrable_domain(official_url)
    if not domain:
        raise ValueError("Could not determine a domain from the official URL.")
    system = (
        "You find additional faculty in a department who might fit a prospective "
        "PhD applicant, using ONLY that institution's own web pages.\n" + _ANTIFAB
        + "\n"
        f"Use ONLY the WebFetch tool, ONLY within {domain}. Start at the given "
        "URL and follow same-domain links to the faculty directory. Suggest only "
        "people who actually appear on pages you fetched — never invent names.\n"
        f"Return AT MOST {settings.max_faculty_per_program} people, those most "
        "central to what the department presents as its main research "
        "thrusts first, and only research/tenure-track "
        "faculty who advise doctoral students — not adjuncts, teaching-track "
        "faculty, emeriti, or online-programme instructors. A directory dump "
        "is not a suggestion.\n"
        "If no one on the pages you fetched is a real fit, return an empty "
        'list — {"faculty": []} is a correct answer. Never pad the list with '
        "weak matches to reach the maximum.\n"
        "Output ONLY a JSON object: "
        '{"faculty": [{"name": str, "research_areas": str|null, '
        '"homepage_url": str|null}]}.'
    )
    existing = [f.name for f in program.faculty]
    prompt = (
        f"Department: {program.university} — {program.department or ''}\n"
        f"Official site to read from: {official_url}\n"
        + (
            "Already on the applicant's list — do NOT suggest these people again:\n"
            + "".join(f"- {n}\n" for n in existing)
            if existing
            else ""
        )
        + "List other faculty at this department worth contacting."
    )
    options = ClaudeAgentOptions(
        model=settings.model_for(ClaudeTask.RESEARCH_SYNTHESIS),
        system_prompt=system,
        # WebFetch is intentionally NOT in allowed_tools — an allow-list entry
        # would auto-approve it and shadow can_use_tool, defeating the domain
        # guard. The callback below allow-lists only in-domain WebFetch (Rule 3).
        disallowed_tools=["WebSearch"],
        can_use_tool=_make_permission_callback(domain),
    )
    text = await _run_text(prompt, options)
    try:
        found = _SuggestList.model_validate(_extract_json(text)).faculty
    except (ValueError, ValidationError) as exc:
        # The raw parser/validator text means nothing to the user; the pass
        # has been billed either way, so say plainly what happened.
        raise ValueError(
            "Claude's answer wasn't a list of faculty, so there was nothing to "
            "show. Nothing was saved — try again."
        ) from exc
    result = _drop_existing(found, existing)
    result.faculty = result.faculty[: settings.max_faculty_per_program]
    return result
