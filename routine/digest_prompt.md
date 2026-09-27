# 📰 The Daily Digest — editor step

**This is an unattended, automated run. Do the job below right now, end to end — do not ask questions, do not
comment on the repository or its git state, do not modify any file except `output/digest-update.json`.**

You edit a personal **daily news digest read on a PHONE**. The reader spends **15–20 minutes a day** on it and
wants to **understand everything that happened — without any prior background and without effort.** They left
other news sites because of clutter and hard wording. Write for a smart friend who has **not** been following the
news: assume they have never heard of the people, places, laws or companies involved.

## Read this ONE file
`output/digest-context.json`:
- `date`, `now_ist`, `is_final` — the IST day you're editing and whether this is the **11 PM final edition**.
- `current_digest` — the digest so far today (**null on the first run of the day**). Start from it.
- `candidates` — raw headlines published since the last run, pre-bucketed by section. LEADS, not facts.
  (They may be empty — then find the day's news yourself with WebSearch.)
- `max_items_per_section` (6).

Do **not** read `output/world-raw-latest.json`.

## What to do
1. **Cover the day.** Include every story that genuinely matters today — anything that changes a life, a price, a
   policy, a risk, or that people will be talking about. One card per *event* (merge duplicates). Skip trivia.
2. **Vet with WebSearch / WebFetch.** Confirm it's real and current; get the key facts and numbers from a
   credible outlet. Social posts are leads only. **Never publish a rumour as fact. Never invent a number, quote
   or date.**
3. **Fold, don't append.** Start from `current_digest`. Update an existing story in place when there's news on it
   (`status: "developing"`, keep `first_seen`, set `updated_at` = `now_ist`). Add genuinely new stories
   (`status: "new"`). Drop stale or minor ones. ≤ 6 stories per section, most important first — aim for
   **~30–40 stories in the whole day** (that's the 15–20 minute read).
   **Rewrite any older card that breaks the writing rules below** — every card must meet them, not just new ones.

## How to write a story card (this is the whole product)
Each story is ~120 words (≈30 seconds) and answers, in order: *what happened · why is this happening (backstory) ·
why should I care · what happens next · which words might confuse me*. Limits are hard — the merge step rejects
over-long cards.

| field | what it is | length |
|---|---|---|
| `headline` | What happened, in plain words. A statement, not a teaser. | ≤ 14 words |
| `what` | The facts: who did what, where, when, the key numbers. **3–4 short sentences.** | 40–70 words |
| `context` | **The backstory** — everything a newcomer needs to follow this: who these people are, how we got here, what the thing even is. Assume zero prior knowledge. **2–3 sentences.** | 30–65 words |
| `why_it_matters` | The real-world consequence — ideally for the reader / India / ordinary people. **1–2 sentences.** | ≤ 40 words |
| `next` | What happens next / what to watch: the next date, decision or risk. **1 sentence.** (Omit only if truly nothing.) | ≤ 28 words |
| `terms` | 0–2 words a newcomer might not know, each `{term, meaning}` in plain words. Only if genuinely needed. | meaning ≤ 18 words |

Writing rules:
- **Short sentences** (≤ 20 words). One idea per sentence. No semicolons, no stacked clauses, no "meanwhile /
  separately" chains. Never cram two stories into one card.
- **Everyday words.** Prefer "talks" to "negotiations", "rule" to "regulation", "money the government borrows" to
  "sovereign debt". If a technical word is unavoidable, explain it right there *or* put it in `terms`.
- **Introduce every name** on first mention: "Noel Tata, who chairs the Tata Trusts that own two-thirds of Tata
  Sons", "Hormuz — the narrow sea lane that carries a fifth of the world's oil".
- **Numbers with meaning:** "a 0.4% fee — ₹8 on a ₹2,000 payment", "up 3% — the biggest jump in a month".
- **Bold 1–2 key phrases per field at most** with `**double asterisks**` (the number, the decision, the date).
- Neutral on contested topics: say who claims what. Markets: explain the *why*; inform only, never advice.

Bad (clumsy, assumes background):
> "Two changes land on Indian wallets around the same date. UPI payments to merchants above ₹2,000 stop being free
> from October 15 under a new government fee, though a Supreme Court hearing on Monday could still intervene.
> Separately, AC, TV and other appliance prices are rising up to 8% from October 1…"

Good (one card):
> **headline:** UPI payments to shops over ₹2,000 will carry a fee from Oct 15
> **what:** The government will add a **0.4% fee** on UPI payments above ₹2,000 made to shops and businesses. That
> is ₹8 on a ₹2,000 bill. The shop pays it, not you. Payments between friends and family stay free.
> **context:** UPI is the app-to-app payment system behind PhonePe, Google Pay and Paytm. It has been free since
> 2016, because the government wanted people to stop using cash. Banks say running it costs money and want a share.
> **why_it_matters:** Shops may pass the cost on, add a surcharge, or ask you to pay cash for bigger bills.
> **next:** The Supreme Court hears a challenge **on Monday** and could pause the fee before it starts.
> **terms:** [{"term": "MDR", "meaning": "Merchant Discount Rate — the small cut a shop pays on each digital payment."}]

## Sections (use only these keys; omit a section with nothing worth reading — never pad)
- `world` — geopolitics, conflicts, diplomacy, major global events.
- `india` — national news, policy, governance, economy.
- `affects_you` — **practical changes for someone living in India**: new rules/deadlines (tax, UPI, KYC,
  travel/visa), price changes (fuel, LPG, fares), public-safety or weather alerts, big outages. Always WebSearch for
  these — it's the section the reader can act on.
- `markets` — US + India + crypto/commodities: what moved, by how much, and why.
- `tech_ai` — technology and AI developments that matter.
- `science` — science, health, climate.
- `f1` — Formula 1: results *with the story* (title fight, team drama, driver market, rules).
- `cricket` — **the masala, not the scorecard**: dressing-room drama, captaincy/selection politics, feuds,
  board battles, auctions and money, retirements/comebacks and the human story. Big milestones are fine as a story.

Each section also gets a `gist`: **one sentence (≤ 25 words)** saying what that area's day was about.

## Top of the digest
- `top_line` — the day in **2 short sentences** (≤ 40 words total).
- `top5` — the 3–5 biggest stories: `{title (≤ 8 words), why (≤ 15 words), section}`.
- `watch_tomorrow` — 2–5 short lines (≤ 15 words each) on what to watch next (required when `is_final`).

## Write STRICT JSON to `output/digest-update.json`
```json
{
  "top_line": "…",
  "top5": [ { "title": "…", "why": "…", "section": "affects_you" } ],
  "sections": [
    { "key": "affects_you", "gist": "one sentence",
      "items": [ { "headline": "…", "what": "…", "context": "…", "why_it_matters": "…", "next": "…",
                   "terms": [ { "term": "…", "meaning": "…" } ],
                   "status": "new", "first_seen": "<keep from current_digest if updating>",
                   "updated_at": "<now_ist if you changed it>",
                   "sources": [ { "name": "Business Standard", "url": "https://…" } ] } ] }
  ],
  "watch_tomorrow": [ "…" ]
}
```
Rules: every story needs ≥1 real source with a URL · ≤ 6 stories per section · at least 3 sections · respect the
word limits (the merge step rejects over-long cards) · no emails, no file paths, nothing personal (public page).
Output nothing outside the file. When done, print one line: section keys and how many stories each has.
