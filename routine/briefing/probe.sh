#!/usr/bin/env bash
# Phase-0 probe for the Morning Briefing: what can a Claude Code routine VM actually do?
#
#   bash routine/briefing/probe.sh
#
# Checks the toolchain, whether a child `claude -p` works inside the VM (the key question for the
# pipeline design), which news sources answer from cloud IPs, and whether edge-tts can synthesise speech.
# Writes /tmp/probe/report.md, pushes it to branch spike/probe, and touches /tmp/probe/DONE at the end.
# Prints only names, status codes and short results: never environment VALUES or tokens.
set -u
OUT=/tmp/probe
mkdir -p "$OUT"
R="$OUT/report.md"
: > "$R"
log() { echo "$*" | tee -a "$R"; }
sec() { log ""; log "## $*"; }

log "# Morning Briefing probe — $(date -u +%Y-%m-%dT%H:%M:%SZ)"

sec "Toolchain"
{
  uname -srm
  echo "cpus: $(nproc 2>/dev/null)"
  free -h 2>/dev/null | sed -n 2p | awk '{print "mem: "$2}'
  df -h / 2>/dev/null | tail -1 | awk '{print "disk free: "$4}'
  echo "python: $(python3 --version 2>&1)"
  echo "node: $(node --version 2>&1) · npm: $(npm --version 2>&1)"
  echo "ffmpeg: $(ffmpeg -version 2>/dev/null | head -1 || true)"
  echo "chrome: $(command -v google-chrome chromium chromium-browser 2>/dev/null | head -1)"
  if sudo -n true 2>/dev/null; then echo "sudo: yes"; else echo "sudo: no"; fi
  echo "claude: $(command -v claude) $(claude --version 2>&1 | head -1)"
} 2>&1 | tee -a "$R"

sec "Environment variable NAMES (values never printed)"
env | cut -d= -f1 | sort | tr '\n' ' ' | tee -a "$R"
log ""

# ---- child claude -p --------------------------------------------------------------------------------
summ() {  # summarise a claude --output-format json envelope without dumping it
  python3 - "$1" <<'PY'
import json, sys
p = sys.argv[1]
try:
    raw = open(p).read()
    d = json.loads(raw)
except Exception as e:
    print(f"  not JSON ({e}); first 300 chars: {open(p).read()[:300]!r}")
    sys.exit()
so = d.get("structured_output")
print(f"  subtype={d.get('subtype')} is_error={d.get('is_error')} cost=${d.get('total_cost_usd')} "
      f"ms={d.get('duration_ms')} model_usage={list((d.get('modelUsage') or {}).keys())}")
print(f"  result: {str(d.get('result'))[:300]!r}")
if so is not None:
    print(f"  structured_output: {json.dumps(so)[:400]}")
PY
}
SCRUB=(-u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_CHILD_SESSION
       -u CLAUDE_CODE_SESSION_ATTENDED -u CLAUDE_CODE_SSE_PORT -u CLAUDE_CODE_MESSAGING_SOCKET
       -u CLAUDE_CODE_MESSAGING_TOKEN -u CLAUDE_PID -u CLAUDE_EFFORT)
SCHEMA='{"type":"object","properties":{"nifty_close":{"type":"string"},"as_of":{"type":"string"},"source_url":{"type":"string"},"wiki_first_event":{"type":"string"}},"required":["nifty_close","as_of","source_url","wiki_first_event"],"additionalProperties":false}'
cd /tmp || exit 1

sec "claude -p · T1 plain (sonnet)"
echo 'Reply with exactly the word PONG.' | timeout 240 claude -p --output-format json --no-session-persistence \
  --model claude-sonnet-5-5 > "$OUT/t1.json" 2> "$OUT/t1.err"; log "  exit=$?"
summ "$OUT/t1.json" | tee -a "$R"; log "  stderr: $(tail -c 300 "$OUT/t1.err" | tr '\n' ' ')"

sec "claude -p · T2 parent-session env vars scrubbed"
echo 'Reply with exactly the word PONG.' | env "${SCRUB[@]}" timeout 240 claude -p --output-format json \
  --no-session-persistence --model claude-sonnet-5-5 > "$OUT/t2.json" 2> "$OUT/t2.err"; log "  exit=$?"
