#!/usr/bin/env python3
"""The Horizon Series — author one all-round deep-dive per day and e-mail it to the Kindle.

Cures the "stuck in a box" feeling by working through a curated curriculum of can't-miss topics
(config/horizon_topics.json), one per day, each a full 5-chapter book. Every book is labelled so the Kindle
groups them into one tidy, ordered collection: title "Horizon NNN — <topic>", author "The Horizon Series",
plus calibre series metadata (handled in make_kindle.build_epub).

Runs on the MAC only (needs the local .env Gmail creds + SMTP), on Sonnet (config/usage.json) to stay light on
the Max limit. Fired once/day from routine/run_hourly.sh via an internal daily guard.

Run:  python routine/horizon.py            # send today's book (no-op if already sent today)
      python routine/horizon.py --force    # author + send the next book now, ignoring the daily gate
      python routine/horizon.py --dry       # author + build the next book but DON'T e-mail (test)
      python routine/horizon.py --n 3        # backfill: send the next 3 books now
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "routine"))
import make_kindle as mk   # noqa: E402
import usage               # noqa: E402

CONFIG = ROOT / "config" / "horizon_topics.json"
STATE = ROOT / "output" / "horizon-state.json"          # {next_index, sent:[], last_sent_date}
ARCHIVE = ROOT / "output" / "horizon"                    # per-book JSON + EPUB
TMP = ROOT / "output" / "horizon-latest.json"            # where Claude writes the authored book
PROMPT = ROOT / "routine" / "horizon_prompt.md"

SERIES = "Horizon"
AUTHOR = "The Horizon Series"
ALLOWED = ["Read", "Write", "Edit"]
CLAUDE = os.environ.get("CLAUDE_BIN") or str(pathlib.Path.home() / ".local" / "bin" / "claude")
if not pathlib.Path(CLAUDE).exists():
    CLAUDE = "claude"


def _load(p: pathlib.Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _today() -> str:
    return dt.date.today().isoformat()


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:48]


def _author_book(topic: dict, number: int) -> list[dict] | None:
    """Ask headless Claude (Sonnet) to write a 5-chapter book on the topic. Returns parts[] or None."""
    base = PROMPT.read_text()
    prompt = base + (
        "\n\n=== TOPIC TO WRITE ===\n"
        f"Title: {topic.get('title')}\n"
        f"Domain: {topic.get('domain', '')}\n"
        f"Angle: {topic.get('blurb', '')}\n\n"
        f"Write the complete 5-chapter book now as STRICT JSON (an object with a \"parts\" array) to this exact "
        f"file, and nothing else:\n{TMP}\n"
    )
    if TMP.exists():
        TMP.unlink()
    for attempt in (1, 2):
        usage.run_claude(prompt, claude_bin=CLAUDE, allowed=ALLOWED, cwd=ROOT,
                         label="horizon", retries=1, timeout=1200)
        data = _load(TMP)
        parts = (data or {}).get("parts") if isinstance(data, dict) else (data if isinstance(data, list) else None)
        if parts and isinstance(parts, list) and all(isinstance(p, dict) and p.get("chunks") for p in parts):
            # stamp the topic's identity onto each part so the cover + headers render correctly
            for i, p in enumerate(parts, 1):
                p.setdefault("part", i)
                p["total_parts"] = len(parts)
                p["subject_title"] = topic.get("title")
                p["emoji"] = topic.get("emoji", "📘")
            return parts
        print(f"  horizon: invalid/empty authoring output (attempt {attempt})", file=sys.stderr)
    return None


def _send_one(topics: list[dict], index: int, *, dry: bool) -> bool:
    """Author, build, and (unless dry) e-mail the book at `index` (0-based). Returns True on success."""
    if index >= len(topics):
        print("horizon: reached the end of the topic list — add more to config/horizon_topics.json")
        return False
    topic = topics[index]
    number = index + 1
    title = f"Horizon {number:03d} — {topic['title']}"
    print(f"horizon: authoring #{number:03d} — {topic['title']} …")

    parts = _author_book(topic, number)
    if not parts:
        print(f"  ! authoring failed for #{number:03d} — nothing sent", file=sys.stderr)
        return False

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / f"{number:03d}.json").write_text(json.dumps({"number": number, "topic": topic, "parts": parts},
                                                           ensure_ascii=False, indent=2))
    epub = mk.build_epub(parts, title, ARCHIVE / f"horizon-{number:03d}-{_slug(topic['title'])}.epub",
                         author=AUTHOR, series=SERIES, series_index=number)
    print(f"  built {epub.name} — {len(parts)} chapters, {epub.stat().st_size // 1024} KB")
    if dry:
        print("  (dry run — not e-mailed)")
        return True
    if mk.send_to_kindle(epub, title):
        print(f"  ✅ sent '{title}' to the Kindle")
        return True
    print("  ! send failed (missing .env Gmail creds?) — not advancing", file=sys.stderr)
    return False


def main(argv: list[str]) -> int:
    force = "--force" in argv
    dry = "--dry" in argv
    count = 1
    if "--n" in argv:
        try:
            count = max(1, int(argv[argv.index("--n") + 1]))
        except (ValueError, IndexError):
            count = 1

    cfg = _load(CONFIG) or {}
    topics = cfg.get("topics") or []
    if not topics:
        print("horizon: no topics in config/horizon_topics.json", file=sys.stderr)
        return 1

    state = _load(STATE) or {"next_index": 0, "sent": [], "last_sent_date": ""}
    idx = int(state.get("next_index", 0))

    # once-per-day guard (a real send only; --force and --dry bypass it)
    if not force and not dry and state.get("last_sent_date") == _today():
        print(f"horizon: today's book already sent (#{idx:03d} next) — one per day")
        return 0

    sent_any = False
    for _ in range(count):
        ok = _send_one(topics, idx, dry=dry)
        if not ok:
            break
        sent_any = True
        if dry:
            break                       # dry run builds the NEXT book but never advances state
        idx += 1
        state["next_index"] = idx
        state["sent"] = (state.get("sent") or []) + [idx]      # store the 1-based number just sent
        state["last_sent_date"] = _today()
        STATE.write_text(json.dumps(state, indent=2))

    return 0 if sent_any else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
