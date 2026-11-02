"""The pipeline: a resumable state machine over files in output/briefing/<date>/.

Every step writes its output file; a re-run skips steps whose output exists. That makes a crash or a
cloud hiccup cheap: `next` just restarts the runner and it picks up where it stopped. The 05:40 IST
deadline is enforced here: past it, no new model work starts and the edition is built from what passed.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import math
import re
import time
import traceback

from . import agenda, build, cluster, config, gather, prompting, ranking, schemas, threads
from .engine import Engine, EngineError


class Run:
    def __init__(self, date: str, engine: Engine, *, now: dt.datetime | None = None, force: bool = False):
        self.date, self.engine, self.force = date, engine, force
        self.dir = config.day_dir(date)
        self.now = now or config.now_ist()
        self.state = self._load("state") or {
            "date": date, "started_at": config.iso(self.now), "deadline": config.iso(config.deadline_for(self.now)),
            "status": "running", "stage": "start", "done": [], "timings": {}, "notes": [], "progress": {}}
        if self.state.get("notes"):          # a resumed run starts with fresh notes; keep the old ones apart
            self.state.setdefault("previous_notes", []).extend(self.state["notes"])
            self.state["notes"] = []
        self.state["status"] = "running"
        self.deadline = config.parse_ts(self.state["deadline"])
        self.notes: list[str] = self.state.setdefault("notes", [])
        self._save_state()

    # ------------------------------------------------------------ files + state
    def _path(self, name: str):
        return self.dir / f"{name}.json"

    def _load(self, name: str):
        try:
            return json.loads(self._path(name).read_text())
        except (OSError, ValueError):
            return None

    def put(self, name: str, obj) -> None:
        self._path(name).write_text(json.dumps(obj, ensure_ascii=False))

    def _save_state(self) -> None:
        self.put("state", self.state)

    def stage(self, name: str, **progress) -> None:
        self.state["stage"] = name
        if progress:
            self.state["progress"].update(progress)
        self._save_state()

    def mark_done(self, name: str, t0: float) -> None:
        if name not in self.state["done"]:
            self.state["done"].append(name)
        self.state["timings"][name] = round(time.monotonic() - t0, 1)
        self._save_state()

    def note(self, text: str) -> None:
        self.notes.append(text[:300])
        self._save_state()

    def left(self) -> float:
        return (self.deadline - config.now_ist()).total_seconds()

    async def ask(self, role, system, prompt, schema, *, label, need_s: int = 0):
        if need_s and self.left() < need_s:
            raise EngineError(f"{label}: skipped, only {int(self.left())} s left before the deadline")
        return await self.engine.ask(role, system, prompt, schema, label=label)

    # ------------------------------------------------------------ context
    def window(self) -> dict:
        w = self._load("window")
        if w:
            return w
        start = self.now - dt.timedelta(hours=config.WINDOW_FALLBACK_H)
        prev = previous_edition(self.date)
        if prev and (pend := config.parse_ts((prev.get("window") or {}).get("end"))):
            start = max(pend - dt.timedelta(minutes=config.WINDOW_OVERLAP_MIN), self.now - dt.timedelta(hours=36))
        w = {"start": config.iso(start), "end": config.iso(self.now)}
        self.put("window", w)
        return w


def previous_edition(date: str) -> dict | None:
    for p in sorted(config.PUB.glob("20??-??-??.json"), reverse=True):
        if p.stem < date:
            try:
                return json.loads(p.read_text())
            except (OSError, ValueError):
                return None
    return None


def covered_headlines(ed: dict | None) -> list[str]:
    if not ed:
        return []
    out = [s["headline"] for s in ed.get("stories") or []]
    for sec in ed.get("sections") or []:
        out += [i["headline"] for i in sec.get("items") or []]
    out += [a["text"] for a in ed.get("also") or []]
    return out


# ================================================================ the pipeline
async def run(date: str, engine: Engine, *, now: dt.datetime | None = None, force: bool = False) -> dict:
    R = Run(date, engine, now=now, force=force)
    try:
        await _pipeline(R)
        R.state["status"] = "done"
    except Exception as e:  # noqa: BLE001 - record and surface; publish still commits the quality file
        R.state["status"] = "failed"
        R.note(f"FAILED: {type(e).__name__}: {e}")
        R.put("traceback", {"tb": traceback.format_exc()})
        qdir = config.PUB / "quality"
        qdir.mkdir(parents=True, exist_ok=True)
        if not (qdir / f"{date}.json").exists():       # the edition app shows "running late"; this says why
            (qdir / f"{date}.json").write_text(json.dumps({
                "date": date, "generated_at": config.iso(config.now_ist()), "status": "failed",
                "stage": R.state.get("stage"), "notes": R.notes, "timings": R.state.get("timings"),
                "usage": engine.usage.as_dict()}, ensure_ascii=False, indent=1))
    R.state["usage"] = engine.usage.as_dict()
    R.state["finished_at"] = config.iso(config.now_ist())
    R._save_state()
    return R.state


async def _pipeline(R: Run) -> None:
    window = R.window()
    tdoc = threads.load()
    cal = agenda.load()
    prev = previous_edition(R.date)
    covered = covered_headlines(prev)

    # ---- 1. gather + cluster (code)
    leads = R._load("leads")
    if not leads:
        t0 = time.monotonic()
        R.stage("gather")
        raw = gather.run(R.date, window)
        R.note("sources: " + gather.health_summary(raw))
        leads = cluster.build(raw, threads.active(tdoc))
        R.mark_done("gather", t0)
    agenda.add_f1(cal, (leads.get("sport") or {}).get("f1") or {})
    clusters = {c["id"]: c for c in leads["clusters"]}

    # ---- 2. first run only: seed thread memory from the old digest archive
    if not tdoc["threads"] and not R._load("bootstrap"):
        old = sorted(config.ROOT.glob("dashboard/digest/digest-*.json"))[-10:]
        if old:
            t0 = time.monotonic()
            R.stage("bootstrap")
            eds = [json.loads(p.read_text()) for p in old]
            try:
                res = await R.ask("bootstrap", prompting.system("bootstrap"), prompting.bootstrap(eds),
                                  schemas.BOOTSTRAP, label="bootstrap")
                R.put("bootstrap", res)
            except EngineError as e:
                R.note(f"bootstrap failed: {e}")
            R.mark_done("bootstrap", t0)
    if not tdoc["threads"] and (boot := R._load("bootstrap")):
        tdoc = threads.from_bootstrap(boot, R.date)
        cluster.attach_thread_hints(leads["clusters"], threads.active(tdoc))
    active = threads.active(tdoc)
    thr_ctx = {t["id"]: threads.context(t, R.date) for t in tdoc["threads"]}

    # ---- 3. recall (yesterday vs the now-complete Wikipedia page) + triage, concurrently
    t0 = time.monotonic()
    R.stage("triage")
    recall_task = asyncio.create_task(_recall(R, prev, leads, window))
    verdicts = await _triage(R, leads, covered, active)
    recall = await recall_task
    R.mark_done("triage", t0)

    # ---- 4. score, same-story merge, scout
    t0 = time.monotonic()
    R.stage("merge")
    scored = ranking.score_all(ranking.select_for_triage(leads["clusters"]), verdicts)
    scored = await _merge(R, scored)
    R.mark_done("merge", t0)
    t0 = time.monotonic()
    R.stage("scout")
    scored, clusters = await _scout(R, scored, clusters, leads, cal, active, window)
    R.mark_done("scout", t0)

    # ---- 5. editor -> plan
    t0 = time.monotonic()
    R.stage("editor")
    start_date = config.parse_ts(window["start"]).astimezone(config.IST).date().isoformat()
    due = agenda.due(cal, start_date, R.date)
    plan = await _editor(R, scored, active, due, agenda.upcoming(cal, R.date), (recall or {}).get("misses") or [],
                         covered, window)
    R.mark_done("editor", t0)
    cmap = {c["id"]: c for c in scored} | clusters

    # ---- 6. big stories and sections, concurrently
    t0 = time.monotonic()
    R.stage("stories", stories_total=len(plan["tier1"]), stories_done=0)
    story_task = asyncio.create_task(_stories(R, plan, cmap, thr_ctx, window, leads.get("markets")))
    section_task = asyncio.create_task(_sections(R, plan, cmap, thr_ctx, window))
    story_recs = await story_task
    brief_recs, gists = await section_task
    R.mark_done("stories+sections", t0)

    # ---- 7. assemble (code), cover (model), finish (code)
    t0 = time.monotonic()
    R.stage("build")
    await _assemble(R, plan=plan, cmap=cmap, verdicts=verdicts, story_recs=story_recs, brief_recs=brief_recs,
                    gists=gists, tdoc=tdoc, cal=cal, due=due, window=window, leads=leads, recall=recall)
    R.mark_done("build", t0)


# ================================================================ steps
async def _recall(R: Run, prev: dict | None, leads: dict, window: dict) -> dict | None:
    cached = R._load("recall")
    if cached is not None:
        return cached
    if not prev:
        return None
    end_utc = config.parse_ts(window["end"]).astimezone(config.UTC).date()
    ref = [e for e in leads.get("wiki_events") or [] if e["page_date"] == (end_utc - dt.timedelta(days=1)).isoformat()]
    if not ref:
        return None
    try:
        res = await R.ask("recall", prompting.system("recall"), prompting.recall(covered_headlines(prev), ref),
                          schemas.RECALL, label="recall")
    except EngineError as e:
        R.note(f"recall failed: {e}")
        return None
    res["edition"] = prev.get("date")
    R.put("recall", res)
    return res


async def _triage(R: Run, leads: dict, covered: list[str], active: list[dict]) -> dict:
    cached = R._load("triage")
    if cached is not None:
        return cached
    cands = ranking.select_for_triage(leads["clusters"])
    batches = [cands[i:i + config.TRIAGE_BATCH] for i in range(0, len(cands), config.TRIAGE_BATCH)]
    sys_p = prompting.system("triage")

    async def one(i, batch):
        try:
            res = await R.ask("triage", sys_p, prompting.triage(batch, date=R.date, covered=covered, threads=active),
                              schemas.TRIAGE, label=f"triage-{i}")
            return res.get("items") or []
        except EngineError as e:
            R.note(f"triage batch {i} failed: {e}")
            return []
    results = await asyncio.gather(*(one(i, b) for i, b in enumerate(batches)))
    verdicts = {v["id"]: v for items in results for v in items if v.get("id")}
    # A story the model skipped isn't lost: give it a middling verdict so code ranking still sees it.
    for c in cands:
        verdicts.setdefault(c["id"], {"id": c["id"], "section": c["section_hint"], "scale": 2, "severity": 2,
                                      "durability": 2, "novelty": 3, "india": 3 if c["signals"]["india"] else 1,
                                      "interest": c["section_hint"] in config.INTEREST_SECTIONS,
                                      "same_as_thread": c.get("thread_hint") or "", "line": c["title"][:160],
                                      "drop_reason": "", "_default": True})
    R.put("triage", verdicts)
    return verdicts


def _merge_clusters(primary: dict, others: list[dict]) -> dict:
    m = dict(primary)
    seen = {x["url"] for x in m["members"]}
    members = list(m["members"])
    names = set(m.get("publisher_names") or [])
    sig = dict(m["signals"])
    for o in others:
        for x in o["members"]:
            if x["url"] not in seen and len(members) < 8:
                members.append(x)
                seen.add(x["url"])
        names |= set(o.get("publisher_names") or [])
        sig["wiki"] = sorted(set(sig["wiki"]) | set(o["signals"]["wiki"]))
        sig["beats"] = sorted(set(sig["beats"]) | set(o["signals"]["beats"]))
        sig["kagi"] = max(sig["kagi"], o["signals"]["kagi"])
        sig["primary"] = sig["primary"] or o["signals"]["primary"]
        m["wiki_text"] = m.get("wiki_text") or o.get("wiki_text")
        m["kagi_summary"] = m.get("kagi_summary") or o.get("kagi_summary")
        m["thread_hint"] = m.get("thread_hint") or o.get("thread_hint")
    m["members"], m["signals"] = members, sig
    m["publisher_names"] = sorted(names)[:16]
    m["publishers"] = max(len(names), primary["publishers"])
    m["merged"] = [o["id"] for o in others]
    return m


async def _merge(R: Run, scored: list[dict]) -> list[dict]:
    cached = R._load("merged")
    if cached is not None:
        return cached
    top = scored[:200]
    try:
        res = await R.ask("same_story", prompting.system("same_story"), prompting.same_story(top), schemas.SAME_STORY,
                          label="same-story")
        groups = res.get("groups") or []
    except EngineError as e:
        R.note(f"same-story merge failed: {e}")
        groups = []
    by_id = {c["id"]: c for c in scored}
    absorbed: set[str] = set()
    for g in groups:
        ids = [i for i in dict.fromkeys(g) if i in by_id and i not in absorbed]
        if len(ids) < 2:
            continue
        ids.sort(key=lambda i: -by_id[i]["score"])
        merged = _merge_clusters(by_id[ids[0]], [by_id[i] for i in ids[1:]])
        merged["score"] = round(ranking.importance_score(merged["triage"], merged)
                                - (0.75 if merged["triage"]["interest"] or merged["section"] in config.INTEREST_SECTIONS
                                   else 0), 3)
        by_id[ids[0]] = merged
        absorbed |= set(ids[1:])
    out = sorted((c for i, c in by_id.items() if i not in absorbed), key=lambda c: -c["score"])
    R.put("merged", out)
    return out


async def _scout(R: Run, scored: list[dict], clusters: dict, leads: dict, cal: dict, active: list[dict],
                 window: dict) -> tuple[list[dict], dict]:
    cached = R._load("scout")
    if cached is None:
        gaps = []
        for b in leads.get("beats") or []:
            if b.get("must_check") and not b.get("hits"):
                gaps.append({"gap": f"beat:{b['id']}", "section": b["section"],
                             "ask": f"{b['label']}: any significant news in the window?"})
        start_date = config.parse_ts(window["start"]).astimezone(config.IST).date().isoformat()
        top_sigs = [cluster.tokens(c["title"]) for c in scored[:150]]
        for e in agenda.due(cal, start_date, R.date):
            esig = cluster.tokens(e["title"])
            if not any(len(esig & sig) >= 2 for sig in top_sigs):
                gaps.append({"gap": f"event:{e['id']}", "section": e["section"],
                             "ask": f"Scheduled for {e['date']}: {e['title']}. What happened (result or decision)?"})
        hinted = {c.get("thread_hint") for c in scored} | {(c.get("triage") or {}).get("same_as_thread") for c in scored}
        for t in sorted(active, key=lambda t: -(t.get("days") or 0)):
            if t["id"] not in hinted:
                gaps.append({"gap": f"thread:{t['id']}", "section": t.get("section") or "world",
                             "ask": f"Ongoing story '{t['title']}'. Any new development? Last state: "
                                    f"{'; '.join(s['fact'] for s in (t.get('last_state') or [])[:3])}"})
        gaps = gaps[:12]
        found = []
        if gaps:
            try:
                res = await R.ask("scout", prompting.system("scout"), prompting.scout(gaps, window), schemas.SCOUT,
                                  label="scout", need_s=600)
                found = res.get("findings") or []
            except EngineError as e:
                R.note(f"scout failed: {e}")
        cached = {"gaps": gaps, "findings": found}
        R.put("scout", cached)
    gap_by = {g["gap"]: g for g in cached["gaps"]}
    new = []
    for i, f in enumerate(cached["findings"], 1):
        g = gap_by.get(f.get("gap"))
        if not f.get("found") or not g or not str(f.get("url", "")).startswith("http"):
            continue
        if not gather.in_window(f.get("published"), config.parse_ts(window["start"]), config.parse_ts(window["end"])):
            continue
        kind, _, ref = g["gap"].partition(":")
        c = {"id": f"x{i:03d}", "title": f["headline"][:200], "section_hint": g["section"], "section": g["section"],
             "first": f["published"], "last": f["published"], "publishers": 1, "publisher_names": [f["publisher"]],
             "tier": 2, "members": [{"pub": f["publisher"], "via": "scout", "url": f["url"], "published": f["published"],
                                     "title": f["headline"][:200], "summary": f["summary"][:300]}],
             "signals": {"wiki": [], "kagi": 0, "beats": [ref] if kind == "beat" else [], "india": 0, "hn": None,
                         "primary": False, "scout": True},
             "thread_hint": ref if kind == "thread" else None, "calendar_hint": ref if kind == "event" else None}
        t = {"scale": 3, "severity": 3, "durability": 3, "novelty": 4,
             "india": 4 if g["section"] in ("india", "affects_you") else 2, "interest": g["section"] in config.INTEREST_SECTIONS}
        c["triage"] = {**t, "line": f["summary"][:160], "same_as_thread": c["thread_hint"] or ""}
        c["score"] = round(ranking.importance_score(t, c), 3)
        new.append(c)
        clusters[c["id"]] = c
    return sorted(scored + new, key=lambda c: -c["score"]), clusters


def _fix_plan(plan: dict, cands: list[dict], active: list[dict]) -> dict:
    """Make the editor's plan obey the hard rules in code (cheaper and surer than another model call)."""
    by_id = {c["id"]: c for c in cands}
    used: set[str] = set()

    def clean_ids(ids):
        out = [i for i in dict.fromkeys(ids or []) if i in by_id and i not in used]
        used.update(out)
        return out

    def take(slots, key="cluster_ids"):
        out = []
        for s in slots or []:
            ids = clean_ids(s.get(key) if key == "cluster_ids" else [s.get(key)])
            if ids:
                out.append({**s, "cluster_ids": ids} if key == "cluster_ids" else {**s, "cluster_id": ids[0]})
        return out

    tier1 = take(plan.get("tier1"))[: config.TIER1_MAX]
    reserves = take(plan.get("reserves"))[:3]
    while len(tier1) < config.TIER1_TARGET and reserves:
        tier1.append(reserves.pop(0))
    for c in cands:                       # still short: promote the best unused serious stories
        if len(tier1) >= config.TIER1_MIN_COMPLETE:
            break
        if c["id"] not in used and c["section"] not in config.INTEREST_SECTIONS:
            used.add(c["id"])
            tier1.append(ranking.fallback_plan([c], [])["tier1"][0] if c.get("triage") else None)
    tier1 = [s for s in tier1 if s]
    tier2 = take(plan.get("tier2"))
    per_sec: dict[str, list] = {}
    for s in tier2:
        per_sec.setdefault(s["section"], []).append(s)
    tier2 = [s for sec in config.SECTION_KEYS for s in per_sec.get(sec, [])[: config.BRIEFS_PER_SECTION[1]]]
    for sec in config.NEVER_QUIET:        # world/india/markets always get 2+ briefs
        have = sum(1 for s in tier2 if s["section"] == sec)
        for c in cands:
            if have >= 2:
                break
            if c["section"] == sec and c["id"] not in used:
                used.add(c["id"])
                tier2.append({"cluster_ids": [c["id"]], "section": sec, "thread_id": c.get("thread_hint") or "",
                              "new_thread": False, "angle": "", "calendar_ids": []})
                have += 1
    tier3 = take(plan.get("tier3"), key="cluster_id")[: config.ALSO_MAX]
    acted = {a.get("thread_id") for a in plan.get("threads") or []}
    actions = list(plan.get("threads") or []) + [{"thread_id": t["id"], "action": "no_change", "note": ""}
                                                 for t in active if t["id"] not in acted]
    out = {**plan, "tier1": tier1, "reserves": reserves, "tier2": tier2, "tier3": tier3, "threads": actions}
    for i, s in enumerate(out["tier1"], 1):
        s["id"] = f"s{i}"
    for i, s in enumerate(out["reserves"], 1):
        s["id"] = f"r{i}"
    counts: dict[str, int] = {}
    for s in out["tier2"]:
        counts[s["section"]] = counts.get(s["section"], 0) + 1
        s["id"] = f"b-{s['section']}-{counts[s['section']]}"
    for i, s in enumerate(out["tier3"], 1):
        s["id"] = f"l-{i:02d}"
    return out