summ "$OUT/t2.json" | tee -a "$R"; log "  stderr: $(tail -c 300 "$OUT/t2.err" | tr '\n' ' ')"

sec "claude -p · T3 web tools + json-schema + safe-mode (the research-call shape)"
printf '%s' "Use WebSearch to find the most recent closing value of India's Nifty 50 index (value + date + the URL you used). Then use WebFetch on https://en.wikipedia.org/wiki/Portal:Current_events and report the first news event listed. Answer in the required JSON." \
  | timeout 420 claude -p --output-format json --no-session-persistence --model claude-sonnet-5-5 --safe-mode \
    --setting-sources "" --strict-mcp-config --tools "WebSearch,WebFetch" --json-schema "$SCHEMA" \
    > "$OUT/t3.json" 2> "$OUT/t3.err"; log "  exit=$?"
summ "$OUT/t3.json" | tee -a "$R"; log "  stderr: $(tail -c 300 "$OUT/t3.err" | tr '\n' ' ')"

sec "claude -p · T4 opus · high effort · no tools · json-schema"
printf '%s' 'Return ok=true and the model name you are.' | timeout 240 claude -p --output-format json \
  --no-session-persistence --model claude-opus-5-5 --effort high --tools "" --setting-sources "" --strict-mcp-config \
  --json-schema '{"type":"object","properties":{"ok":{"type":"boolean"},"model":{"type":"string"}},"required":["ok","model"],"additionalProperties":false}' \
  > "$OUT/t4.json" 2> "$OUT/t4.err"; log "  exit=$?"
summ "$OUT/t4.json" | tee -a "$R"; log "  stderr: $(tail -c 300 "$OUT/t4.err" | tr '\n' ' ')"

# ---- sources from cloud IPs ---------------------------------------------------------------------------
sec "Source reachability from this VM (HTTP code · seconds · bytes)"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
cat > "$OUT/urls.txt" <<'EOF'
BBC World|http://feeds.bbci.co.uk/news/world/rss.xml
BBC India|https://feeds.bbci.co.uk/news/world/asia/india/rss.xml
BBC F1|http://feeds.bbci.co.uk/sport/formula1/rss.xml
BBC Cricket|https://feeds.bbci.co.uk/sport/cricket/rss.xml
Al Jazeera|https://www.aljazeera.com/xml/rss/all.xml
Guardian World|https://www.theguardian.com/world/rss
NPR World|https://feeds.npr.org/1004/rss.xml
DW|https://rss.dw.com/rdf/rss-en-all
NYT World|https://rss.nytimes.com/services/xml/rss/nyt/World.xml
GN India top|https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en
GN World topic|https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en
GN Reuters 1d|https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en
GN AP 1d|https://news.google.com/rss/search?q=site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en
The Hindu|https://www.thehindu.com/news/national/feeder/default.rss
Indian Express|https://indianexpress.com/feed/
Livemint|https://www.livemint.com/rss/news
TOI|https://timesofindia.indiatimes.com/rssfeedstopstories.cms
NDTV|https://feeds.feedburner.com/ndtvnews-top-stories
Business Standard|https://www.business-standard.com/rss/home_page_top_stories.rss
ET Markets|https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms
Moneycontrol|https://www.moneycontrol.com/rss/latestnews.xml
Scroll|https://scroll.in/feed
ThePrint|https://theprint.in/feed/
RBI|https://www.rbi.org.in/pressreleases_rss.xml
PIB|https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3
SEBI|https://www.sebi.gov.in/sebirss.xml
Fed|https://www.federalreserve.gov/feeds/press_all.xml
ECB|https://www.ecb.europa.eu/rss/press.html
HN firebase|https://hacker-news.firebaseio.com/v0/topstories.json
HN algolia|https://hn.algolia.com/api/v1/search?tags=front_page
Techmeme|https://www.techmeme.com/feed.xml
The Verge|https://www.theverge.com/rss/index.xml
Ars|http://feeds.arstechnica.com/arstechnica/index
arXiv cs.AI|https://rss.arxiv.org/rss/cs.AI
Nature|https://www.nature.com/nature.rss
Science|https://www.science.org/rss/news_current.xml
ScienceDaily|https://www.sciencedaily.com/rss/top/science.xml
F1 official|https://www.formula1.com/en/latest/all.xml
Autosport|https://www.autosport.com/rss/f1/news/
Jolpica|https://api.jolpi.ca/ergast/f1/current/last/results.json
Cricinfo stories|https://www.espncricinfo.com/rss/content/story/feeds/0.xml
Cricinfo scores|https://static.espncricinfo.com/rss/livescores.xml
Yahoo chart|https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=5d&interval=1d
Stooq|https://stooq.com/q/l/?s=%5Ensei&f=sd2t2ohlcv&h&e=csv
Wikipedia API|https://en.wikipedia.org/w/api.php?action=parse&page=Portal:Current_events/2026_November_1&prop=wikitext&format=json&formatversion=2
Kagi News|https://kite.kagi.com/kite.json
GDELT|https://api.gdeltproject.org/api/v2/doc/doc?query=election&mode=artlist&format=json&timespan=24h&maxrecords=5
Guardian API (no key)|https://content.guardianapis.com/search
Reddit worldnews|https://www.reddit.com/r/worldnews/hot/.rss
nitter|https://nitter.net/Reuters/rss
PRS India|https://prsindia.org/
Semafor|https://www.semafor.com/
GitHub release dl|https://github.com/cli/cli/releases/latest
npm registry|https://registry.npmjs.org/remotion
PyPI|https://pypi.org/simple/edge-tts/
EOF
probe_one() {
  local name="${1%%|*}" url="${1#*|}"
  local res
  res=$(curl -s -o /dev/null -L --max-time 15 -A "$UA" -w '%{http_code} %{time_total} %{size_download}' "$url" 2>/dev/null || echo "ERR")
  printf '%-22s %s\n' "$name" "$res"
}
export -f probe_one
export UA
xargs -a "$OUT/urls.txt" -d '\n' -P 8 -I{} bash -c 'probe_one "$@"' _ {} 2>/dev/null | sort | tee -a "$R"

