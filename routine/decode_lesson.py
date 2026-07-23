#!/usr/bin/env python3
"""Deep-dive course — a growing catalog of lesson parts the reader walks at their own pace.

A Claude-curated syllabus (dashboard/curriculum.json) of broad subjects, each split into 4-6 sessions.
This authors those sessions IN ORDER into a public catalog (dashboard/lessons.json) — every part, kept
forever, fully readable. The reels '🎓 Learn' tab reads that catalog and lets the reader move through it
CLIENT-SIDE (so "next part" is instant and works even on the static public site — no server round-trip).

Why a catalog + buffer instead of "author on demand when the reader taps complete": the tap can't reliably
reach the pipeline (the reader may be on the static GitHub Pages site, or a stale local server). So instead
we keep a BUFFER of parts authored AHEAD of the reader, plus a gentle daily drip, so the next part is
always already published. The reader's position (best-effort, localhost only) comes from
output/lesson-progress.json (server.py writes it) and just tunes how far ahead we stay.

Run:  python routine/decode_lesson.py [--force]   (--force authors one more part right now)
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
import usage                         # noqa: E402  (routine/usage.py — token/cost ledger)

OUT = ROOT / "output"
DASH = ROOT / "dashboard"
ROUTINE = ROOT / "routine"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

STATE = OUT / "curriculum-state.json"       # pipeline pointer: which subject/session is next + authored_seq
CURRIC = DASH / "curriculum.json"           # public syllabus
CATALOG = DASH / "lessons.json"             # public catalog of ALL authored parts (the reader's library)
LESSON_TMP = OUT / "lesson-latest.json"     # Claude writes ONE part here; we read + append to the catalog
CURRIC_TMP = OUT / "curriculum.json"        # where the plan prompt writes new subjects
PROGRESS = OUT / "lesson-progress.json"     # best-effort {completed_seq} the reels post (localhost only)

MIN_SUBJECTS_AHEAD = 2                       # extend the syllabus when fewer than this remain unstarted
BOOTSTRAP_COUNT = 15
EXTEND_COUNT = 10

AHEAD = 4            # keep this many parts published beyond where the reader has read
DRIP_CAP = 30       # ...and drip +1/day up to this many beyond the reader (bounds an inactive reader)
MAX_PER_RUN = 2     # author at most this many parts in a single run (bounds wall-clock per tick)

ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"]
CLAUDE = os.environ.get("CLAUDE_BIN") or str(pathlib.Path.home() / ".local" / "bin" / "claude")
if not pathlib.Path(CLAUDE).exists():
    CLAUDE = "claude"


def claude(prompt: str, retries: int = 2, timeout: int = 900, label: str = "lesson") -> str | None:
    """Run one headless Claude call (logging token/cost to the usage ledger); returns result text or None."""
    return usage.run_claude(prompt, claude_bin=CLAUDE, allowed=ALLOWED, cwd=ROOT,
                            label=label, retries=retries, timeout=timeout)


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
        "\n\n=== SESSION TO AUTHOR ===\n"
        f"Subject: {subject.get('title')} — {subject.get('blurb', '')}\n"
        f"This is Part {part} of {total}: \"{session.get('title')}\"\n"
        f"Focus of this part: {session.get('focus', '')}\n"
        f"{recap_line}\n"
        f"Today's date: {today}\n\n"
        "Author this session now as STRICT JSON to output/lesson-latest.json following the schema above. "
        "Go deep — 4-6 chunks, each with the short-paragraph `detail` + `example` + `points`. Nothing outside the file."
    )


def _recap_ctx(sessions: list[dict], ji: int) -> str:
    return "; ".join(f"Part {k + 1}: {s.get('title')} ({s.get('focus', '')})"
                     for k, s in enumerate(sessions[:ji]))


def _ensure_syllabus():
    cur = _load(CURRIC)
    if cur and cur.get("subjects"):
        return cur
    pg.set_progress("lessons", "Designing your curriculum", 0, 0, "first run — this takes a minute")
    subs = author_subjects([], BOOTSTRAP_COUNT)
    return merge_curriculum(subs) if subs else None


def _author_one(subjects: list[dict], si: int, ji: int, seq: int, today: str):
    """Author ONE part at pointer (si, ji). Returns (part_dict, next_si, next_ji) or None on failure.
    May extend/roll the syllabus. `subjects` may be mutated (extended)."""
    # roll forward past a finished subject
    while si < len(subjects) and ji >= len(subjects[si].get("sessions") or []):
        si, ji = si + 1, 0
    # extend the syllabus if we're near the end
    if si >= len(subjects) - MIN_SUBJECTS_AHEAD:
        extra = author_subjects([s["title"] for s in subjects], EXTEND_COUNT)
        if extra:
            merge_curriculum(extra)
            subjects[:] = (_load(CURRIC) or {}).get("subjects") or subjects
    if si >= len(subjects):
        print("WARN: curriculum exhausted and could not extend", file=sys.stderr)
        return None

    subject = subjects[si]
    sessions = subject.get("sessions") or []
    session = sessions[ji]
    part, total = ji + 1, len(sessions)

    pg.set_progress("lessons", f"Writing: {subject['title']} · Part {part}/{total}",
                    0, 0, session.get("title", ""))
    if LESSON_TMP.exists():
        LESSON_TMP.unlink()
    claude(_lesson_prompt(subject, session, part, total, _recap_ctx(sessions, ji), today))
    lesson = _load(LESSON_TMP)
    if not lesson or not lesson.get("chunks"):
        print(f"WARN: authoring failed at seq {seq} ({subject['title']} P{part}) — stopping run", file=sys.stderr)
        return None

    lesson.update({
        "seq": seq, "date": today, "generated_at": _now(),
        "subject_slug": subject.get("slug"), "subject_title": subject.get("title"),
        "emoji": subject.get("emoji", "🎓"), "part": part, "total_parts": total,
        "session_title": session.get("title", ""),
    })
    ji += 1
    if ji >= total:
        si, ji = si + 1, 0
    return lesson, si, ji


def _write_catalog(parts: list[dict]):
    CATALOG.write_text(json.dumps(
        {"generated_at": _now(), "count": len(parts), "parts": parts}, indent=2, ensure_ascii=False))


def main(argv: list[str]) -> int:
    force = "--force" in argv
    today = _today()

    state = _load(STATE) or {}
    si = state.get("subject_index", 0)
    ji = state.get("session_index", 0)
    last_date = state.get("last_authored_date", "")

    catalog = _load(CATALOG) or {"parts": []}
    parts = catalog.get("parts") or []
    authored_seq = state.get("authored_seq")
    if authored_seq is None:                       # derive on first run / migration
        authored_seq = len(parts)

    # ONE FRESH SUBJECT PER CALENDAR DAY: each day, author every remaining session of the subject at the
    # pointer so a whole new lesson (all its parts) is ready — the reader wanted a complete subject daily,
    # delivered together to the Kindle. `--force` authors a subject now regardless of the daily gate.
    if last_date == today and not force:
        print(f"lesson: today's subject already authored ({authored_seq} parts) — one subject/day")
        pg.set_progress("lessons", "Today's lesson is ready", 1, 1, "one complete subject per day", active=False)
        return 0

    pg.set_progress("lessons", "Writing today's lesson", 0, 0, f"{authored_seq} parts so far")
    cur = _ensure_syllabus()
    if not cur:
        print("WARN: curriculum authoring failed — no lessons this run", file=sys.stderr)
        pg.set_progress("failed", "Curriculum planning failed", 0, 0, "", active=False)
        return 1
    subjects = cur["subjects"]

    SAFETY_CAP = 8      # a subject is 4-6 sessions; this just backstops a runaway loop
    made = 0
    for _ in range(SAFETY_CAP):
        res = _author_one(subjects, si, ji, authored_seq + 1, today)
        if not res:
            break
        lesson, si, ji = res
        parts.append(lesson)
        authored_seq = lesson["seq"]
        made += 1
        # persist incrementally so a mid-run crash keeps what we made
        _write_catalog(parts)
        STATE.write_text(json.dumps({
            "subject_index": si, "session_index": ji,
            "authored_seq": authored_seq, "last_authored_date": today}, indent=2))
        if ji == 0:     # pointer rolled to the next subject's start → this subject is COMPLETE, stop for the day
            break

    if made == 0:
        pg.set_progress("failed", "Lesson generation failed", 0, 0, "", active=False)
        return 1

    pg.set_progress("publishing", "Publishing today's lesson", 1, 1, f"{authored_seq} parts")
    try:
        build_dashboard.main()
    except SystemExit:
        pass   # build exits non-zero only if NO briefs exist yet; the catalog is already written
    print(f"lesson: authored {made} new part(s) this subject → {authored_seq} total", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
