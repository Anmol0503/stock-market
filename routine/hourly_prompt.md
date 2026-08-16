# Headless prompt — the HOURLY top-up (a few trending NEW stories)

This runs every 30 minutes the laptop is on. It is small and must stay reliable: you decode a handful of
**new top-trending stories** across the requested regions and add them to the feed. Do NOT re-decode the
whole feed.

Follow `analyze/world_prompt.md` for the DECODING SCHEMA and depth bar (every field filled, plain
language, define jargon, the_lesson + concepts + key_points, published_iso, real sources).

## Read this ONE file
`output/hourly-context.json` — **everything you need for this run**:
- `regions` — which regions to fill and how many stories each (e.g. 2 global, 2 india, 1 f1, 1 cricket).
  Only fill the regions listed. If a region isn't listed this run, skip it entirely.
- `already_today` — normalized titles ALREADY covered today. Your picks must NOT be any of these, and
  must not be same-event rehashes of them.
- `prior_stories` — stories from YESTERDAY (title + one-line). Used for development detection (below).
- `candidates` — the **freshest raw headlines for the requested region, pre-filtered for you** (source,
  headline, url, published_iso, summary). This is your lead list — pick the most trending from here.

**Do NOT read `output/world-raw-latest.json`** — it's a large firehose and the `candidates` above are already
sliced from it for this region. Use **WebSearch / WebFetch** only to VET a candidate (confirm it's real and
current) and to gather the detail you need to decode it well. If `candidates` is thin or nothing there is
genuinely fresh, you may WebSearch for today's top story in that region instead.

## Region meaning
- **global** — geopolitics | economy | technology | science | health | climate (world stories that matter).
- **india** — category `india` (national news, economy, policy, markets).
- **f1** — Formula 1: races, results, driver/team news, regulations, standings. category `f1`.
- **cricket** — the STORIES behind the game, not the scorecard. Go for the **"masala" a boxscore never tells**:
  dressing-room drama, captaincy & selection politics, feuds / spats / sledging, board & governance battles
  (BCCI / ICC / PCB / CA), auctions, contracts & franchise moves, retirements / comebacks / axings and the human
  story behind them, off-field controversies, money, and personalities. Records or milestones **only** when there
  is a genuine human story in them. **AVOID** pure match reports, "who won", ball-by-ball, scorecards, points
  tables, and bare fixtures — the reader gets scores elsewhere; here they want the intrigue. India-heavy is fine.
  category `cricket`.

## How to pick (per region)
1. Find what is **TRENDING RIGHT NOW** in that region: the story across the MOST sources/feeds, most
   recently. Volume across independent feeds + recency = trending. Confirm with WebSearch it's real & current.
   - **RECENCY IS A HARD REQUIREMENT.** Look at `published_iso`. Pick from **TODAY's** items (or, if truly
     nothing today, the last ~24h). **Never pick a story published before yesterday.** Prefer the freshest.
   - For **f1**: explore broadly (official F1, BBC Sport, Autosport, PlanetF1, RaceFans, Reddit) and take the
     most-talked-about stories right now — results, signings, injuries, controversies, standings.
   - For **cricket**: chase the **off-field story, not the result**. Explore ESPNcricinfo (features/news, not
     scorecards), Cricbuzz, The Guardian/Telegraph cricket, Indian sports desks, and Reddit r/Cricket for what
     people are actually ARGUING about right now — a captaincy row, an auction twist, a retirement, a board spat,
     a snub, a feud, a big money move. Decode it like intrigue: who's involved, what's really going on, why it
     matters, what happens next.
   - When asked for 2, pick two genuinely DIFFERENT threads (for cricket e.g. a selection controversy AND an
     auction/money story — never two angles on one event). Corroborate before publishing — never a rumour as fact.
2. Pick the requested COUNT of genuinely new stories per region (not in `already_today`, not near-duplicates
   of each other). If you truly can't find enough new ones, return fewer — never pad with rehashes or duds.
3. **VET:** if a candidate is only on Reddit/X and you can't corroborate it with a credible outlet, skip it.
   Never publish a rumor as fact.
4. FULLY DECODE each per `analyze/world_prompt.md` — exact real `published_iso`, real `sources`, and (per
   the reader-facing trim) make sure **`what_happened`, `background`, and `key_points` are strong and in
   plain language** (those three + sources are what the reader sees).

## Development detection (link to yesterday)
For each pick, check `prior_stories`: **is this a major new development of a story we covered YESTERDAY?**
(e.g. yesterday "talks begin", today "deal signed"; yesterday "driver injured", today "ruled out for season").
If yes, add to that story object:
- `"develops"`: the exact `title` of the yesterday story it continues,
- `"thread"`: `{ "previously": "1–2 lines on where it stood yesterday", "changed": "what's new today" }`.
Only set these for a REAL continuation of a prior-DAY story — not for two stories that merely share a topic,
and never for a story already covered today (that's a dup — skip it instead).

## Write STRICT JSON to `output/world-hourly.json`
```json
{
  "stories": [
    { ...one fully-decoded story per analyze/world_prompt.md...,
      "region": "global",                     // one of: global | india | f1 | cricket
      "develops": "<yesterday title>",        // OPTIONAL — only for a real prior-day development
      "thread": { "previously": "...", "changed": "..." }   // OPTIONAL — required if `develops` is set
    }
    // ... one object per story, across the requested regions ...
  ]
}
```
Strict JSON only — nothing outside the file. If a region has nothing genuinely new, just include fewer
stories (better to add nothing than a duplicate or a dud). When done, output one line naming what you added.
