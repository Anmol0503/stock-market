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


# ---------------------------------------------------------------- photos (network mocked)
from video import images  # noqa: E402


def _meta(lic, artist="<a href='x'>Jane &amp; Co</a>", nonfree=None):
    m = {"LicenseShortName": {"value": lic}, "Artist": {"value": artist}}
    if nonfree is not None:
        m["NonFree"] = {"value": nonfree}
    return m


def test_only_clearly_free_licences_are_used():
    for ok in ("CC BY-SA 4.0", "CC BY 2.0", "CC0", "Public domain", "PD-USGov", "GODL-India", "cc-by-sa-3.0"):
        assert images.licence_ok(_meta(ok)), ok
    for bad in ("Fair use", "Non-free media", "All rights reserved", "", "CC BY-NC 4.0", "CC BY-ND 2.0"):
        assert not images.licence_ok(_meta(bad)), bad
    assert not images.licence_ok(_meta("CC BY-SA 4.0", nonfree="true"))
    assert images.credit(_meta("CC BY 4.0")) == "Photo: Jane & Co, CC BY 4.0, Wikimedia Commons"


class _Wiki:
    """A fake Wikipedia API: lead images, article image lists and file info."""

    def __init__(self, pages, files, parsed=None, fail=False):
        self.pages, self.files, self.parsed, self.fail, self.calls = pages, files, parsed or {}, fail, []

    def fetch(self, params):
        self.calls.append(params)
        if self.fail:
            raise OSError("network down")
        if params.get("action") == "parse":
            return {"parse": {"images": self.parsed.get(params["page"], [])}}
        titles = params["titles"].split("|")
        if titles[0].startswith("File:"):
            return {"query": {"pages": [{"title": t, "imageinfo": [self.files[t[5:]]]} for t in titles
                                        if t[5:] in self.files]}}
        return {"query": {"pages": [self.pages.get(titles[0], {"title": titles[0], "missing": True})]}}

    def download(self, url):
        return b"x" * 6000


def _info(lic="CC BY-SA 4.0", w=2000, h=1300, mime="image/jpeg"):
    return {"mime": mime, "width": w, "height": h, "thumburl": "https://upload.wikimedia.org/a.jpg",
            "thumbwidth": 1600, "thumbheight": int(1600 * h / w), "extmetadata": _meta(lic)}


def test_resolver_uses_the_lead_photo_and_caches(tmp_path):
    w = _Wiki({"Dhaka": {"title": "Dhaka", "pageimage": "Dhaka_skyline.jpg"}}, {"Dhaka_skyline.jpg": _info()})
    r = images.Resolver(tmp_path, fetch=w.fetch, download=w.download)
    ph = r.resolve("Dhaka")
    assert ph and ph.path.exists() and ph.width == 1600 and "CC BY-SA 4.0" in ph.credit
    n = len(w.calls)
    assert r.resolve("Dhaka") is ph and len(w.calls) == n                   # cached per title


def test_resolver_skips_logos_and_non_free_then_falls_back_to_article_photos(tmp_path):
    w = _Wiki({"Reserve Bank of India": {"title": "Reserve Bank of India", "pageimage": "RBI_seal.svg"}},
              {"Fair_use_photo.jpg": _info("Fair use"), "RBI_logo_big.jpg": _info(),
               "RBI_tower.jpg": _info("CC BY 4.0"), "Tiny.jpg": _info(w=300, h=200)},
              parsed={"Reserve Bank of India": ["RBI_seal.svg", "Fair_use_photo.jpg", "RBI_logo_big.jpg", "Tiny.jpg",
                                                "RBI_tower.jpg"]})
    ph = images.Resolver(tmp_path, fetch=w.fetch, download=w.download).resolve("Reserve Bank of India")
    assert ph and ph.path.name.startswith("RBI_tower") and "CC BY 4.0" in ph.credit


