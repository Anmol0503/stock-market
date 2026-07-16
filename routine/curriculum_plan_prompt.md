# Headless prompt — Design a "learn anything" curriculum

You are designing a lifelong-learning curriculum for a curious beginner who wants to **learn something in
depth every day**. Each subject becomes a multi-day course in a swipeable mobile app; each **session** is
one day's reading (a few chunks). Think of the best of a great teacher plus the "Very Short Introductions"
series — broad, rigorous, and genuinely enlightening.

## What to produce
A broad, well-sequenced set of **subjects** spanning many domains — history, science, economics, philosophy,
technology, psychology, mathematics, art, politics, the natural world, and how everyday things work. Order
them so a curious person steadily builds a genuinely educated worldview (foundational, fascinating subjects
first). Each subject is split into **4–6 sessions (parts)** that build logically from foundations to depth.

Rules:
- **Beginner-first**: assume zero prior knowledge. Every subject should be graspable by a curious 16-year-old.
- Each session's `focus` is **one clear sentence** on what that part teaches (a later step writes it in depth),
  and the parts must build on each other in a sensible teaching order.
- Titles are **specific and inviting**, not dry ("Why gold won" beats "Commodity money"; "The day the
  dinosaurs died" beats "The K–Pg extinction").
- Cover a genuine variety of domains across the set — don't cluster everything in one field.
- Do **NOT** repeat any subject listed as already covered in the context block below.

## Output — STRICT JSON to `output/curriculum.json`
```json
{
  "subjects": [
    {
      "slug": "story-of-money",
      "title": "The Story of Money",
      "emoji": "💰",
      "blurb": "How humanity went from swapping goats to tapping phones — and what money really is.",
      "sessions": [
        {"n": 1, "title": "The barter problem", "focus": "why swapping goods directly breaks down — the double coincidence of wants"},
        {"n": 2, "title": "The first money", "focus": "how commodities and then coins became money, and why gold won"},
        {"n": 3, "title": "Banks and the invention of credit", "focus": "how lending and paper claims multiplied money"},
        {"n": 4, "title": "The leap to fiat", "focus": "how money became pure trust, backed by nothing but a government's word"},
        {"n": 5, "title": "The digital future", "focus": "cards, UPI, crypto — what happens when money becomes information"}
      ]
    }
  ]
}
```

Write **only** the JSON to `output/curriculum.json` — output nothing outside the file. Strict JSON only.
