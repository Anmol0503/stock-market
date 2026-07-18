#!/usr/bin/env python3
"""Claude-usage ledger — tracks the automated pipeline's own Claude consumption in a rolling window.

Every headless Claude call in the pipeline goes through `run_claude()`, which runs the CLI with
`--output-format json` (so we get exact token counts + an API-equivalent `total_cost_usd`) and appends
one line to `logs/claude-usage.jsonl`. `window_summary()` sums the trailing WINDOW_H hours so the status
dashboard can show "how much of my 5-hour window have the automated runs used".

IMPORTANT — this only sees the AUTOMATED PIPELINE. Your interactive Claude Code usage shares the same
5-hour Max limit but is invisible here, and Anthropic doesn't publish the real cap as a number, so the
percentage is an ESTIMATE against a tunable budget (config/usage.json → budget_usd). Calibrate it over
time: if you hit the real limit while the meter reads ~70%, lower the budget so 100% lines up.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "claude-usage.jsonl"
CONFIG = ROOT / "config" / "usage.json"        # {"budget_usd": 10.0, "window_hours": 5}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

DEFAULT_BUDGET_USD = 10.0      # tunable proxy for the 5-hour Max limit (see module docstring)
WINDOW_H = 5                   # the Max limit resets on a rolling 5-hour window


def _now(now: dt.datetime | None = None) -> dt.datetime:
    return now or dt.datetime.now(IST)


def _cfg() -> dict:
    try:
        return json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}


def _budget_usd() -> float:
    try:
        return float(_cfg().get("budget_usd") or DEFAULT_BUDGET_USD)
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_USD


def _window_h() -> float:
    try:
        return float(_cfg().get("window_hours") or WINDOW_H)
    except (TypeError, ValueError):
        return WINDOW_H


def record(label: str, usage: dict | None, cost_usd: float, *, ts: str | None = None,
           duration_ms: int | None = None) -> None:
    """Append one usage row. Never raises — logging must not break a run."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        u = usage or {}
        row = {
            "ts": ts or _now().isoformat(timespec="seconds"),
            "label": label,
            "cost_usd": round(float(cost_usd or 0.0), 6),
            "input_tokens": int(u.get("input_tokens") or 0),
            "cache_read_tokens": int(u.get("cache_read_input_tokens") or 0),
            "cache_write_tokens": int(u.get("cache_creation_input_tokens") or 0),
            "output_tokens": int(u.get("output_tokens") or 0),
            "duration_ms": duration_ms,
        }
        with LOG.open("a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:  # noqa: BLE001 - best-effort
        print(f"  · usage log failed: {e}", file=sys.stderr)


def _rows_in_window(now: dt.datetime, window_h: float) -> list[dict]:
    if not LOG.exists():
        return []
    cutoff = now - dt.timedelta(hours=window_h)
    out = []
    for line in LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            t = dt.datetime.fromisoformat(str(r.get("ts")).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=now.tzinfo)
        if t >= cutoff:
            r["_ts"] = t
            out.append(r)
    return out


def window_summary(now: dt.datetime | None = None) -> dict:
    """Trailing-window totals for the status dashboard's usage meter."""
    now = _now(now)
    window_h = _window_h()
    budget = _budget_usd()
    rows = _rows_in_window(now, window_h)
    cost = sum(r.get("cost_usd") or 0.0 for r in rows)
    tokens = sum((r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
                 + (r.get("cache_read_tokens") or 0) + (r.get("cache_write_tokens") or 0) for r in rows)
    pct = min(100, round(100 * cost / budget)) if budget > 0 else 0
    oldest = min((r["_ts"] for r in rows), default=None)
    resets_at = (oldest + dt.timedelta(hours=window_h)).isoformat(timespec="seconds") if oldest else None
    return {
        "calls": len(rows),
        "cost_usd": round(cost, 4),
        "tokens": tokens,
        "budget_usd": round(budget, 2),
        "pct": pct,
        "window_hours": window_h,
        "resets_at": resets_at,           # when the oldest call ages out of the window
        "scope": "automated pipeline only (excludes interactive Claude Code)",
    }


def run_claude(prompt: str, *, claude_bin: str, allowed: list[str], cwd: pathlib.Path,
               label: str, retries: int = 2, timeout: int = 600,
               disallow: tuple[str, ...] = ("Bash",)) -> str | None:
    """Run the headless CLI with JSON output, log usage/cost, and return the result text (or None).

    Falls back to plain text parsing if the JSON envelope is missing, so callers still get output even
    if a future CLI changes the shape.
    """
    for attempt in range(1, retries + 1):
        try:
            r = subprocess.run(
                [claude_bin, "-p", prompt, "--permission-mode", "acceptEdits",
                 "--allowedTools", *allowed, "--disallowedTools", *disallow,
                 "--output-format", "json"],
                cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode != 0:
                print(f"  claude rc={r.returncode} (attempt {attempt})", file=sys.stderr)
                continue
            out = r.stdout or ""
            try:
                env = json.loads(out)
                record(label, env.get("usage"), env.get("total_cost_usd") or 0.0,
                       duration_ms=env.get("duration_ms"))
                return env.get("result") or ""
            except ValueError:
                record(label, None, 0.0)     # couldn't parse cost, but still record the call happened
                return out
        except subprocess.TimeoutExpired:
            print(f"  claude timeout (attempt {attempt})", file=sys.stderr)
    return None


if __name__ == "__main__":       # quick peek:  python routine/usage.py
    print(json.dumps(window_summary(), indent=2))
