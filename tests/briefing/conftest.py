"""Shared fixtures: an isolated output/ and dashboard/briefing/ per test, and helpers to build valid content."""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from routine.briefing import config  # noqa: E402

NOW = dt.datetime(2026, 11, 3, 4, 10, tzinfo=config.IST)
LOREM = ("clear plain words help every reader follow each step of the story with calm care and steady focus "
         "while context shows why the change matters for people across many towns and cities").split()


def words(n: int, seed: int = 0) -> str:
    return " ".join(LOREM[(i + seed) % len(LOREM)] for i in range(n)) + "."


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    out, pub = tmp_path / "output" / "briefing", tmp_path / "dashboard" / "briefing"
    pub.mkdir(parents=True)
    monkeypatch.setattr(config, "OUT_ROOT", out)
    monkeypatch.setattr(config, "PUB", pub)
    monkeypatch.setenv("BRIEFING_NOW", NOW.isoformat())
    monkeypatch.setenv("BRIEFING_RETRY_SLEEP", "0")
    from routine.briefing import agenda, threads
    monkeypatch.setattr(threads, "PATH", pub / "threads.json")
    monkeypatch.setattr(agenda, "PATH", pub / "calendar.json")
    yield tmp_path


def iso(hours_ago: float) -> str:
    return (NOW - dt.timedelta(hours=hours_ago)).astimezone(config.UTC).isoformat(timespec="seconds")


def research(n_claims: int = 10, *, fresh_hours: float = 3) -> dict:
    doms = ["reuters.com", "thehindu.com", "pib.gov.in", "bbc.co.uk", "apnews.com", "livemint.com"]
    claims = []
    for i in range(1, n_claims + 1):
        d = doms[(i - 1) % len(doms)]
        claims.append({"cid": f"k{i}", "text": f"Fact {i}: the panel reported 1,250 cases and 68 deaths.",
                       "kind": "fact", "pub": d.split(".")[0].title(), "url": f"https://{d}/story-{i}",
                       "published": iso(fresh_hours + i * 0.1), "type": "primary" if d == "pib.gov.in" else "outlet",
                       "excerpt": f"Excerpt {i}: 1,250 cases were reported and 68 people died.", "confidence": "high"})
    return {"claims": claims, "numbers": [{"cid": "k1", "value": "1,250 cases", "compare": "double last year",
                                           "compare_cid": ""}],
            "timeline": [], "players": [], "views": [], "current_facts": [], "unknowns": ["exact cause"],
            "searches": 6, "fetches": 2, "notes": ""}


def story(*, contested: bool = False) -> dict:
    """A writer output that satisfies every word range."""
    # A full-coverage reel: every chapter in order, 14 scenes, ~470 words.
    chaps = ["hook", "what_happened", "what_happened", "history", "why", "why", "players", "idea", "idea",
             "example", "for_you", "next", "remember", "remember"]
    scenes = [{"kind": "hook" if c == "hook" else "outro" if c == "remember" else "kinetic", "chapter": c,
               "say": words(34, i % 6), "show": "Key point"} for i, c in enumerate(chaps)]
    for sc in scenes:
        sc.update({"number_value": "", "number_label": "", "number_cid": "", "map_iso3": [], "map_lon": 0, "map_lat": 0,
                   "map_label": "", "chart_title": "", "chart_unit": "", "chart_points": [], "chart_cids": [],
                   "timeline": [], "players": [], "steps": [], "views": []})
    return {
        "headline": "Panel reports 1,250 cases after the outbreak spreads",
        "question": "Why is the outbreak spreading faster than officials expected this season?",
        "dek": words(32, 2),
        "so_far": {"text": words(105, 3), "cids": ["k1", "k2"]},
        "history": {"text": words(140, 4), "cids": ["k3", "k4"],
                    "timeline": [{"when": w, "what": words(8, i), "cid": f"k{i + 1}"}
                                 for i, w in enumerate(["Jan 2025", "Jun 2025", "Feb 2026", "Oct 2026"], 1)]},
        "what_happened": {"text": "The panel reported 1,250 cases and 68 deaths. " + words(95, 4), "cids": ["k1", "k3"]},
        "why_chain": [{"text": words(22, i), "cids": ["k4"]} for i in range(4)],
        "players": [], "numbers": [{"value": "1,250 cases", "meaning": "double last year", "cids": ["k1"]}],
        "analogy": {"text": "", "breaks": ""},
        "views": ([{"holder": "Health ministry", "view": words(15, 6), "cid": "k5"},
                   {"holder": "Doctors' union", "view": words(15, 7), "cid": "k6"}] if contested else []),
        "for_you": {"text": words(65, 8), "cids": ["k3"]},
        "misconception": {"myth": "", "fact": "", "cids": []},
        "next": {"text": words(45, 9), "dates": [{"date": "2026-11-10", "what": "Panel review"}], "unknowns": []},
        "changed": "", "thread_summary": words(40, 10), "state_facts": [{"fact": "Cases: 1,250", "cid": "k1"}],
        "terms": [{"term": "Outbreak", "meaning": "a sudden rise in cases of a disease"}],
        "check": {"q": "What did the panel report about the outbreak?", "options": ["Fewer cases", "1,250 cases", "No change"],
                  "answer": 1, "why": "The panel reported 1,250 cases."},
        "lesson": lesson(),
        "takeaways": ["An outbreak grows when each case passes on to more than one person.",
                      "The panel reported 1,250 cases and 68 deaths in the outbreak.",
                      "Watch the panel review on 10 November for the cause."],
        "reel": scenes,
    }


def lesson() -> dict:
    """A lesson that passes every rule: hypothetical example with made-up numbers, facts only in `apply`."""
    return {
        "concept": "How an outbreak grows from case to case",
        "big_idea": "An outbreak grows when each sick person passes the illness to more than one other person, "
                    "so the numbers multiply instead of adding up.",
        "steps": [{"title": "Each case infects others", "text": words(30, 11), "cids": []},
                  {"title": "Count the multiplier", "text": words(30, 12), "cids": []},
                  {"title": "Above one, it grows", "text": words(30, 13), "cids": ["k4"]}],
        "example": {"setup": "Say 10 people are sick and each one passes it to 2 more people every week.",
                    "lines": [{"label": "Week 1", "calc": "10 × 2 = 20 new cases", "note": "each case infects two"},
                              {"label": "Week 2", "calc": "20 × 2 = 40 new cases", "note": "the new cases do the same"},
                              {"label": "Week 3", "calc": "40 × 2 = 80 new cases", "note": "it doubles each week"}],
                    "result": "Three weeks turn 10 cases into 80 new ones a week, which is why early action matters."},
        "apply": {"text": "The panel reported 1,250 cases and 68 deaths, which means the multiplier stayed above one "
                          "for weeks before officials acted.", "cids": ["k1"]},
        "practice": {"q": "If 5 people each infect 3 others every week, how many new cases come in week 2?",
                     "answer": "Week 1: 5 × 3 = 15. Week 2: 15 × 3 = 45 new cases."},
    }
