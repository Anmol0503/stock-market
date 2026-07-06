# Analysis spec — how to produce the daily brief

Read `output/raw-latest.json`, run WebSearch for the day's top global market headlines (and anything
missing, especially India news), then write the brief as **strict JSON** matching the schema below to
`output/brief-<YYYY-MM-DD>.json` and copy it to `output/brief-latest.json`.

## Depth discipline (the reader is new to markets — teach as you go)
- Do **not** write a thin overview. Explain the *why* behind every move, and define any term you use
  (e.g. "yields", "FII flows", "core inflation") in plain words inline. Numbers must be real (from the
  data or cited sources) — never invent them.
- `market_story` is the centerpiece: a short decoded narrative of *what is driving markets today and
  why*, connecting macro → sectors → the user's stocks, in language a beginner follows.
- `board` gives the key numbers with a one-line plain-English read each — not just a number.
- `themes` explains what's leading/lagging today and why.

## Ranking discipline
- `what_to_watch` = the 3–5 things that matter most **today**, across all markets, ranked #1 first.
- Favor items that change a price, a thesis, or a risk. Drop generic market color.
- **DECODE each one — do not leave it as a headline + a number.** The reader is new to markets, so each
  item must teach: what's happening (numbers explained in words), why it matters, what it means for them,
  and any jargon defined. Fill every field below.

## Schema

```json
{
  "date": "2026-07-02",
  "generated_at": "2026-07-02T07:05:00+05:30",
  "headline": "One punchy sentence summarizing the day.",
  "market_story": "3–5 sentences decoding what's driving markets today and why. Connect the dots: the macro backdrop (rates, inflation, oil, FX) → which sectors it helps/hurts → what it means for the user's stocks. Beginner-friendly; define jargon inline.",
  "board": [
    {"name": "S&P 500", "ticker": "^GSPC", "currency": "", "value": "5,xxx", "change_pct": -0.4, "read": "One line: what this number is telling you today (e.g. 'US large-caps slipped as rate-hike fears returned')."},
    {"name": "Nifty 50", "ticker": "^NSEI", "currency": "", "value": "2x,xxx", "change_pct": 0.3, "read": "..."},
    {"name": "Bitcoin", "ticker": "BTC-USD", "currency": "$", "value": "x,xxx", "change_pct": -1.2, "read": "..."}
  ],
  "themes": [
    {"theme": "Energy", "direction": "up", "note": "Oil spike lifts oil & gas names; explain the driver."},
    {"theme": "Rate-sensitive tech", "direction": "down", "note": "Higher-for-longer rates pressure high-growth valuations."}
  ],
  "what_to_watch": [
    {
      "rank": 1,
      "title": "Short title",
      "key_points": ["3–4 short scannable bullets — the essence in 5 seconds. Each ≤ ~14 words, punchy, numbers included (e.g. 'Bitcoin slips 0.7% to ~$62.7k', 'Support at $62.4k is the level to hold'). The fast read before the detail."],
      "gist": "2–3 sentences: what's actually happening, with the key numbers EXPLAINED in plain words (not just stated). This is the always-visible summary.",
      "why_it_matters": "2–3 sentences: why this moves prices / changes the picture / is a risk. Teach the mechanism.",
      "what_it_means": "1–2 sentences: the plain-English takeaway for the reader — what it means for them / their stocks.",
      "watch": "1 line: the specific next thing to watch (a level, date, data point, or event).",
      "key_terms": [{"term": "core PCE", "definition": "One plain sentence defining a term used above."}],
      "the_lesson": "1–2 sentences: the generalizable market lesson this item teaches (a mechanism/principle the reader keeps, e.g. 'Markets price the FUTURE — a calmer Fed tone can lift stocks before any actual rate change happens.'). Required.",
      "concepts": ["central_bank", "interest_rates"],
      "tickers": ["NVDA"],
      "market": "US",                        // US | IN | CRYPTO | MACRO
      "sources": [{"name": "Reuters", "url": "https://..."}]
    }
  ],
  "global_summary": {
    "us": "2–3 sentences: overnight/pre-market US picture.",
    "india": "2–3 sentences: Nifty/Sensex, notable movers, flows.",
    "crypto": "1–2 sentences: BTC/ETH and risk appetite.",
    "macro": "1–2 sentences: rates, FX, commodities, key data due."
  },
  "catalysts_today": [
    {"when": "Pre-open", "event": "US CPI (Jun)", "ticker": null, "importance": "high"},
    {"when": "After close", "event": "Nvidia earnings", "ticker": "NVDA", "importance": "high"}
  ],
  "favorites": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "price": 231.4,
      "change_pct": -0.6,
      "whats_new": "What changed since yesterday — the delta, in one or two lines.",
      "news": [{"headline": "...", "url": "...", "source": "..."}],
      "fundamentals": "Valuation + latest fundamentals read (PE, growth, margins) in plain words.",
      "technicals": "Trend vs 50/200 DMA, RSI, 52-wk range, key levels.",
      "catalysts": "Next earnings / events that matter.",
      "risks": "The main risks to the thesis right now.",
      "stance": "constructive"              // constructive | neutral | cautious | watch
    }
  ],
  "risks": ["Cross-book risk 1", "Risk 2"],
  "disclaimer": "For information only. Not financial advice. Data may be delayed and can be inaccurate; verify before acting."
}
```

## The learning layer (`the_lesson` + `concepts` on each what_to_watch item)
- **`the_lesson`** (required): the transferable market principle the item illustrates — something the
  reader keeps after today's numbers are stale.
- **`concepts`** (optional, max 4): glossary keys rendered as tap-to-learn chips. **Use ONLY keys from
  this list — never invent keys; omit if none apply:**
  `inflation, interest_rates, central_bank, bond_market, tariffs, sanctions, gdp, fiscal_vs_monetary,
  supply_chain, fii_flows, crude_geopolitics, currency_strength, risk_on_off, vix, yields,
  bull_bear_market, usdinr, gold_asset, crude_asset, bitcoin_asset, index, rsi, macd, moving_average,
  support_resistance, range_52w, volatility, overbought_oversold, pe, market_cap, beta`

## Notes
- Keep prose tight and scannable, but **substantive** — depth that's easy to digest, not a thin summary.
- `board` should span the key gauges: US (S&P/Nasdaq/Dow), India (Nifty/Sensex/Bank Nifty),
  crypto (BTC/ETH), commodities (Gold/Crude), and FX (USD/INR). Pull real values from
  `raw-latest.json` / `dashboard/stocks/index.json`; every entry needs a plain-English `read`.
- For each favorite, EXPLAIN the technical read in plain English (don't just cite RSI/DMA numbers).
- If `raw-latest.json` lacks India/crypto news, fill it from WebSearch and cite sources.
- Numbers must come from the data or cited sources — never invent them.
