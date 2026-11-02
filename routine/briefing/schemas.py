"""JSON schemas for every model step (passed to `claude -p --json-schema`).

Rules that keep structured output reliable: every property is required, "none" is an empty string or empty
list (never null or a missing key), no mixed-type arrays, additionalProperties false everywhere.
"""
from __future__ import annotations

from . import config

SECTION = {"type": "string", "enum": config.SECTION_KEYS}
STR = {"type": "string"}
INT = {"type": "integer"}
NUM = {"type": "number"}
BOOL = {"type": "boolean"}


def arr(item: dict) -> dict:
    return {"type": "array", "items": item}


def obj(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def enum(*vals: str) -> dict:
    return {"type": "string", "enum": list(vals)}


TRIAGE = obj(items=arr(obj(
    id=STR, section={"type": "string", "enum": config.SECTION_KEYS + ["drop"]},
    scale=INT, severity=INT, durability=INT, novelty=INT, india=INT, interest=BOOL,
    same_as_thread=STR, line=STR, drop_reason=STR)))

SAME_STORY = obj(groups=arr(arr(STR)))

SCOUT = obj(findings=arr(obj(gap=STR, found=BOOL, headline=STR, summary=STR, url=STR, publisher=STR, published=STR)))

_SLOT = dict(cluster_ids=arr(STR), section=SECTION, thread_id=STR, new_thread=BOOL,
             india_angle=enum("primary", "secondary", "none"), contested=BOOL, us_domestic=BOOL,
             question=STR, must_answer=arr(STR), why_chosen=STR, calendar_ids=arr(STR))
EDITOR = obj(
    tier1=arr(obj(**_SLOT)),
    reserves=arr(obj(**_SLOT)),
    tier2=arr(obj(cluster_ids=arr(STR), section=SECTION, thread_id=STR, new_thread=BOOL, angle=STR,
                  calendar_ids=arr(STR))),
    tier3=arr(obj(cluster_id=STR, section=SECTION)),
    quiet=arr(obj(section=SECTION, note=STR)),
    threads=arr(obj(thread_id=STR, action=enum("update", "no_change", "resolve", "dormant"), note=STR)),
    watch_today=arr(obj(text=STR, time_ist=STR, calendar_id=STR)),
    misses=arr(obj(event=STR, decision=enum("cover", "ignore"), cluster_id=STR)),
)

RESEARCH = obj(
    claims=arr(obj(cid=STR, text=STR, kind=enum("fact", "number", "quote", "date", "background"),
                   pub=STR, url=STR, published=STR, type=enum("primary", "wire", "outlet", "analysis", "data"),
                   excerpt=STR, confidence=enum("high", "medium", "low"))),
    numbers=arr(obj(cid=STR, value=STR, compare=STR, compare_cid=STR)),
    timeline=arr(obj(date=STR, event=STR, cid=STR)),
    players=arr(obj(name=STR, who=STR, cid=STR)),
    views=arr(obj(holder=STR, position=STR, cid=STR)),
    current_facts=arr(obj(entity=STR, value=STR, cid=STR)),
    unknowns=arr(STR), searches=INT, fetches=INT, notes=STR,
)

_CIDS = arr(STR)
SCENE_KINDS = ["hook", "kinetic", "big_number", "map", "bar", "line", "timeline", "players", "outro"]
STORY = obj(
    headline=STR, question=STR, dek=STR,
    so_far=obj(text=STR, cids=_CIDS),
    what_happened=obj(text=STR, cids=_CIDS),
    why_chain=arr(obj(text=STR, cids=_CIDS)),
    players=arr(obj(name=STR, who=STR, cid=STR)),
    numbers=arr(obj(value=STR, meaning=STR, cids=_CIDS)),
    analogy=obj(text=STR, breaks=STR),
    views=arr(obj(holder=STR, view=STR, cid=STR)),
    for_you=obj(text=STR, cids=_CIDS),
    misconception=obj(myth=STR, fact=STR, cids=_CIDS),
    next=obj(text=STR, dates=arr(obj(date=STR, what=STR)), unknowns=arr(STR)),
    changed=STR, thread_summary=STR, state_facts=arr(obj(fact=STR, cid=STR)),
    terms=arr(obj(term=STR, meaning=STR)),
    check=obj(q=STR, options=arr(STR), answer=INT, why=STR),
    reel=arr(obj(kind={"type": "string", "enum": SCENE_KINDS}, say=STR, show=STR,
                 number_value=STR, number_label=STR, number_cid=STR,
                 map_iso3=arr(STR), map_lon=NUM, map_lat=NUM, map_label=STR,
                 chart_title=STR, chart_unit=STR, chart_points=arr(obj(label=STR, value=NUM)), chart_cids=_CIDS,
                 timeline=arr(obj(when=STR, what=STR)), players=arr(obj(name=STR, role=STR)))),
)

CHECK = obj(ok=BOOL, problems=arr(obj(where=STR, issue=STR, severity=enum("fix", "drop"))))

SECTION_RESEARCH = obj(items=arr(obj(
    item_id=STR, ok=BOOL, note=STR,
    facts=arr(obj(text=STR, pub=STR, url=STR, published=STR, excerpt=STR)))))

BRIEFS = obj(
    briefs=arr(obj(item_id=STR, headline=STR, text=STR, background=STR, why=STR, source_urls=arr(STR),
                   status=enum("new", "update"), thread_summary=STR)),
    gists=arr(obj(section=SECTION, gist=STR)),
)

BRIEFS_CHECK = obj(checks=arr(obj(item_id=STR, severity=enum("ok", "fix", "drop"), problems=arr(STR))))

COVER = obj(top_line=STR, changes=arr(obj(text=STR, ref=STR)), watch_today=arr(obj(text=STR, time_ist=STR)))

RECALL = obj(total=INT, matched=INT, misses=arr(obj(event=STR, category=STR, major=BOOL, cluster_hint=STR)))

BOOTSTRAP = obj(threads=arr(obj(
    id=STR, title=STR, section=SECTION, summary=STR, keywords=arr(STR),
    last_state=arr(obj(fact=STR, date=STR)), watch=arr(obj(date=STR, what=STR)))))
