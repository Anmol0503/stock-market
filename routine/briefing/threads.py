"""Ongoing-story memory ("threads"): the fix for repeats, contradictions and stories that vanish.

dashboard/briefing/threads.json is updated by CODE after each edition: day counts, the previous summary
and the canonical state facts are never left to a model to remember. Each new edition's editor and writers
get the relevant thread so they report what CHANGED, and the checker can catch contradictions.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from . import cluster, config

PATH = config.PUB / "threads.json"
DORMANT_AFTER_DAYS = 7
MAX_THREADS = 60


def load() -> dict:
    try:
        doc = json.loads(PATH.read_text())
        doc.setdefault("threads", [])
        return doc
    except (OSError, ValueError):
        return {"updated": None, "threads": []}


def active(doc: dict) -> list[dict]:
    return [t for t in doc["threads"] if t.get("status") == "active"]


def find(doc: dict, tid: str) -> dict | None:
    return next((t for t in doc["threads"] if t["id"] == tid), None)


def before(t: dict, date: str) -> dict:
    """The thread as it stood before `date`'s edition touched it: {days, summary, last_state}."""
    b = t.get("before_today") or {}
    if b.get("date") == date:
        return b
    return {"days": int(t.get("days") or 0), "summary": t.get("summary", ""), "last_state": t.get("last_state") or []}


def context(t: dict, date: str | None = None) -> dict:
    """The compact view prompts get (as of before `date`'s edition, so same-day re-runs see the same thing)."""
    b = before(t, date) if date else {"days": t.get("days", 1), "summary": t.get("summary", ""),
                                      "last_state": t.get("last_state") or []}
    return {"id": t["id"], "title": t["title"], "section": t.get("section"), "days": b["days"],
            "last_covered": t.get("last_covered"), "summary": b["summary"],
            "last_state": [s["fact"] for s in (b["last_state"] or [])][:6],
            "recent": [f"{e['date']}: {e['text']}" for e in (t.get("timeline") or [])[-5:]],
            "watch": t.get("watch") or [], "keywords": t.get("keywords") or []}


def new_id(doc: dict, title: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 2][:4] or ["story"]
    base = "t-" + "-".join(words)
    tid, n = base, 2
    while find(doc, tid):
        tid, n = f"{base}-{n}", n + 1
    return tid


def _days_between(a: str | None, b: str) -> int:
    try:
        return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return 999


def touch(doc: dict, *, tid: str | None, title: str, section: str, date: str, summary: str,
          timeline_text: str, item_id: str, state: list[dict] | None = None, watch: list[dict] | None = None,
          keywords_from: str = "") -> dict:
    """Record that an edition covered a thread (creating it if needed). Returns the thread."""
    t = find(doc, tid) if tid else None
    if t is None:
        t = {"id": tid or new_id(doc, title), "title": title[:80], "section": section, "status": "active",
             "opened": date, "last_covered": None, "days": 0, "summary": "", "last_state": [], "timeline": [],
             "watch": [], "keywords": [], "resolution": None}
        doc["threads"].append(t)
    if t.get("last_covered") != date:
        # Snapshot the state before today's first touch, so a same-day re-run reports the same day count and
        # "previously" instead of counting the day twice.
        t["before_today"] = {"date": date, "days": int(t.get("days") or 0), "summary": t.get("summary", ""),
                             "last_state": t.get("last_state") or []}
        t["days"] = int(t.get("days") or 0) + 1
    t["last_covered"] = date
    t["status"] = "active"
    if summary:
        t["summary"] = summary
    if state:
        t["last_state"] = state[:6]
    if watch is not None:
        t["watch"] = [w for w in watch if w.get("date")][:6]
    tl = [e for e in (t.get("timeline") or []) if not (e.get("edition") == date and e.get("item") == item_id)]
    tl.append({"date": date, "text": timeline_text[:220], "edition": date, "item": item_id})
    t["timeline"] = tl[-15:]
    kw = set(t.get("keywords") or []) | set(sorted(cluster.tokens(keywords_from or title), key=len, reverse=True)[:6])
    t["keywords"] = sorted(kw)[:12]
    return t


def apply_actions(doc: dict, actions: list[dict], date: str) -> None:
    for a in actions or []:
        t = find(doc, a.get("thread_id") or "")
        if not t:
            continue
        if a.get("action") == "resolve":
            t["status"], t["resolution"] = "resolved", (a.get("note") or "")[:200] or "Resolved"
            t.setdefault("timeline", []).append({"date": date, "text": f"Resolved: {a.get('note') or ''}"[:220],
                                                 "edition": date, "item": None})
        elif a.get("action") == "dormant":
            t["status"] = "dormant"


def expire(doc: dict, date: str) -> None:
    for t in doc["threads"]:
        if t.get("status") == "active" and _days_between(t.get("last_covered"), date) > DORMANT_AFTER_DAYS:
            t["status"] = "dormant"
    if len(doc["threads"]) > MAX_THREADS:
        keep_active = [t for t in doc["threads"] if t["status"] == "active"]
        rest = sorted((t for t in doc["threads"] if t["status"] != "active"),
                      key=lambda t: t.get("last_covered") or "", reverse=True)
        doc["threads"] = keep_active + rest[: max(0, MAX_THREADS - len(keep_active))]


def save(doc: dict, date: str) -> None:
    doc["updated"] = date
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1))


def from_bootstrap(result: dict, date: str) -> dict:
    """Seed threads.json from the bootstrap model call (first run only)."""
    doc = {"updated": None, "bootstrapped": date, "threads": []}
    for b in (result.get("threads") or [])[:15]:
        tid = b.get("id") or new_id(doc, b.get("title") or "story")
        if not tid.startswith("t-") or find(doc, tid):
            tid = new_id(doc, b.get("title") or "story")
        doc["threads"].append({
            "id": tid, "title": (b.get("title") or "")[:80], "section": b.get("section") or "world",
            # covered by the old digest up to the day before: today's first touch then counts as day 2
            "status": "active", "opened": date,
            "last_covered": (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat(), "days": 1,
            "summary": b.get("summary") or "", "keywords": [k.lower() for k in (b.get("keywords") or [])][:10],
            "last_state": [{"fact": s.get("fact", ""), "url": None, "published": s.get("date")}
                           for s in (b.get("last_state") or [])][:6],
            "timeline": [], "watch": [w for w in (b.get("watch") or []) if w.get("date")][:6], "resolution": None,
        })
    return doc
