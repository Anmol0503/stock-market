"""Video side without rendering: frame HTML, chapters, and the parallel-render manifest merge."""
from __future__ import annotations

import json

from video import pipeline, reel, scenes


def test_frame_shows_the_chapter_and_views():
    sc = {"kind": "views", "show": "Two sides", "views": [{"who": "RBI", "view": "Rates <stay> on hold."},
                                                           {"who": "Banks", "view": "Cuts are due."}]}
    html = scenes.scene_html(sc, section="markets", headline="H", idx=3, total=9, meta="m", chapter="Different views")
    assert "class='chap'>Different views<" in html and "Rates &lt;stay&gt; on hold." in html
    assert html.count("<i class='on'>") == 4 and html.count("<i class") == 9          # chapter progress
    hook = scenes.scene_html({"kind": "hook", "show": "Why?"}, section="world", headline="H", idx=0, total=9,
                             meta="m", chapter="The question")
    assert hook.count("The question") == 1                                          # no duplicate kick
    old = scenes.scene_html({"kind": "hook", "show": "Why?"}, section="world", headline="H", idx=0, total=5, meta="m")
    assert "The question" in old and "The Briefing" in old                          # unchaptered reels unchanged


def test_chapter_labels_match_the_pipeline():
    from routine.briefing import config
    assert reel.CHAPTER_LABELS == config.CHAPTERS


def _setup(tmp_path, monkeypatch):
    pub = tmp_path / "pub"
    (pub / "videos").mkdir(parents=True)
    monkeypatch.setattr(pipeline, "PUB", pub)
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    ed = {"date": "2026-11-11", "published_at": "x",
          "stories": [{"id": f"s{i}", "reel": {"scenes": [{}]}, "reel_hash": f"h{i}"} for i in range(1, 12)]}
    (pub / "2026-11-11.json").write_text(json.dumps(ed))
    return pub


def test_plan_lists_only_reels_that_need_rendering(tmp_path, monkeypatch, capsys):
    pub = _setup(tmp_path, monkeypatch)
    (pub / "videos" / "2026-11-11.json").write_text(json.dumps({"items": [{"story": "s1", "reel_hash": "h1"},
                                                                          {"story": "s2", "reel_hash": "old"}]}))
    pipeline.main(["--date", "2026-11-11", "--plan"])
    ids = json.loads(capsys.readouterr().out)["ids"]
    assert "s1" not in ids and "s2" in ids and len(ids) == 10


def test_merge_builds_the_manifest_from_parallel_jobs(tmp_path, monkeypatch):
    pub = _setup(tmp_path, monkeypatch)
    meta = tmp_path / "meta"
    meta.mkdir()
    for i in (2, 10, 1):
        (meta / f"s{i}.json").write_text(json.dumps({
            "story": f"s{i}", "reel_hash": f"h{i}", "file": f"s{i}.mp4", "poster_file": f"s{i}.jpg",
            "duration_s": 200.0, "bytes": 1, "narrated": True, "chapters": [{"t": 0, "key": "hook", "label": "The question"}]}))
    (meta / "s3.json").write_text(json.dumps({"story": "s3", "failed": "RuntimeError: boom"}))
    (meta / "s4.json").write_text(json.dumps({"story": "s4", "reel_hash": "stale", "file": "x", "poster_file": "y",
                                              "duration_s": 1, "bytes": 1, "narrated": True}))
    assert pipeline.main(["--date", "2026-11-11", "--merge", str(meta), "--manifest"]) == 0
    man = json.loads((pub / "videos" / "2026-11-11.json").read_text())
    assert [i["story"] for i in man["items"]] == ["s1", "s2", "s10"]                 # numeric order, stale dropped
    assert man["items"][0]["chapters"][0]["label"] == "The question"
    assert man["items"][0]["src"] == "../media/2026-11-11/s1.mp4"
    assert man["failed"] == [{"story": "s3", "reason": "RuntimeError: boom"}]
