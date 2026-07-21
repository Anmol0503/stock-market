#!/bin/bash
# Daily Intelligence — Mac-side maintenance (Learn course + Kindle), every 30 minutes the laptop is on.
#
# NOTE: the NEWS top-up now runs 24/7 in the CLOUD (RemoteTrigger routine, hourly) so it keeps publishing
# even when this laptop is off. To avoid doing the same expensive decode in two places, this Mac run no
# longer fetches/decodes news — it only advances the 🎓 Learn course and (re)builds + emails the Kindle
# EPUB, which needs the local .env secrets the cloud can't have. It still pulls the cloud's news pushes
# before publishing its own changes.
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

echo "=== mac maintenance (Learn + Kindle) started $(date '+%F %T') ==="
export CLAUDE_BIN="$CLAUDE"; [ -x "$CLAUDE_BIN" ] || export CLAUDE_BIN="claude"

# ---- NEWS is handled by the cloud routine now (see header) — nothing to fetch/decode here. ----
progress fetching "Refreshing Learn course" 0 0 "cloud handles news; Mac does Learn + Kindle"

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
    git commit -m "mac: Learn/Kindle refresh $TODAY $(date '+%H:%M')" >/dev/null
    git pull --rebase --autostash origin main >/dev/null 2>&1 || true
    git push origin main && echo "published Mac maintenance" || echo "WARN: git publish failed"
  fi
fi

progress done "Up to date" 0 0 "Learn/Kindle refresh $(date '+%H:%M')" false
echo "=== mac maintenance finished $(date '+%F %T') ==="
