"""Dashboard summaries.

``/dashboard`` — overdue / due-soon / stale buckets.
``/dashboard/overview`` — everything the Dashboard page shows: a date-ordered agenda
across programs, what needs attention and why, the checklist grid and the
comparison table. Read-only; computed from existing rows, no schema of its own.
"""

from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import insights
from app.db import get_session
from app.models import Program
from app.models.enums import (
    BUILTIN_STEPS,
    ApplicationStep,
    RequirementKind,
    RequirementSource,
)
from app.routers.programs import _all_enriched, _summary
from app.schemas import (
    AgendaItem,
    AttentionItem,
    ChecklistRow,
    CompareCell,
    CompareRow,
    DashboardOut,
    DashboardOverview,
    StepColumn,
)

router = APIRouter(prefix="/api", tags=["dashboard"])

CONFIRMED = RequirementSource.CONFIRMED_BY_PROGRAM.value

#: The requirements the comparison table shows; blank ones are flagged.
COMPARED_KINDS = [
    (RequirementKind.GRE.value, "GRE"),
    (RequirementKind.TOEFL.value, "TOEFL"),
    (RequirementKind.APP_FEE.value, "application fee"),
]

#: Most pressing first — the attention list is read top-down.
ATTENTION_ORDER = ["overdue", "stale", "no_deadline_date", "missing_requirements", "unverified"]

