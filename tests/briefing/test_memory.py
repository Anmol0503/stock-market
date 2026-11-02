"""Thread memory and the calendar: code-maintained, so they must be exactly right."""
from __future__ import annotations

from routine.briefing import agenda, threads


def test_touch_counts_days_once_per_date_and_keeps_history():
    doc = {"threads": []}
    t = threads.touch(doc, tid=None, title="Spain train crash investigation", section="world", date="2026-11-01",
                      summary="first", timeline_text="crash", item_id="s1")
    assert t["id"].startswith("t-spain") and t["days"] == 1
    threads.touch(doc, tid=t["id"], title="x", section="world", date="2026-11-01", summary="first b",
                  timeline_text="again", item_id="s1")
    assert t["days"] == 1 and len(t["timeline"]) == 1          # same day, same item: no double count
    threads.touch(doc, tid=t["id"], title="x", section="world", date="2026-11-02", summary="second",
                  timeline_text="signal fault", item_id="s2", state=[{"fact": "Toll: 68"}])
    assert t["days"] == 2 and t["summary"] == "second" and t["last_state"] == [{"fact": "Toll: 68"}]
    assert threads.context(t)["recent"][-1] == "2026-11-02: signal fault"


def test_resolve_dormant_and_expire():
    doc = {"threads": []}
    a = threads.touch(doc, tid=None, title="Alpha story here", section="world", date="2026-10-20", summary="",
                      timeline_text="", item_id="s1")
    b = threads.touch(doc, tid=None, title="Beta story here", section="world", date="2026-11-02", summary="",
                      timeline_text="", item_id="s2")
    threads.apply_actions(doc, [{"thread_id": b["id"], "action": "resolve", "note": "ended"}], "2026-11-03")
    threads.expire(doc, "2026-11-03")
    assert a["status"] == "dormant" and b["status"] == "resolved" and b["resolution"] == "ended"


def test_bootstrap_seed():
    doc = threads.from_bootstrap({"threads": [{"id": "t-israel-coalition", "title": "Israel coalition talks",
                                               "section": "world", "summary": "s", "keywords": ["Israel", "coalition"],
                                               "last_state": [{"fact": "No majority", "date": "2026-11-01"}],
                                               "watch": [{"date": "2026-11-09", "what": "deadline"}]}]}, "2026-11-03")
    t = doc["threads"][0]
    assert t["id"] == "t-israel-coalition" and t["keywords"] == ["israel", "coalition"] and t["status"] == "active"


def test_calendar_due_covered_pending():
    cal = {"events": []}
    agenda.add(cal, date="2026-11-03", title="US midterm results", section="world", source="seed")
    agenda.add(cal, date="2026-11-03", title="Fed speech", section="markets", source="seed")
    agenda.add(cal, date="2026-11-09", title="Israel coalition deadline", section="world", source="story:s1")
    agenda.add(cal, date="not-a-date", title="bad", section="world", source="x")
    due = agenda.due(cal, "2026-11-02", "2026-11-03")
    assert len(due) == 2 and len(cal["events"]) == 3
    agenda.mark(cal, covered={due[0]["id"]: "2026-11-03/s1"}, due_ids=[e["id"] for e in due], date="2026-11-03")
    statuses = sorted(e["status"] for e in cal["events"] if e["date"] == "2026-11-03")
    assert statuses == ["covered", "pending"]
    assert [e["title"] for e in agenda.upcoming(cal, "2026-11-04")] == ["Israel coalition deadline"]


def test_same_day_rerun_does_not_count_twice():
    doc = {"threads": []}
    t = threads.touch(doc, tid=None, title="Cyclone Murasu landfall", section="india", date="2026-11-02",
                      summary="first", timeline_text="x", item_id="s4")
    threads.touch(doc, tid=t["id"], title="x", section="india", date="2026-11-03", summary="second",
                  timeline_text="y", item_id="s1")
    assert threads.before(t, "2026-11-03") == {"date": "2026-11-03", "days": 1, "summary": "first", "last_state": []}
    threads.touch(doc, tid=t["id"], title="x", section="india", date="2026-11-03", summary="second again",
                  timeline_text="y", item_id="s1")                     # a re-run on the same morning
    assert t["days"] == 2 and threads.before(t, "2026-11-03")["summary"] == "first"
    assert threads.context(t, "2026-11-03")["days"] == 1 and threads.context(t, "2026-11-03")["summary"] == "first"
