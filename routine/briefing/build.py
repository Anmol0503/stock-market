"""Assembly + validation: turn checked model outputs into the public edition, enforcing the quality rules.

Content is never deleted just to pass. A failing story is demoted to a brief, or dropped with a note that
the reader sees. A failing optional block is removed, and a bad reel script means no video.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import urllib.parse

from . import config

from routine.digest import _EMAIL, _words  # noqa: E402  (reuse: same word counting + privacy regex)

RELATIVE = re.compile(r"(?<!India )(?<!USA )\b(today|yesterday|tonight|tomorrow|last night|this (?:morning|afternoon|"
                      r"evening|week)|next week)\b", re.I)
UNSPEAKABLE = re.compile(r"[₹$%&/()*\[\]#@<>{}|~^]")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
AGGREGATORS = {"news.google.com", "msn.com", "flipboard.com", "news.yahoo.com", "newsbreak.com"}
REQUIRED_BLOCKS = ("so_far", "what_happened", "why_chain", "for_you", "next")
W = config.WORDS


def words(s) -> int:
    return _words(s)


def domain(url: str | None) -> str:
    try:
        host = urllib.parse.urlparse(url or "").netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _in(n: int, key: str, slack: float = 0.0) -> bool:
    lo, hi = W[key]
    return lo * (1 - slack) <= n <= hi * (1 + slack)


def _nums(text: str) -> set[str]:
    return {m.replace(",", "") for m in NUMBER.findall(text or "")}


def claim_corpus(research: dict, markets: dict | None = None) -> set[str]:
    parts = []
    for c in research.get("claims") or []:
        parts += [c.get("text", ""), c.get("excerpt", "")]
    for n in research.get("numbers") or []:
        parts += [n.get("value", ""), n.get("compare", "")]
    for t in research.get("timeline") or []:
        parts += [t.get("date", ""), t.get("event", "")]
    for q in (markets or {}).get("quotes") or []:
        parts.append(str(q.get("last")))
    return _nums(" ".join(parts))


def unverified_numbers(text: str, corpus: set[str], year: int) -> list[str]:
    bad = []
    for n in _nums(text):
        try:
            v = float(n)
        except ValueError:
            continue
        if v <= 31 or (year - 1 <= v <= year + 1 and "." not in n):
            continue
        if n not in corpus and n.rstrip("0").rstrip(".") not in corpus:
            bad.append(n)
    return bad


def story_text(s: dict) -> str:
    parts = [s.get("headline"), s.get("question"), s.get("dek"), s.get("so_far", {}).get("text"),
             s.get("what_happened", {}).get("text"), s.get("for_you", {}).get("text"), s.get("next", {}).get("text"),
             (s.get("analogy") or {}).get("text"), (s.get("analogy") or {}).get("breaks"),
             (s.get("misconception") or {}).get("myth"), (s.get("misconception") or {}).get("fact"), s.get("changed")]
    parts += [x.get("text") for x in s.get("why_chain") or []]
    parts += [f"{x.get('value')} {x.get('meaning')}" for x in s.get("numbers") or []]
    parts += [x.get("view") for x in s.get("views") or []]
    parts += [x.get("who") for x in s.get("players") or []]
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------- story checks (also used before the checker)
def story_problems(s: dict, research: dict, *, slot: dict, year: int, markets: dict | None = None) -> list[dict]:
    """Code-detectable problems in a writer's story. severity: fix (fixable) or drop (unusable)."""
    P = []

    def bad(where, issue, sev="fix"):
        P.append({"where": where, "issue": issue, "severity": sev})

    cids = {c.get("cid") for c in research.get("claims") or []}
    for key, wkey in (("headline", "headline"), ("question", "question"), ("dek", "dek")):
        n = words(s.get(key))
        if not _in(n, wkey, 0.15):
            bad(key, f"{n} words; must be {W[wkey][0]}–{W[wkey][1]}")
    if not str(s.get("question", "")).strip().endswith("?"):
        bad("question", "must end with a question mark")
    for b in ("so_far", "what_happened", "for_you"):
        n = words((s.get(b) or {}).get("text"))
        if n == 0:
            bad(b, "required block is empty", "drop" if b == "what_happened" else "fix")
        elif not _in(n, b, 0.15):
            bad(b, f"{n} words; must be {W[b][0]}–{W[b][1]}")
    steps = s.get("why_chain") or []
    if not 3 <= len(steps) <= 5:
        bad("why_chain", f"{len(steps)} steps; must be 3–5")
    for i, st in enumerate(steps):
        if not _in(words(st.get("text")), "why_step", 0.25):
            bad(f"why_chain[{i}]", f"{words(st.get('text'))} words; must be 8–25")
    nx = s.get("next") or {}
    if not _in(words(nx.get("text")), "next", 0.2):
        bad("next", f"{words(nx.get('text'))} words; must be 20–50")
    an = s.get("analogy") or {}
    if an.get("text") and (not _in(words(an.get("text")), "analogy", 0.2) or not an.get("breaks")):
        bad("analogy", "analogy needs 20–60 words plus where it breaks (or leave both empty)")
    if slot.get("contested") and len([v for v in s.get("views") or [] if v.get("holder")]) < 2:
        bad("views", "contested story needs views from at least 2 named holders")
    for b in ("so_far", "what_happened"):
        used = (s.get(b) or {}).get("cids") or []
        if not used:
            bad(b, "FACT block cites no claims (cids empty)")
        for c in used:
            if c not in cids:
                bad(b, f"cites unknown claim {c}")
    total = words(story_text(s))
    if not _in(total, "story_total", 0.1):
        bad("story", f"{total} words in total; must be {W['story_total'][0]}–{W['story_total'][1]}")
    txt = story_text(s)
    for m in set(RELATIVE.findall(txt)):
        bad("dates", f"relative date '{m}': use an absolute date")
    nums = unverified_numbers(txt, claim_corpus(research, markets), year)
    if nums:   # 3+ invented-looking numbers after a fix pass blocks the story
        bad("facts:numbers", f"numbers not found in the claims: {', '.join(sorted(nums)[:6])}",
            "drop" if len(nums) >= 3 else "fix")
    P += lesson_problems(s, research, year, markets)
    P += reel_problems(s.get("reel") or [], research, year, markets)
    return P


