"""Ranking: which stories get shortlisted for the editor, and the code-only fallback plan if the editor fails.

The editor (Opus) makes the final call, but it only sees the shortlist this module builds, so the score
below decides what is even considered.
"""
from __future__ import annotations

import math
from collections import defaultdict

from . import config


def _clamp(v, lo=1, hi=5) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def importance_score(t: dict, c: dict) -> float:
    """How important is this story for THIS reader? Higher = more likely to reach the editor's shortlist.

    t = the triage verdict for the story, each 1–5 (already clamped):
        t["scale"]       how many people it affects (1 = a town … 5 = the world)
        t["severity"]    how much it changes lives / money / safety (1 = trivial … 5 = life and death)
        t["durability"]  how long it will matter (1 = gone tomorrow … 5 = shapes years)
        t["novelty"]     new vs. what you already read yesterday (1 = repeat … 5 = all new)
        t["india"]       direct relevance to someone living in India (1 = none … 5 = direct)
        t["interest"]    True for personal-interest beats (F1, cricket, AI-industry gossip)
    c = the cluster's hard evidence:
        c["publishers"]          distinct outlets that carried it (corroboration; 1 … 30+)
        c["tier"]                best source tier (1 = wire/established/official, 3 = social/aggregator)
        c["signals"]["wiki"]     non-empty list if Wikipedia's curated daily page lists it
        c["signals"]["kagi"]     Kagi's distinct-domain count (0 if Kagi didn't cluster it)
        c["signals"]["primary"]  True if an official source (RBI, PIB, SEBI, Fed…) published it

    Design:
      - significance (how big and how lasting) is the core, 1–5;
      - India relevance can lift a medium story by up to +1.2, but can't make a trivial one big;
      - corroboration has diminishing returns (30 outlets isn't 10x better than 3) and is capped, so wide
        coverage alone can't push trivia up; Wikipedia listing / official source / wire tier add a little;
      - novelty MULTIPLIES everything: a repeat with nothing new (x0.55) sinks below genuinely new
        medium stories; an all-new story gets x1.15.
    Worked examples (before the novelty factor): a big world story (5/4/4, 12 outlets, on Wikipedia) ≈ 6.9;
    a medium Indian policy change (3/3/4, india 5, 4 outlets, official source) ≈ 6.6; a viral trivial item
    (1/1/1, 20 outlets) ≈ 3.0.
    """
    significance = 0.35 * t["scale"] + 0.35 * t["severity"] + 0.30 * t["durability"]
    india = 0.3 * (t["india"] - 1)
    s = c.get("signals") or {}
    evidence = min(0.5 * math.log2(1 + c["publishers"]), 2.0) + min((s.get("kagi") or 0) / 50, 0.4)
    evidence += (0.4 if s.get("wiki") else 0) + (0.3 if s.get("primary") else 0) + (0.2 if c.get("tier") == 1 else 0)
    novelty = 0.4 + 0.15 * t["novelty"]
    return round((significance + india + evidence) * novelty, 3)


def normalise(v: dict) -> dict:
    return {"scale": _clamp(v.get("scale")), "severity": _clamp(v.get("severity")),
            "durability": _clamp(v.get("durability")), "novelty": _clamp(v.get("novelty")),
            "india": _clamp(v.get("india")), "interest": bool(v.get("interest"))}


def select_for_triage(clusters: list[dict], cap: int = config.TRIAGE_CAP) -> list[dict]:
    """Cheap code pre-filter: top overall + top per section + everything with a curated/beat signal."""
    chosen: dict[str, dict] = {}
    for c in clusters[:200]:
        chosen[c["id"]] = c
    per = defaultdict(list)
    for c in clusters:
        per[c["section_hint"]].append(c)
    for sec, cs in per.items():
        for c in cs[:20]:
            chosen.setdefault(c["id"], c)
    for c in clusters:
        if c["signals"]["wiki"] or c["signals"]["beats"] or c["signals"]["primary"] or c["signals"].get("scout"):
            chosen.setdefault(c["id"], c)
    out = sorted(chosen.values(), key=lambda c: -c["pre_score"])
    return out[:cap]


