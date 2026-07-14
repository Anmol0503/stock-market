# Headless prompt — SELECT the stories to decode (small, fast, reliable)

This is the fast **selection** pass. You are NOT decoding here — you are just choosing and ranking the
headlines that will be decoded in small batches afterward. Keep the output SMALL (one line of context
per story) so this call never drops.

## Do this
1. Read `output/world-raw-latest.json` — a wide raw net (reputable RSS + Google News + Reddit +
   Twitter/X via nitter), each item tagged `region` (global/india) with a real `published_iso`.
2. Choose the stories that genuinely matter today and are plausibly real (you'll verify fully in the
   decode step). **Prefer items you can corroborate; be wary of lone Reddit/X claims** — if something is
   only on social and looks dubious, don't select it.
3. **De-duplicate:** the same event appears across many feeds — select it ONCE, picking the most credible
   source for it.
4. Select **up to 20 GLOBAL** (category geopolitics|economy|technology|science|health|climate) and
   **up to 20 INDIA** (category india). Order each list most-important-and-newest first. Spread global
   across topics — not 20 politics items. Fewer than 20 is fine if fewer truly matter.

## Write STRICT JSON to `output/world-plan.json`
```json
{
  "generated_at": "<now ISO +05:30>",
  "headline": "One sentence: the single most important thing in the world today (for the dashboard).",
  "the_big_picture": "3–4 sentences connecting today's top stories (for the dashboard).",
  "global": [
    {
      "category": "geopolitics",
      "title": "Short, clear title for the story.",
      "source": "Reuters",
      "url": "https://... (best/original source you'll cite)",
      "published_iso": "2026-07-15T09:12:00+00:00",   // exact break time from the raw item; null only if unknown
      "angle": "One line: what this is and why it matters — a hint for the decoder."
    }
  ],
  "india": [ { ...same shape, category:"india"... } ]
}
```
Strict JSON only — nothing outside the file. When done, output one line: "selected N global + M india".