def lesson_text(s: dict) -> str:
    ls = s.get("lesson") or {}
    ex = ls.get("example") or {}
    parts = [ls.get("concept"), ls.get("big_idea"), ex.get("setup"), ex.get("result"),
             (ls.get("apply") or {}).get("text"), (ls.get("practice") or {}).get("q"),
             (ls.get("practice") or {}).get("answer")]
    parts += [f"{x.get('title')}. {x.get('text')}" for x in ls.get("steps") or []]
    parts += [f"{x.get('label')} {x.get('calc')} {x.get('note')}" for x in ex.get("lines") or []]
    parts += list(s.get("takeaways") or [])
    return " ".join(p for p in parts if p)


HYPOTHETICAL = re.compile(r"^\s*(say|imagine|suppose|assume|picture|let's say|let us say|think of)\b", re.I)


def lesson_problems(s: dict, research: dict, year: int, markets: dict | None = None) -> list[dict]:
    """The lesson ("Learn the idea") is required, but it is never a reason to drop a story: every problem is a fix,
    and a lesson still broken after the fix pass is removed (see stages._strip_optional)."""
    P = []

    def bad(where, issue, soft=False):   # soft = length/shape only; the lesson is kept even if it stays
        P.append({"where": where, "issue": issue, "severity": "fix", **({"soft": True} if soft else {})})
    ls = s.get("lesson") or {}
    if not ls.get("concept") or not (ls.get("steps") or []):
        return [{"where": "lesson", "issue": "the lesson is missing: teach the one idea behind the story",
                 "severity": "fix"}]
    for key, wkey in (("concept", "concept"), ("big_idea", "big_idea")):
        if not _in(words(ls.get(key)), wkey, 0.2):
            bad(f"lesson.{key}", f"{words(ls.get(key))} words; must be {W[wkey][0]}–{W[wkey][1]}", True)
    steps = ls.get("steps") or []
    if not 3 <= len(steps) <= 5:
        bad("lesson.steps", f"{len(steps)} steps; must be 3–5", True)
    for i, st in enumerate(steps):
        if not st.get("title") or not _in(words(st.get("text")), "lesson_step", 0.25):
            bad(f"lesson.steps[{i}]", f"each step needs a title and 15–55 words (has {words(st.get('text'))})", True)
    ex = ls.get("example") or {}
    lines = ex.get("lines") or []
    if not 3 <= len(lines) <= 6 or not all(x.get("label") and x.get("calc") for x in lines):
        bad("lesson.example", f"worked example needs 3–6 lines, each with a label and the working (has {len(lines)})", True)
    if not HYPOTHETICAL.search(ex.get("setup") or ""):
        bad("lesson.example", "the example's setup must start with 'Say', 'Imagine' or 'Suppose' (it is made up)")
    if not ex.get("result"):
        bad("lesson.example", "the example needs a result: what it shows")
    ap = ls.get("apply") or {}
    if not _in(words(ap.get("text")), "apply", 0.2):
        bad("lesson.apply", f"{words(ap.get('text'))} words; must be 20–70 and link the idea back to the news", True)
    for c in ap.get("cids") or []:
        if c not in {x.get("cid") for x in research.get("claims") or []}:
            bad("lesson.apply", f"cites unknown claim {c}")
    pr = ls.get("practice") or {}
    if not pr.get("q") or not pr.get("answer"):
        bad("lesson.practice", "add a try-it-yourself question with a worked answer", True)
    tk = [t for t in s.get("takeaways") or [] if t]
    if len(tk) != 3 or not all(_in(words(t), "takeaway", 0.25) for t in tk):
        bad("takeaways", "exactly 3 takeaways of 5–22 words each", True)
    if not _in(words(lesson_text(s)), "lesson_total", 0.1):
        bad("lesson", f"{words(lesson_text(s))} words; the lesson should be {W['lesson_total'][0]}–{W['lesson_total'][1]}", True)
    for m in set(RELATIVE.findall(lesson_text(s))):
        bad("lesson", f"relative date '{m}': use an absolute date")
    # Real-world facts in the lesson live in `apply` (the example and practice are made-up numbers).
    nums = unverified_numbers(ap.get("text") or "", claim_corpus(research, markets), year)
    if nums:
        bad("lesson.apply", f"numbers not found in the claims: {', '.join(sorted(nums)[:6])}")
    return P


