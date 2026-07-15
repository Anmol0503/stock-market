#!/usr/bin/env python3
"""Write dashboard/status.json — the public, honest 'when was this last updated' record.

Both the phone feed (dashboard/reels/index.html) and the local Update Center read this so you can see,
at a glance, exactly when the feed last changed, what was just added, the auto-update cadence, and the
next expected update. It contains only titles/times/counts already public in reels.json — NO secrets
(this file is published to the public GitHub Pages site).

Used two ways:
  - imported:  publish_status.write_status("hourly", added=[{title,region,published_iso}, ...])
  - CLI:       python routine/publish_status.py <hourly|full>      (stamps a 'checked' with no new story)
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
DASH = ROOT / "dashboard"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# The automatic top-up interval, in minutes. Keep in sync with com.dailyintel.hourly.plist StartInterval.
CADENCE_MIN = 30


def _region(s: dict) -> str:
    return "india" if s.get("category") == "india" else "global"


def _counts() -> dict:
    try:
        stories = (json.loads((OUT / "world-latest.json").read_text()).get("stories") or [])
    except (ValueError, OSError):
        return {"global": 0, "india": 0}
    c = {"global": 0, "india": 0}
    for s in stories:
        c[_region(s)] += 1
    return c


def write_status(kind: str, added: list[dict] | None = None, cadence_min: int = CADENCE_MIN) -> pathlib.Path:
    """Merge-update dashboard/status.json. `added` = stories added THIS run (each: title, region,
    published_iso); pass None/empty for a check that added nothing (keeps the previous last_update)."""
    path = DASH / "status.json"
    try:
        cur = json.loads(path.read_text()) if path.exists() else {}
    except (ValueError, OSError):
        cur = {}

    now = dt.datetime.now(IST)
    cur["last_check"] = now.isoformat(timespec="seconds")
    cur["last_kind"] = kind
    cur["cadence_min"] = cadence_min
    cur["next_update_est"] = (now + dt.timedelta(minutes=cadence_min)).isoformat(timespec="seconds")
    cur["counts"] = _counts()
    cur["total"] = cur["counts"]["global"] + cur["counts"]["india"]

    added = [a for a in (added or []) if a and a.get("title")]
    if added:
        cur["last_update"] = now.isoformat(timespec="seconds")
        cur["added_count"] = len(added)
        cur["last_added"] = [{"title": a.get("title"), "region": a.get("region", "global"),
                              "published_iso": a.get("published_iso")} for a in added[:4]]
    cur.setdefault("last_update", cur["last_check"])
    cur.setdefault("last_added", [])
    cur.setdefault("added_count", 0)

    path.write_text(json.dumps(cur, indent=2, ensure_ascii=False))
    return path


def main(argv: list[str]) -> int:
    kind = argv[1] if len(argv) > 1 else "hourly"
    write_status(kind, added=None)
    print(f"wrote {DASH.name}/status.json (kind={kind})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
