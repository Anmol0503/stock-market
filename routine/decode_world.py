#!/usr/bin/env python3
"""Batched World decode orchestrator — small, reliable Claude calls + a live progress tracker.

Instead of one giant Claude call (which dropped mid-stream), this:
  1. SELECTS the ~20 global + ~20 india headlines that matter  (routine/world_select_prompt.md → world-plan.json)
  2. DECODES them in small batches of ~5 per call               (each writes output/world-batch.json → accumulated)
  3. writes the MARKETS brief                                    (routine/markets_prompt.md)
  4. MERGES the two world halves                                 (routine/merge_world.py)
Every step updates logs/progress.json (via routine/progress.py) so the Update Center shows exactly
what's happening. Each Claude call is small enough to essentially never drop; a failed batch loses only
those ~5 stories, and a totally failed decode leaves the last good brief untouched (merge_world).

Run:  python routine/decode_world.py     (called by routine/run_daily.sh)
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import merge_world          # same directory (routine/ is sys.path[0] when run as a script)
import progress as pg
import usage                # routine/usage.py — logs token/cost to the rolling ledger

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
ROUTINE = ROOT / "routine"

BATCH = 5
ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"]
CLAUDE = os.environ.get("CLAUDE_BIN") or str(pathlib.Path.home() / ".local" / "bin" / "claude")
if not pathlib.Path(CLAUDE).exists():
    CLAUDE = "claude"


def claude(prompt: str, retries: int = 2, timeout: int = 900, label: str = "daily-decode") -> str | None:
    """Run one headless Claude call (logging token/cost to the usage ledger); returns result text or None."""
    return usage.run_claude(prompt, claude_bin=CLAUDE, allowed=ALLOWED, cwd=ROOT,
                            label=label, retries=retries, timeout=timeout)


def _batch_prompt(region: str, items: list[dict]) -> str:
    lines = []
    for n, it in enumerate(items, 1):
        lines.append(
            f'{n}. [{it.get("category")}] "{it.get("title")}" — source: {it.get("source")}, '
            f'published_iso: {it.get("published_iso")}, url: {it.get("url")}. angle: {it.get("angle")}')
    cat_rule = ('Every story\'s category MUST be "india".' if region == "india"
                else "Keep each story's given non-india category.")
    return (
        f"Decode these {len(items)} news stories FULLY. First read `analyze/world_prompt.md` for the exact\n"
        "decoding schema and depth bar (every field filled, plain language, define jargon inline,\n"
        "the_lesson + concepts + key_points, real sources). Use WebSearch to VERIFY each story and enrich\n"
        "it — if a story can't be corroborated by a credible outlet, decode what's known and mark it\n"
        "unconfirmed (or drop it if clearly false).\n\n"
        f"For each story set `published_iso` to the exact break time (use the value given, or an earlier\n"
        f"verified time — NEVER invent one). {cat_rule}\n\n"
        "Stories to decode:\n" + "\n".join(lines) + "\n\n"
        f"Write a STRICT JSON array of up to {len(items)} fully-decoded story objects (schema per\n"
        "`analyze/world_prompt.md`) to `output/world-batch.json`. Output nothing outside the file."
    )


def _decode_region(region: str, items: list[dict]) -> list[dict]:
    decoded: list[dict] = []
    total = len(items)
    phase = f"decoding_{region}"
    label = f"Decoding {region.title()} stories"
    if not total:
        pg.set_progress(phase, label, 0, 0, "nothing selected")
        return decoded
    batches = [items[i:i + BATCH] for i in range(0, total, BATCH)]
    for bi, batch in enumerate(batches, 1):
        pg.set_progress(phase, label, len(decoded), total, f"batch {bi}/{len(batches)}")
        bf = OUT / "world-batch.json"
        if bf.exists():
            bf.unlink()
        claude(_batch_prompt(region, batch))
        try:
            data = json.loads(bf.read_text()) if bf.exists() else []
            arr = data.get("stories") if isinstance(data, dict) else data
            decoded.extend(arr or [])
        except (ValueError, OSError, AttributeError) as e:
            print(f"  ! {region} batch {bi} unreadable: {e}", file=sys.stderr)
    pg.set_progress(phase, label, len(decoded), total, "done")
    return decoded


def main() -> int:
    # 1. selection (small, fast)
    pg.set_progress("selecting", "Choosing the stories that matter", 0, 0, "reading the raw feed")
    if claude((ROUTINE / "world_select_prompt.md").read_text()) is None:
        print("WARN: selection call failed", file=sys.stderr)
    try:
        plan = json.loads((OUT / "world-plan.json").read_text())
    except (ValueError, OSError) as e:
        print(f"WARN: no usable world-plan.json ({e}) — keeping last good brief", file=sys.stderr)
        pg.set_progress("failed", "Selection failed — kept last brief", 0, 0, str(e), active=False)
        return 1

    gsel = plan.get("global") or []
    isel = plan.get("india") or []
    print(f"selected {len(gsel)} global + {len(isel)} india", flush=True)

    # 2. decode in small batches
    gdec = _decode_region("global", gsel)
    idec = _decode_region("india", isel)

    (OUT / "world-global.json").write_text(json.dumps({
        "headline": plan.get("headline") or "",
        "the_big_picture": plan.get("the_big_picture") or "",
        "stories": gdec, "also_notable": [],
    }, indent=2, ensure_ascii=False))
    (OUT / "world-india.json").write_text(json.dumps({"stories": idec}, indent=2, ensure_ascii=False))

    # 3. markets brief (separate small-ish call)
    pg.set_progress("markets", "Writing the markets brief", 0, 0, "")
    if claude((ROUTINE / "markets_prompt.md").read_text()) is None:
        print("WARN: markets call failed", file=sys.stderr)

    # 4. merge the two world halves into world-latest.json
    n = len(gdec) + len(idec)
    pg.set_progress("merging", "Assembling the feed", n, n, f"{len(gdec)} global + {len(idec)} india")
    merge_world.main()
    # stay ACTIVE — run_daily.sh owns the publishing → done transition
    print(f"decode complete: {len(gdec)} global + {len(idec)} india", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