# "$75", "USD 90", "US$ 105.00", "$1,000" — or a value that is only a number.
_DOLLARS = re.compile(r"(?:US\$|\$|USD)\s*(\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)
_BARE = re.compile(r"^\s*(\d[\d,]*(?:\.\d+)?)\s*$")

# A test's status, by whichever phrase comes first in the value — so
# "Required for PhD (not required for MS)" reads as required, and
# "Optional / not required" as optional.
_STATUS = [
    ("Not accepted", re.compile(r"\bnot (?:be )?(?:accepted|considered)\b", re.I)),
    ("Not required", re.compile(r"\b(?:not required|does not require|no longer required|not needed|waived)\b", re.I)),
    ("Optional", re.compile(r"optional", re.I)),
    ("Required", re.compile(r"(?<!not )(?<!no longer )\b(?:required|mandatory)\b", re.I)),
]
# A minimum score: the first number right after the test's name, else after
# "min"/"minimum"/"at least". Bounded to the test's own scale so a year
# ("iBT 2026 scale") or a sub-score on another scale can't pass for one.
_SCORE_RANGE = {"gre": (260, 340), "toefl": (0, 120)}
_MIN_WORD = re.compile(r"\b(?:min(?:imum)?|at least)\b\D{0,20}?\b(\d{2,3})\b", re.I)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(session: Session = Depends(get_session)) -> DashboardOut:
    summaries = _all_enriched(session)
    return DashboardOut(
        overdue=[s for s in summaries if s.urgency == "overdue"],
        due_soon=[s for s in summaries if s.urgency == "due_soon"],
        stale=[s for s in summaries if s.is_stale],
    )


def parse_fee(value: str | None) -> float | None:
    """A fee's dollar amount, or None when it doesn't read as one.

    Free text, so only the unambiguous shapes count: a dollar-marked amount
    (the first one, when a value lists domestic and international fees) or a
    bare number. Anything else — another currency, "waived", "see site" — is
    left out of the total and counted as unknown rather than guessed at.
    """
    if not value:
        return None
    match = _DOLLARS.search(value) or _BARE.match(value)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def test_status(value: str | None) -> str | None:
    """"Required" / "Optional" / "Not required" / "Not accepted", or None."""
    if not value:
        return None
    hits = [(m.start(), label) for label, rx in _STATUS if (m := rx.search(value))]
    return min(hits)[1] if hits else None


def min_score(value: str | None, test: str) -> int | None:
    """The minimum score a test requirement states, or None if it states none."""
    if not value:
        return None
    low, high = _SCORE_RANGE[test]
    named = re.compile(rf"\b{test}\b\D{{0,25}}?\b(\d{{2,3}})\b", re.I)
    for rx in (named, _MIN_WORD):
        for m in rx.finditer(value):
            score = int(m.group(1))
            if low <= score <= high:
                return score
    return None


def summarize_test(value: str | None, test: str) -> str | None:
    """A test requirement as a quick read: "Required · min 90", "Optional".
    A value that says neither reads "See details" — the hover has it all."""
    if not value or not value.strip():
        return None
    status = test_status(value)
    if status == "Required":
        score = min_score(value, test)
        return f"Required · min {score}" if score is not None else "Required"
    return status or "See details"


def summarize_fee(value: str | None) -> str | None:
    """The application fee as "$125", or "See details" if it isn't a $ amount."""
    if not value or not value.strip():
        return None
    fee = parse_fee(value)
    if fee is None:
        return "See details"
    return f"${fee:,.0f}" if fee == int(fee) else f"${fee:,.2f}"


def _compare_cell(program: Program, kind: str, summarize) -> CompareCell:
    match = next((r for r in program.requirements if r.kind.strip().lower() == kind), None)
    if match is None:
        return CompareCell()
    return CompareCell(
        text=summarize(match.value),
        detail=match.value.strip() if match.value and match.value.strip() else None,
        source=match.source,
        needs_human_verification=match.needs_human_verification,
    )


def _is_submitted(program: Program) -> bool:
    return any(
        s.key == ApplicationStep.SUBMITTED.value and s.completed for s in program.steps
    )


def _unverified(program: Program) -> int:
    """Researched facts that have something to verify — a seeded blank
    requirement or an undated placeholder deadline isn't a fact yet."""
    return (
        sum(1 for d in program.deadlines if d.date and d.source != CONFIRMED)
        + sum(
            1
            for r in program.requirements
            if r.value and r.value.strip() and r.source != CONFIRMED
        )
        + sum(1 for n in program.notes if n.source != CONFIRMED)
    )


def _requirement_value(program: Program, kind: str) -> str | None:
    match = next((r for r in program.requirements if r.kind.strip().lower() == kind), None)
    return match.value.strip() if match and match.value and match.value.strip() else None


def _reminder_label(note) -> str:
    return note.text.strip() or note.file_name or note.link_url or "Reminder"


@router.get("/dashboard/overview", response_model=DashboardOverview)
def overview(session: Session = Depends(get_session)) -> DashboardOverview:
    programs = session.scalars(
        select(Program).options(
            selectinload(Program.deadlines),
            selectinload(Program.faculty),
            selectinload(Program.steps),
            selectinload(Program.my_notes),
            selectinload(Program.requirements),
            selectinload(Program.notes),
        )
    ).all()
    programs = sorted(programs, key=lambda p: (p.sort_order, p.id))
    summaries = [_summary(p) for p in programs]
    today = date.today()

    agenda: list[AgendaItem] = []
    attention: list[AttentionItem] = []
    checklist: list[ChecklistRow] = []
    compare: list[CompareRow] = []
    fee_total, fee_counted, fee_unknown = 0.0, 0, 0
    submitted_count = unverified_count = 0
    builtin_keys = [key for key, _ in BUILTIN_STEPS]

    for program, summary in zip(programs, summaries):
        submitted = _is_submitted(program)
        submitted_count += submitted
        unverified = _unverified(program)
        unverified_count += unverified

        def flag(kind: str, detail: str, tab: str = "overview") -> None:
            attention.append(
                AttentionItem(
                    program_id=program.id,
                    university=program.university,
                    kind=kind,
                    detail=detail,
                    tab=tab,
                )
            )

        # ── Agenda ──
        for d in program.deadlines:
            if d.date is None:
                continue
            # Once submitted, the application deadline has done its job; a
            # funding or letters deadline can still matter.
            if submitted and d.type.strip().lower() == "application":
                continue
            agenda.append(
                AgendaItem(
                    program_id=program.id,
                    university=program.university,
                    kind="deadline",
                    label=d.type,
                    date=d.date,
                    source=d.source,
                    needs_human_verification=d.needs_human_verification,
                )
            )
        for n in program.my_notes:
            if n.due_date is None:
                continue
            agenda.append(
                AgendaItem(
                    program_id=program.id,
                    university=program.university,
                    kind="reminder",
                    label=_reminder_label(n),
                    date=n.due_date,
                )
            )

        # ── Attention — a submitted program has nothing left to chase ──
        if not submitted:
            days = summary.days_until_deadline
            if summary.urgency == "overdue" and days is not None:
                flag("overdue", f"Application deadline passed {-days}d ago, not submitted")
            if summary.is_stale:
                idle = (today - insights.last_activity_of(program).date()).days
                flag("stale", f"No activity in {idle}d, deadline in {days}d")
            if summary.application_deadline is None:
                flag("no_deadline_date", "Application deadline has no date")
            missing = [
                label for kind, label in COMPARED_KINDS if not _requirement_value(program, kind)
            ]
            if missing:
                flag("missing_requirements", f"Unknown: {', '.join(missing)}")
            if unverified:
                noun = "fact" if unverified == 1 else "facts"
                flag("unverified", f"{unverified} researched {noun} not confirmed")

        # ── Checklist grid ──
        by_key = {s.key: s for s in program.steps if not s.is_custom}
        custom = [s for s in program.steps if s.is_custom or s.key not in builtin_keys]
        checklist.append(
            ChecklistRow(
                program_id=program.id,
                university=program.university,
                steps={
                    key: (by_key[key].completed if key in by_key else None)
                    for key in builtin_keys
                },
                custom_done=sum(1 for s in custom if s.completed),
                custom_total=len(custom),
            )
        )

        # ── Comparison table ──
        compare.append(
            CompareRow(
                program_id=program.id,
                gre=_compare_cell(program, RequirementKind.GRE.value, lambda v: summarize_test(v, "gre")),
                toefl=_compare_cell(program, RequirementKind.TOEFL.value, lambda v: summarize_test(v, "toefl")),
                app_fee=_compare_cell(program, RequirementKind.APP_FEE.value, summarize_fee),
            )
        )

        # ── Fees ──
        fee = parse_fee(_requirement_value(program, RequirementKind.APP_FEE.value))
        if fee is None:
            fee_unknown += 1
        else:
            fee_total += fee
            fee_counted += 1

    agenda.sort(key=lambda a: (a.date, a.university.lower()))
    rank = {kind: i for i, kind in enumerate(ATTENTION_ORDER)}
    # Stable sort: within a kind, programs keep the user's own order.
    attention.sort(key=lambda a: rank[a.kind])

    return DashboardOverview(
        programs=summaries,
        submitted_count=submitted_count,
        unverified_count=unverified_count,
        agenda=agenda,
        attention=attention,
        step_columns=[StepColumn(key=k, label=label) for k, label in BUILTIN_STEPS],
        checklist=checklist,
        compare=compare,
        fee_total=fee_total,
        fee_counted=fee_counted,
        fee_unknown=fee_unknown,
    )
