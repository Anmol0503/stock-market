# stock-market repo: operating guide

## What's live
**The Morning Briefing** is the one live product. A daily deep-research news edition for one reader in India,
ready by about 6:00 AM IST:
- **Content:** 5 big stories (full explainer, a "Learn the idea" lesson with a worked example, and a narrated
  reel that teaches the same idea), briefs for 8 sections,
  one-liners, a quiz, and "still developing" threads.
- **Code:** `routine/briefing/`, run as `python3 -m routine.briefing`.
- **Schedule:** a Claude Code cloud routine at 04:05 IST follows `routine/briefing/RUNBOOK.md`.
- **Output:** `dashboard/briefing/` (editions, `index.json`, `threads.json`, `calendar.json`, `quality/`).
- **App:** `dashboard/reels/index.html` (old digests: `dashboard/reels/digest.html`).

Legacy code, kept for history and not running: Daily Digest (`routine/digest.py`, `dashboard/digest/`),
World/Markets briefs (`analyze/`, `build_dashboard.py`), Learn course, Horizon series, and the Kindle senders.
Don't revive them without asking.

## Rules
- **Public repo + GitHub Pages.** Never write secrets, email addresses, personal data or local paths into
  the repo, especially under `dashboard/`.
- **Two writers.**
  - The cloud routine commits ONLY `dashboard/briefing/`; `publish.py` refuses anything else.
  - The Mac commits code. Never run `git add -A`, `git add .` or `git checkout -- .`.
  - Push from the Mac with `git -c credential.helper= -c credential.helper='!gh auth git-credential' push`
    (gh lives at `~/miniforge3/bin/gh`, account Anmol0503).
- **Don't hand-edit `dashboard/briefing/`.** The pipeline owns it.
- **No fact from model memory.** Every fact in an edition traces to a dated source via claim ids.
  `build.py` enforces it: dated sources, 3+ outlets per big story, no relative dates, numbers must come from
  the claims.
- **Claude calls** are headless `claude -p` on the Max plan (`engine.py`). Never use `--bare`, because it
  breaks subscription login.
- **Never ship UI without rendering it** at 390×664, 375×548 and 412×780 (`tests/ui/`).

## Working on it
- **Tests** (fake engine, no network, under 1 s): `.venv/bin/python -m pytest tests/briefing -q`
- **Dry run on the Mac without touching the repo:**
  `BRIEFING_PUB_DIR=/tmp/b/pub BRIEFING_OUT_DIR=/tmp/b/out .venv/bin/python -m routine.briefing run`
- **Sources only:** `python3 -m routine.briefing gather`
- **Pipeline map:**
  - `gather.py`, `cluster.py`, `wiki.py`, `markets.py`, `sport.py`: sweep and group sources (code only).
  - `ranking.py`: shortlist.
  - `engine.py`: model calls; models per role are in `config.ROLES`.
  - `prompts/*.md`: house style and step prompts.
  - `stages.py`: resumable state machine with a 05:40 IST deadline.
  - `build.py`: quality rules.
  - `threads.py`, `agenda.py`: memory.
  - `publish.py`.