def reel_problems(scenes: list[dict], research: dict, year: int, markets: dict | None = None) -> list[dict]:
    """Reel script checks. Only problems that would make a video WRONG or MISLEADING are hard (they drop the
    video): a big number not in the claims, a relative date, symbols the voice can't read. Length, scene count,
    scene order and map codes are soft: the fixer is asked to correct them, but the video is still made."""
    P = []

    def add(where, issue, soft):
        P.append({"where": where, "issue": issue, "severity": "fix", "soft": soft})
    if not scenes:
        return [{"where": "reel", "issue": "no reel script", "severity": "fix", "soft": False}]
    if not 5 <= len(scenes) <= 9:
        add("reel", f"{len(scenes)} scenes; aim for 5–8", True)
    total = sum(words(sc.get("say")) for sc in scenes)
    lo, hi = config.WORDS["reel_total"]
    if not _in(total, "reel_total", 0.12):
        add("reel", f"narration {total} words; aim for {lo}–{hi}", 80 <= total <= 260)
    corpus = claim_corpus(research, markets)
    for i, sc in enumerate(scenes):
        say = sc.get("say") or ""
        if words(say) > 55:
            add(f"reel[{i}]", "scene narration over 50 words", words(say) <= 90)
        if UNSPEAKABLE.search(say):
            add(f"reel[{i}]", "narration has symbols; spell them out (per cent, rupees)", False)
        if RELATIVE.search(say):
            add(f"reel[{i}]", "relative date in narration", False)
        if sc.get("kind") == "big_number" and unverified_numbers(sc.get("number_value", ""), corpus, year):
            add(f"reel[{i}]", "big number not in the claims", False)
        if sc.get("kind") == "map" and not all(re.fullmatch(r"[A-Z]{3}", c or "") for c in sc.get("map_iso3") or [""]):
            add(f"reel[{i}]", "map needs ISO alpha-3 country codes", True)
    if scenes[0].get("kind") != "hook":
        add("reel[0]", "first scene must be the hook", True)
    return P


