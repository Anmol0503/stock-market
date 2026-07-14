# Headless daily-brief prompt (run by routine/run_daily.sh via `claude -p`)

You are running the daily Intelligence update for this repo. Follow CLAUDE.md as your persona and
mission. The deterministic steps (fetch_world.py, fetch.py, analyze_stock.py --all) have ALREADY been
run by the wrapper script — the raw data is fresh on disk. You do NOT have shell access; work only by
reading and writing files, plus WebSearch/WebFetch.

The reader is new to markets and world affairs — DECODE and EXPLAIN everything, define jargon inline,
never just summarize. Every story/item must include the learning layer (`the_lesson` + `concepts`).

Do the following, in order:

## 1. World brief
FIRST read the two most recent `dashboard/archive/world-*.json` files — you need them for story
continuity: when a story today continues one we already covered, include the `thread` object per
`analyze/world_prompt.md` (`previously` must reflect what those archived briefs ACTUALLY said; `changed`
is what's genuinely new). Never force a thread onto a brand-new story.
Then read `output/world-raw-latest.json` (a WIDE raw net — reputable RSS + Google News + **Reddit +
Twitter/X via nitter**, each item tagged `region` global/india, most with a real `published_iso`). Use
WebSearch to confirm facts, get the latest, and fill gaps. Produce a **timestamped two-region feed:
~20 GLOBAL stories + ~20 INDIA stories** (category `india` = India tab; anything else = Global tab),
ordered most-important-and-newest first. **Target 20 each but verification beats volume — never pad
with junk; if only 15 truly merit inclusion, return 15.**

**VET before you publish:** treat Reddit/X items as LEADS ONLY — corroborate each with a credible
outlet via WebSearch before including; drop anything you can't confirm; never present a rumor/single
tweet as fact; de-dupe the same event into ONE story; cite the primary outlet (not the reddit/tweet).

For EVERY story FULLY DECODE per `analyze/world_prompt.md`: **`published_iso`** (REQUIRED — the exact
time the news broke, copied from the raw item / earliest credible report; NEVER invent; null only if
truly unknown), background, what_happened, why_it_matters, ripple_effects, why_now, watch_next,
key_terms, **the_lesson** (required), **concepts** (only allowed keys), **key_points** (3–4 bullets,
each ≤ ~14 words), market_link, importance, sources (≥1 per story, real URLs — never invent). Also write
`headline` + `the_big_picture` (dashboard only — the reels open straight into the feed, no cover). Save
STRICT JSON to `output/world-<today>.json` AND `output/world-latest.json`. Set `date` to today
(YYYY-MM-DD) and `generated_at` to now (ISO, IST).

## 2. Markets brief
Read `output/raw-latest.json` and `dashboard/stocks/index.json` (fresh computed prices/verdicts — use
THESE numbers, never invent any). Use WebSearch for the day's market news (US, India, crypto,
commodities). Write the Markets brief per `analyze/brief_prompt.md`: headline, market_story (decoded
narrative), board (real numbers from index.json, each with a plain-English `read`), themes,
what_to_watch (3–5, each fully decoded: gist, why_it_matters, what_it_means, watch, key_terms,
**the_lesson**, **concepts**, **key_points** [3–4 short scannable bullets]), global_summary, catalysts_today, favorites (what CHANGED since
yesterday — read the previous brief in `dashboard/archive/` for the delta; explain technicals in
plain English), risks, disclaimer. Save STRICT JSON to `output/brief-<today>.json` AND
`output/brief-latest.json`. Set `date` to today and `generated_at` to now (ISO, IST).

## 3. Enrich the favorites' deep panels
For each favorite in the brief, open the matching `dashboard/stocks/<TICKER>.json` (`^`→`_`, `/`→`_`)
and set its `whats_new` and `news` fields from the brief, then save the file (keep all other fields
exactly as they are).

Rules: strict JSON only (the dashboard breaks otherwise); never invent numbers — use the fetched data
or cited sources; cite sources with real URLs; every output ends with the not-financial-advice
disclaimer. When done, output a one-line summary: the #1 world story + the #1 market item.
