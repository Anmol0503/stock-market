#!/bin/bash
# Daily Intelligence — full morning pipeline.
# Fired by ~/Library/LaunchAgents/com.dailyintel.daily.plist on login/wake (RunAtLoad + StartInterval),
# so it runs "the first time you open your laptop each day". The guard below makes every extra firing
# a no-op once today's brief exists; failed runs self-retry on the next 30-min tick.
#
# Manual:  bash routine/run_daily.sh --force     (--force regenerates even if today's brief exists)
set -u

ROOT="/Users/anmolkhilwani/Learn AI/stock-market"
PY="$ROOT/.venv/bin/python"
CLAUDE="$HOME/.local/bin/claude"
TODAY=$(date +%F)

cd "$ROOT" || exit 1
mkdir -p logs

# ---- once-per-day guard (the archive file only exists after a successful publish) ----
if [ "${1:-}" != "--force" ] && [ -f "dashboard/archive/brief-$TODAY.json" ]; then
  exit 0
fi

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

# ---- deterministic data steps ----
"$PY" fetch_world.py          || echo "WARN: fetch_world failed"
"$PY" fetch.py                || echo "WARN: fetch failed"
"$PY" analyze_stock.py --all  || echo "WARN: analyze failed"

# ---- the analyst (headless Claude on the Max subscription) writes both briefs ----
if [ -x "$CLAUDE" ] || command -v claude >/dev/null 2>&1; then
  "$CLAUDE" -p "$(cat routine/claude_routine.md)" \
    --permission-mode acceptEdits \
    --allowedTools "Read" "Write" "Edit" "Glob" "Grep" "WebSearch" "WebFetch" \
    --disallowedTools "Bash" \
    --output-format text \
    || echo "WARN: claude brief generation failed"
else
  echo "WARN: claude CLI not found — briefs not regenerated"
fi

# ---- sanity: did the brief actually advance to today? ----
if ! grep -q "\"date\": \"$TODAY\"" output/brief-latest.json 2>/dev/null; then
  echo "WARN: brief-latest.json is not dated $TODAY — publishing whatever exists"
fi

# ---- publish + archive (also writes dashboard/headlines.json) ----
"$PY" build_dashboard.py      || echo "WARN: publish failed"

# ---- email only when credentials exist ----
if [ -f .env ]; then
  "$PY" send.py               || echo "WARN: email failed"
else
  echo "no .env — skipping email"
fi

# ---- publish to GitHub Pages (best-effort — never abort the run) ----
if [ -d .git ] && git remote get-url origin >/dev/null 2>&1; then
  git add -A >/dev/null 2>&1
  if git diff --cached --quiet; then
    echo "nothing new to publish"
  else
    git commit -m "daily: $TODAY" >/dev/null \
      && git push origin main \
      && echo "published to GitHub Pages" \
      || echo "WARN: git publish failed (self-retries on the next daily run)"
  fi
else
  echo "no git remote — skipping publish"
fi

echo "=== daily run finished $(date '+%F %T') ==="