# ---------------------------------------------------------------- public shapes
def _excerpt(s: str) -> str:
    s = " ".join((s or "").split())
    if len(s) <= config.EXCERPT_MAX_CHARS:
        return s
    cut = s[: config.EXCERPT_MAX_CHARS].rsplit(" ", 1)[0]
    return cut + "…"


def _ist(published: str | None) -> str | None:
    t = config.parse_ts(published)
    return config.iso(t) if t else None


def _scene(sc: dict) -> dict:
    out = {"kind": sc.get("kind"), "say": sc.get("say", "").strip(), "show": " ".join((sc.get("show") or "").split()[:8])}
    k = sc.get("kind")
    if k == "big_number":
        out["number"] = {"value": sc.get("number_value", ""), "label": sc.get("number_label", "")}
    elif k == "map":
        out["map"] = {"iso3": sc.get("map_iso3") or [], "pin": [sc.get("map_lon") or 0, sc.get("map_lat") or 0],
                      "label": sc.get("map_label", "")}
    elif k in ("bar", "line"):
        out["chart"] = {"title": sc.get("chart_title", ""), "unit": sc.get("chart_unit", ""),
                        "points": (sc.get("chart_points") or [])[:8]}
    elif k == "timeline":
        out["timeline"] = (sc.get("timeline") or [])[:5]
    elif k == "players":
        out["players"] = (sc.get("players") or [])[:4]
    elif k == "steps":
        out["steps"] = [x for x in sc.get("steps") or [] if x.get("calc")][:4]
    return out


