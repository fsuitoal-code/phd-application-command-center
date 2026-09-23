"""Value constants for string columns.

These are ``str``-valued ``Enum``s used only to constrain and document the set
of allowed values in Python. The database columns stay ``String`` (not DB
enums) to keep SQLite migrations simple and portable.
"""

from __future__ import annotations

from enum import Enum


class DeadlineType(str, Enum):
    APPLICATION = "application"
    FUNDING = "funding"
    REC_LETTERS_BY = "rec_letters_by"
    TEST_SCORES_BY = "test_scores_by"
    OTHER = "other"


class RequirementKind(str, Enum):
    """Reference/suggestion values only -- the ``kind`` column is free text
    (same role this enum plays for Deadline.type), so a program can still
    record a requirement Claude or the user names outside this set.
    """

    GRE = "gre"
    TOEFL = "toefl"
    APP_FEE = "app_fee"
    FEE_WAIVER = "fee_waiver"
    APP_COST = "app_cost"
    REC_LETTERS = "rec_letters"
    ESSAY_TYPE = "essay_type"
    OTHER = "other"


#: The six fields every new program is seeded with (Requirement rows, blank
#: until research or the user fills them in), in this display order.
BUILTIN_REQUIREMENT_KINDS: list[str] = [
    RequirementKind.GRE.value,
    RequirementKind.TOEFL.value,
    RequirementKind.APP_FEE.value,
    RequirementKind.FEE_WAIVER.value,
    RequirementKind.REC_LETTERS.value,
    RequirementKind.ESSAY_TYPE.value,
]


class RequirementSource(str, Enum):
    """Rule 8: how a requirement fact was obtained.

    ``confirmed_by_program`` overrides ``researched`` when both exist.
    """

    RESEARCHED = "researched"
    CONFIRMED_BY_PROGRAM = "confirmed_by_program"


#: (key, display title) for the two doc types every fresh install is seeded
#: with. Same role BUILTIN_STEPS plays for program_steps: a starting point,
#: not a protected set — any DocType, built-in or custom, may be renamed or
#: deleted from here on.
BUILTIN_DOC_TYPES: list[tuple[str, str]] = [
    ("cv", "CV"),
    ("sop", "Statement of Purpose"),
]


class ApplicationStep(str, Enum):
    """The built-in steps of an application, in order.

    Completion is recorded per program in ``program_steps`` and is always set by
    the user — nothing here is inferred from the presence of other data.

    ``researched`` (a generic catch-all) and ``recommenders`` (cycle-level, not
    program-level, done once per application season) were retired by the
    migration that renamed these labels; neither tracked anything the others
    don't already cover.
    """

    REQUIREMENTS = "requirements"
    DEADLINES = "deadlines"
    FACULTY = "faculty"
    FACULTY_OUTREACH = "faculty_outreach"
    SOP = "sop"
    CV = "cv"
    SUBMITTED = "submitted"


#: (key, display label) for each built-in step. The order fixes sort_order 0..6.
BUILTIN_STEPS: list[tuple[str, str]] = [
    (ApplicationStep.REQUIREMENTS.value, "Researched requirements"),
    (ApplicationStep.DEADLINES.value, "Researched deadlines"),
    (ApplicationStep.FACULTY.value, "Researched faculty"),
    (ApplicationStep.FACULTY_OUTREACH.value, "Reach out to faculty"),
    (ApplicationStep.SOP.value, "Essays"),
    (ApplicationStep.CV.value, "Polish CV"),
    (ApplicationStep.SUBMITTED.value, "Submit application"),
]
