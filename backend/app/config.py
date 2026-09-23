"""Application configuration and per-task Claude model selection.

Model choice per task is config-driven, never hardcoded at call sites. Every task
tier currently resolves to Sonnet -- a Haiku trial run of the research passes
turned out well, and a side-by-side check showed Sonnet held up just as well
as Opus for the judgement tasks (faculty dossiers)
at a fraction of the cost, so Opus was downgraded across the board. The
``model_opus`` setting and the tier split in ``model_for`` are kept as the
knob for moving a task back up if a harder case ever needs it.
"""

from __future__ import annotations

from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class ClaudeTask(str, Enum):
    """Logical Claude tasks, mapped to a model tier in ``Settings``."""

    EXTRACT = "extract"                 # structured extraction
    RESEARCH_SYNTHESIS = "research"     # program research
    FACULTY_DOSSIER = "faculty_dossier"  # per-faculty researched profile


class Settings(BaseSettings):
    """Runtime settings, overridable via env vars (prefix ``PHDTRACKER_``)."""

    model_config = SettingsConfigDict(
        env_prefix="PHDTRACKER_",
        env_file=".env",
        extra="ignore",
    )

    # Model IDs are config, not hardcoded at call sites. Override either with
    # PHDTRACKER_MODEL_OPUS / PHDTRACKER_MODEL_SONNET.
    model_opus: str = "claude-opus-5"
    model_sonnet: str = "claude-sonnet-5"

    # How many faculty a research pass may keep for one program. A department
    # directory runs to dozens of names -- adjuncts, emeriti, online-program
    # instructors -- and a list that long is not a shortlist, it is the
    # directory again. The pass is asked for the N most central to the
    # department's own research emphasis, and the result is truncated to N
    # regardless.
    max_faculty_per_program: int = 3

    # No daily cap and no per-pass budget or turn ceiling: research passes run
    # until they finish. Every pass emits its result as ONE JSON object at the
    # very end, so a ceiling only ever stopped a pass after it had spent the
    # money and before it produced anything to store.

    # Deadline urgency and staleness thresholds (days).
    deadline_due_soon_days: int = 14
    deadline_upcoming_days: int = 45
    stale_days: int = 21
    stale_deadline_window_days: int = 60

    # CORS origin for the Vite dev server.
    frontend_origin: str = "http://localhost:5173"

    def model_for(self, task: ClaudeTask) -> str:
        """Resolve the Claude model ID for a logical task.

        Every task currently runs on Sonnet (see module docstring).
        """
        del task  # every tier maps to the same model right now
        return self.model_sonnet


settings = Settings()
