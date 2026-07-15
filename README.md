# Personal Daily Intelligence Agent

A fully-automated analyst that emails you a short daily digest and maintains an intuitive dashboard
with two pillars:

- **🌍 World** — a *decoded* global-news feed: the 6–10 things you shouldn't miss, each broken down
  into what happened, why it matters, the ripple effects, and why you're seeing it now.
- **📈 Markets** — US + India + crypto/commodities, with an in-house technical-analysis engine and a
  deep panel per stock where **every metric is explained in plain English** (tap the ⓘ to learn it).

Plus **📱 Reels** (`dashboard/reels/`) — the whole day as a full-screen, swipeable mobile deck, in
**three tabs: 🌍 Global · 🇮🇳 India · 📈 Markets**. Every card is built around **one bold takeaway**;
tapping the button opens a **bulleted briefing** (key points, why it matters, ripple effects, sources)
one tap away. A **↻ refresh button** on the phone pulls the latest deck. On your phone: open the site →
Share → **Add to Home Screen** → it launches like an app and works offline.

**Refresh cadence:** the full AI-decoded deep-dives (World + Markets) regenerate **about every 2 hours**
on your Mac while the laptop is awake (Claude on your Max subscription), so the reels stay both deep and
fresh — no shallow raw-headline ticker.

Built **free / near-free**, with the AI brain running on your **Claude Max subscription** (not the
paid API). Designed for someone new to markets: it decodes and explains, it doesn't just summarize.

See [PLAN.md](PLAN.md) for the full design and rationale.

## How it works

A scheduled **Claude Code routine** runs **about every 2 hours** (while the laptop is awake) on your
subscription: it gathers free data + broad world news, Claude decodes/analyzes both pillars
(web-searching to confirm and fill gaps), publishes the full depth to the dashboard, and emails a short
digest **once a day**.

```
fetch_world.py ─► output/world-raw-latest.json ─┐
fetch.py       ─► output/raw-latest.json         ├─► [Claude decodes + analyzes] ─┐
analyze_stock.py ─► dashboard/stocks/*.json  ────┘                                 │
                                                    ┌─────────────────────────────┘
              output/world-latest.json  ◄───────────┤ (World brief — decoded)
              output/brief-latest.json  ◄───────────┘ (Markets brief)
                          │
                          ├─► send.py ─────────► short two-pillar EMAIL
                          └─► build_dashboard.py ─► GitHub Pages (full depth)
```

## Setup (all free, ~15 min)

1. **Python deps**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Keys & credentials** — copy the template and fill it in:
   ```bash
   cp .env.example .env
   ```
   - `FINNHUB_API_KEY` — free key from https://finnhub.io (optional; news + calendars).
   - `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` — turn on 2FA, then create an App Password at
     https://myaccount.google.com/apppasswords (16 chars).
   - `EMAIL_TO` — where the digest goes (usually your own email).
   - `DASHBOARD_URL` — your GitHub Pages URL (fill in after step 5).

3. **Pick your tickers** — edit `config/watchlist.yml` (the broad scan) and `config/favorites.yml`
   (the deep-dive list).

4. **Test the chain manually**
   ```bash
   python fetch.py            # pulls free data -> output/raw-latest.json
   # then, in a Claude Code session, paste routine/daily_routine.md steps 2–3 to generate the brief
   python send.py             # emails the digest
   python build_dashboard.py  # publishes dashboard/brief.json
   ```

5. **Dashboard on GitHub Pages** — one-time:
   ```bash
   gh auth login --web && gh auth setup-git
   gh repo create stock-market --public --source . --push
   gh api -X POST repos/{owner}/{repo}/pages -f 'source[branch]=main' -f 'source[path]=/'
   ```
   Pages serves the repo root (a root `index.html` redirects into `dashboard/`). Your site:
   `https://USER.github.io/stock-market/dashboard/` (+ `/dashboard/reels/` for the mobile deck).
   Publishing runs via **GitHub Actions** (`.github/workflows/pages.yml`) on every push — set Pages
   source to "GitHub Actions" (`gh api -X PUT repos/{owner}/{repo}/pages -f build_type=workflow`).
   The Mac run (about every 2 hours) writes the AI-decoded briefs and pushes them, which triggers the
   deploy — the phone always gets fresh, fully-decoded reels.
   ⚠️ The repo is **public** (free Pages requires it): briefs, archives, and your watchlist are
   visible; `.env`, `output/`, and `logs/` are gitignored — never commit secrets.

6. **Automation (already set up on this Mac)** — a LaunchAgent
   (`~/Library/LaunchAgents/com.dailyintel.daily.plist`) runs [routine/run_daily.sh](routine/run_daily.sh)
   **about every 2 hours while the laptop is awake** (a freshness guard skips runs when the last brief is
   <110 min old): fetch → analyze → headless Claude writes both briefs → publish + archive (+ email once
   per day if `.env` exists). See
   [routine/daily_routine.md](routine/daily_routine.md) for manage/disable/manual-run commands.

## Files