async def _editor(R: Run, scored, active, due, upcoming, misses, covered, window) -> dict:
    cached = R._load("plan")
    if cached is not None:
        return cached
    cands = ranking.editor_candidates(scored)
    sys_p = prompting.system("editor", TIER1=config.TIER1_TARGET, TIER1_MIN=config.TIER1_MIN_COMPLETE,
                             BRIEFS_MIN=config.BRIEFS_MIN, BRIEFS_MAX=config.BRIEFS_MAX)
    try:
        plan = await R.ask("editor", sys_p, prompting.editor(date=R.date, window=window, cands=cands,
                                                              threads=[threads.context(t, R.date) for t in active],
                                                              due=due,
                                                              upcoming=upcoming, misses=misses, covered=covered),
                           schemas.EDITOR, label="editor")
    except EngineError as e:
        R.note(f"editor failed, using the fallback plan: {e}")
        plan = ranking.fallback_plan(cands, active)
    plan = _fix_plan(plan, cands, active)
    R.put("plan", plan)
    return plan


# ---------------------------------------------------------------- big stories
async def _story_chain(R: Run, slot: dict, cmap: dict, thr_ctx: dict, window: dict, markets: dict | None) -> dict:
    sid = slot["id"]
    rec = R._load(f"story-{sid}")
    if rec and rec.get("status") in ("ok", "demote"):      # failures are retried on resume (cached steps reused)
        return rec
    thread = thr_ctx.get(slot.get("thread_id") or "")
    clusters = [cmap[c] for c in slot["cluster_ids"] if c in cmap]
    style_writer = prompting.system("style", "writer")
    rec = {"id": sid, "slot": slot, "status": "failed", "problems": []}
    try:
        research = R._load(f"research-{sid}")
        if research is None:
            for attempt in range(2):
                research = await R.ask("research", prompting.system("research"),
                                       prompting.research(slot, clusters, date=R.date, window=window, thread=thread),
                                       schemas.RESEARCH, label=f"research-{sid}", need_s=540)
                good = [c for c in research.get("claims") or [] if str(c.get("url", "")).startswith("http")]
                if len(good) >= 5:
                    break
                research = None
            if research is None:
                raise EngineError(f"research-{sid}: fewer than 5 sourced claims")
            R.put(f"research-{sid}", research)
        story = R._load(f"draft-{sid}")
        if story is None:
            story = await R.ask("writer", style_writer, prompting.writer(slot, research, date=R.date, thread=thread),
                                schemas.STORY, label=f"writer-{sid}", need_s=420)
            R.put(f"draft-{sid}", story)
        year = R.now.year
        code_p = build.story_problems(story, research, slot=slot, year=year, markets=markets)
        chk = await R.ask("checker", prompting.system("checker"),
                          prompting.checker(story, research, thread=thread, code_problems=code_p),
                          schemas.CHECK, label=f"check-{sid}", need_s=240)
        problems = (chk.get("problems") or []) + [p for p in code_p if p not in (chk.get("problems") or [])]
        if any(p["severity"] == "drop" for p in chk.get("problems") or []):
            rec.update(status="demote", story=story, problems=problems)
        elif problems:
            fixed = await R.ask("fixer", prompting.system("style", "writer"),
                                prompting.fixer(story, research, problems, date=R.date),
                                schemas.STORY, label=f"fix-{sid}", need_s=360)
            code_p2 = build.story_problems(fixed, research, slot=slot, year=year, markets=markets)
            chk2 = await R.ask("checker", prompting.system("checker"),
                               prompting.checker(fixed, research, thread=thread, code_problems=code_p2),
                               schemas.CHECK, label=f"recheck-{sid}", need_s=180)
            left = (chk2.get("problems") or []) + code_p2
            blocking = [p for p in left if p["severity"] == "drop" or p["where"].split("[")[0] in build.REQUIRED_BLOCKS]
            rec.update(status="demote" if blocking else "ok", story=fixed, problems=left)
        else:
            rec.update(status="ok", story=story, problems=[])
    except EngineError as e:
        rec["error"] = str(e)
        R.note(f"{sid} failed: {e}")
    R.put(f"story-{sid}", rec)
    R.state["progress"]["stories_done"] = R.state["progress"].get("stories_done", 0) + 1
    R._save_state()
    return rec


