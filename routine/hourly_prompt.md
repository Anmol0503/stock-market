# Headless prompt — the HOURLY top-up (1 trending story per region)

This runs every hour the laptop is on. It is TINY and must stay reliable: you decode just **ONE new
top-trending GLOBAL story and ONE new top-trending INDIA story** and add them to the feed. Do NOT
re-decode the whole feed.

Follow `analyze/world_prompt.md` for the DECODING SCHEMA and depth bar (every field filled, plain
language, define jargon, the_lesson + concepts + key_points, published_iso, real sources).

## Do this
1. Read `output/world-latest.json` — the CURRENT feed. Note the titles/topics already covered; you must
   pick stories that are **NOT already in it** (no duplicates, no same-event rehashes).
2. Read `output/world-raw-latest.json` — the fresh raw net (RSS + Google News + Reddit + Twitter/X via
   nitter), each item tagged `region` with a `published_iso`.
3. Find what is **TRENDING RIGHT NOW**: the story being reported across the MOST sources/feeds and most
   recently. Volume across independent feeds + recency = trending. Use WebSearch to confirm it's real
   and current.
4. Pick exactly **one GLOBAL** (category geopolitics|economy|technology|science|health|climate) and
   **one INDIA** (category india) trending story that are genuinely new vs the current feed and matter.
5. **VET:** if the top candidate is only on Reddit/X and you can't corroborate it with a credible
   outlet, skip it and take the next trending one. Never publish a rumor as fact.
6. FULLY DECODE each per `analyze/world_prompt.md`, including an exact `published_iso` (the real break
   time — never invented) and real `sources`.

If nothing genuinely new is trending for a region this hour, set that region to `null` (better to add
nothing than a duplicate or a dud).

## Write STRICT JSON to `output/world-hourly.json`
```json
{
  "global": { ...one fully-decoded story per analyze/world_prompt.md... }  // or null
  ,
  "india":  { ...one fully-decoded story, category:"india"... }            // or null
}
```
Strict JSON only — nothing outside the file. When done, output one line naming the two stories you added.
