#!/usr/bin/env python3
"""Local dashboard server with live stock lookup + an Update Center control panel.

Serves the dashboard/ folder AND exposes:
    /status                  — the Update Center: freshness, last-run, publish + live-site health
    /api/analyze?ticker=XYZ  — live in-depth technical analysis for ANY ticker on demand
    /api/refresh             — recompute the whole tracked universe (fresh prices/verdicts)
    /api/status              — JSON health snapshot the Update Center renders
    /api/run   (POST)        — trigger a full update (routine/run_daily.sh --force) in the background
    /api/log?n=200           — tail of logs/daily.log

Threaded, so a long refresh never blocks live lookups. A lock serializes index writes;
the refresh endpoint rejects concurrent duplicates instead of stacking runs.

Run:  python server.py        # then open http://localhost:8000  (Update Center: /status)
"""
from __future__ import annotations

import datetime as dt
import http.server
import json
import pathlib
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

import analyze_stock

ROOT = pathlib.Path(__file__).resolve().parent
DASH = ROOT / "dashboard"
LOGS = ROOT / "logs"
SOCIAL_OUT = ROOT / "social" / "out"
PORT = 8000

LIVE_REELS = "https://anmol-png.github.io/stock-market/dashboard/reels.json"

# Freshness thresholds (minutes). The pipeline runs ~every 2h while the laptop is awake,
# so "fresh" is a cycle + buffer; overnight (laptop closed) naturally drifts into "aging".
FRESH_MIN = 180      # <=3h  → green
AGING_MIN = 720      # <=12h → amber, older → red (stale)

INDEX_LOCK = threading.Lock()    # serializes save()+build_index() across threads
STOCKS_LOCK = threading.Lock()   # one /api/refresh at a time