async def _stories(R: Run, plan: dict, cmap: dict, thr_ctx: dict, window: dict, markets) -> list[dict]:
    recs = await asyncio.gather(*(_story_chain(R, s, cmap, thr_ctx, window, markets) for s in plan["tier1"]))
    ok = sum(1 for r in recs if r["status"] == "ok")
    for reserve in plan.get("reserves") or []:       # replace failures while there's time
        if ok >= config.TIER1_TARGET or R.left() < 900:
            break
        rec = await _story_chain(R, reserve, cmap, thr_ctx, window, markets)
        recs.append(rec)
        ok += rec["status"] == "ok"
    return list(recs)


# ---------------------------------------------------------------- sections
BRIEF_BATCHES = [["world", "india"], ["affects_you", "markets", "tech_ai"], ["science", "f1", "cricket"]]


async def _sections(R: Run, plan: dict, cmap: dict, thr_ctx: dict, window: dict) -> tuple[dict, dict]:
    items_by_sec: dict[str, list] = {}
    for it in plan["tier2"]:
        items_by_sec.setdefault(it["section"], []).append(it)

    async def research(sec):
        cached = R._load(f"secres-{sec}")
        if cached is not None:
            return sec, cached
        try:
            res = await R.ask("section", prompting.system("section"),
                              prompting.section_research(sec, items_by_sec[sec], cmap, window=window),
                              schemas.SECTION_RESEARCH, label=f"section-{sec}", need_s=480)
        except EngineError as e:
            R.note(f"section research {sec} failed: {e}")
            res = {"items": [], "_failed": True}
        R.put(f"secres-{sec}", res)
        return sec, res
    secres = dict(await asyncio.gather(*(research(s) for s in items_by_sec)))
    facts = {}
    for sec, res in secres.items():
        for it in res.get("items") or []:
            if it.get("ok") and it.get("facts"):
                facts[it["item_id"]] = it["facts"]

    sys_b = prompting.system("style", "briefs")

    async def write(k, secs):
        secs = [s for s in secs if items_by_sec.get(s)]
        if not secs:
            return {}
        cached = R._load(f"briefs-{k}")
        if cached is None:
            ok_items = {s: [i for i in items_by_sec[s] if i["id"] in facts] for s in secs}
            if not any(ok_items.values()):
                return {}
            try:
                cached = await R.ask("briefs", sys_b, prompting.briefs(secs, ok_items, facts, thr_ctx, date=R.date),
                                     schemas.BRIEFS, label=f"briefs-{k}", need_s=300)
            except EngineError as e:
                R.note(f"briefs batch {k} failed: {e}")
                cached = {"briefs": [], "gists": []}
            R.put(f"briefs-{k}", cached)
        return cached
    outs = await asyncio.gather(*(write(k, secs) for k, secs in enumerate(BRIEF_BATCHES)))
    briefs = {b["item_id"]: b for o in outs for b in (o or {}).get("briefs") or []}
    gists = {g["section"]: g["gist"] for o in outs for g in (o or {}).get("gists") or []}

    checked = R._load("briefs-check")
    if checked is None and briefs:
        try:
            checked = await R.ask("checker", prompting.system("briefs_check"),
                                  prompting.briefs_check(list(briefs.values()), facts), schemas.BRIEFS_CHECK,
                                  label="briefs-check", need_s=200)
            R.put("briefs-check", checked)          # only a real check is cached; a failure is retried on resume
        except EngineError as e:
            R.note(f"briefs check failed, briefs published unchecked: {e}")
            checked = {"checks": []}
    verdict = {c["item_id"]: c for c in (checked or {}).get("checks") or []}
    to_fix = [i for i, v in verdict.items() if v.get("severity") == "fix" and i in briefs]
    if to_fix and not R._load("briefs-fixed") and R.left() > 300:
        fix_items = {}
        for it in plan["tier2"]:
            if it["id"] in to_fix:
                fix_items.setdefault(it["section"], []).append({**it, "angle": "FIX THESE PROBLEMS: " +
                                                                "; ".join(verdict[it["id"]]["problems"])})
        try:
            fixed = await R.ask("briefs", sys_b, prompting.briefs(list(fix_items), fix_items, facts, thr_ctx, date=R.date),
                                schemas.BRIEFS, label="briefs-fix", need_s=240)
            R.put("briefs-fixed", fixed)
        except EngineError as e:
            R.note(f"briefs fix failed: {e}")
    for b in (R._load("briefs-fixed") or {}).get("briefs") or []:
        if b["item_id"] in briefs:
            briefs[b["item_id"]] = b
            verdict[b["item_id"]] = {"severity": "ok", "problems": []}
    recs = {}
    for it in plan["tier2"]:
        b = briefs.get(it["id"])
        v = verdict.get(it["id"], {})
        if b and v.get("severity") != "drop" and not (v.get("severity") == "fix" and it["id"] in to_fix
                                                      and not R._load("briefs-fixed")):
            recs[it["id"]] = {"item": it, "brief": b, "facts": facts.get(it["id"]) or []}
    return recs, gists


