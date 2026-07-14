# Analysis spec — how to produce the DECODED World brief

This is the **World News** pillar — separate from Markets. The reader is smart but **new to world
affairs and markets**, reads on a phone, and wants the *decoded* version of the day: not raw
headlines, but what each story actually means, why it matters, what it sets in motion, and why it's
in front of them today. Assume nothing is obvious. Explain the context a headline takes for granted.

Read `output/world-raw-latest.json` for the raw feed, then run **WebSearch** to confirm facts, get the
latest, and fill gaps. Write **strict JSON** matching the schema below to
`output/world-<YYYY-MM-DD>.json` and copy it to `output/world-latest.json`.

## Selection discipline — TWO regional feeds, ~20 each
The reels are now a **pure, timestamped news feed split into two tabs: GLOBAL and INDIA.** Produce:
- **~20 GLOBAL stories** (category is anything EXCEPT `india`), and
- **~20 INDIA stories** (category `india`).
Target 20 each; **quality and verification come first — never pad to hit 20 with junk or unverified
items.** If only 15 global stories genuinely matter and check out today, return 15. Within each region,
order by importance × freshness (put the biggest, newest first — story `rank` is a single global 1..N
counter across both regions, most important first).
- Cover the spread inside GLOBAL: geopolitics, economy, technology, science, health, climate/energy —
  whatever is actually important. Don't return 20 politics stories.
- **INDIA IS HOME.** The reader lives in India — the India tab is a first-class feed of ~20 national
  news / economy / policy / markets / India-in-the-world stories, decoded to the same depth as global.
- **Exact timestamps are required.** Every story carries `published_iso` = the real time the news
  broke, taken from the `published_iso` of the raw-feed item you based it on (or the earliest credible
  report time you confirm via WebSearch). **Never invent a time.** If genuinely unknown, set it to null.
- A story earns its place only if you can explain why it matters AND you have verified it (below).

## Vetting discipline — the raw feed includes SOCIAL; verify before you publish
`world-raw-latest.json` now casts a very wide net: reputable wires and RSS, **plus Google News,
Reddit (`r/worldnews`, `r/india`, …) and Twitter/X (via nitter)**. Treat **Reddit and X items as LEADS,
not facts.** Before including anything sourced from social:
- **Confirm it with a credible outlet via WebSearch.** If you cannot corroborate it, DROP it.
- Never present a rumor, unconfirmed claim, or single-tweet assertion as established fact. If a claim is
  contested or still developing, say who claims what and that it's unconfirmed.
- Prefer the **primary/original reporting** as the cited source (not the reddit/tweet link). Every
  story still needs ≥1 credible `sources` entry with a real URL.
- De-duplicate: the same event will appear many times across feeds — decode it once, as one story.

## Decoding discipline (the whole point — go DEEP)
For **every** story, fully decode it. Write in plain language, short sentences, no unexplained jargon
(if you must use a term like "sovereign debt", "current-account deficit", or "quantitative tightening",
define it inline AND add it to `key_terms`). Each field below must be genuinely and richly filled —
this is the depth the reader asked for. Don't be terse; expand and explain. The reader would rather
read three extra sentences that make them *understand* than a clipped summary they can't follow.

- **`background` is required** — give the backstory a newcomer needs: how we got here, the longer arc,
  who the players are. Someone who has never heard of this story should finish `background` +
  `what_happened` fully oriented.
- **Never invent facts or numbers.** Use the raw feed + cited web sources. If something is unconfirmed,
  say so. Cite at least one credible source per story (name + URL).
- Be neutral and factual on contested topics; present what's known and who claims what.

## Schema

