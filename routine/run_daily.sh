#!/bin/bash
# Daily Intelligence — full decoded pipeline (regenerates ~every 2 hours while the laptop is awake).
# Fired by ~/Library/LaunchAgents/com.dailyintel.daily.plist on login/wake (RunAtLoad + 30-min
# StartInterval). The freshness guard below makes every firing a no-op unless the last brief is older
# than ~110 min, so the net effect is a real run about every 2 hours (and once at first open).
#
# Manual:  bash routine/run_daily.sh --force     (--force regenerates even if the brief is fresh)
set -u

ROOT="/Users/anmolkhilwani/Learn AI/stock-market"
PY="$ROOT/.venv/bin/python"
CLAUDE="$HOME/.local/bin/claude"
TODAY=$(date +%F)
FRESH_MIN=110          # skip a run if the brief was regenerated less than this many minutes ago

cd "$ROOT" || exit 1
mkdir -p logs

# ---- freshness guard: run at most ~every 2h (a 30-min wake tick past 110 min triggers the next run) ----
if [ "${1:-}" != "--force" ] && [ -f "output/brief-latest.json" ] \
   && [ -n "$(find output/brief-latest.json -mmin -$FRESH_MIN 2>/dev/null)" ]; then
  exit 0
fi

# ---- single-run lock: NEVER let two pipelines overlap (overlap corrupts the output files and
#      stacks duplicate commits — the "concurrent process" bug). Atomic mkdir = the lock. ----
LOCK="logs/run.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin -180 2>/dev/null)" ]; then
    echo "another run is active ($LOCK) — exiting"
    exit 0
  fi
  echo "stale lock (>3h) — reclaiming"
  rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" 2>/dev/null || { echo "could not acquire lock — exiting"; exit 0; }
fi
trap 'rmdir "'"$LOCK"'" 2>/dev/null' EXIT   # release the lock however we exit

echo "=== daily run started $(date '+%F %T') ==="

# ---- wait for network (fresh wake: Wi-Fi can lag) ----
for i in $(seq 1 24); do
  if curl -s --max-time 5 -o /dev/null "https://query1.finance.yahoo.com" 2>/dev/null \
     || curl -s --max-time 5 -o /dev/null "https://www.google.com" 2>/dev/null; then
    break
  fi
  echo "  waiting for network ($i/24)..."
  sleep 5
done

# progress() — one-liner that updates logs/progress.json for the Update Center live tracker
progress () { "$PY" routine/progress.py "$@" >/dev/null 2>&1 || true; }

# ---- deterministic data steps ----
progress fetching "Gathering news & data" 0 0 "world + market feeds"
"$PY" fetch_world.py          || echo "WARN: fetch_world failed"
"$PY" fetch.py                || echo "WARN: fetch failed"
progress analyzing "Computing stock signals" 0 0 ""
"$PY" analyze_stock.py --all  || echo "WARN: analyze failed"

# ---- the analyst (headless Claude) writes the briefs, DECODED IN SMALL BATCHES ----
# routine/decode_world.py: select ~20+20 headlines, decode ~5 per call (so no response is big enough
# to drop mid-stream), write the markets brief, then merge — updating the live tracker at every step.
export CLAUDE_BIN="$CLAUDE"; [ -x "$CLAUDE_BIN" ] || export CLAUDE_BIN="claude"
if [ -x "$CLAUDE" ] || command -v claude >/dev/null 2>&1; then
  "$PY" routine/decode_world.py || echo "WARN: decode failed (kept last good brief)"
else
  echo "WARN: claude CLI not found — briefs not regenerated"
fi

# ---- sanity: did the brief actually advance to today? ----
if ! grep -q "\"date\": \"$TODAY\"" output/brief-latest.json 2>/dev/null; then
  echo "WARN: brief-latest.json is not dated $TODAY — publishing whatever exists"
fi

# ---- publish + archive (world.json / brief.json / reels.json + dated archive) ----
progress publishing "Publishing to your phone" 0 0 ""
"$PY" build_dashboard.py      || echo "WARN: publish failed"

# ---- generate ready-to-post Instagram carousels (best-effort — never abort the run) ----
"$PY" make_social.py          || echo "WARN: social generation failed"

# ---- email once per day (the pipeline now runs every ~2h; don't spam the inbox) ----
if [ -f .env ]; then
  if [ -f "logs/emailed-$TODAY" ]; then
    echo "already emailed today — skipping email"
  elif "$PY" send.py; then
    touch "logs/emailed-$TODAY"
  else
    echo "WARN: email failed (will retry next run)"
  fi
else
  echo "no .env — skipping email"
fi

# ---- publish to GitHub Pages (best-effort — never abort the run) ----
if [ -d .git ] && git remote get-url origin >/dev/null 2>&1; then
  git add -A >/dev/null 2>&1
  if git diff --cached --quiet; then
    echo "nothing new to publish"
  else
    git commit -m "daily: $TODAY" >/dev/null
    git pull --rebase --autostash origin main >/dev/null 2>&1 || true   # avoid clobbering the hourly cloud job
    git push origin main \
      && echo "published to GitHub Pages" \
      || echo "WARN: git publish failed (self-retries on the next daily run)"
  fi
else
  echo "no git remote — skipping publish"
fi

progress done "Up to date" 0 0 "last run finished $(date '+%H:%M')" false
echo "=== daily run finished $(date '+%F %T') ==="