# ---------------------------------------------------------------- assemble the edition
def _strip_optional(story: dict, problems: list[dict]) -> dict:
    s = dict(story)
    for p in problems:
        w = p["where"].split("[")[0]
        if w == "analogy":
            s["analogy"] = {"text": "", "breaks": ""}
        elif w == "misconception":
            s["misconception"] = {"myth": "", "fact": "", "cids": []}
        elif w == "numbers":                      # a problem inside the "by the numbers" block: drop the block
            s["numbers"] = []
        elif w == "views" and len(s.get("views") or []) < 2:
            s["views"] = []
        elif w == "players":
            s["players"] = []
    return s


async def _assemble(R: Run, *, plan, cmap, verdicts, story_recs, brief_recs, gists, tdoc, cal, due, window,
                    leads, recall) -> None:
    now = config.now_ist()
    markets = leads.get("markets")
    reader_notes, qnotes = [], []
    stories, demoted = [], []
    thread_updates = []
    slot_to_item: dict[str, str] = {}
    for rec in story_recs:
        if rec["status"] == "failed" or not rec.get("story"):
            qnotes.append(f"{rec['id']}: failed ({rec.get('error', 'no story')})")
            continue
        slot, s = rec["slot"], rec["story"]
        research = R._load(f"research-{rec['id']}") or {}
        if rec["status"] == "ok":
            s = _strip_optional(s, rec.get("problems") or [])
            t = threads.find(tdoc, slot.get("thread_id") or "")
            pub_thread = None
            if t:
                b = threads.before(t, R.date)
                pub_thread = {"id": t["id"], "status": "developing", "day": b["days"] + 1,
                              "previously": b["summary"] or None, "changed": s.get("changed") or None}
            story, notes, _reel_ok = build.public_story(f"s{len(stories) + 1}", slot, s, research, thread=pub_thread,
                                                        window=window, now=now, markets=markets)
            qnotes += notes
            if story:
                stories.append(story)
                slot_to_item[slot["id"]] = story["id"]
                thread_updates.append(("story", story, slot, s, research))
                continue
        b = build.demote(rec["id"], slot["section"], s, research, window)
        if b:
            demoted.append(b)
            slot_to_item[slot["id"]] = b["id"]
            qnotes.append(f"{rec['id']}: demoted to a brief")
        else:
            qnotes.append(f"{rec['id']}: dropped (couldn't meet the source rules)")
    stories = stories[: config.TIER1_MAX]

    # briefs per section
    sec_items: dict[str, list] = {k: [] for k in config.SECTION_KEYS}
    for item_id, r in brief_recs.items():
        it = r["item"]
        t = threads.find(tdoc, it.get("thread_id") or "")
        item = {**it, "thread": {"id": t["id"], "day": threads.before(t, R.date)["days"] + 1} if t else None}
        b, err = build.public_brief(item, r["brief"], r["facts"], window)
        if b:
            sec_items[it["section"]].append(b)
            thread_updates.append(("brief", b, it, r["brief"], None))
        elif err:
            qnotes.append(err)
    for b in demoted:
        sec_items[b["section"]].append(b)
    quiet = {q["section"]: q["note"] for q in plan.get("quiet") or []}
    sections = []
    for k in config.SECTION_KEYS:
        emoji, title = config.SECTIONS[k]
        items = sec_items[k][: config.BRIEFS_PER_SECTION[1] + 2]
        sec = {"key": k, "emoji": emoji, "title": title, "gist": gists.get(k, ""), "quiet": not items, "items": items}
        if not items:
            sec["quiet_note"] = quiet.get(k) or "Checked: nothing major in this window."
            if k in config.NEVER_QUIET:
                reader_notes.append(f"{title} has fewer briefs than usual today.")
        elif k in config.NEVER_QUIET and len(items) < 2:
            reader_notes.append(f"{title} has fewer briefs than usual today.")
        sections.append(sec)

    # one-liners (tier 3) from triage lines + the best dated member
    start = config.parse_ts(window["start"]) - dt.timedelta(hours=24)
    also = []
    for t3 in plan.get("tier3") or []:
        c = cmap.get(t3["cluster_id"])
        if not c:
            continue
        line = (verdicts.get(c["id"]) or {}).get("line") or (c.get("triage") or {}).get("line") or ""
        m = next((m for m in c["members"] if (ts := config.parse_ts(m.get("published"))) and ts >= start), None)
        if not m or not 5 <= build.words(line) <= 30 or build.RELATIVE.search(line):
            continue
        also.append({"id": t3["id"], "section": t3["section"], "text": line,
                     "source": {"pub": m["pub"], "url": m["url"], "published": build._ist(m["published"])}})

    # cover (model) from the final items
    brief_list = [b for s in sections for b in s["items"]]
    cover = R._load("cover")
    if cover is None:
        today_events = [e for e in cal["events"] if e["date"] == R.date]
        try:
            cover = await R.ask("cover", prompting.system("cover"),
                                prompting.cover(stories, brief_list, date=R.date, today_events=today_events,
                                                watch=plan.get("watch_today") or []),
                                schemas.COVER, label="cover", need_s=60)
        except EngineError as e:
            R.note(f"cover failed: {e}")
            cover = {"top_line": stories[0]["dek"] if stories else "", "watch_today": [],
                     "changes": [{"text": x["headline"], "ref": x["id"]} for x in stories + brief_list[:3]]}
        else:
            R.put("cover", cover)                    # only cache a real cover; a fallback is rebuilt next time
    ids = {x["id"] for x in stories} | {b["id"] for b in brief_list}
    changes = [c for c in cover.get("changes") or [] if c.get("ref") in ids][:8]

    # thread memory + calendar (code)
    covered_threads: dict[str, str] = {}
    for kind, obj, slot, raw, research in thread_updates:
        if kind == "story":
            claims = {c["cid"]: c for c in (research or {}).get("claims") or []}
            state = [{"fact": f["fact"], "url": claims.get(f.get("cid"), {}).get("url"),
                      "published": claims.get(f.get("cid"), {}).get("published")} for f in raw.get("state_facts") or []]
            t = threads.touch(tdoc, tid=slot.get("thread_id") or None, title=obj["headline"], section=obj["section"],
                              date=R.date, summary=raw.get("thread_summary") or obj["dek"],
                              timeline_text=raw.get("changed") or obj["dek"], item_id=obj["id"], state=state,
                              watch=obj["blocks"]["next"]["dates"], keywords_from=obj["headline"] + " " + obj["dek"])
            if obj.get("thread") is None:
                obj["thread"] = {"id": t["id"], "status": "new", "day": 1, "previously": None, "changed": None}
            for d in obj["blocks"]["next"]["dates"]:
                agenda.add(cal, date=d["date"], title=d["what"], section=obj["section"], source=f"story:{obj['id']}",
                           thread_id=t["id"])
            covered_threads[t["id"]] = obj["id"]
        elif slot.get("thread_id") or slot.get("new_thread"):
            t = threads.touch(tdoc, tid=slot.get("thread_id") or None, title=obj["headline"], section=obj["section"],
                              date=R.date, summary=raw.get("thread_summary") or "", timeline_text=obj["headline"],
                              item_id=obj["id"], keywords_from=obj["headline"])
            covered_threads[t["id"]] = obj["id"]
    threads.apply_actions(tdoc, plan.get("threads") or [], R.date)
    threads.expire(tdoc, R.date)
    item_ids = {x["id"] for x in stories} | {b["id"] for b in brief_list}
    covered_events = {}
    for slot in plan["tier1"] + (plan.get("reserves") or []) + plan["tier2"]:
        item_id = slot_to_item.get(slot.get("id"), slot.get("id"))
        if item_id in item_ids:
            for eid in slot.get("calendar_ids") or []:
                covered_events[eid] = f"{R.date}/{item_id}"
    agenda.mark(cal, covered=covered_events, due_ids=[e["id"] for e in due], date=R.date)

    notes_by_thread = {a["thread_id"]: a for a in plan.get("threads") or []}
    developing = []
    for t in tdoc["threads"]:
        if t["status"] == "active" or (t["status"] == "resolved" and (t.get("timeline") or [{}])[-1].get("date") == R.date):
            today = "update" if t["id"] in covered_threads else ("resolved" if t["status"] == "resolved" else "no_change")
            line = (notes_by_thread.get(t["id"], {}).get("note") or (t.get("timeline") or [{}])[-1].get("text") or "")
            developing.append({"thread_id": t["id"], "title": t["title"], "day": t.get("days", 1), "today": today,
                               "ref": covered_threads.get(t["id"]), "line": line[:160]})
    developing.sort(key=lambda d: (d["today"] != "update", -d["day"]))

    n1 = len(stories)
    status = "complete" if n1 >= config.TIER1_MIN_COMPLETE else ("partial" if n1 >= 2 else "lite")
    if any("fewer briefs" in n for n in reader_notes) and status == "complete":
        status = "partial"
    failed = [n for n in qnotes if ": failed" in n or ": dropped" in n or ": demoted" in n]
    if failed:
        reader_notes.append(f"{len(failed)} planned big {'story was' if len(failed) == 1 else 'stories were'} held back "
                            "or shortened because it didn't pass the fact check.")
    if (leads.get("stats") or {}).get("items", 0) < 300:
        reader_notes.append("Fewer news sources than usual were reachable for this edition.")
    read_min = sum(s["read_min"] for s in stories) + math.ceil(sum(build.words(b["text"]) for b in brief_list) / 200) + 2
    ed = {
        "schema": 1, "date": R.date, "edition": f"Morning · {now.strftime('%-I:%M %p')}",
        "published_at": config.iso(now), "window": window, "status": status, "notes": reader_notes,
        "cover": {"top_line": cover.get("top_line", ""), "changes": changes,
                  "watch_today": [{"text": w["text"], "time_ist": w.get("time_ist") or None, "calendar_id": None}
                                  for w in cover.get("watch_today") or []][:3],
                  "read_min": read_min, "watch_min": round(sum(1.3 for s in stories if s.get("reel")))},
        "stories": stories, "sections": sections, "also": also[: config.ALSO_MAX],
        "quiz": [{**s["check"], "story": s["id"]} for s in stories if s.get("check")][: config.QUIZ_N],
        "developing": developing[:12], "markets": markets, "disclaimer": config.DISCLAIMER,
    }
    if stories:
        stories[0]["must_read"] = True
    if errs := build.privacy_ok(ed):
        raise RuntimeError("privacy check failed: " + "; ".join(errs))

    out = config.PUB / f"{R.date}.json"
    old = None
    try:
        old = json.loads(out.read_text())
    except (OSError, ValueError):
        pass
    if old and old.get("status") == "complete" and status != "complete" and not R.force:
        qnotes.append("kept the earlier complete edition (this run was partial)")
    else:
        config.PUB.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(ed, ensure_ascii=False, indent=1))
        threads.save(tdoc, R.date)
        agenda.save(cal, R.date)
        build.rebuild_index()
    quality = {
        "date": R.date, "generated_at": config.iso(now), "status": status, "window": window,
        "counts": {"stories": len(stories), "briefs": len(brief_list), "also": len(also),
                   "planned_stories": len(plan["tier1"]), "planned_briefs": len(plan["tier2"]),
                   "clusters": (leads.get("stats") or {}).get("clusters"), "items": (leads.get("stats") or {}).get("items")},
        "sources": {"ok": sum(1 for h in leads.get("source_health") or [] if h["ok"]),
                    "total": len(leads.get("source_health") or []),
                    "failed": [f"{h['name']}: {h['error']}" for h in leads.get("source_health") or [] if not h["ok"]][:30]},
        "recall": {k: (recall or {}).get(k) for k in ("edition", "total", "matched")} |
                  {"misses": [m["event"][:160] for m in (recall or {}).get("misses") or [] if m.get("major")][:10]},
        "fallback_plan": bool(plan.get("_fallback")), "notes": qnotes + R.notes,
        "timings": R.state.get("timings"), "usage": R.engine.usage.as_dict(),
    }
    (config.PUB / "quality").mkdir(parents=True, exist_ok=True)
    (config.PUB / "quality" / f"{R.date}.json").write_text(json.dumps(quality, ensure_ascii=False, indent=1))
    R.state["edition_status"] = status
    R.state["counts"] = quality["counts"]
