"""The whole pipeline on a fake engine and synthetic sources: no network, no model calls, a few seconds.

Checks the plumbing end to end: gather → cluster → triage → merge → scout → editor → research/write/check per
story → section research/briefs/check → cover → validation → edition + memory + quality files.
"""
from __future__ import annotations

import asyncio
import json
import re

from routine.briefing import config, engine, gather, stages

from .conftest import NOW, iso, research, story, words

SECTIONS = ["world", "india", "affects_you", "markets", "tech_ai", "science", "f1", "cricket"]
CAT = {"world": "geopolitics", "india": "india", "affects_you": "affects_you", "markets": "markets",
       "tech_ai": "technology", "science": "science", "f1": "f1", "cricket": "cricket"}
TOPICS = ["volcano erupts island", "parliament passes budget", "central bank holds rates", "chip maker unveils",
          "telescope spots planet", "driver wins grand prix", "captain named series", "fuel price cut announced",
          "ceasefire talks resume", "court rules privacy", "rupee hits record", "satellite launch succeeds",
          "storm floods coast", "minister resigns scandal", "startup raises funding", "vaccine trial results"]


def fake_raw(date, window):
    items = []
    for i, sec in enumerate(SECTIONS):
        for j in range(6):
            k = i * 10 + j            # unique words per story so the clusterer keeps them apart
            title = f"{sec.title()} report alpha{k} bravo{k} charlie{k} delta{k} echo{k}"
            for pub in ("Reuters", "BBC", "The Hindu")[: 1 + (j % 3)]:
                items.append({"title": title, "url": f"https://{pub.lower().replace(' ', '')}.com/{sec}/{j}",
                              "summary": words(30, j), "published": iso(2 + j), "pub": pub, "via": pub,
                              "category": CAT[sec], "kind": "rss", "beat": None})
    raw = {"date": date, "window": window, "generated_at": NOW.isoformat(), "items": items, "wiki_events": [],
           "markets": {"as_of": NOW.isoformat(), "quotes": [{"sym": "^NSEI", "name": "Nifty 50", "last": 23321.7,
                                                            "chg_pct": 1.17}]},
           "sport": {"f1": {}}, "beats": [{"id": "rbi", "section": "markets", "label": "RBI", "must_check": True,
                                           "hits": 0}],
           "source_health": [{"name": "fake", "kind": "rss", "ok": True, "items": len(items), "error": None}]}
    (config.day_dir(date) / "raw.json").write_text(json.dumps(raw))
    return raw


def ids(prompt, pattern=r'<item id="([^"]+)"'):
    return re.findall(pattern, prompt)


def hinglish(p, s):
    rows = json.loads(re.search(r"<story>\n(.*)\n</story>", p, re.S).group(1))
    return {"scenes": [{"say": "Dekhiye " + r["say"], "speak": "देखिए " + r["say"]} for r in rows]}


def handlers():
    def triage(p, s):
        out = []
        for block in re.findall(r'<item id="([^"]+)">\ntitle: [^\n]*\noutlets: [^\n]*\nsection hint: (\w+)', p):
            cid, sec = block
            out.append({"id": cid, "section": sec, "scale": 3, "severity": 3, "durability": 3, "novelty": 4,
                        "india": 3, "interest": sec in ("f1", "cricket"), "same_as_thread": "",
                        "line": f"A plain one line summary of story {cid} for the reader.", "drop_reason": ""})
        return {"items": out}

    def editor(p, s):
        cands = re.findall(r"^\[(\w+)\] (\w+) ·", p, flags=re.M)
        t1, t2, t3, per = [], [], [], {}
        for cid, sec in cands:
            if len(t1) < 5 and sec not in ("f1", "cricket") and sum(1 for x in t1 if x["section"] == sec) < 2:
                t1.append({"cluster_ids": [cid], "section": sec, "thread_id": "", "new_thread": True,
                           "india_angle": "primary" if sec == "india" else "secondary", "contested": False,
                           "us_domestic": False, "question": f"What happened in story {cid} and why?",
                           "must_answer": ["What?", "Why?"], "why_chosen": "big", "calendar_ids": []})
            elif per.get(sec, 0) < 2:
                per[sec] = per.get(sec, 0) + 1
                t2.append({"cluster_ids": [cid], "section": sec, "thread_id": "", "new_thread": False, "angle": "",
                           "calendar_ids": []})
            elif len(t3) < 6:
                t3.append({"cluster_id": cid, "section": sec})
        return {"tier1": t1, "reserves": [], "tier2": t2, "tier3": t3, "quiet": [], "threads": [],
                "watch_today": [{"text": "Panel review", "time_ist": "", "calendar_id": ""}], "misses": []}

    def section(p, s):
        return {"items": [{"item_id": i, "ok": True, "note": "", "facts": [
            {"text": "fact", "pub": "Reuters", "url": f"https://reuters.com/{i}", "published": iso(2), "excerpt": "x"}]}
            for i in ids(p)]}

    def briefs(p, s):
        out = [{"item_id": i, "headline": f"Clear headline for item {i}", "text": words(70, 3),
                "background": words(12), "why": words(12, 2), "source_urls": [f"https://reuters.com/{i}"],
                "status": "new", "thread_summary": ""} for i in ids(p)]
        secs = re.findall(r"## Section: [^(]+\((\w+)\)", p)
        return {"briefs": out, "gists": [{"section": sec, "gist": words(12, 4)} for sec in secs]}

    def cover(p, s):
        refs = re.findall(r"^- (s\d+|b-[\w-]+)", p, flags=re.M)
        return {"top_line": words(25, 1), "changes": [{"text": words(8), "ref": r} for r in refs[:6]],
                "watch_today": [{"text": "Panel review", "time_ist": ""}]}

    return {
        "triage": triage, "same_story": lambda p, s: {"groups": []}, "scout": lambda p, s: {"findings": []},
        "editor": editor, "research": lambda p, s: research(), "writer": lambda p, s: story(),
        "checker": lambda p, s: ({"checks": [{"item_id": i, "severity": "ok", "problems": []} for i in ids(p)]}
                                 if "checks" in s["properties"] else {"ok": True, "problems": []}),
        "fixer": lambda p, s: story(), "section": section, "briefs": briefs, "cover": cover,
        "recall": lambda p, s: {"total": 0, "matched": 0, "misses": []},
        "bootstrap": lambda p, s: {"threads": []}, "hinglish": hinglish,
    }


