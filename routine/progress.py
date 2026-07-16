#!/usr/bin/env python3
"""Tiny live-progress writer — powers the Update Center's real-time tracker.

Writes logs/progress.json (a single small snapshot the server reads). Both the bash wrapper
(run_daily.sh, at phase boundaries) and the Python decode orchestrator (decode_world.py, per batch)
call this so the user can watch exactly what's happening while a run is in flight.

CLI:  python routine/progress.py <phase> <label> [done] [total] [message] [active]
Py:   from progress import set_progress; set_progress("decoding_global", "Decoding Global", 10, 20, "batch 2/4")
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PF = ROOT / "logs" / "progress.json"

# ordered phases → so the tracker can show a checklist and an overall %
PHASES = ["starting", "fetching", "analyzing", "selecting", "decoding_global",
          "decoding_india", "markets", "merging", "lessons", "publishing", "done", "failed"]


def set_progress(phase: str, label: str, done: int = 0, total: int = 0,
                 message: str = "", active: bool = True) -> None:
    PF.parent.mkdir(exist_ok=True)
    pct = round(100 * done / total) if total else (0 if active else 100)
    try:
        idx = PHASES.index(phase)
    except ValueError:
        idx = -1
    PF.write_text(json.dumps({
        "active": active,
        "phase": phase,
        "phase_index": idx,
        "phases": PHASES,
        "label": label,
        "done": done,
        "total": total,
        "pct": pct,
        "message": message,
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }, indent=2))


if __name__ == "__main__":
    a = sys.argv + [""] * 6
    set_progress(
        a[1] or "starting", a[2] or "",
        int(a[3]) if a[3].strip() else 0,
        int(a[4]) if a[4].strip() else 0,
        a[5],
        (a[6].lower() != "false") if a[6].strip() else True,
    )
