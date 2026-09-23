"""ORM models package.

Importing this package imports every model module, which registers all tables
on ``app.db.Base.metadata`` — needed by Alembic autogenerate and by
``Base.metadata.create_all`` in tests.
"""

from __future__ import annotations

from app.models.deadline import Deadline
from app.models.doc_file import DocFile
from app.models.doc_type import DocType
from app.models.enums import (
    BUILTIN_DOC_TYPES,
    BUILTIN_STEPS,
    ApplicationStep,
    DeadlineType,
    RequirementKind,
    RequirementSource,
)
from app.models.faculty import Faculty
from app.models.faculty_note import FacultyNote
from app.models.my_note import MyNote
from app.models.program import Program
from app.models.program_note import ProgramNote
from app.models.program_step import ProgramStep
from app.models.requirement import Requirement

__all__ = [
    "Program",
    "ProgramStep",
    "Faculty",
    "FacultyNote",
    "Deadline",
    "Requirement",
    "ProgramNote",
    "DocType",
    "DocFile",
    "MyNote",
    "DeadlineType",
    "RequirementKind",
    "RequirementSource",
    "ApplicationStep",
    "BUILTIN_STEPS",
    "BUILTIN_DOC_TYPES",
]