```json
{
  "date": "2026-07-02",
  "generated_at": "2026-07-02T07:05:00+05:30",
  "headline": "One sentence capturing the single most important thing in the world today. (Shown on the dashboard, NOT as a reels cover — the reels open straight into the news feed.)",
  "the_big_picture": "3–4 sentences connecting today's top stories — the throughline a smart friend would give you over coffee. (Dashboard only.)",
  "stories": [
    {
      "rank": 1,
      "category": "geopolitics",          // geopolitics | economy | technology | science | health | climate | india
                                          // category === "india" → shows in the INDIA tab; anything else → GLOBAL tab
      "published_iso": "2026-07-14T15:33:38+00:00",  // REQUIRED — exact time the news broke, copied from the raw
                                          // feed item / earliest credible report. NEVER invent. null only if truly unknown.
      "regions": ["Middle East", "US"],
      "title": "Short, clear title — no clickbait.",
      "key_points": ["3–4 short scannable bullets — the essence a reader grasps in 5 seconds. Each ≤ ~14 words, punchy, no need for full sentences. The fast read before the detail (e.g. 'Iran holds the biggest day of the funeral', 'The likely successor stays out of public view')."],
      "background": "2–3 sentences: the backstory a newcomer needs. How we got here, the longer arc, who the key players are. This is what turns a headline into something the reader actually understands.",
      "what_happened": "2–4 plain sentences: the facts. What occurred, who's involved, when, the key numbers.",
      "why_it_matters": "2–3 sentences: why this is significant. What changes because of it. What's genuinely at stake.",
      "ripple_effects": "2–4 sentences: the second-order consequences. Who is affected and how — economies, industries, ordinary people, other countries, markets. The 'so what happens next'.",
      "why_now": "1–2 sentences: why this is surfacing today — what triggered it, what's the deeper trend it's part of, or why it escalated now.",
      "watch_next": "1 sentence: the specific thing to watch for next (a date, decision, data point, or escalation).",
      "key_terms": [{"term": "Strait of Hormuz", "definition": "One plain sentence defining a term used above that a newcomer may not know."}],
      "the_lesson": "1–3 sentences: the GENERALIZABLE takeaway — what this story teaches about how the world/economy/markets work, phrased so it applies beyond today's headline (e.g. 'When refineries get hit, fuel can run short even when crude is plentiful — processing capacity matters as much as supply.'). Required for every story.",
      "concepts": ["inflation", "supply_chain"],
      "market_link": "1 sentence IF it touches markets/assets (which stocks, sectors, currencies, or commodities move on this) — else null.",
      "importance": "critical",            // critical | high | notable
      "thread": {                          // OPTIONAL — ONLY when this story continues one we covered on a previous day
        "status": "developing",            // developing | escalating | cooling | resolved
        "day": 3,                          // Nth consecutive-ish day of OUR coverage (count from the archives you read)
        "previously": "1–2 sentences: what we actually told the reader before (from the archived brief — don't guess).",
        "changed": "1–2 sentences: what is genuinely NEW today vs what we said before."
      },
      "sources": [{"name": "Reuters", "url": "https://..."}]
    }
  ],
  "also_notable": [
    {"title": "One-liner for a smaller-but-real story", "why": "Why it's worth a glance", "source": {"name": "...", "url": "..."}}
  ],
  "disclaimer": "Decoded from public reporting for general understanding. Verify before relying on any single claim; details evolve."
}
```

## Story threads (`thread`) — continuity across days
Before writing, read the 1–2 most recent `dashboard/archive/world-*.json` files. When today's story
**continues one we already covered**, add the `thread` object: `previously` must reflect what those
archived briefs *actually said* (never reconstruct from memory), and `changed` is what's genuinely new
since. This is how the reader follows a developing story instead of re-reading it from scratch.
**Never force a thread onto a genuinely new story — omit the field entirely.**

## The learning layer (`the_lesson` + `concepts`)
The reader wants to LEARN from the news, not just follow it. So every story carries:
- **`the_lesson`** (required): the transferable insight — the mechanism or principle this story
  illustrates. Not a summary of the story; a lesson the reader keeps after the news is stale.
- **`concepts`** (optional, max 4): keys into the dashboard glossary, rendered as tap-to-learn chips.
  **Use ONLY keys from this exact list — never invent keys; omit the field if none apply:**
  `inflation, interest_rates, central_bank, bond_market, tariffs, sanctions, gdp,
  fiscal_vs_monetary, supply_chain, fii_flows, crude_geopolitics, currency_strength,
  risk_on_off, vix, yields, bull_bear_market, usdinr, gold_asset, crude_asset, bitcoin_asset, index`

## Notes
- `the_big_picture` is the reader's favorite part — make it genuinely illuminating, the connective tissue.
- Explain, don't just report. The test: could a curious 16-year-old read a story and fully understand
  what happened AND why it matters? If not, add the missing context.
- `market_link` is the bridge to the Markets pillar — fill it whenever a world event moves assets.
- Keep each field tight and scannable, but complete. **You are now writing ~40 stories (≈20 global +
  ≈20 india), each fully decoded** — so be efficient and don't pad, but NEVER drop a required field
  (`background`, `what_happened`, `why_it_matters`, `ripple_effects`, `why_now`, `watch_next`,
  `the_lesson`, `published_iso`, `sources`). Full decode on every one; depth AND breadth.
