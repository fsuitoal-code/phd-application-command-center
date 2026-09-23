"""Connection check: a live round-trip through the Claude Agent SDK.

Confirms Rule 1 end-to-end — a Claude call goes through the Agent SDK (which
spawns the signed-in `claude` CLI), with per-task model selection. This makes
ONE small request against the current user's own Claude account, so run it deliberately, not on every startup:

    cd backend
    .venv/Scripts/python.exe scripts/verify_sdk.py     # Windows
    .venv/bin/python scripts/verify_sdk.py             # macOS

If it prints the model's reply, the SDK connection works. If it raises about
authentication, run `claude /login` once on this machine and retry.
"""

from __future__ import annotations

import asyncio

from app.claude.client import ask, model_for_task
from app.config import ClaudeTask


async def main() -> None:
    task = ClaudeTask.EXTRACT  # cheapest current tier — used for the probe.
    print(f"Task {task.value!r} -> model {model_for_task(task)}")
    reply = await ask(
        "Reply with exactly the word: pong",
        task=task,
    )
    print("Reply:", reply)
    ok = "pong" in reply.lower()
    print("SDK round-trip:", "OK" if ok else "UNEXPECTED REPLY")


if __name__ == "__main__":
    asyncio.run(main())