def score_all(clusters: list[dict], verdicts: dict[str, dict]) -> list[dict]:
    """Attach triage + combined score; drop the ones triage dropped. Returns sorted best-first."""
    out = []
    for c in clusters:
        v = verdicts.get(c["id"])
        if not v or v.get("section") == "drop":
            continue
        t = normalise(v)
        c = {**c, "triage": {**t, "line": v.get("line", ""), "same_as_thread": v.get("same_as_thread", "")},
             "section": v.get("section") if v.get("section") in config.SECTIONS else c["section_hint"]}
        s = importance_score(t, c)
        if t["interest"] or c["section"] in config.INTEREST_SECTIONS:
            s -= 0.75          # interest beats compete within their own sections, never against serious news
        c["score"] = round(float(s), 3)
        out.append(c)
    out.sort(key=lambda c: -c["score"])
    return out


def editor_candidates(scored: list[dict], n: int = config.EDITOR_CANDIDATES, per_section: int = 6) -> list[dict]:
    chosen: dict[str, dict] = {}
    by_sec = defaultdict(list)
    for c in scored:
        by_sec[c["section"]].append(c)
    for sec in config.SECTION_KEYS:
        for c in by_sec.get(sec, [])[:per_section]:
            chosen[c["id"]] = c
    for c in scored:
        if len(chosen) >= n:
            break
        chosen.setdefault(c["id"], c)
    return sorted(chosen.values(), key=lambda c: -c["score"])


def fallback_plan(cands: list[dict], threads_active: list[dict]) -> dict:
    """If the editor call fails: a plain, rule-based plan so the edition still ships."""
    used: set[str] = set()
    tier1, reserves, tier2, tier3 = [], [], [], []
    per_sec = defaultdict(int)
    for c in cands:
        if c["section"] in config.INTEREST_SECTIONS:
            continue
        if len(tier1) < config.TIER1_TARGET and per_sec[c["section"]] < 2:
            tier1.append(c)
        elif len(reserves) < config.TIER1_RESERVES:
            reserves.append(c)
        else:
            continue
        used.add(c["id"])
        per_sec[c["section"]] += 1
    sec_count = defaultdict(int)
    for c in cands:
        if c["id"] in used:
            continue
        if sec_count[c["section"]] < 4 and len(tier2) < config.BRIEFS_MAX:
            tier2.append(c)
            sec_count[c["section"]] += 1
            used.add(c["id"])
        elif len(tier3) < config.ALSO_MAX:
            tier3.append(c)
            used.add(c["id"])

    def slot(c):
        return {"cluster_ids": [c["id"]], "section": c["section"], "thread_id": c.get("thread_hint") or "",
                "new_thread": False, "india_angle": "primary" if c["triage"]["india"] >= 4 else "secondary",
                "contested": False, "us_domestic": False, "question": c["title"][:120],
                "must_answer": ["What exactly happened?", "Why did it happen?", "What happens next?"],
                "why_chosen": "fallback ranking", "calendar_ids": []}
    return {
        "tier1": [slot(c) for c in tier1], "reserves": [slot(c) for c in reserves],
        "tier2": [{"cluster_ids": [c["id"]], "section": c["section"], "thread_id": c.get("thread_hint") or "",
                   "new_thread": False, "angle": "", "calendar_ids": []} for c in tier2],
        "tier3": [{"cluster_id": c["id"], "section": c["section"]} for c in tier3],
        "quiet": [{"section": s, "note": "Checked: nothing major in this window."}
                  for s in config.SECTION_KEYS if s not in sec_count and s not in config.NEVER_QUIET],
        "threads": [{"thread_id": t["id"], "action": "no_change", "note": ""} for t in threads_active],
        "watch_today": [], "misses": [], "_fallback": True,
    }