def test_full_pipeline_on_fake_engine(monkeypatch):
    monkeypatch.setattr(gather, "run", fake_raw)
    monkeypatch.setattr(config, "ROOT", config.PUB.parent.parent)        # no old digest archive -> no bootstrap
    eng = engine.FakeEngine(handlers())
    state = asyncio.run(stages.run("2026-11-03", eng, now=NOW))
    assert state["status"] == "done", state.get("notes")
    ed = json.loads((config.PUB / "2026-11-03.json").read_text())
    assert ed["status"] == "complete" and len(ed["stories"]) == 5
    assert [s["key"] for s in ed["sections"]] == SECTIONS
    assert ed["stories"][0]["must_read"] and ed["stories"][0]["reel"]["voice"] == config.REEL_VOICE_HI
    sc = ed["stories"][0]["reel"]["scenes"][0]
    assert sc["say"].startswith("Dekhiye ") and sc["speak"].startswith("देखिए ") and "say_en" not in sc
    assert all(s["thread"] and s["thread"]["status"] == "new" for s in ed["stories"])
    assert len(ed["quiz"]) == 3 and ed["cover"]["changes"] and ed["markets"]["quotes"]
    assert sum(len(s["items"]) for s in ed["sections"]) >= 8
    thr = json.loads((config.PUB / "threads.json").read_text())
    assert len([t for t in thr["threads"] if t["status"] == "active"]) >= 5
    idx = json.loads((config.PUB / "index.json").read_text())
    assert idx["latest"] == "2026-11-03"
    q = json.loads((config.PUB / "quality" / "2026-11-03.json").read_text())
    assert q["counts"]["stories"] == 5 and q["usage"]["calls"] > 10

    # Resume: a second run re-uses every cached step (no new model calls) and keeps the edition.
    calls_before = len(eng.calls)
    asyncio.run(stages.run("2026-11-03", eng, now=NOW))
    assert len(eng.calls) - calls_before <= 1                          # at most the briefs-fix probe


def test_failed_engine_still_writes_quality_report(monkeypatch):
    monkeypatch.setattr(gather, "run", fake_raw)
    monkeypatch.setattr(config, "ROOT", config.PUB.parent.parent)
    state = asyncio.run(stages.run("2026-11-03", engine.FakeEngine({}), now=NOW))
    # Every model step fails -> fallback plan, no stories; the edition is 'lite' or the run fails, never silent.
    q = json.loads((config.PUB / "quality" / "2026-11-03.json").read_text())
    assert q["status"] in ("lite", "partial", "failed")
    assert state["status"] in ("done", "failed")


def test_failed_section_falls_back_to_one_liners(monkeypatch):
    """If every planned brief in a section fails verification, its headlines become one-liners and the
    section says so honestly (no fake 'nothing major' note); diagnostics land in the quality file."""
    monkeypatch.setattr(gather, "run", fake_raw)
    monkeypatch.setattr(config, "ROOT", config.PUB.parent.parent)
    h = handlers()
    base_section = h["section"]

    def section(p, s):
        out = base_section(p, s)
        if "Section: Tech & AI" in p:
            for it in out["items"]:
                it["ok"] = False
        return out
    h["section"] = section
    state = asyncio.run(stages.run("2026-11-03", engine.FakeEngine(h), now=NOW))
    assert state["status"] == "done", state.get("notes")
    ed = json.loads((config.PUB / "2026-11-03.json").read_text())
    tech = next(s for s in ed["sections"] if s["key"] == "tech_ai")
    assert tech["quiet"] and "couldn't be verified" in tech["quiet_note"]
    assert any(a["section"] == "tech_ai" for a in ed["also"])
    q = json.loads((config.PUB / "quality" / "2026-11-03.json").read_text())
    assert q["sections"]["tech_ai"]["verified"] == 0 and q["stories"][0]["research"]["sites"] >= 3
