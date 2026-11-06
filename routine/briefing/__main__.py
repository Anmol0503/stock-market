"""The Morning Briefing command line.

  python3 -m routine.briefing next              # cloud routine: start/continue the run; prints ONE line
  python3 -m routine.briefing run [--fresh]     # run the whole pipeline in the foreground (Mac / Actions)
  python3 -m routine.briefing publish [--branch B] [--dry-run]
  python3 -m routine.briefing status | summary
  python3 -m routine.briefing gather            # sources only (debug): writes raw.json + leads.json
  python3 -m routine.briefing hinglish [--publish]   # re-voice a published edition's English reels as Hinglish

Options: --date YYYY-MM-DD (default: today in IST), --force (overwrite a complete edition with a partial one).
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time

from . import config


def _state(date: str) -> dict:
    try:
        return json.loads((config.day_dir(date) / "state.json").read_text())
    except (OSError, ValueError):
        return {}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def cmd_run(args) -> int:
    from . import stages
    from .engine import ClaudeEngine
    d = config.day_dir(args.date)
    if args.fresh and d.exists():
        shutil.rmtree(d)
        d = config.day_dir(args.date)
    state = asyncio.run(stages.run(args.date, ClaudeEngine(), force=args.force))
    print(f"{state['status'].upper()} {state.get('edition_status', '')} {json.dumps(state.get('counts') or {})}")
    if args.publish:
        from . import publish
        print(publish.publish(args.date))
    return 0 if state["status"] == "done" else 1


def cmd_next(args) -> int:
    """Start the runner in the background if it isn't running, then wait up to ~8.5 minutes and report."""
    d = config.day_dir(args.date)
    st = _state(args.date)
    if st.get("status") in ("done", "failed") and not args.force:
        print(f"{'DONE' if st['status'] == 'done' else 'FAILED'} {st.get('edition_status') or st.get('notes', [''])[-1][:120]}")
        return 0
    pidf = d / "runner.pid"
    pid = int(pidf.read_text()) if pidf.exists() else 0
    if not pid or not _alive(pid):
        log = open(d / "runner.log", "a")
        cmd = [sys.executable, "-m", "routine.briefing", "run", "--date", args.date] + (["--force"] if args.force else [])
        p = subprocess.Popen(cmd, cwd=config.ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        pidf.write_text(str(p.pid))
        pid = p.pid
    t_end = time.monotonic() + config.NEXT_TICK_SECONDS
    while time.monotonic() < t_end:
        st = _state(args.date)
        if st.get("status") in ("done", "failed") and not _alive(pid):
            break
        if not _alive(pid):
            break
        time.sleep(10)
    st = _state(args.date)
    if st.get("status") == "done":
        print(f"DONE {st.get('edition_status', '')}")
    elif st.get("status") == "failed" or not _alive(pid):
        note = (st.get("notes") or ["runner stopped"])[-1]
        print(f"FAILED {note[:160]}")
    else:
        pr = st.get("progress") or {}
        print(f"NEXT {st.get('stage', 'start')} stories {pr.get('stories_done', 0)}/{pr.get('stories_total', '?')}")
    return 0


def cmd_status(args) -> int:
    print(json.dumps(_state(args.date), indent=1)[:4000])
    return 0


def cmd_summary(args) -> int:
    st = _state(args.date)
    q = {}
    try:
        q = json.loads((config.PUB / "quality" / f"{args.date}.json").read_text())
    except (OSError, ValueError):
        pass
    print(f"Morning Briefing {args.date}: run {st.get('status')} · edition {q.get('status')}")
    print(f"counts: {json.dumps(q.get('counts') or {})}")
    print(f"sources: {(q.get('sources') or {}).get('ok')}/{(q.get('sources') or {}).get('total')} ok")
    u = q.get("usage") or st.get("usage") or {}
    print(f"model calls: {u.get('calls')} (failures {u.get('failures')}), ≈${u.get('cost_usd')} API-equivalent")
    print(f"timings (s): {json.dumps(st.get('timings') or {})}")
    for n in (q.get("notes") or st.get("notes") or [])[-15:]:
        print(f"  · {n}")
    return 0


def cmd_publish(args) -> int:
    from . import publish
    print(publish.publish(args.date, branch=args.branch, dry_run=args.dry_run))
    return 0


def cmd_gather(args) -> int:
    from . import cluster, gather, stages, threads
    from .engine import FakeEngine
    r = stages.Run(args.date, FakeEngine({}))
    raw = gather.run(args.date, r.window())
    leads = cluster.build(raw, threads.active(threads.load()))
    print(gather.health_summary(raw), "·", json.dumps(leads["stats"]))
    return 0


def cmd_hinglish(args) -> int:
    """Re-voice an already published edition's English reels in Hinglish (new reel_hash -> Actions re-renders)."""
    import hashlib
    from . import hinglish
    from .engine import ClaudeEngine, EngineError
    path = config.PUB / f"{args.date}.json"
    ed = json.loads(path.read_text())
    eng, year, changed = ClaudeEngine(), int(args.date[:4]), 0

    async def one(s):
        reel = s.get("reel") or {}
        scenes = reel.get("scenes") or []
        if not scenes or all(sc.get("speak") for sc in scenes):
            return f"{s['id']}: nothing to do"

        async def ask(system, prompt, schema):
            return await eng.ask("hinglish", system, prompt, schema, label=f"hinglish-{s['id']}")
        try:
            hi, left = await hinglish.adapt(ask, s, scenes, hinglish.story_corpus(s), year)
        except EngineError as e:
            hi, left = None, [str(e)]
        if hi is None:
            return f"{s['id']}: stays English ({left[0] if left else 'no output'})"
        new = [{k: v for k, v in sc.items() if k != "say_en"} for sc in hinglish.apply(scenes, hi)]
        s["reel"] = {"voice": config.REEL_VOICE_HI, "scenes": new}
        s["reel_hash"] = hashlib.sha1(json.dumps(s["reel"], sort_keys=True).encode()).hexdigest()[:12]
        return f"{s['id']}: hinglish"

    async def all_():
        return await asyncio.gather(*(one(s) for s in ed.get("stories") or []))
    for line in asyncio.run(all_()):
        print(line)
        changed += line.endswith(": hinglish")
    if changed:
        path.write_text(json.dumps(ed, ensure_ascii=False, indent=1))
        if args.publish:
            from . import publish
            print(publish.publish(args.date))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m routine.briefing")
    ap.add_argument("command", choices=["next", "run", "status", "summary", "publish", "gather", "hinglish"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--fresh", action="store_true", help="discard today's working files first")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--publish", action="store_true", help="(run) publish when done")
    ap.add_argument("--branch", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    args.date = args.date or config.edition_date()
    signal.signal(signal.SIGPIPE, signal.SIG_DFL) if hasattr(signal, "SIGPIPE") else None
    return {"next": cmd_next, "run": cmd_run, "status": cmd_status, "summary": cmd_summary,
            "publish": cmd_publish, "gather": cmd_gather, "hinglish": cmd_hinglish}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
