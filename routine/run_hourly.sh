#!/bin/bash
# Daily Intelligence — top-up. Adds ONE trending new story per region (Global + India) to the
# live feed, every 30 minutes the laptop is on. Light + fast (only 2 stories decoded), so it never hits
# the oversized-generation drop. The heavy ~40-story decode stays on-demand (routine/run_daily.sh).
#
# Fired by ~/Library/LaunchAgents/com.dailyintel.hourly.plist (StartInterval 1800 = 30 min).
# Manual:  bash routine/run_hourly.sh
set -u

ROOT="/Users/anmolkhilwani/Learn AI/stock-market"
PY="$ROOT/.venv/bin/python"
CLAUDE="$HOME/.local/bin/claude"
TODAY=$(date +%F)

cd "$ROOT" || exit 1
mkdir -p logs

# need a base feed to append to — the full decode seeds it
if [ ! -f output/world-latest.json ]; then
  echo "no world-latest.json yet — run the full decode first; skipping hourly"
  exit 0
fi

# ---- shared single-run lock: never overlap another hourly OR the full on-demand run ----
LOCK="logs/run.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin -180 2>/dev/null)" ]; then
    echo "another run is active — skipping this hourly tick"
    exit 0
  fi
  rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" 2>/dev/null || { echo "could not acquire lock"; exit 0; }
fi
trap 'rmdir "'"$LOCK"'" 2>/dev/null' EXIT

progress () { "$PY" routine/progress.py "$@" >/dev/null 2>&1 || true; }

echo "=== hourly top-up started $(date '+%F %T') ==="
export CLAUDE_BIN="$CLAUDE"; [ -x "$CLAUDE_BIN" ] || export CLAUDE_BIN="claude"

# ---- fresh raw pull so we can spot what's trending this hour ----
progress fetching "Checking what's trending" 0 0 "pulling fresh feeds"
"$PY" fetch_world.py || echo "WARN: fetch_world failed"

# ---- decode 1 trending new story per region + append + rebuild ----
if [ -x "$CLAUDE" ] || command -v claude >/dev/null 2>&1; then
  "$PY" routine/hourly_top.py || echo "WARN: hourly top-up failed"
else
  echo "WARN: claude CLI not found — no hourly story added"
fi

# ---- advance the deep-dive course when the reader marked the current part complete (reader-paced) ----
#      decode_lesson.py only authors the next part if output/lesson-next.flag exists (set by the reels
#      "Mark complete" button via server.py) — otherwise it's a fast no-op. First run bootstraps Part 1.
if [ -x "$CLAUDE" ] || command -v claude >/dev/null 2>&1; then
  "$PY" routine/decode_lesson.py || echo "WARN: lesson generation failed"
fi

# ---- publish the 🎓 Learn course as a downloadable Kindle EPUB (+ auto-email new parts if .env has creds) ----
"$PY" make_kindle.py || echo "WARN: kindle build failed"

# ---- always stamp the public status record (so 'last checked' advances even if nothing was added) ----
"$PY" routine/publish_status.py hourly >/dev/null 2>&1 || true

# ---- publish (best-effort) ----
if [ -d .git ] && git remote get-url origin >/dev/null 2>&1; then
  git add -A >/dev/null 2>&1
  if git diff --cached --quiet; then
    echo "nothing new to publish this hour"
  else
    git commit -m "hourly: +trending stories $TODAY $(date '+%H:%M')" >/dev/null
    git pull --rebase --autostash origin main >/dev/null 2>&1 || true
    git push origin main && echo "published hourly top-up" || echo "WARN: git publish failed"
  fi
fi

progress done "Up to date" 0 0 "hourly top-up $(date '+%H:%M')" false
echo "=== hourly top-up finished $(date '+%F %T') ==="
