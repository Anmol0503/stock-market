# Personal Daily Intelligence Agent

A fully-automated analyst that emails you a short daily digest and maintains an intuitive dashboard
with two pillars:

- **🌍 World** — a *decoded* global-news feed: the 6–10 things you shouldn't miss, each broken down
  into what happened, why it matters, the ripple effects, and why you're seeing it now.
- **📈 Markets** — US + India + crypto/commodities, with an in-house technical-analysis engine and a
  deep panel per stock where **every metric is explained in plain English** (tap the ⓘ to learn it).

Plus **📱 Reels** (`dashboard/reels/`) — the whole day as a full-screen, swipeable mobile deck.
Every card is built around **one bold takeaway** ("the moot"), with the full decoded depth one tap
away, glossary chips inline, a concept-of-the-day, and a flashback quiz that tests yesterday's
lesson. On your phone: open the site → Share → **Add to Home Screen** → it launches like an app and
the last-loaded deck stays readable offline.

Built **free / near-free**, with the AI brain running on your **Claude Max subscription** (not the
paid API). Designed for someone new to markets: it decodes and explains, it doesn't just summarize.

See [PLAN.md](PLAN.md) for the full design and rationale.

## How it works

A scheduled **Claude Code routine** runs each morning on your subscription: it gathers free data +
broad world news, Claude decodes/analyzes both pillars (web-searching to confirm and fill gaps),
emails a short digest, and publishes the full depth to the dashboard.

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
   The daily run then auto-commits and pushes, so the public site updates itself each morning.
   ⚠️ The repo is **public** (free Pages requires it): briefs, archives, and your watchlist are
   visible; `.env`, `output/`, and `logs/` are gitignored — never commit secrets.

6. **Automation (already set up on this Mac)** — a LaunchAgent
   (`~/Library/LaunchAgents/com.dailyintel.daily.plist`) runs [routine/run_daily.sh](routine/run_daily.sh)
   **the first time you open your laptop each day**: fetch → analyze → headless Claude writes both
   briefs → publish + archive (+ email if `.env` exists). See
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
| `server.py` | Local server (threaded): serves the dashboard + `/api/analyze` (live any-ticker analysis), `/api/refresh` (recompute all), `/api/refresh_news` (re-pull headlines) |
| `dashboard/index.html` | Two-pillar dashboard: 🌍 World (decoded stories + latest headlines) and 📈 Markets (feed + live deep panel), with 🎓 lessons, 📚 concept chips, 📈 developing-story threads, board sparklines, and freshness timestamps everywhere |
| `dashboard/reels/` | 📱 The mobile deck (PWA): swipe-per-card, one takeaway per card, decode sheet, learn cards; `build_dashboard.build_reels()` compiles `dashboard/reels.json` daily |
| `dashboard/glossary.js` | The **education layer** — plain-English "what is it / how to read it / why it matters" for every metric AND macro/world concept |
| `routine/run_daily.sh` + `routine/claude_routine.md` | The automated morning pipeline (LaunchAgent fires it at first laptop-open each day) |
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

## Notes / limitations

- Free data is ~15-min delayed or EOD; `yfinance` is unofficial and can occasionally break. Good for
  a daily brief and big-move awareness, not day-trading.
- India real-time is the one hard free path — quotes come via `.NS`/`.BO` + web search; open a free
  Angel One / Fyers demat account later if you want tick-level NSE/BSE data.
- Cloud routines run headless, so email uses Gmail SMTP (not the interactive Gmail integration). Keep
  secrets in `.env` / routine secrets, never in code.
- **Not financial advice.** This is decision-support: it flags, ranks, and explains — you decide.