def test_resolver_never_raises(tmp_path):
    r = images.Resolver(tmp_path, fetch=_Wiki({}, {}, fail=True).fetch)
    assert r.resolve("Anything") is None and r.resolve("") is None
    dis = _Wiki({"Mercury": {"title": "Mercury", "pageprops": {"disambiguation": ""}, "pageimage": "M.jpg"}}, {})
    assert images.Resolver(tmp_path, fetch=dis.fetch).resolve("Mercury") is None
    assert images.Resolver(tmp_path, fetch=_Wiki({}, {}).fetch).resolve("No such page") is None


def test_scenes_without_a_photo_borrow_the_last_one_blurred():
    class R:
        def resolve(self, title, min_width=400):
            return {"Dhaka": "P1", "Sheikh Hasina": "P2"}.get(title)
    sc = [{"image": ""}, {"image": "Dhaka"}, {"image": ""}, {"image": "Sheikh Hasina"}, {"image": "Nowhere"},
          {"kind": "players", "players": [{"name": "Sheikh Hasina"}, {"name": "Nobody"}]}]
    photos, reused, av = reel._photos(sc, R())
    assert photos == ["P1", "P1", "P1", "P2", "P2", "P2"]
    assert reused == [True, False, True, False, True, True]
    assert av == {"Sheikh Hasina": "P2"}


# ---------------------------------------------------------------- layers and odd input
class _P:
    def __init__(self, w=1600):
        self.path, self.width, self.credit = "/tmp/x.jpg", w, "Photo: A <b>, CC BY 4.0, Wikimedia Commons"


def test_layers_passes_and_reveal_times():
    sc = {"kind": "steps", "show": "Example", "steps": [{"label": "a", "calc": "1+1=2"}, {"label": "b", "calc": "2+2=4"},
                                                       {"label": "c", "calc": "4+4=8"}]}
    page = scenes.scene_html(sc, section="india", headline="H", idx=0, total=3, meta="m", chapter="Worked example",
                             photo=_P(), reused=True)
    assert scenes.layer_count(page) == 4                                     # kicker + 3 rows
    assert "Photo: A &lt;b&gt;" in page and "ph deep" in page               # credit escaped; borrowed photo blurred
    assert ".ui,.vis,.ly{visibility:hidden" in scenes.with_pass(page, "bg")  # nothing drawn into the panning layer
    assert ".ly2{visibility:visible" in scenes.with_pass(page, "2")
    t = scenes.reveal_times(sc, 4, 20.0)
    assert t[0] < t[1] < t[2] < t[3] < 20 and t[3] > 8                       # rows arrive with the narration
    assert scenes.reveal_times({"kind": "kinetic"}, 2, 10.0) == [0.12, 0.42]


def test_every_kind_survives_odd_input():
    odd = [{"kind": k} for k in ("hook", "kinetic", "outro", "big_number", "map", "bar", "line", "timeline", "players",
                                 "steps", "views", "mystery", None)]
    odd += [{"kind": "timeline", "timeline": [{"when": None, "what": "<script>"}] * 9},
            {"kind": "bar", "chart": {"points": [{"label": None, "value": -5}, {"label": "b", "value": "x"},
                                                 {"label": "c", "value": 7}]}},
            {"kind": "players", "players": [{"name": None, "role": None}]},
            {"kind": "steps", "steps": [{"label": None, "calc": None}]},
            {"kind": "big_number", "number": {"value": "₹45,960 crore", "label": None}},
            {"kind": "hook", "show": "It's 50% <b>bigger</b>"}]
    for sc in odd:
        for photo in (None, _P(), _P(500)):
            page = scenes.scene_html(sc, section="nope", headline=None, idx=0, total=1, meta="", photo=photo)
            assert "<script>" not in page and "<b>bigger" not in page
    tl = scenes.scene_html(odd[-6], section="world", headline="H", idx=0, total=1, meta="")
    assert scenes.layer_count(tl) == 9                                       # kicker + at most 8 rows
    assert "<mark>50%</mark>" in scenes.scene_html(odd[-1], section="world", headline="", idx=0, total=1, meta="")