# ---- edge-tts --------------------------------------------------------------------------------------
sec "edge-tts (en-IN-NeerjaNeural, word boundaries)"
python3 -m pip install -q edge-tts >/dev/null 2>&1 || log "  pip install edge-tts failed"
timeout 120 python3 - <<'PY' 2>&1 | tee -a "$R"
import asyncio
try:
    import edge_tts
except Exception as e:
    print(f"  import failed: {e}"); raise SystemExit
async def main():
    words, audio = 0, bytearray()
    c = edge_tts.Communicate("Why would the Reserve Bank cut rates while prices are still rising? Here is the short answer.",
                             "en-IN-NeerjaNeural", boundary="WordBoundary")
    async for ch in c.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words += 1
    open("/tmp/probe/tts.mp3", "wb").write(audio)
    print(f"  ok: {len(audio)} bytes of audio, {words} word-boundary events (edge-tts {getattr(edge_tts, '__version__', '?')})")
try:
    asyncio.run(main())
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
PY

sec "Done"
log "finished $(date -u +%H:%M:%SZ)"

# ---- publish the report to a branch (never main) ------------------------------------------------------
cd - >/dev/null 2>&1 || true
REPO=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$REPO" ]; then
  cd "$REPO"
  cur=$(git rev-parse --abbrev-ref HEAD)
  git stash -u -q 2>/dev/null || true
  git checkout -q -B spike/probe
  mkdir -p spike && cp "$R" spike/probe-report.md
  git add spike/probe-report.md
  git commit -q -m "probe report $(date -u +%FT%TZ)" || true
  if git push -q -f origin spike/probe 2>"$OUT/push.err"; then
    echo "pushed report to spike/probe"
  elif git push -q -f origin spike/probe:claude/spike-probe 2>>"$OUT/push.err"; then
    echo "pushed report to claude/spike-probe"
  else
    echo "push failed: $(tail -c 300 "$OUT/push.err")"
  fi
  git checkout -q "$cur" 2>/dev/null || true
fi
touch "$OUT/DONE"
