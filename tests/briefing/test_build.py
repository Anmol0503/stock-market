"""The quality rules: every rule violation must produce a specific problem, and a good story must pass."""
from __future__ import annotations

import copy

from routine.briefing import build

from .conftest import NOW, iso, research, story

WINDOW = {"start": (NOW.replace(hour=3)).isoformat(), "end": NOW.isoformat()}
SLOT = {"id": "s1", "section": "world", "india_angle": "secondary", "contested": False}


def problems(s, r=None, slot=SLOT):
    return build.story_problems(s, r or research(), slot=slot, year=2026)


def test_good_story_passes():
    assert problems(story()) == []


def test_relative_dates_are_rejected_but_india_today_is_fine():
    s = story()
    s["what_happened"]["text"] = s["what_happened"]["text"].replace("The panel", "Today the panel", 1)
    assert any("relative date" in p["issue"] for p in problems(s))
    s2 = story()
    s2["for_you"]["text"] += " India Today reported it first."
    assert not any("relative date" in p["issue"] for p in problems(s2))


def test_unknown_claim_ids_and_empty_fact_blocks():
    s = story()
    s["so_far"]["cids"] = ["k99"]
    assert any("unknown claim k99" in p["issue"] for p in problems(s))
    s["what_happened"] = {"text": "", "cids": []}
    assert any(p["where"] == "what_happened" and p["severity"] == "drop" for p in problems(s))


def test_numbers_must_come_from_the_claims():
    s = story()
    s["what_happened"]["text"] += " Officials said 4,700 people were moved and 9,999 homes and 8,888 shops shut."
    ps = [p for p in problems(s) if p["where"] == "facts:numbers"]
    assert ps and ps[0]["severity"] == "drop" and "4700" in ps[0]["issue"]


def test_word_ranges_enforced():
    s = story()
    s["dek"] = "Too short."
    assert any(p["where"] == "dek" for p in problems(s))


def test_contested_story_needs_two_named_views():
    s = story(contested=False)
    assert any(p["where"] == "views" for p in problems(s, slot={**SLOT, "contested": True}))
    assert not any(p["where"] == "views" for p in problems(story(contested=True), slot={**SLOT, "contested": True}))


def test_reel_rules():
    s = story()
    s["reel"][1]["say"] = "Prices rose 5% to ₹100 " + s["reel"][1]["say"]
    s["reel"][0]["kind"] = "kinetic"
    issues = " ".join(p["issue"] for p in problems(s))
    assert "symbols" in issues and "hook" in issues


def test_public_story_sources_numbered_and_confidence():
    st, notes, reel_ok = build.public_story("s1", SLOT, story(), research(), thread=None, window=WINDOW, now=NOW,
                                            markets=None)
    assert st and reel_ok and st["reel_hash"]
    assert [x["n"] for x in st["sources"]] == list(range(1, len(st["sources"]) + 1))
    assert st["blocks"]["so_far"]["src"] == [1, 2]
    assert all(len(x["excerpt"]) <= 201 for x in st["sources"])
    assert st["confidence"]["level"] in ("high", "medium")


def test_public_story_rejects_stale_or_thin_sourcing():
    r = research(fresh_hours=200)                      # every source a week old
    st, notes, _ = build.public_story("s1", SLOT, story(), r, thread=None, window=WINDOW, now=NOW, markets=None)
    assert st is None and any("no source published inside the news window" in n for n in notes)
    r2 = research()
    for c in r2["claims"]:
        c["url"] = "https://reuters.com/" + c["cid"]       # one site only
    st2, notes2, _ = build.public_story("s1", SLOT, story(), r2, thread=None, window=WINDOW, now=NOW, markets=None)
    assert st2 is None and any("sites" in n for n in notes2)


def test_demote_needs_a_fresh_source():
    assert build.demote("s1", "world", story(), research(), WINDOW)["section"] == "world"
    assert build.demote("s1", "world", story(), research(fresh_hours=200), WINDOW) is None


