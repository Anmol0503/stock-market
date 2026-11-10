"""Render the reels for one edition, optionally upload them to a GitHub Release, and write the manifest.

  python -m video.pipeline --date 2026-11-03                    # render into video/out/<date>/
  python -m video.pipeline --date latest --upload --manifest    # what the GitHub Actions job runs

The manifest (dashboard/briefing/videos/<date>.json) is what the app reads. A reel is listed only with the
reel_hash of the script it was rendered from, so a re-published edition never shows a stale video. MP4s
never go into git: they live in the release `briefing-<date>`, and the Pages deploy copies the last few days
next to the app so phones play them from the same site.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

from . import reel

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = ROOT / "dashboard" / "briefing"
OUT = ROOT / "video" / "out"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
REPO = os.environ.get("GITHUB_REPOSITORY", "Anmol0503/stock-market")


def latest_date() -> str:
    idx = json.loads((PUB / "index.json").read_text())
    return idx["latest"]


def gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def upload(date: str, files: list[pathlib.Path]) -> None:
    tag = f"briefing-{date}"
    if gh("release", "view", tag, "-R", REPO).returncode != 0:
        r = gh("release", "create", tag, "-R", REPO, "--prerelease", "--title", f"Briefing reels {date}",
               "--notes", f"Narrated reels for the {date} Morning Briefing (generated).")
        if r.returncode != 0 and "already exists" not in r.stderr:
            raise RuntimeError(f"release create failed: {r.stderr[-300:]}")
    r = gh("release", "upload", tag, "-R", REPO, "--clobber", *map(str, files))
    if r.returncode != 0:
        raise RuntimeError(f"release upload failed: {r.stderr[-300:]}")


def item(date: str, m: dict) -> dict:
    return {"story": m["story"], "reel_hash": m["reel_hash"],
            "src": f"../media/{date}/{m['file']}",
            "fallback_src": f"https://github.com/{REPO}/releases/download/briefing-{date}/{m['file']}",
            "poster": f"../media/{date}/{m['poster_file']}",
            "duration_s": m["duration_s"], "bytes": m["bytes"], "narrated": m["narrated"],
            "chapters": m.get("chapters") or []}


def main(argv=None) -> int:
    """Modes:
      (default)   render the reels that need it (all, or --only), optionally --upload and --manifest;
      --plan      print the ids that need rendering as a JSON list (the Actions matrix);
      --meta-out  also write each rendered reel's metadata (or failure) to DIR/<id>.json;
      --merge DIR build the manifest from the metadata files written by parallel render jobs.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="latest")
    ap.add_argument("--edition", help="edition JSON path (default: dashboard/briefing/<date>.json)")
    ap.add_argument("--only", help="comma-separated story ids")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-render even if the manifest has this reel_hash")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--meta-out")
    ap.add_argument("--merge")
    a = ap.parse_args(argv)
    date = latest_date() if a.date == "latest" else a.date
    ed_path = pathlib.Path(a.edition) if a.edition else PUB / f"{date}.json"
    ed = json.loads(ed_path.read_text())
    man_path = PUB / "videos" / f"{date}.json"
    old = json.loads(man_path.read_text()) if man_path.exists() else {"items": []}
    have = {(i["story"], i.get("reel_hash")) for i in old.get("items") or []}
    only = set(a.only.split(",")) if a.only else None
    out_dir = OUT / date
    label = dt.date.fromisoformat(date).strftime("%-d %b %Y")
    todo = [s for s in ed.get("stories") or []
            if s.get("reel") and (not only or s["id"] in only) and ((s["id"], s.get("reel_hash")) not in have or a.force)]

    if a.plan:
        print(json.dumps({"date": date, "ids": [s["id"] for s in todo]}))
        return 0

    items = [i for i in old.get("items") or []
             if any(s["id"] == i["story"] and s.get("reel_hash") == i.get("reel_hash") for s in ed.get("stories") or [])]
    failed, made = [], []
    if a.merge:
        for f in sorted(pathlib.Path(a.merge).glob("*.json")):
            m = json.loads(f.read_text())
            if m.get("failed"):
                failed.append({"story": m["story"], "reason": m["failed"]})
            elif any(s["id"] == m["story"] and s.get("reel_hash") == m["reel_hash"] for s in ed.get("stories") or []):
                made.append(m)
    else:
        for s in todo:
            try:
                meta = reel.build(s, out_dir, date_label=label)
                made.append(meta)
                print(f"{s['id']}: {meta['file']} {meta['duration_s']} s, {meta['bytes'] // 1024} KB, "
                      f"{len(meta.get('chapters') or [])} chapters, "
                      f"{'narrated' if meta['narrated'] else 'SILENT (voice failed)'}")
            except Exception as e:  # noqa: BLE001 - one reel failing must not stop the others
                failed.append({"story": s["id"], "reason": f"{type(e).__name__}: {e}"[:200]})
                print(f"{s['id']}: FAILED {e}", file=sys.stderr)
        if a.upload and made:
            upload(date, [out_dir / m["file"] for m in made] + [out_dir / m["poster_file"] for m in made])
        if a.meta_out:
            d = pathlib.Path(a.meta_out)
            d.mkdir(parents=True, exist_ok=True)
            for m in made:
                (d / f"{m['story']}.json").write_text(json.dumps(m))
            for f in failed:
                (d / f"{f['story']}.json").write_text(json.dumps({"story": f["story"], "failed": f["reason"]}))
    for m in made:
        items = [i for i in items if i["story"] != m["story"]]
        items.append(item(date, m))
    if a.manifest:
        man_path.parent.mkdir(parents=True, exist_ok=True)
        man = {"date": date, "edition_published_at": ed.get("published_at"),
               "generated_at": dt.datetime.now(IST).isoformat(timespec="minutes"),
               "run_url": os.environ.get("RUN_URL"),
               "items": sorted(items, key=lambda i: int(i["story"][1:]) if i["story"][1:].isdigit() else 99),
               "failed": failed}
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=1))
        print(f"manifest: {len(items)} reels, {len(failed)} failed -> {man_path.relative_to(ROOT)}")
    return 1 if failed and not made and not items else 0      # fail the job only if nothing is playable


if __name__ == "__main__":
    sys.exit(main())