def public_story(sid: str, slot: dict, s: dict, research: dict, *, thread: dict | None, window: dict,
                 now: dt.datetime, markets: dict | None) -> tuple[dict | None, list[str], bool]:
    """Returns (story or None, notes, reel_ok). None = can't be a story (caller may demote to a brief)."""
    notes: list[str] = []
    claims = {c["cid"]: c for c in research.get("claims") or [] if c.get("cid")}
    order: list[str] = []          # urls in order of first use
    src_by_url: dict[str, dict] = {}

    def refs(cids) -> list[int]:
        out = []
        for cid in cids or []:
            c = claims.get(cid)
            if not c or not str(c.get("url", "")).startswith("http"):
                continue
            u = c["url"]
            if u not in src_by_url:
                src_by_url[u] = {"pub": c.get("pub") or domain(u), "url": u, "published": _ist(c.get("published")),
                                 "type": c.get("type") or "outlet", "excerpt": _excerpt(c.get("excerpt", ""))}
                order.append(u)
            n = order.index(u) + 1
            if n not in out:
                out.append(n)
        return out

    blocks = {
        "so_far": {"text": s["so_far"]["text"], "src": refs(s["so_far"].get("cids"))},
        "what_happened": {"text": s["what_happened"]["text"], "src": refs(s["what_happened"].get("cids"))},
        "why_chain": {"steps": [{"text": st["text"], "src": refs(st.get("cids"))} for st in s.get("why_chain") or []]},
    }
    if s.get("players"):
        blocks["players"] = {"items": [{"name": p["name"], "who": p["who"]} for p in s["players"][:5] if p.get("name")]}
    if s.get("numbers"):
        blocks["numbers"] = {"items": [{"value": n["value"], "meaning": n["meaning"], "src": refs(n.get("cids"))}
                                       for n in s["numbers"][:4] if n.get("value")]}
    an = s.get("analogy") or {}
    if an.get("text") and an.get("breaks"):
        blocks["analogy"] = {"text": an["text"], "breaks": an["breaks"]}
    views = [v for v in s.get("views") or [] if v.get("holder") and v.get("view")]
    if views:
        blocks["views"] = {"items": [{"holder": v["holder"], "view": v["view"], "src": refs([v.get("cid")])}
                                     for v in views[:4]]}
    blocks["for_you"] = {"text": s["for_you"]["text"], "src": refs(s["for_you"].get("cids"))}
    mc = s.get("misconception") or {}
    if mc.get("myth") and mc.get("fact"):
        blocks["misconception"] = {"myth": mc["myth"], "fact": mc["fact"], "src": refs(mc.get("cids"))}
    nx = s.get("next") or {}
    blocks["next"] = {"text": nx.get("text", ""), "dates": [d for d in nx.get("dates") or [] if d.get("date")][:5],
                      "unknowns": [u for u in nx.get("unknowns") or [] if u][:4]}

    lesson = public_lesson(s, refs)
    if lesson:
        blocks["lesson"] = lesson

    sources = [{"n": i + 1, **src_by_url[u]} for i, u in enumerate(order)]
    # ---- source rules
    start = config.parse_ts(window["start"]) - dt.timedelta(hours=24)
    doms = {domain(x["url"]) for x in sources}
    fresh = [x for x in sources if (t := config.parse_ts(x["published"])) and t >= start]
    future = [x for x in sources if (t := config.parse_ts(x["published"])) and t > now + dt.timedelta(hours=1)]
    undated_nonprimary = [x for x in sources if not x["published"] and x["type"] not in ("primary", "analysis", "data")]
    ok = True
    if len(sources) < 3 or len(doms) < 3:
        notes.append(f"{sid}: only {len(sources)} sources from {len(doms)} sites (need 3+)")
        ok = False
    if not fresh:
        notes.append(f"{sid}: no source published inside the news window")
        ok = False
    if future:
        notes.append(f"{sid}: source dated in the future ({future[0]['url']})")
        ok = False
    if doms and doms <= AGGREGATORS:
        notes.append(f"{sid}: only aggregator sources")
        ok = False
    if undated_nonprimary:
        notes.append(f"{sid}: {len(undated_nonprimary)} undated non-official source(s) kept, flagged")
    if not ok:
        return None, notes, False

    pubs = {x["pub"] for x in sources}
    primary = sum(1 for x in sources if x["type"] == "primary")
    wire = sum(1 for x in sources if x["type"] == "wire")
    level = "high" if len(pubs) >= 4 and (primary or wire) else ("medium" if len(pubs) >= 3 else "low")
    newest = max((x["published"] for x in sources if x["published"]), default=None)

    scenes = [_scene(sc) for sc in s.get("reel") or []]
    rp = [p for p in reel_problems(s.get("reel") or [], research, now.year, markets) if not p.get("soft")]
    reel_ok = bool(scenes) and not rp
    if not reel_ok and scenes:
        notes.append(f"{sid}: reel script failed checks, no video ({rp[0]['issue'] if rp else 'empty'})")
    reel = {"voice": config.REEL_VOICE, "scenes": scenes} if reel_ok else None
    reel_hash = hashlib.sha1(json.dumps(reel, sort_keys=True).encode()).hexdigest()[:12] if reel else None

    story = {
        "id": sid, "slug": _slug(s.get("headline") or sid), "section": slot["section"],
        "india_angle": slot.get("india_angle", "none"), "contested": bool(slot.get("contested")),
        "thread": thread, "headline": s["headline"], "question": s["question"], "dek": s["dek"],
        "blocks": blocks,
        "terms": [t for t in s.get("terms") or [] if t.get("term") and t.get("meaning")][:4],
        "check": _check(s.get("check")),
        "takeaways": [t for t in s.get("takeaways") or [] if t][:3] if lesson else [],
        "confidence": {"level": level, "publishers": len(pubs), "primary": primary, "newest": newest},
        "sources": sources, "reel": reel, "reel_hash": reel_hash,
        "read_min": max(2, math.ceil((words(story_text(s)) + (words(lesson_text(s)) if lesson else 0)) / 200)),
    }
    return story, notes, reel_ok


def public_lesson(s: dict, refs) -> dict | None:
    ls = s.get("lesson") or {}
    steps = [x for x in ls.get("steps") or [] if x.get("title") and x.get("text")]
    ex = ls.get("example") or {}
    lines = [{"label": x["label"], "calc": x["calc"], "note": x.get("note", "")}
             for x in ex.get("lines") or [] if x.get("label") and x.get("calc")]
    if not ls.get("concept") or len(steps) < 2:
        return None
    out = {"concept": ls["concept"], "big_idea": ls.get("big_idea", ""),
           "steps": [{"title": x["title"], "text": x["text"], "src": refs(x.get("cids"))} for x in steps[:5]]}
    if ex.get("setup") and lines:
        out["example"] = {"setup": ex["setup"], "lines": lines[:6], "result": ex.get("result", "")}
    ap = ls.get("apply") or {}
    if ap.get("text"):
        out["apply"] = {"text": ap["text"], "src": refs(ap.get("cids"))}
    pr = ls.get("practice") or {}
    if pr.get("q") and pr.get("answer"):
        out["practice"] = {"q": pr["q"], "answer": pr["answer"]}
    return out


