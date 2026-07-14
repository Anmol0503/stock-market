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
import threading
import urllib.parse
import urllib.request

import analyze_stock

ROOT = pathlib.Path(__file__).resolve().parent
DASH = ROOT / "dashboard"
LOGS = ROOT / "logs"
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
        "publish": _publish_status(),
        "live": _live_status(DASH / "reels.json"),
        "next_run_est": _next_run_est(),
        "cadence": {"guard_min": 110,
                    "note": "The decoded briefs regenerate <b>about every 2 hours</b> while the laptop is awake. "
                            "When it’s closed nothing updates — hit <b>Update now</b> to force a fresh pull."},
    }


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
        super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/run"):
            self.handle_run()
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
