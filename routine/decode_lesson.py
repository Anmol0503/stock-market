#!/usr/bin/env python3
"""Daily deep-dive lesson — advance a multi-day curriculum by ONE session per day.

A Claude-curated syllabus (dashboard/curriculum.json) of broad subjects, each split into 4-6 sessions.
A pointer (output/curriculum-state.json) advances one session per calendar day. Each run authors that
session's 4-6 in-depth chunks -> output/lesson-latest.json -> (via build_dashboard COPIES) dashboard/
lesson.json -> the reels '🎓 Learn' tab.

Guarded to advance at most once per day, so it's safe to call from BOTH run_daily.sh and (every 30 min)
run_hourly.sh — all but the first call of the day is a fast no-op. Use --force to author the next session
now (testing / "learn the next part").

Run:  python routine/decode_lesson.py [--force]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))        # so `build_dashboard` (repo root) imports when run as a script

import build_dashboard               # noqa: E402
import progress as pg                # noqa: E402  (routine/ is already on sys.path)

OUT = ROOT / "output"
DASH = ROOT / "dashboard"
ROUTINE = ROOT / "routine"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

STATE = OUT / "curriculum-state.json"
CURRIC = DASH / "curriculum.json"          # public syllabus
LESSON = OUT / "lesson-latest.json"        # today's session (copied to dashboard/lesson.json by build)
CURRIC_TMP = OUT / "curriculum.json"        # where the plan prompt writes new subjects

MIN_SUBJECTS_AHEAD = 2                       # extend the syllabus when fewer than this remain unstarted
BOOTSTRAP_COUNT = 15
EXTEND_COUNT = 10

ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"]
CLAUDE = os.environ.get("CLAUDE_BIN") or str(pathlib.Path.home() / ".local" / "bin" / "claude")
if not pathlib.Path(CLAUDE).exists():
    CLAUDE = "claude"


def claude(prompt: str, retries: int = 2, timeout: int = 900) -> str | None:
    """Run one headless Claude call; retry once on failure/timeout. Returns stdout or None."""
    for attempt in range(1, retries + 1):
        try:
            r = subprocess.run(
                [CLAUDE, "-p", prompt, "--permission-mode", "acceptEdits",
                 "--allowedTools", *ALLOWED, "--disallowedTools", "Bash", "--output-format", "text"],
                cwd=ROOT, capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode == 0:
                return r.stdout or ""
            print(f"  claude rc={r.returncode} (attempt {attempt}): {(r.stderr or '')[:200]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"  claude timeout (attempt {attempt})", file=sys.stderr)
    return None


def _load(p: pathlib.Path):
    try:
        return json.loads(p.read_text())
    except (ValueError, OSError):
        return None


def _today() -> str:
    return dt.date.today().isoformat()


def _now() -> str:
    return dt.datetime.now(IST).isoformat(timespec="seconds")


def author_subjects(existing_titles: list[str], n: int) -> list[dict]:
    """Run the curriculum planner for `n` NEW subjects (avoiding existing titles)."""
    base = (ROUTINE / "curriculum_plan_prompt.md").read_text()
    seed = ROOT / "config" / "learn.yml"
    ctx = ["\n\n=== CONTEXT ==="]
    if existing_titles:
        ctx.append("Already covered (do NOT repeat any of these): " + "; ".join(existing_titles))
    if seed.exists():
        ctx.append("The learner listed these interests — prioritise and include them where they fit:\n"
                   + seed.read_text().strip())
    ctx.append(f"Author {n} NEW subjects now, following the schema above. Write to output/curriculum.json.")
    if CURRIC_TMP.exists():
        CURRIC_TMP.unlink()
    claude(base + "\n".join(ctx))
    data = _load(CURRIC_TMP) or {}
    return data.get("subjects") or []


def merge_curriculum(new_subjects: list[dict]) -> dict:
    cur = _load(CURRIC) or {"subjects": []}
    have = {s.get("slug") for s in cur["subjects"]}
    for s in new_subjects:
        if s.get("slug") and s["slug"] not in have and s.get("sessions"):
            cur["subjects"].append(s)
            have.add(s["slug"])
    cur["generated_at"] = _now()
    CURRIC.write_text(json.dumps(cur, indent=2, ensure_ascii=False))
    return cur


def _lesson_prompt(subject: dict, session: dict, part: int, total: int, recap_ctx: str, today: str) -> str:
    base = (ROUTINE / "lesson_prompt.md").read_text()
    recap_line = (f"Earlier parts of this course covered — {recap_ctx}" if recap_ctx
                  else "This is the FIRST part of the course — no recap needed (recap_so_far = \"\").")
    return base + (
        "\n\n=== TODAY'S SESSION TO AUTHOR ===\n"
        f"Subject: {subject.get('title')} — {subject.get('blurb', '')}\n"
        f"This is Part {part} of {total}: \"{session.get('title')}\"\n"
        f"Focus of this part: {session.get('focus', '')}\n"
        f"{recap_line}\n"
        f"Today's date: {today}\n\n"
        "Author this session now as STRICT JSON to output/lesson-latest.json following the schema above. "
        "Go deep — 4-6 chunks, each with a 400-700 word `detail`. Nothing outside the file."
    )


def _recap_ctx(sessions: list[dict], ji: int) -> str:
    return "; ".join(f"Part {k + 1}: {s.get('title')} ({s.get('focus', '')})"
                     for k, s in enumerate(sessions[:ji]))


def main(argv: list[str]) -> int:
    force = "--force" in argv
    state = _load(STATE) or {"subject_index": 0, "session_index": 0, "last_advanced": ""}
    today = _today()

    if state.get("last_advanced") == today and not force:
        print("lesson: already advanced today — skipping")
        pg.set_progress("lessons", "Today's lesson is ready", 1, 1, "already done", active=False)
        return 0

    pg.set_progress("lessons", "Preparing today's deep dive", 0, 0, "")

    # 1. ensure a syllabus exists
    cur = _load(CURRIC)
    if not cur or not cur.get("subjects"):
        pg.set_progress("lessons", "Designing your curriculum", 0, 0, "first run — this takes a minute")
        subs = author_subjects([], BOOTSTRAP_COUNT)
        if not subs:
            print("WARN: curriculum authoring failed — no lesson today", file=sys.stderr)
            pg.set_progress("failed", "Curriculum planning failed", 0, 0, "", active=False)
            return 1
        cur = merge_curriculum(subs)

    subjects = cur["subjects"]
    si, ji = state["subject_index"], state["session_index"]

    # roll forward if the pointer landed past a subject's sessions
    while si < len(subjects) and ji >= len(subjects[si].get("sessions") or []):
        si, ji = si + 1, 0

    # 2. extend the syllabus if we're near the end
    if si >= len(subjects) - MIN_SUBJECTS_AHEAD:
        extra = author_subjects([s["title"] for s in subjects], EXTEND_COUNT)
        if extra:
            cur = merge_curriculum(extra)
            subjects = cur["subjects"]

    if si >= len(subjects):
        print("WARN: curriculum exhausted and could not extend", file=sys.stderr)
        return 1

    subject = subjects[si]
    sessions = subject.get("sessions") or []
    session = sessions[ji]
    part, total = ji + 1, len(sessions)

    # 3. author the session
    pg.set_progress("lessons", f"Composing: {subject['title']} · Part {part}/{total}",
                    0, 0, session.get("title", ""))
    if LESSON.exists():
        LESSON.unlink()
    claude(_lesson_prompt(subject, session, part, total, _recap_ctx(sessions, ji), today))
    lesson = _load(LESSON)
    if not lesson or not lesson.get("chunks"):
        print("WARN: lesson authoring failed — keeping last good lesson", file=sys.stderr)
        pg.set_progress("failed", "Lesson generation failed", 0, 0, "", active=False)
        return 1

    # trust the pipeline for metadata (not the model)
    lesson.update({
        "date": today, "generated_at": _now(),
        "subject_slug": subject.get("slug"), "subject_title": subject.get("title"),
        "emoji": subject.get("emoji", "🎓"), "part": part, "total_parts": total,
        "session_title": session.get("title", ""),
    })
    txt = json.dumps(lesson, indent=2, ensure_ascii=False)
    LESSON.write_text(txt)
    (OUT / f"lesson-{today}.json").write_text(txt)

    # 4. advance the pointer + stamp the day
    ji += 1
    if ji >= total:
        si, ji = si + 1, 0
    STATE.write_text(json.dumps({"subject_index": si, "session_index": ji,
                                 "last_advanced": today}, indent=2))

    # 5. rebuild the dashboard so the Learn tab shows it now (build copies lesson-latest -> lesson.json)
    pg.set_progress("publishing", "Publishing your lesson", 1, 1, subject["title"])
    try:
        build_dashboard.main()
    except SystemExit:
        pass   # build exits non-zero only if NO briefs exist yet; lesson JSON is still written
    print(f"lesson: {subject['title']} — Part {part}/{total} · {len(lesson['chunks'])} chunks", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