def _check(c: dict | None) -> dict | None:
    if not c or not c.get("q") or len(c.get("options") or []) < 2:
        return None
    ans = c.get("answer", 0)
    if not isinstance(ans, int) or not 0 <= ans < len(c["options"]):
        return None
    return {"q": c["q"], "options": c["options"][:4], "answer": ans, "why": c.get("why", "")}


def _slug(text: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower())[:6]) or "story"


def demote(sid: str, section: str, s: dict, research: dict, window: dict) -> dict | None:
    """Turn a story that failed the big-story rules into a brief, if it has at least one fresh dated source."""
    claims = {c["cid"]: c for c in research.get("claims") or []}
    cited = [claims[c] for c in ((s.get("what_happened") or {}).get("cids") or []) if c in claims]
    start = config.parse_ts(window["start"]) - dt.timedelta(hours=24)
    fresh = [c for c in cited if (t := config.parse_ts(c.get("published"))) and t >= start]
    if not fresh or not (s.get("what_happened") or {}).get("text"):
        return None
    text = s["what_happened"]["text"]
    bg = re.split(r"(?<=[.!?])\s", (s.get("so_far") or {}).get("text", ""))[0]
    why = re.split(r"(?<=[.!?])\s", (s.get("for_you") or {}).get("text", ""))[0]
    seen, srcs = set(), []
    for c in cited:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        srcs.append({"pub": c.get("pub") or domain(c["url"]), "url": c["url"], "published": _ist(c.get("published"))})
    return {"id": f"b-{section}-{sid}", "section": section, "headline": s.get("headline", ""), "text": text,
            "background": bg, "why": why, "status": "new", "thread": None, "sources": srcs[:4], "_demoted": sid}


def public_brief(item: dict, b: dict, facts: list[dict], window: dict) -> tuple[dict | None, str | None]:
    by_url = {f["url"]: f for f in facts if str(f.get("url", "")).startswith("http")}
    urls = [u for u in b.get("source_urls") or [] if u in by_url] or list(by_url)[:2]
    start = config.parse_ts(window["start"]) - dt.timedelta(hours=24)
    srcs = [{"pub": by_url[u].get("pub") or domain(u), "url": u, "published": _ist(by_url[u].get("published"))}
            for u in urls[:4]]
    if not srcs:
        return None, f"{item['id']}: no usable source"
    if not any((t := config.parse_ts(x["published"])) and t >= start for x in srcs):
        return None, f"{item['id']}: no fresh dated source"
    text = " ".join([b.get("headline", ""), b.get("text", ""), b.get("background", ""), b.get("why", "")])
    m = RELATIVE.search(text)
    if m:
        return None, f"{item['id']}: relative date '{m.group(0)}'"
    n = words(b.get("text"))
    if not 30 <= n <= 150 or not b.get("headline"):
        return None, f"{item['id']}: brief text {n} words"
    return {"id": item["id"], "section": item["section"], "headline": b["headline"], "text": b["text"],
            "background": b.get("background", ""), "why": b.get("why", ""), "status": b.get("status", "new"),
            "thread": item.get("thread"), "sources": srcs}, None


def privacy_ok(obj) -> list[str]:
    blob = json.dumps(obj, ensure_ascii=False)
    errs = []
    if _EMAIL.search(blob):
        errs.append("contains an email address")
    if "/Users/" in blob or "/home/user" in blob:
        errs.append("contains a local file path")
    return errs


def rebuild_index() -> dict:
    days = []
    for p in sorted(config.PUB.glob("20??-??-??.json"), reverse=True):
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        days.append({"date": d.get("date"), "edition": d.get("edition"), "status": d.get("status"),
                     "stories": len(d.get("stories") or []),
                     "briefs": sum(len(s.get("items") or []) for s in d.get("sections") or []),
                     "top_line": ((d.get("cover") or {}).get("top_line") or "")[:200]})
    idx = {"generated_at": config.iso(config.now_ist()), "latest": days[0]["date"] if days else None, "days": days}
    (config.PUB / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    return idx
