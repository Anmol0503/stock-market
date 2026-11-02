"""Wikipedia's daily "Current events" pages: a human-curated, categorised list of the day's news with source links.

Used two ways: as leads (events the feeds missed) and as the yardstick for the next-day recall audit.
Pages are dated in UTC, so a morning-IST window spans two pages.
"""
from __future__ import annotations

import datetime as dt
import re
import time

import requests

from . import sources

_TEMPLATE_SUB = re.compile(r"\{\{\s*(?:sub|sup)\s*\|([^{}|]*)\}\}", re.I)
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_LINK_PIPED = re.compile(r"\[\[[^\[\]|]*\|([^\[\]]*)\]\]")
_LINK = re.compile(r"\[\[([^\[\]]*)\]\]")
_EXT = re.compile(r"\[(https?://[^\s\]]+)\s+([^\]]*)\]")
_REF = re.compile(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_CATEGORY = re.compile(r"^'''(.+?)'''\s*$")
_BULLET = re.compile(r"^(\*+)\s*(.*)$")


def page_title(day: dt.date) -> str:
    return f"Portal:Current_events/{day.year}_{day.strftime('%B')}_{day.day}"


def clean(text: str) -> str:
    t = _COMMENT.sub("", text or "")
    t = _REF.sub("", t)
    t = _TEMPLATE_SUB.sub(r"\1", t)
    t = _TEMPLATE.sub("", t)
    t = _LINK_PIPED.sub(r"\1", t)
    t = _LINK.sub(r"\1", t)
    t = t.replace("'''", "").replace("''", "")
    return " ".join(t.split())


def parse(wikitext: str, page_date: str) -> list[dict]:
    """wikitext -> [{page_date, category, topic, text, urls:[{url, source}]}]. An 'event' is any bullet that cites a link."""
    events: list[dict] = []
    category, stack = "", []
    for raw in (wikitext or "").splitlines():
        line = raw.strip()
        m = _CATEGORY.match(line)
        if m:
            category, stack = clean(m.group(1)), []
            continue
        m = _BULLET.match(line)
        if not m:
            continue
        depth, body = len(m.group(1)), m.group(2)
        links = _EXT.findall(body)
        if not links:
            stack = stack[: depth - 1] + [clean(body)]
            continue
        text = clean(_EXT.sub("", body)).rstrip(" .") + "."
        events.append({
            "page_date": page_date,
            "category": category,
            "topic": " › ".join(s for s in stack[: depth - 1] if s),
            "text": text,
            "urls": [{"url": u, "source": clean(s).strip(" ()")} for u, s in links],
        })
    return events


def fetch_day(day: dt.date, *, timeout: int = 20) -> tuple[list[dict], dict]:
    """Fetch and parse one UTC day's page. Returns (events, health)."""
    params = {"action": "parse", "page": page_title(day), "prop": "wikitext", "format": "json", "formatversion": "2"}
    health = {"name": f"Wikipedia {day.isoformat()}", "kind": "wiki", "ok": False, "items": 0, "error": None}
    try:
        for attempt in range(4):                      # Wikipedia rate-limits shared cloud IPs: back off and retry
            r = requests.get(sources.WIKI_API, params=params, timeout=timeout,
                             headers={"User-Agent": sources.API_AGENT})
            if r.status_code != 429:
                break
            time.sleep(3 * (attempt + 1))
        if r.status_code != 200:
            health["error"] = f"HTTP {r.status_code}"
            return [], health
        data = r.json()
        if "error" in data:                       # page not created yet (very early in the UTC day)
            health["error"] = data["error"].get("code", "missing")
            return [], health
        events = parse(data["parse"]["wikitext"], day.isoformat())
        health.update(ok=True, items=len(events))
        return events, health
    except Exception as e:  # noqa: BLE001 - one source must never break the run
        health["error"] = f"{type(e).__name__}: {e}"[:200]
        return [], health
