"""Stage 1b: group raw items into stories ("clusters") and attach significance signals. Pure code.

A cluster = one real-world story, with the count of DISTINCT publishers that carried it (the corroboration
signal), the best source tier, which must-check beats it hit, whether Wikipedia's curated page lists it,
Kagi's outlet count, and a hint if it continues an ongoing thread.

Writes output/briefing/<date>/leads.json.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict

from . import config, sources

import fetch_world  # noqa: E402

_STOP_EXTRA = {"live", "updates", "latest", "news", "today", "says", "report", "watch", "video", "photos", "explained"}


def tokens(text: str) -> set:
    return {t for t in fetch_world._sig(text) if t not in _STOP_EXTRA}


def _norm_pub(p: str | None) -> str:
    p = (p or "").strip()
    p = re.sub(r"^(the|www\.)\s*", "", p, flags=re.I)
    return re.sub(r"\.(com|in|org|co\.uk|net)$", "", p.lower())


def _tier(pub: str) -> int:
    if pub in sources.PRIMARY_PUBLISHERS:
        return 1
    return fetch_world._source_tier(pub)


def _similar(a: set, b: set) -> bool:
    """Same story? Jaccard >= 0.45, or >= 3 shared words covering >= 60% of the shorter headline."""
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / len(a | b) >= 0.45 or (inter >= 3 and min(len(a), len(b)) >= 4 and inter / min(len(a), len(b)) >= 0.6)


def build(raw: dict, threads: list[dict] | None = None) -> dict:
    """raw.json -> leads.json (clusters sorted by pre_score, ids c0001…)."""
    clusters: list[dict] = []
    index: dict[str, set] = defaultdict(set)          # token -> cluster indexes (candidate lookup)

    def add_member(ci: int, m: dict, sig: set):
        cl = clusters[ci]
        cl["members"].append(m)
        cl["sig_all"] |= sig
        if sig and len(cl["member_sigs"]) < 16:
            cl["member_sigs"].append(sig)
        for t in sig:
            index[t].add(ci)

    def place(title: str, member: dict) -> int:
        sig = tokens(title)
        cand = Counter()
        for t in sig:
            for ci in index.get(t, ()):
                cand[ci] += 1
        for ci, _n in cand.most_common(10):
            if any(_similar(sig, ms) for ms in clusters[ci]["member_sigs"]):   # match ANY headline already in it
                add_member(ci, member, sig)
                return ci
        clusters.append({"sig": sig, "sig_all": set(sig), "member_sigs": [], "title": title, "members": [], "kagi_domains": 0,
                         "beats": set(), "wiki": [], "hn_points": None, "section_votes": Counter()})
        add_member(len(clusters) - 1, member, sig)
        return len(clusters) - 1

    # Kagi first: its clusters are pre-grouped and well titled, so they make good seeds.
    for it in sorted(raw["items"], key=lambda i: (i["kind"] != "kagi", i.get("published") or "")):
        if it["kind"] == "kagi":
            ci = None
            for a in it.get("articles") or []:
                m = {"pub": a.get("pub") or "", "via": it["via"], "url": a.get("url"), "published": a.get("published"),
                     "title": a.get("title") or "", "summary": ""}
                ci = place(it["title"], m) if ci is None else (add_member(ci, m, tokens(m["title"])) or ci)
            if ci is not None:
                clusters[ci]["kagi_domains"] = max(clusters[ci]["kagi_domains"], it.get("kagi_domains") or 0)
                clusters[ci]["section_votes"][it.get("section_hint") or "world"] += 3
                clusters[ci]["kagi_summary"] = it.get("summary") or ""
            continue
        m = {"pub": it["pub"], "via": it["via"], "url": it["url"], "published": it.get("published"),
             "title": it["title"], "summary": it.get("summary") or ""}
        ci = place(it["title"], m)
        cl = clusters[ci]
        if it.get("beat"):
            cl["beats"].add(it["beat"])
        if it.get("hn_points"):
            cl["hn_points"] = max(cl["hn_points"] or 0, it["hn_points"])
        cl["section_votes"][config.CATEGORY_SECTION.get(it["category"], it["category"])] += 1

    # Wikipedia events: attach to a matching cluster, or become a cluster of their own (feeds can miss things).
    for ev in raw.get("wiki_events") or []:
        sig = tokens(ev["text"])
        best, best_n = None, 0
        cand = Counter()
        for t in sig:
            for ci in index.get(t, ()):
                cand[ci] += 1
        for ci, n in cand.most_common(5):
            csig = clusters[ci]["sig"]
            if n >= 3 and n / max(1, min(len(sig), len(csig))) >= 0.5 and n > best_n:
                best, best_n = ci, n
        if best is not None:
            clusters[best]["wiki"].append(ev["category"])
            clusters[best].setdefault("wiki_text", ev["text"])
            continue
        first = ev["urls"][0] if ev["urls"] else {"url": None, "source": "Wikipedia"}
        title = re.split(r"(?<=[.!?])\s", ev["text"])[0][:180]
        m = {"pub": first["source"] or "Wikipedia", "via": "Wikipedia Current events", "url": first["url"],
             "published": None, "title": title, "summary": ev["text"][:300]}
        ci = place(title, m)
        clusters[ci]["wiki"].append(ev["category"])
        clusters[ci]["wiki_text"] = ev["text"]
        clusters[ci]["section_votes"][_wiki_section(ev)] += 2

    out = [_finish(cl) for cl in clusters]
    if threads:
        attach_thread_hints(out, threads)
    out.sort(key=lambda c: -c["pre_score"])
    for i, c in enumerate(out, 1):
        c["id"] = f"c{i:04d}"

    beats = raw.get("beats") or []
    for b in beats:
        b["cluster_ids"] = [c["id"] for c in out if b["id"] in c["signals"]["beats"]][:8]

    leads = {
        "date": raw["date"], "window": raw["window"], "generated_at": raw.get("generated_at"),
        "clusters": out, "wiki_events": raw.get("wiki_events") or [], "markets": raw.get("markets"),
        "sport": raw.get("sport"), "beats": beats, "source_health": raw.get("source_health"),
        "stats": {"items": len(raw["items"]), "clusters": len(out),
                  "multi_publisher": sum(1 for c in out if c["publishers"] >= 2)},
    }
    (config.day_dir(raw["date"]) / "leads.json").write_text(json.dumps(leads, ensure_ascii=False))
    return leads


_WIKI_SECTION = {
    "Business and economy": "markets", "Science and technology": "science", "Health and environment": "science",
    "Sports": "cricket", "Arts and culture": "world", "Disasters and accidents": "world",
    "Armed conflicts and attacks": "world", "International relations": "world", "Law and crime": "world",
    "Politics and elections": "world",
}


def _wiki_section(ev: dict) -> str:
    text = ev["text"].lower()
    if "india" in text:
        return "india"
    if ev["category"] == "Sports":
        return "f1" if ("formula one" in text or "grand prix" in text) else ("cricket" if "cricket" in text else "world")
    return _WIKI_SECTION.get(ev["category"], "world")


def _finish(cl: dict) -> dict:
    members = cl["members"]
    pubs = {}
    for m in members:
        key = _norm_pub(m["pub"])
        if key and key not in ("google news", "kagi news", "hacker news", "wikipedia"):
            pubs.setdefault(key, m["pub"])
    tier = min((_tier(p) for p in pubs.values()), default=3)
    dates = sorted(d for d in (m.get("published") for m in members) if d)
    # Representative title: prefer a tier-1 publisher's headline, then the longest informative one.
    rep = min(members, key=lambda m: (_tier(m["pub"]), -len(tokens(m["title"]))))
    # Keep a diverse handful of members: distinct publishers, best tier first, newest first.
    seen, keep = set(), []
    for m in sorted(members, key=lambda m: (_tier(m["pub"]), -(len(m.get("summary") or "")), m.get("published") or ""),
                    reverse=False):
        k = _norm_pub(m["pub"])
        if k in seen or not m.get("url"):
            continue
        seen.add(k)
        keep.append({"pub": m["pub"], "via": m["via"], "url": m["url"], "published": m.get("published"),
                     "title": m["title"][:200], "summary": (m.get("summary") or "")[:300]})
        if len(keep) >= 6:
            break
    section = cl["section_votes"].most_common(1)[0][0] if cl["section_votes"] else "world"
    if section not in config.SECTIONS:
        section = "world"
    india_hits = sum(1 for m in members if "india" in (m["title"] + " " + (m.get("summary") or "")).lower())
    n_pub = len(pubs)
    primary = any(p in sources.PRIMARY_PUBLISHERS for p in pubs.values())
    pre = (1.6 * math.log2(1 + n_pub) + (1.2 if tier == 1 else 0) + (1.0 if cl["wiki"] else 0)
           + (0.6 if cl["beats"] else 0) + min(cl["kagi_domains"] / 15, 2.0) + (0.5 if primary else 0)
           + (min((cl["hn_points"] or 0) / 400, 1.0)))
    return {
        "title": rep["title"][:200], "section_hint": section, "first": dates[0] if dates else None,
        "last": dates[-1] if dates else None, "publishers": n_pub, "publisher_names": sorted(pubs.values())[:12],
        "tier": tier, "members": keep, "kagi_summary": cl.get("kagi_summary"), "wiki_text": cl.get("wiki_text"),
        "signals": {"wiki": sorted(set(cl["wiki"])), "kagi": cl["kagi_domains"], "beats": sorted(cl["beats"]),
                    "india": india_hits, "hn": cl["hn_points"], "primary": primary, "scout": False},
        "thread_hint": None, "pre_score": round(pre, 3), "_sig": sorted(cl["sig"]),
    }


def attach_thread_hints(clusters: list[dict], threads: list[dict]) -> None:
    """Mark clusters that look like the next chapter of an active thread (keyword overlap)."""
    active = [t for t in threads if t.get("status") == "active"]
    for c in clusters:
        sig = set(c.get("_sig") or tokens(c["title"]))
        best, best_n = None, 0
        for t in active:
            kw = {k.lower() for k in (t.get("keywords") or [])} | tokens(t.get("title") or "")
            n = len(sig & kw)
            if n >= 2 and n > best_n:
                best, best_n = t["id"], n
        c["thread_hint"] = best
