"""Thin wrapper over the Claude Agent SDK.

Rule 1: ALL Claude calls go through the Agent SDK, never the raw Messages
endpoint. Each machine authenticates with its own Claude account via a one-time
``claude /login`` on the CLI the SDK spawns. If the SDK cannot do something, we
stop and flag it rather than falling back to another route.

This module is the minimal round-trip: pick a model per logical task
(``ClaudeTask``) and get text back. The structured, tool-using contracts live
in ``research.py``, ``faculty.py`` and ``faculty_dossier.py``.
"""

from __future__ import annotations

from app.config import ClaudeTask, settings

# The SDK is imported lazily inside functions so that importing this module
# (e.g. during Alembic migrations or tests that never call Claude) does not
# require the CLI to be installed/authenticated.


async def ask(prompt: str, task: ClaudeTask = ClaudeTask.EXTRACT) -> str:
    """Send ``prompt`` to Claude via the Agent SDK and return the text reply.

    ``task`` selects the model tier through ``settings.model_for`` (currently
    Sonnet for every task; see ``app.config``). Raises if the SDK/CLI is
    unavailable — we do not silently fall back (Rule 1).
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "claude-agent-sdk is not installed. Run `pip install -e .` in "
            "backend/, then authenticate the bundled CLI with `claude /login`."
        ) from exc

    model = settings.model_for(task)
    options = ClaudeAgentOptions(model=model)

    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        chunks.append(_text_of(message))
    return "".join(chunks).strip()


def _text_of(message: object) -> str:
    """Best-effort extraction of text from an SDK message object.

    The SDK yields typed message objects (system/assistant/result). We only
    want assistant text blocks; anything else contributes nothing.
    """
    content = getattr(message, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def model_for_task(task: ClaudeTask) -> str:
    """Expose the resolved model id for a task (used by the /health probe)."""
    return settings.model_for(task)
