"""Model calls. Each step runs as a headless `claude -p` on the Max plan, ported from AI Pulse's ClaudeCLI.

Flags that matter (and why):
  --json-schema            the answer must match our exact shape; it arrives as "structured_output"
  --system-prompt          replaces Claude Code's coding-agent prompt with ours
  --tools / --allowedTools only the tools a role needs exist, and they're pre-approved (headless calls can't ask)
  --safe-mode              no CLAUDE.md, skills, hooks or custom agents leak into these calls
  --setting-sources ""     ignore settings files;  --strict-mcp-config: no MCP servers
  --no-session-persistence keep these calls out of session history
  --fallback-model         if Opus is overloaded, Sonnet answers instead of failing
  --max-budget-usd         a runaway research loop can't burn the plan
Never use --bare: it only reads ANTHROPIC_API_KEY and breaks subscription login.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable

from . import config

try:
    from routine import usage as _usage_log   # logs/claude-usage.jsonl (best-effort)
except Exception:  # noqa: BLE001
    _usage_log = None

# Markers a parent Claude Code session leaves in the environment; a child that inherits them can mistake
# itself for part of that session. The cloud probe showed child calls work with or without them.
_PARENT_SESSION_VARS = {
    "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_PID", "CLAUDE_EFFORT",
}


class EngineError(RuntimeError):
    """The model couldn't be reached, or answered with something unusable."""


@dataclass
class Usage:
    calls: int = 0
    failures: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    by_role: dict = field(default_factory=dict)

    def record(self, role: str, cost: float, seconds: float, ok: bool) -> None:
        self.calls += 1
        self.failures += 0 if ok else 1
        self.cost_usd += cost or 0.0
        self.seconds += seconds
        r = self.by_role.setdefault(role, {"calls": 0, "cost_usd": 0.0, "seconds": 0.0, "failures": 0})
        r["calls"] += 1
        r["cost_usd"] = round(r["cost_usd"] + (cost or 0.0), 4)
        r["seconds"] = round(r["seconds"] + seconds, 1)
        r["failures"] += 0 if ok else 1

    def as_dict(self) -> dict:
        return {"calls": self.calls, "failures": self.failures, "cost_usd": round(self.cost_usd, 3),
                "seconds": round(self.seconds, 1), "by_role": self.by_role}


class Engine:
    """Interface: ask(role, system, prompt, schema) -> dict matching schema."""

    def __init__(self) -> None:
        self.usage = Usage()
        self._sem = asyncio.Semaphore(config.CONCURRENCY)

    async def ask(self, role: str, system: str, prompt: str, schema: dict, *, label: str = "",
                  retries: int = 1) -> dict:
        last: Exception | None = None
        for attempt in range(retries + 1):
            try:
                async with self._sem:
                    return await self._ask_once(role, system, prompt, schema, label=label or role)
            except EngineError as e:
                last = e
                if attempt < retries:
                    await asyncio.sleep(float(os.environ.get("BRIEFING_RETRY_SLEEP", "5")) * (attempt + 1))
        raise last or EngineError("unknown failure")

    async def _ask_once(self, role, system, prompt, schema, *, label) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError


class ClaudeEngine(Engine):
    def __init__(self, *, scrub_env: bool = True) -> None:
        super().__init__()
        self.binary = shutil.which("claude") or "claude"
        self.scrub_env = scrub_env and os.environ.get("BRIEFING_NO_SCRUB") != "1"

    def command(self, role: str, system: str, schema: dict) -> list[str]:
        r = config.ROLES[role]
        cmd = [self.binary, "-p", "--model", r["model"], "--output-format", "json",
               "--json-schema", json.dumps(schema), "--system-prompt", system,
               "--tools", r["tools"], "--safe-mode", "--setting-sources", "", "--strict-mcp-config",
               "--no-session-persistence", "--effort", r["effort"],
               "--max-budget-usd", str(r["budget"])]
        if r["tools"]:
            cmd += ["--allowedTools", r["tools"]]
        if r["model"] != config.FALLBACK_MODEL:
            cmd += ["--fallback-model", config.FALLBACK_MODEL]
        return cmd

    async def _ask_once(self, role, system, prompt, schema, *, label) -> dict:
        r = config.ROLES[role]
        env = {k: v for k, v in os.environ.items() if not (self.scrub_env and k in _PARENT_SESSION_VARS)}
        t0 = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *self.command(role, system, schema), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=tempfile.gettempdir(), env=env)
        try:
            out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=r["timeout"])
        except asyncio.TimeoutError:
            proc.kill()
            self.usage.record(role, 0.0, time.monotonic() - t0, False)
            raise EngineError(f"{label}: no answer within {r['timeout']} s") from None
        except asyncio.CancelledError:
            proc.kill()
            raise
        secs = time.monotonic() - t0
        if proc.returncode != 0 and not out:
            self.usage.record(role, 0.0, secs, False)
            raise EngineError(f"{label}: claude exited {proc.returncode}: {err.decode(errors='replace')[-300:]}")
        try:
            env_out = json.loads(out)
        except json.JSONDecodeError as exc:
            self.usage.record(role, 0.0, secs, False)
            raise EngineError(f"{label}: output isn't JSON: {out[:200]!r}") from exc
        cost = float(env_out.get("total_cost_usd") or 0.0)
        ok = not env_out.get("is_error") and env_out.get("subtype") == "success"
        self.usage.record(role, cost, secs, ok)
        if _usage_log is not None:
            _usage_log.record(f"briefing:{label}", env_out.get("usage"), cost, duration_ms=env_out.get("duration_ms"))
        if not ok:
            raise EngineError(f"{label}: {env_out.get('subtype')}: {str(env_out.get('result'))[:300]}")
        data = env_out.get("structured_output")
        if data is None:
            try:
                data = json.loads(env_out.get("result") or "")
            except json.JSONDecodeError as exc:
                raise EngineError(f"{label}: answer wasn't the JSON we asked for") from exc
        return data


class FakeEngine(Engine):
    """For tests: role -> handler(prompt, schema) -> dict. Records calls."""

    def __init__(self, handlers: dict[str, Callable[[str, dict], dict]]) -> None:
        super().__init__()
        self.handlers = handlers
        self.calls: list[tuple[str, str]] = []

    async def _ask_once(self, role, system, prompt, schema, *, label) -> dict:
        self.calls.append((role, label))
        handler = self.handlers.get(role)
        if handler is None:
            self.usage.record(role, 0.0, 0.0, False)
            raise EngineError(f"{label}: no fake handler for role {role}")
        out = handler(prompt, schema)
        self.usage.record(role, 0.0, 0.0, True)
        return out


ITEM_TAG = "item"


def safe(text: str) -> str:
    """Scraped text can't close our <item>/<source> tags early and smuggle in instructions."""
    import re
    return re.sub(r"<\s*(/?)\s*(item|source|claims|story|thread)", r"< \1 \2", text or "", flags=re.I)
