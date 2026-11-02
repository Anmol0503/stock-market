"""The calendar of scheduled events: how the briefing follows up on things it knows are coming
(an election result, a central-bank decision, a race), the gap that let the Brazil runoff slip by.

dashboard/briefing/calendar.json grows from the seed file, the F1 schedule, and the dated "what's next"
items in every big story. An event that falls due must be covered by an item or marked pending.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from . import config

PATH = config.PUB / "calendar.json"
SEED = config.CONFIG_DIR / "briefing_calendar_seed.json"
KEEP_PAST_DAYS = 30


def load() -> dict:
    try:
        doc = json.loads(PATH.read_text())
        doc.setdefault("events", [])
        return doc
    except (OSError, ValueError):
        pass
    doc = {"updated": None, "events": []}
    try:
        for e in json.loads(SEED.read_text()).get("events", []):
            doc["events"].append({**e, "thread_id": e.get("thread_id"), "source": "seed", "url": None,
                                  "status": "upcoming", "covered_by": None})
    except (OSError, ValueError):
        pass
    return doc


def _slug(text: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower())[:4]) or "event"


def add(doc: dict, *, date: str, title: str, section: str, source: str, time_ist: str | None = None,
        thread_id: str | None = None) -> None:
    try:
        dt.date.fromisoformat(date)
    except (TypeError, ValueError):
        return
    eid = f"ev-{date}-{_slug(title)}"
    if any(e["id"] == eid for e in doc["events"]):
        return
    # skip near-duplicates on the same date (same first words)
    if any(e["date"] == date and _slug(e["title"])[:12] == _slug(title)[:12] for e in doc["events"]):
        return
    doc["events"].append({"id": eid, "date": date, "time_ist": time_ist, "title": title[:100], "section": section,
                          "thread_id": thread_id, "source": source, "url": None, "status": "upcoming",
                          "covered_by": None})


def add_f1(doc: dict, f1: dict) -> None:
    nxt = (f1 or {}).get("next_race")
    if nxt and nxt.get("date"):
        add(doc, date=nxt["date"], title=f"F1: {nxt['name']}", section="f1", source="jolpica")


def due(doc: dict, start_date: str, edition_date: str) -> list[dict]:
    return [e for e in doc["events"]
            if start_date <= e["date"] <= edition_date and e.get("status") in ("upcoming", "due", "pending")]


def upcoming(doc: dict, edition_date: str, days: int = 7) -> list[dict]:
    end = (dt.date.fromisoformat(edition_date) + dt.timedelta(days=days)).isoformat()
    return sorted((e for e in doc["events"] if edition_date <= e["date"] <= end and e.get("status") != "cancelled"),
                  key=lambda e: (e["date"], e.get("time_ist") or ""))


def mark(doc: dict, *, covered: dict[str, str], due_ids: list[str], date: str) -> None:
    """covered: event id -> "date/item id". Due events not covered become pending."""
    for e in doc["events"]:
        if e["id"] in covered:
            e["status"], e["covered_by"] = "covered", covered[e["id"]]
        elif e["id"] in due_ids and e.get("status") != "covered":
            e["status"] = "pending"
    cutoff = (dt.date.fromisoformat(date) - dt.timedelta(days=KEEP_PAST_DAYS)).isoformat()
    doc["events"] = [e for e in doc["events"] if e["date"] >= cutoff]


def save(doc: dict, date: str) -> None:
    doc["updated"] = date
    doc["events"].sort(key=lambda e: (e["date"], e.get("time_ist") or ""))
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