def test_brief_rules():
    item = {"id": "b-world-1", "section": "world", "thread": None}
    facts = [{"text": "x", "pub": "Reuters", "url": "https://reuters.com/a", "published": iso(2), "excerpt": "x"}]
    b = {"item_id": "b-world-1", "headline": "A clear headline about the event", "text": " ".join(["word"] * 60),
         "background": "Some context.", "why": "It matters.", "source_urls": ["https://reuters.com/a"], "status": "new",
         "thread_summary": ""}
    ok, err = build.public_brief(item, b, facts, WINDOW)
    assert ok and not err
    stale = [{**facts[0], "published": iso(300)}]
    assert build.public_brief(item, b, stale, WINDOW)[0] is None
    rel = copy.deepcopy(b)
    rel["text"] = "Yesterday " + rel["text"]
    assert "relative date" in build.public_brief(item, rel, facts, WINDOW)[1]


def test_privacy_check():
    assert build.privacy_ok({"a": "write to someone@example.com"})
    assert build.privacy_ok({"a": "/Users/me/file"})
    assert not build.privacy_ok({"a": "clean text"})


def test_a_slightly_long_reel_keeps_its_video():
    s = story()
    for sc in s["reel"][1:4]:                                                       # ~145 -> ~235 words in all
        sc["say"] = sc["say"] + " " + " ".join(["more"] * 15)
    st, notes, reel_ok = build.public_story("s1", SLOT, s, research(), thread=None, window=WINDOW, now=NOW,
                                            markets=None)
    assert reel_ok and st["reel"] and not any("reel script failed" in n for n in notes)


def test_a_misleading_reel_loses_its_video_but_not_the_story():
    s = story()
    s["reel"][2]["kind"], s["reel"][2]["number_value"] = "big_number", "9,999 deaths"   # not in the claims
    st, notes, reel_ok = build.public_story("s1", SLOT, s, research(), thread=None, window=WINDOW, now=NOW,
                                            markets=None)
    assert st and not reel_ok and st["reel"] is None


def test_good_story_has_a_published_lesson_and_takeaways():
    s = story()
    s["reel"][2].update(kind="steps", steps=[{"label": "Week 1", "calc": "10 × 2 = 20"}])
    st, _, _ = build.public_story("s1", SLOT, s, research(), thread=None, window=WINDOW, now=NOW, markets=None)
    ls = st["blocks"]["lesson"]
    assert ls["concept"] and len(ls["steps"]) == 3 and len(ls["example"]["lines"]) == 3
    assert ls["apply"]["src"] and ls["practice"]["answer"] and len(st["takeaways"]) == 3
    assert st["reel"]["scenes"][2]["steps"] == [{"label": "Week 1", "calc": "10 × 2 = 20"}]


def test_lesson_rules():
    s = story()
    s["lesson"] = {}
    assert any(p["where"] == "lesson" and "missing" in p["issue"] for p in problems(s))
    s = story()
    s["lesson"]["example"]["setup"] = "The panel counted 10 people who each infected 2 more every week."
    assert any(p["where"] == "lesson.example" and "Say" in p["issue"] and not p.get("soft") for p in problems(s))
    s = story()
    s["lesson"]["apply"]["text"] += " Officials moved 4,700 people."          # a real-world number not in claims
    assert any(p["where"] == "lesson.apply" and "4700" in p["issue"] for p in problems(s))
    # made-up numbers in the worked example are fine, and lesson problems never drop the story
    assert not any(p["where"].startswith("lesson") for p in problems(story()))
    s = story()
    s["lesson"]["steps"] = s["lesson"]["steps"][:1]
    assert all(p["severity"] == "fix" for p in problems(s) if p["where"].startswith("lesson"))


def test_a_wrong_lesson_is_removed_but_a_long_one_is_kept():
    from routine.briefing import stages
    s = story()
    kept = stages._strip_optional(s, [{"where": "lesson", "issue": "600 words", "severity": "fix", "soft": True}])
    assert kept["lesson"]["concept"]
    gone = stages._strip_optional(s, [{"where": "lesson.example", "issue": "10 × 2 is not 30", "severity": "fix"}])
    assert gone["lesson"] == {} and gone["takeaways"] == []
    st, _, _ = build.public_story("s1", SLOT, gone, research(), thread=None, window=WINDOW, now=NOW, markets=None)
    assert st and "lesson" not in st["blocks"] and st["takeaways"] == []


def test_checker_cannot_drop_a_story_over_its_lesson():
    from routine.briefing import stages
    chk = {"ok": False, "problems": [{"where": "lesson.example", "issue": "bad sums", "severity": "drop"},
                                     {"where": "what_happened", "issue": "unsupported", "severity": "drop"}]}
    stages._lesson_never_drops(chk)
    assert [p["severity"] for p in chk["problems"]] == ["fix", "drop"]