| File | Role |
|---|---|
| `CLAUDE.md` | The analyst persona, two-pillar mission + rules the agent follows |
| `analyze/world_prompt.md` | JSON schema for the **decoded World** brief |
| `analyze/brief_prompt.md` | JSON schema for the **Markets** brief |
| `config/watchlist.yml` / `favorites.yml` | What to scan / what to go deep on |
| `fetch_world.py` | Pulls broad global news across all categories (RSS + best-effort GDELT) |
| `fetch.py` | Pulls free market data + news (yfinance, Finnhub, CoinGecko, RSS) |
| `analyze_stock.py` | Technical-analysis engine — computes the industry indicator suite and turns it into a processed verdict + plain-English notes per stock (`python analyze_stock.py AAPL` or `--all`) |
| `send.py` | Renders + emails the **short two-pillar** digest via Gmail SMTP |
| `build_dashboard.py` | Publishes both briefs (`world.json` + `brief.json`) to the dashboard |
| `make_social.py` + `social/post.html` | Auto-generates ready-to-post **Instagram carousels** (branded 1080×1350 slides + caption) from the decoded feed → `social/out/<date>/` (local, gitignored). Preview/download at `localhost:8000/posts` |
| `server.py` | Local server (threaded): serves the dashboard + `/api/analyze` (live any-ticker analysis), `/api/refresh` (recompute all) |
| `dashboard/index.html` | Two-pillar dashboard: 🌍 World (decoded stories) and 📈 Markets (feed + live deep panel), with 🎓 lessons, 📚 concept chips, 📈 developing-story threads, board sparklines, and freshness timestamps everywhere |
| `dashboard/reels/` | 📱 The mobile deck (PWA): swipe-per-card, one takeaway per card, decode sheet, learn cards; `build_dashboard.build_reels()` compiles `dashboard/reels.json` daily |
| `dashboard/glossary.js` | The **education layer** — plain-English "what is it / how to read it / why it matters" for every metric AND macro/world concept |
| `routine/run_daily.sh` + `routine/claude_routine.md` | The automated pipeline (LaunchAgent fires it ~every 2h while the laptop is awake) |
| `routine/daily_routine.md` | How the automation works + manage/disable commands |

## The dashboard

Two tabs at the top: **🌍 World** and **📈 Markets**.

**World** is a *decoded* news feed — not raw headlines. Each story shows **what happened → why it
matters**, with a tap to expand **ripple effects → why you're seeing it now → what to watch next →
market link**. A "the big picture" block connects the day, and category chips (geopolitics, economy,
tech, science, health, climate, India) let you filter.

**Markets** is **knowledge-driven, not search-first**: it pours the day's "don't miss" items, a market
at-a-glance, and a processed **verdict per stock** (Strong Buy … Strong Sell). Click any stock for a
deep panel — plain-English read, moving-average & oscillator ratings, key levels, 52-week position,
volatility, a price chart, and every indicator as a signal. **Nothing is a bare number:** tap the **ⓘ**
next to any metric (RSI, MACD, P/E, ADX, beta…) for a beginner-friendly explanation. A secondary search
box looks up any ticker; run `python server.py` for live on-demand analysis of tickers you haven't
pre-computed.

## 📸 Social (Instagram carousels)

The decoded feed doubles as social content. `make_social.py` turns each day's **top 5 Global + top 5
India** stories into **branded 1080×1350 carousel images** (cover → story slides with the takeaway as the
hero → a call-to-action slide) plus an auto-written **caption** (hook + headlines + hashtags + disclaimer).
It reuses the reels design and renders with headless Chrome.

- **Generate:** `python make_social.py` (also runs automatically after each full pipeline run). Output →
  `social/out/<date>/{global,india}/` — local only, **gitignored** (never published to the public site).
- **Post (manual MVP):** open **`localhost:8000/posts`** → download the images, copy the caption, post to
  Instagram. No API, so zero ban risk — the goal is to validate the content before automating.
- **Config** (`.env`, all optional): `SOCIAL_HANDLE`, `SOCIAL_BIO_LINK`, and monetization hooks
  `SPONSOR_LINE` / `AFFILIATE_URL` (blank = off). Keep it **news/education framed** — "not financial
  advice" is baked into every carousel; attribute sources, don't reproduce article text.
- **Phase 2** (once it gets traction): auto-posting via the official Meta Graph **Content Publishing API**
  (needs an IG Business/Creator account + a Facebook app + tokens in `.env`), short video Reels, a paid tier.

## Notes / limitations

- Free data is ~15-min delayed or EOD; `yfinance` is unofficial and can occasionally break. Good for
  a daily brief and big-move awareness, not day-trading.
- India real-time is the one hard free path — quotes come via `.NS`/`.BO` + web search; open a free
  Angel One / Fyers demat account later if you want tick-level NSE/BSE data.
- Cloud routines run headless, so email uses Gmail SMTP (not the interactive Gmail integration). Keep
  secrets in `.env` / routine secrets, never in code.
- **Not financial advice.** This is decision-support: it flags, ranks, and explains — you decide.
