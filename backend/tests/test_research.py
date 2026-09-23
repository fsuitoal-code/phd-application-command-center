"""Tests for the Rule 3 domain guard and research output parsing.

These never call Claude — they exercise the guardrails around the research flow.
"""

from __future__ import annotations

import asyncio

import pytest


def test_permission_callback_enforces_domain():
    from app.claude.research import _make_permission_callback

    cb = _make_permission_callback("stanford.edu")

    async def run(tool, inp):
        return await cb(tool, inp, None)

    # WebFetch inside the domain is allowed.
    allow = asyncio.run(run("WebFetch", {"url": "https://cs.stanford.edu/phd"}))
    assert allow.behavior == "allow"
    # Off-domain fetch denied.
    deny = asyncio.run(run("WebFetch", {"url": "https://scholar.google.com/x"}))
    assert deny.behavior == "deny"
    # Any non-WebFetch tool (e.g. WebSearch) denied.
    deny2 = asyncio.run(run("WebSearch", {"query": "stanford cs phd"}))
    assert deny2.behavior == "deny"


def test_json_extraction_tolerates_prose():
    from app.claude.research import _extract_json

    text = 'Here is the data:\n{"university": "X", "faculty": []}\nDone.'
    assert _extract_json(text)["university"] == "X"


def test_json_extraction_tolerates_literal_newlines_in_strings():
    # Models often emit multi-line string VALUES with raw newlines (e.g. an
    # email body), which strict json.loads rejects. _extract_json must cope.
    from app.claude.research import _extract_json

    text = '{"subject": "Hi", "body": "Line one\nLine two\nLine three"}'
    data = _extract_json(text)
    assert data["body"].count("\n") == 2


def test_notes_drops_non_dict_items():
    # Each note becomes its own ProgramNote row, so it must arrive as a
    # structured object with a citation -- a model that free-styles plain
    # strings instead of the schema gets nothing kept, rather than a guess
    # at what it meant.
    from app.claude.research import ResearchedProgram

    p = ResearchedProgram.model_validate(
        {
            "university": "X",
            "notes": ["Fully funded for five years", "- Cohort of about six students"],
        }
    )
    assert p.notes == []


def test_notes_non_list_value_yields_empty_list():
    from app.claude.research import ResearchedProgram

    prose = ResearchedProgram.model_validate(
        {"university": "X", "notes": "One paragraph of prose."}
    )
    assert prose.notes == []

    empty = ResearchedProgram.model_validate({"university": "X", "notes": []})
    assert empty.notes == []


def test_sdk_failures_explain_themselves_instead_of_500ing():
    # ClaudeSDKError is not a RuntimeError, so an unhandled one escaped the
    # router's handler and surfaced as a bare HTTP 500 -- after the pass had
    # already spent real money.
    from claude_agent_sdk import ResultError

    from app.claude.research import _explain_sdk_failure

    api = ResultError("stopped", {"terminal_reason": "api_error", "api_error_status": 529})
    assert "529" in _explain_sdk_failure(api)

    # Anything unrecognised still names its type rather than vanishing.
    assert "ValueError" in _explain_sdk_failure(ValueError("boom"))


def test_note_objects_are_kept_as_structured_items():
    # Fragment-decorating the URL happens later, in the router, when a
    # ProgramNote row is actually written -- the contract layer just keeps
    # the plain fields.
    from app.claude.research import ResearchedProgram

    p = ResearchedProgram.model_validate(
        {
            "university": "X",
            "notes": [
                {
                    "text": "Assistantships need no separate application.",
                    "quote": "All accepted students are automatically considered.",
                    "source_url": "https://eng.x.edu/grad.php",
                    "source_label": "IE graduate page",
                },
            ],
        }
    )
    assert len(p.notes) == 1
    note = p.notes[0]
    assert note.text == "Assistantships need no separate application."
    assert note.quote == "All accepted students are automatically considered."
    assert note.source_url == "https://eng.x.edu/grad.php"
    assert note.source_label == "IE graduate page"


def test_a_note_without_a_quote_or_url_is_dropped():
    # An uncitable note is the kind that turned out to be commentary on the
    # app's own other fields; requiring a quote removes the category.
    from app.claude.research import ResearchedProgram

    p = ResearchedProgram.model_validate(
        {
            "university": "X",
            "notes": [
                {"text": "The portal did not list the dates."},
                {"text": "No url", "quote": "Something"},
                {
                    "text": "Kept.",
                    "quote": "A real sentence.",
                    "source_url": "https://x.edu/a",
                    "source_label": "a page",
                },
            ],
        }
    )
    assert len(p.notes) == 1
    assert p.notes[0].text == "Kept."


def test_fragment_escapes_the_characters_the_syntax_uses():
    # "-" and "," delimit the fragment's own grammar, so a quote containing
    # them must arrive escaped or the browser parses it as prefix/suffix.
    from app.claude.research import quote_fragment_url

    url = quote_fragment_url("https://x.edu/a", "Full-time students, and others")
    assert "%2D" in url and "%2C" in url
    assert "-" not in url.split("text=")[1]
