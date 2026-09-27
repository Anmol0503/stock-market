#!/usr/bin/env python3
"""📖 Send each day's FINAL Daily Digest to the Kindle (Mac-side — the Gmail/Kindle creds live only in .env).

The digest itself is built in the cloud (routine/digest.py) and published to GitHub Pages. This script reads it
straight from the LIVE SITE over HTTPS — no git, so the Mac's checkout state never matters — and e-mails the
final (11 PM) edition to the Kindle once per day. If the Mac was asleep at 11 PM, the next run catches up on
unsent finals from the last 2 days (oldest first). Titles "Digest · 27 Sep 2026", author/series "The Daily
Digest", so the Kindle library groups and sorts them.

Run:  python routine/digest_kindle.py                    # send any unsent finals (today, yesterday)
      python routine/digest_kindle.py --date 2026-09-27  # that day only (must be final unless --force)
      python routine/digest_kindle.py --dry              # build the EPUB(s) but don't send
      python routine/digest_kindle.py --local            # read dashboard/digest/ instead of the live site
Fired every 30 min by the LaunchAgent com.dailyintel.digest-kindle (no Claude call, no git — ~free).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import make_kindle as mk   # noqa: E402

SITE = os.environ.get("DIGEST_SITE", "https://anmol0503.github.io/stock-market/dashboard")
LOCAL_DIR = ROOT / "dashboard" / "digest"
STATE = ROOT / "output" / "digest-kindle-state.json"     # {sent: [dates]}  (output/ is gitignored)
BOOKS = ROOT / "output" / "digest-kindle"
SERIES = AUTHOR = "The Daily Digest"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _fetch(date: str, local: bool) -> dict | None:
    if local:
        try:
            return json.loads((LOCAL_DIR / f"digest-{date}.json").read_text())
        except (OSError, ValueError):
            return None
    url = f"{SITE}/digest/digest-{date}.json?_={int(dt.datetime.now().timestamp())}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache"}),
                                    timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - 404 (not published yet) / offline → just try again next tick
        return None


def _parts(d: dict) -> list[dict]:
    """Digest → the part/chunk schema make_kindle.build_epub renders."""
    base = {"subject_title": "The Daily Digest", "emoji": "📰"}
    sections = d.get("sections") or []
    total = len(sections) + 2
    parts = [dict(base, part=1, total_parts=total, session_title="The day in one breath",
                  recap_so_far=d.get("top_line") or "",
                  chunks=[{"heading": t.get("title"), "idea": t.get("why")} for t in d.get("top5") or []])]
    for i, sc in enumerate(sections, 2):
        srcs = [s for it in sc.get("items") or [] for s in (it.get("sources") or [])]
        parts.append(dict(base, part=i, total_parts=total,
                          session_title=f"{sc.get('emoji', '')} {sc.get('title', '')}".strip(),
                          recap_so_far=sc.get("gist") or sc.get("summary") or "",
                          chunks=[{"heading": it.get("headline"), "idea": it.get("what"),
                                   "detail": ("New to this? " + it["context"]) if it.get("context") else None,
                                   "key_takeaway": "Why it matters: " + (it.get("why_it_matters") or "")}
                                  for it in sc.get("items") or []],
                          sources=srcs))
    parts.append(dict(base, part=total, total_parts=total, session_title="👀 Watch tomorrow",
                      chunks=[{"heading": "What to watch next", "points": d.get("watch_tomorrow") or []}],
                      recap=[d.get("disclaimer") or "Not financial advice."]))
    return parts


def _title(date: str) -> str:
    return "Digest · " + dt.date.fromisoformat(date).strftime("%-d %b %Y")


def send_day(date: str, *, dry: bool, force: bool, local: bool) -> bool:
    d = _fetch(date, local)
    if not d:
        print(f"digest-kindle: {date} not published yet")
        return False
    if not d.get("final") and not force:
        print(f"digest-kindle: {date} is not final yet ({d.get('edition')}) — waiting for the 11 PM edition")
        return False
    title = _title(date)
    BOOKS.mkdir(parents=True, exist_ok=True)
    epub = mk.build_epub(_parts(d), title, BOOKS / f"digest-{date}.epub", author=AUTHOR, series=SERIES,
                         series_index=dt.date.fromisoformat(date).timetuple().tm_yday)
    if dry:
        print(f"digest-kindle: built {epub.relative_to(ROOT)} (dry run — not sent)")
        return True
    ok = mk.send_to_kindle(epub, title)
    print(f"digest-kindle: {'sent' if ok else 'FAILED to send'} {title}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--local", action="store_true")
    a = ap.parse_args()
    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        state = {"sent": []}
    today = dt.datetime.now(IST).date()
    dates = [a.date] if a.date else [(today - dt.timedelta(days=1)).isoformat(), today.isoformat()]
    for date in dates:
        if date in state["sent"] and not (a.force or a.dry):
            continue
        if send_day(date, dry=a.dry, force=a.force, local=a.local) and not a.dry:
            state["sent"] = sorted(set(state["sent"]) | {date})[-60:]
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