# ---------------------------------------------------------------- helpers
def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=8).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _age_min(iso: str | None):
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    now = dt.datetime.now(t.tzinfo) if t.tzinfo else dt.datetime.now()
    return max(0, int((now - t).total_seconds() // 60))


def _state(age_min):
    if age_min is None:
        return "stale"
    if age_min <= FRESH_MIN:
        return "fresh"
    if age_min <= AGING_MIN:
        return "aging"
    return "stale"


def _brief_status(path: pathlib.Path) -> dict:
    try:
        d = json.loads(path.read_text())
        gen = d.get("generated_at")
        age = _age_min(gen)
        return {"date": d.get("date"), "generated_at": gen, "age_min": age, "state": _state(age)}
    except Exception:  # noqa: BLE001
        return {"date": None, "generated_at": None, "age_min": None, "state": "stale"}


def _run_from_log() -> dict:
    """Parse logs/daily.log for the most recent run's start/finish/result."""
    log = LOGS / "daily.log"
    out = {"active": False, "last_start": None, "last_finish": None, "result": "unknown"}
    # a lockfile (created by run_daily.sh) means a run is currently active
    lock = LOGS / "run.lock"
    if lock.exists():
        out["active"] = True
    if not log.exists():
        return out
    try:
        text = log.read_text(errors="replace")
    except Exception:  # noqa: BLE001
        return out
    starts = re.findall(r"=== daily run started (.+?) ===", text)
    finishes = re.findall(r"=== daily run finished (.+?) ===", text)
    if starts:
        out["last_start"] = starts[-1]
    if finishes:
        out["last_finish"] = finishes[-1]
    # a run is active if it started but hasn't logged a finish after that start
    if starts and (not finishes or text.rfind("started") > text.rfind("finished")):
        out["active"] = True
    # result of the last finished run: look at the tail after the last "started"
    tail = text[text.rfind("=== daily run started"):] if starts else text
    if "published to GitHub Pages" in tail:
        out["result"] = "published"
    elif "git publish failed" in tail or "WARN:" in tail:
        out["result"] = "failed"
    elif finishes:
        out["result"] = "published" if "nothing new to publish" in tail else "done"
    return out


def _publish_status() -> dict:
    head = _git("log", "-1", "--format=%h %s")
    # local main vs the last-known origin/main ref (no network — reflects the last fetch/push)
    behind = _git("rev-list", "--count", "origin/main..main") or "0"
    try:
        behind_n = int(behind)
    except ValueError:
        behind_n = 0
    return {"local_commit": head, "pushed": behind_n == 0, "behind_by": behind_n}


def _live_status(local_reels: pathlib.Path) -> dict:
    out = {"reachable": False, "date": None, "generated_at": None, "matches_local": False}
    try:
        req = urllib.request.Request(LIVE_REELS + "?_=" + str(int(dt.datetime.now().timestamp())),
                                     headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=4) as r:
            d = json.loads(r.read().decode())
        out["reachable"] = True
        out["date"] = d.get("date")
        out["generated_at"] = d.get("generated_at")
        try:
            local = json.loads(local_reels.read_text())
            out["matches_local"] = (d.get("date") == local.get("date")
                                    and d.get("generated_at") == local.get("generated_at"))
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    return out


def _progress() -> dict | None:
    """The live per-step tracker written by routine/progress.py during a run."""
    p = LOGS / "progress.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (ValueError, OSError):
        return None


def _next_run_est() -> str:
    """~110 min after the last brief was written (only fires while the laptop is awake)."""
    brief = ROOT / "output" / "brief-latest.json"
    if not brief.exists():
        return "at next laptop-open"
    try:
        mtime = dt.datetime.fromtimestamp(brief.stat().st_mtime)
    except Exception:  # noqa: BLE001
        return "—"
    nxt = mtime + dt.timedelta(minutes=110)
    if nxt < dt.datetime.now():
        return "due now (on next laptop-open)"
    return "≈ " + nxt.strftime("%H:%M") + " (if awake)"


def _age_min(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(iso)
    except ValueError:
        return None
    now = dt.datetime.now(t.tzinfo) if t.tzinfo else dt.datetime.now()
    return max(0, int((now - t).total_seconds() // 60))


def _topup_status() -> dict | None:
    """The automatic top-up record (dashboard/status.json) + derived freshness for the Update Center."""
    p = DASH / "status.json"
    try:
        s = json.loads(p.read_text())
    except (ValueError, OSError):
        return None
    cad = s.get("cadence_min", 30)
    chk_age = _age_min(s.get("last_check"))
    upd_age = _age_min(s.get("last_update"))
    # "active" = a check happened within ~1.5 cadence windows (else the laptop was asleep → paused)
    active = chk_age is not None and chk_age <= cad * 1.5 + 5
    nxt = s.get("next_update_est")
    try:
        nxt_clock = dt.datetime.fromisoformat(nxt).strftime("%H:%M") if nxt else None
    except ValueError:
        nxt_clock = None
    return {
        "cadence_min": cad, "active": active,
        "last_update_age": upd_age, "last_check_age": chk_age,
        "next_clock": nxt_clock, "counts": s.get("counts") or {},
        "last_added": s.get("last_added") or [], "last_kind": s.get("last_kind"),
    }


def build_status() -> dict:
    world = _brief_status(ROOT / "output" / "world-latest.json")
    markets = _brief_status(ROOT / "output" / "brief-latest.json")
    # overall = the worse of the two
    order = {"fresh": 0, "aging": 1, "stale": 2}
    worse = world if order[world["state"]] >= order[markets["state"]] else markets
    overall = {"state": worse["state"], "age_min": worse["age_min"],
               "label": f"Both briefs last updated {('%dm' % worse['age_min']) if worse['age_min'] is not None else '—'} ago"
                        if worse["age_min"] is not None else "No briefs found yet"}
    return {
        "now": dt.datetime.now().isoformat(timespec="seconds"),
        "briefs": {"world": world, "markets": markets, "overall": overall},
        "run": _run_from_log(),
        "progress": _progress(),
        "publish": _publish_status(),
        "live": _live_status(DASH / "reels.json"),
        "topup": _topup_status(),
        "next_run_est": _next_run_est(),
        "cadence": {"guard_min": 110,
                    "note": "A fresh, fully-decoded story is added <b>automatically every 30 minutes</b> "
                            "(one per region) while the laptop is awake. The full ~40-story rebuild is "
                            "<b>on-demand</b> — hit <b>Update now</b>. When the laptop’s closed, nothing updates."},
    }


def _slide_order(p: pathlib.Path):
    stem = p.stem
    if stem == "cover":
        return (0, 0)
    if stem == "cta":
        return (2, 0)
    try:
        return (1, int(stem.split("-")[-1]))
    except ValueError:
        return (1, 99)


def build_posts_page() -> str:
    """HTML for /posts — the latest generated carousels, ready to download + post by hand."""
    css = """
    :root{--bg:#0b0f17;--panel:#131a26;--line:#222c3b;--txt:#e7edf5;--dim:#8ea0b5;--accent:#5b9dff;
      --round:ui-rounded,'SF Pro Rounded',-apple-system,'Segoe UI',Roboto,sans-serif;--sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);font-family:var(--sans);padding:22px 16px 60px}
    .wrap{max-width:1000px;margin:0 auto} h1{font-family:var(--round);font-size:24px;margin:0 0 4px}
    .sub{color:var(--dim);font-size:13px;margin-bottom:18px} .sub b{color:var(--txt)}
    .car{border:1px solid var(--line);border-radius:16px;background:var(--panel);padding:16px;margin-bottom:20px}
    .car h2{font-family:var(--round);font-size:19px;margin:0 0 12px}
    .strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px}
    .strip a{flex:0 0 auto;display:block;border:1px solid var(--line);border-radius:10px;overflow:hidden}
    .strip img{display:block;width:150px;height:187px;object-fit:cover}
    textarea{width:100%;min-height:150px;background:#05080d;color:#c6d2e0;border:1px solid var(--line);
      border-radius:10px;padding:12px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px;line-height:1.5;margin-top:12px}
    button{font-family:var(--round);font-weight:800;font-size:14px;cursor:pointer;border:none;border-radius:10px;
      padding:10px 16px;color:#fff;background:linear-gradient(135deg,var(--accent),#3a6fd0);margin-top:10px}
    button.ghost{background:var(--panel);border:1px solid var(--line);color:var(--txt)}
    a.dl{color:var(--accent);text-decoration:none;font-size:12.5px;font-weight:700;margin-right:14px}
    .empty{color:var(--dim);text-align:center;padding:40px}
    .foot{color:var(--dim);font-size:12px;text-align:center;margin-top:12px}
    .reel{flex:0 0 auto;width:150px;border:1px solid var(--accent);border-radius:10px;overflow:hidden}
    .reel video{display:block;width:150px;height:187px;object-fit:cover;background:#05080d}
    .reel .cap{font-size:10px;font-weight:800;color:var(--accent);text-align:center;padding:3px}
    .brandcard{display:flex;align-items:center;gap:16px}
    .brandcard img{width:96px;height:96px;border-radius:50%;border:1px solid var(--line)}
    """
    dates = sorted([d for d in SOCIAL_OUT.glob("*") if d.is_dir()], reverse=True) if SOCIAL_OUT.exists() else []
    head = (f"<style>{css}</style><div class='wrap'><h1>📸 Today's posts</h1>"
            "<div class='sub'>Auto-generated carousels from the decoded feed. <b>Workflow:</b> download the "
            "images (or drag to Finder), copy the caption, and post to Instagram. "
            "<button onclick='regen(this)'>↻ Regenerate</button></div>")
    script = """<div class='foot'><a class="dl" href="/status">← Update Center</a> · <a class="dl" href="/">Dashboard</a></div>
    <script>
    function copyCap(id,btn){const t=document.getElementById(id);t.select();document.execCommand('copy');btn.textContent='Copied ✓';setTimeout(()=>btn.textContent='Copy caption',1500);}
    async function regen(btn){btn.disabled=true;btn.textContent='↻ Generating…';try{await fetch('/api/social/run',{method:'POST'});}catch(e){}
      setTimeout(()=>location.reload(),9000);}
    </script></div>"""
    if not dates:
        return head + "<div class='empty'>No posts generated yet.<br>Run <code>python make_social.py</code> or hit Regenerate.</div>" + script

    date = dates[0].name
    out = [head, f"<div class='sub' style='margin-top:-8px'>Latest: <b>{date}</b></div>"]
    any_region = False
    for region, label in (("global", "🌍 Global"), ("india", "🇮🇳 India")):
        rdir = dates[0] / region
        if not rdir.is_dir():
            continue
        any_region = True
        pngs = sorted(rdir.glob("*.png"), key=_slide_order)
        thumbs = "".join(
            f"<a href='/posts/file?f={date}/{region}/{p.name}' target='_blank'>"
            f"<img src='/posts/file?f={date}/{region}/{p.name}'></a>" for p in pngs)
        reel = rdir / "reel.mp4"
        reel_html = (
            f"<div class='reel'><video src='/posts/file?f={date}/{region}/reel.mp4' "
            f"muted loop autoplay playsinline></video><div class='cap'>🎬 REEL</div></div>"
            if reel.exists() else "")
        dls = "".join(
            f"<a class='dl' href='/posts/file?f={date}/{region}/{p.name}' download='{region}-{p.name}'>⬇ {p.stem}</a>"
            for p in pngs)
        if reel.exists():
            dls += (f"<a class='dl' href='/posts/file?f={date}/{region}/reel.mp4' "
                    f"download='{region}-reel.mp4'>🎬 reel.mp4</a>")
        cap_path = rdir / "caption.txt"
        cap = cap_path.read_text() if cap_path.exists() else ""
        cap = cap.replace("&", "&amp;").replace("<", "&lt;")   # safe inside <textarea>
        cid = f"cap-{region}"
        out.append(
            f"<div class='car'><h2>{label} — {len(pngs)} slides + reel</h2>"
            f"<div class='strip'>{reel_html}{thumbs}</div><div style='margin-top:10px'>{dls}</div>"
            f"<textarea id='{cid}' readonly>{cap}</textarea>"
            f"<button class='ghost' onclick=\"copyCap('{cid}',this)\">Copy caption</button></div>")
    prof = dates[0] / "brand" / "profile.png"
    if prof.exists():
        out.append(
            f"<div class='car brandcard'><img src='/posts/file?f={date}/brand/profile.png'>"
            f"<div><h2 style='margin:0'>Brand kit</h2>"
            f"<div class='sub' style='margin:2px 0 6px'>Your Instagram profile picture.</div>"
            f"<a class='dl' href='/posts/file?f={date}/brand/profile.png' download='profile.png'>⬇ profile.png</a>"
            f"<span class='sub'>Full walkthrough → <b>INSTAGRAM_SETUP.md</b> in the repo root.</span></div></div>")
    if not any_region:
        out.append("<div class='empty'>No carousels for the latest date yet.</div>")
    return "".join(out) + script


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASH), **kwargs)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/status"):
            self.serve_panel()
            return
        if self.path.startswith("/api/status"):
            self._send_json(build_status())
            return
        if self.path.startswith("/api/log"):
            self.handle_log()
            return
        if self.path.startswith("/api/analyze"):
            self.handle_analyze()
            return
        if self.path.startswith("/api/refresh"):
            self.handle_refresh()
            return
        if self.path.startswith("/posts/file"):
            self.serve_social_file()
            return
        if self.path.startswith("/posts"):
            self.serve_posts()
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/run"):
            self.handle_run()
            return
        if self.path.startswith("/api/social/run"):
            self.handle_social_run()
            return
        self.send_error(404, "not found")

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_panel(self):
        page = ROOT / "routine" / "status_panel.html"
        if not page.exists():
            self.send_error(404, "status panel missing")
            return
        body = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_log(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        n = int((params.get("n") or ["200"])[0])
        log = LOGS / "daily.log"
        text = log.read_text(errors="replace") if log.exists() else "(no log yet — no run has happened on this Mac)"
        tail = "\n".join(text.splitlines()[-n:])
        body = tail.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_run(self):
        """Kick off routine/run_daily.sh --force detached; the lockfile stops overlaps."""
        if (LOGS / "run.lock").exists():
            self._send_json({"started": False, "busy": True})
            return
        try:
            LOGS.mkdir(exist_ok=True)
            script = ROOT / "routine" / "run_daily.sh"
            logf = open(LOGS / "daily.log", "a")  # noqa: SIM115 — child keeps it open
            subprocess.Popen(["/bin/bash", str(script), "--force"], cwd=ROOT,
                             stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
            self._send_json({"started": True})
        except Exception as exc:  # noqa: BLE001
            self._send_json({"started": False, "error": str(exc)})

    def handle_social_run(self):
        """Regenerate today's Instagram carousels (make_social.py) in the background."""
        try:
            logf = open(LOGS / "social.log", "a")  # noqa: SIM115
            subprocess.Popen([sys.executable, str(ROOT / "make_social.py")], cwd=ROOT,
                             stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
            self._send_json({"started": True})
        except Exception as exc:  # noqa: BLE001
            self._send_json({"started": False, "error": str(exc)})

    def serve_social_file(self):
        """Serve a generated post asset (PNG / caption) from social/out — path-traversal guarded."""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rel = (params.get("f") or [""])[0]
        target = (SOCIAL_OUT / rel).resolve()
        if not str(target).startswith(str(SOCIAL_OUT.resolve())) or not target.is_file():
            self.send_error(404, "not found")
            return
        ctype = {".png": "image/png", ".mp4": "video/mp4"}.get(
            target.suffix, "text/plain; charset=utf-8")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_posts(self):
        """A local gallery of the latest generated carousels — preview, download, copy caption."""
        body = build_posts_page().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_analyze(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ticker = (params.get("ticker") or [""])[0].strip()
        if not ticker:
            self.send_error(400, "ticker required")
            return
        try:
            res = analyze_stock.analyze(ticker)
            if not res:
                self.send_error(404, "no data for ticker")
                return
            with INDEX_LOCK:
                analyze_stock.save(res)
                analyze_stock.build_index()
            self._send_json(res)
        except Exception as exc:  # noqa: BLE001
            self.send_error(500, str(exc))

    def handle_refresh(self):
        """Recompute live technical analysis for every tracked ticker (fresh prices/verdicts)."""
        if not STOCKS_LOCK.acquire(blocking=False):
            self._send_json({"ok": False, "busy": True})
            return
        try:
            n = 0
            for ticker, name in analyze_stock._all_tickers():
                res = analyze_stock.analyze(ticker, name)
                if res:
                    with INDEX_LOCK:
                        analyze_stock.save(res)
                    n += 1
            with INDEX_LOCK:
                analyze_stock.build_index()
            self._send_json({"ok": True, "refreshed": n})
        except Exception as exc:  # noqa: BLE001
            self.send_error(500, str(exc))
        finally:
            STOCKS_LOCK.release()

    def log_message(self, *args):  # quiet
        pass


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("", PORT), Handler)
    server.daemon_threads = True
    print(f"Dashboard on http://localhost:{PORT}   ·   Update Center on http://localhost:{PORT}/status  (Ctrl-C to stop)")
    server.serve_forever()
