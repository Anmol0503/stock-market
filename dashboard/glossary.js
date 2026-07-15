/* ==========================================================================
   GLOSSARY — plain-English explanations for every metric on the dashboard.
   Written for someone brand-new to markets. No jargon without a definition.

   Each entry:
     term  — the human name
     one   — a single-sentence "what is it"
     what  — what it actually measures, in plain words
     read  — how to read the number / signal you're seeing
     why   — why it matters to YOU as a decision-maker
     scale — (optional) quick reference for typical values

   Used by index.html: every indicator, fundamental, and verdict has an "ⓘ"
   that opens the matching entry. Nothing on the dashboard is a bare number.
   ========================================================================== */
const GLOSSARY = {

  /* ---------- the big picture ---------- */
  verdict: {
    term: "Technical rating (Strong Buy … Strong Sell)",
    one: "A single scorecard that blends ~16 standard indicators into one word.",
    what: "We compute the indicators professional chart-readers use, turn each into a Buy, Sell, or Neutral vote, then tally the votes. More buy votes → a bullish rating; more sell votes → bearish.",
    read: "Strong Buy / Buy = most indicators lean up right now. Neutral = mixed, no clear edge. Sell / Strong Sell = most lean down. It describes the CURRENT technical posture, not a prediction or a recommendation.",
    why: "It's a fast, unemotional read of 'what is the chart saying today' so you don't have to eyeball a dozen indicators yourself. It is one input — pair it with the news and fundamentals below before forming a view.",
    scale: "Score runs -1 (all sell) to +1 (all buy). ≥ +0.5 Strong Buy · +0.15 Buy · middle Neutral · -0.15 Sell · ≤ -0.5 Strong Sell."
  },
  moving_averages_rating: {
    term: "Moving-averages rating",
    one: "The verdict from trend indicators only (the 10 moving averages).",
    what: "Counts how many of the 10 moving averages the price is currently ABOVE (bullish) vs BELOW (bearish).",
    read: "Price above most of its averages = uptrend = bullish tally. Below most = downtrend = bearish tally.",
    why: "Isolates the trend picture from the momentum picture. When this and the oscillator rating disagree, the stock is in transition — worth a closer look."
  },
  oscillators_rating: {
    term: "Oscillators rating",
    one: "The verdict from momentum indicators only (RSI, MACD, Stochastic, etc.).",
    what: "Counts buy vs sell votes across the momentum oscillators — tools that measure speed and stretch rather than trend.",
    read: "Bullish tally = momentum building. Bearish = momentum fading or overextended.",
    why: "Momentum often turns BEFORE the trend does, so this can give an early warning that a trend is tiring."
  },

  /* ---------- momentum oscillators ---------- */
  rsi: {
    term: "RSI — Relative Strength Index (14)",
    one: "A 0–100 speedometer of recent buying vs selling pressure.",
    what: "Compares the size of recent up-days to recent down-days over the last 14 sessions. High = buyers have been dominating; low = sellers have.",
    read: "Above 70 = 'overbought' (risen fast, may be due for a pause/pullback). Below 30 = 'oversold' (fallen fast, may be due for a bounce). 40–60 = neutral.",
    why: "It flags when a move has gone too far, too fast in either direction. Overbought isn't a sell signal by itself — strong stocks can stay overbought for weeks — but it tells you the easy part of the move may be over.",
    scale: "0 ——[30 oversold]—— 50 ——[70 overbought]—— 100"
  },
  macd: {
    term: "MACD — Moving Average Convergence Divergence",
    one: "Measures whether short-term momentum is speeding up or slowing down vs the longer term.",
    what: "Subtracts a 26-day average from a 12-day average (the 'MACD line'), then compares it to its own 9-day average (the 'signal line'). It's the classic trend-momentum tool.",
    read: "MACD line ABOVE its signal line = bullish (momentum improving). BELOW = bearish (momentum deteriorating). A cross from below to above is a common bullish trigger; the reverse is bearish.",
    why: "It catches shifts in momentum early and works in trending markets — one of the most-watched signals on Wall Street, so it can be partly self-fulfilling."
  },
  stochastic: {
    term: "Stochastic %K (14,3)",
    one: "Shows where today's close sits within the recent high-low range.",
    what: "0% = closing at the bottom of the last 14 days' range; 100% = closing at the very top. It measures 'closing strength'.",
    read: "Above 80 = closing near the highs (overbought). Below 20 = closing near the lows (oversold). Turning up from below 20 is an early bounce signal.",
    why: "Great for spotting exhaustion in sideways/range-bound stocks, where price keeps bouncing between a floor and a ceiling."
  },
  cci: {
    term: "CCI — Commodity Channel Index (20)",
    one: "Measures how far price has strayed from its recent average.",
    what: "Zero = price is right at its 20-day average. Big positive/negative readings mean price is unusually far above/below normal.",
    read: "Above +100 = strong up-move (can mean overbought OR the start of a powerful trend). Below -100 = strong down-move. Between = normal.",
    why: "Highlights unusually strong thrusts — useful for catching the start of a breakout or spotting an overstretched move."
  },
  williams_r: {
    term: "Williams %R (14)",
    one: "Another overbought/oversold gauge, scaled from 0 to -100.",
    what: "Like Stochastic upside-down: measures where the close sits in the recent range. -100 = bottom of range, 0 = top.",
    read: "Above -20 = overbought (near recent highs). Below -80 = oversold (near recent lows).",
    why: "A fast, sensitive read on short-term extremes — often used to time entries within a bigger trend."
  },
  momentum: {
    term: "Momentum (10-day)",
    one: "Simply: is the price higher or lower than it was 10 days ago?",
    what: "Today's price minus the price 10 sessions back. Positive = rising over the period; negative = falling.",
    read: "Positive and growing = accelerating uptrend. Negative and falling = accelerating downtrend. Fading toward zero = the move is losing steam.",
    why: "The simplest momentum check there is. 'The trend is your friend' — momentum tells you if the trend still has energy."
  },

  /* ---------- trend / moving averages ---------- */
  moving_average: {
    term: "Moving average (SMA / EMA)",
    one: "The average price over the last N days — a smoothed line that shows the underlying trend.",
    what: "SMA = simple average of the last N closes. EMA = exponential, which weights recent days more so it reacts faster. Common windows: 10/20/50/100/200 days.",
    read: "Price ABOVE the average = bullish for that timeframe; BELOW = bearish. Short averages (10/20) show near-term mood; long ones (200) show the primary trend.",
    why: "Trend is the single biggest driver of returns. A stock above its rising 200-day average is in a healthy long-term uptrend; below a falling 200-day is a long-term downtrend. The averages also often act as support/resistance (see below).",
    scale: "Short-term: 10/20-day · Medium: 50-day · Long-term: 100/200-day"
  },
  sma: {
    term: "SMA — Simple Moving Average",
    one: "The plain average of the last N daily closes.",
    what: "Add up the last N closing prices and divide by N. A steady, slower-moving trend line.",
    read: "Price above the SMA = uptrend for that window; below = downtrend. The 50-day and 200-day SMAs are the most-watched.",
    why: "The 50-day crossing above the 200-day is the famous 'golden cross' (bullish); crossing below is a 'death cross' (bearish). Big funds watch these levels."
  },
  ema: {
    term: "EMA — Exponential Moving Average",
    one: "A moving average that reacts faster because it weights recent days more heavily.",
    what: "Like an SMA but the most recent prices count for more, so it hugs the price more closely and turns sooner.",
    read: "Same as SMA — price above = bullish, below = bearish — but the EMA signals trend changes earlier (and gives more false alarms).",
    why: "Traders use EMAs when they want to react quickly; investors prefer SMAs for a calmer, less twitchy trend read."
  },
  adx: {
    term: "ADX — Average Directional Index (14)",
    one: "Measures how STRONG the trend is — not its direction.",
    what: "A 0–100 reading of trend strength. It says nothing about up or down, only how forceful and sustained the move is.",
    read: "Below 20 = weak / no real trend (choppy, range-bound). 20–25 = a trend is forming. Above 25 = strong trend. Above 40 = very strong.",
    why: "It tells you whether trend-following signals (like moving-average crosses) are trustworthy right now. In a low-ADX chop, breakouts often fail; in high-ADX, trends tend to persist.",
    scale: "0 ——[20 weak]——[25 trending]——[40 strong]—— 100"
  },
  trend: {
    term: "Trend direction",
    one: "Our plain-English label: Uptrend, Downtrend, or Sideways.",
    what: "Derived from where price sits relative to its 50-day and 200-day averages. Above both = Uptrend. Below both = Downtrend. In between = Sideways/transitional.",
    read: "Uptrend = higher highs, buyers in control. Downtrend = lower lows, sellers in control. Sideways = no one in control; range-trading conditions.",
    why: "Most strategies work with the trend, not against it. Knowing the regime tells you whether to lean on breakout signals (trend) or bounce signals (range)."
  },
  golden_cross: {
    term: "Golden cross / Death cross",
    one: "When the 50-day average crosses the 200-day average.",
    what: "Golden cross = 50-day rises above the 200-day (bullish long-term shift). Death cross = 50-day falls below the 200-day (bearish shift).",
    read: "These are slow, big-picture signals — they confirm a trend change rather than predict it.",
    why: "Widely covered in the media and watched by large investors, so they can move sentiment even though they lag the actual turn."
  },

  /* ---------- levels, range, volatility ---------- */
  support_resistance: {
    term: "Support & Resistance",
    one: "Price floors (support) and ceilings (resistance) where moves often stall.",
    what: "Support = a level where buyers have historically stepped in and stopped declines. Resistance = a level where sellers have historically capped rallies. We estimate them from pivot math on the recent range.",
    read: "Approaching resistance from below = expect a possible stall or pullback. Approaching support from above = expect a possible bounce. A decisive BREAK through either is significant — resistance broken can become new support.",
    why: "They're natural places to watch for entries, exits, and risk levels. 'Buy near support, watch for rejection at resistance' is a core idea in technical trading."
  },
  pivot: {
    term: "Pivot point",
    one: "A reference midpoint for the day, derived from yesterday's high/low/close.",
    what: "The average of the prior day's high, low, and close. Support and resistance levels are calculated around it.",
    read: "Trading above the pivot = mildly bullish bias for the session; below = mildly bearish. It's a day-trader's anchor.",
    why: "Gives a quick, objective 'line in the sand' for the day without any opinion baked in."
  },
  range_52w: {
    term: "52-week range & percentile",
    one: "Where today's price sits between its one-year low and high.",
    what: "The lowest and highest price over the past year, and where the current price falls between them (0th percentile = at the low, 100th = at the high).",
    read: "Near the high (80th+ percentile) = strong stock, but less 'room' and possibly stretched. Near the low (under 20th) = weak or beaten-down; could be value or a falling knife.",
    why: "Context for whether you're buying strength or weakness. New 52-week highs often keep going (momentum); new lows often keep falling — until they don't."
  },
  volatility: {
    term: "Volatility (ATR-based)",
    one: "How much this stock typically moves in a day.",
    what: "Based on ATR (Average True Range) — the average daily high-to-low travel — expressed as a % of price. We label it Low, Normal, or High.",
    read: "High volatility = bigger daily swings (bigger potential gains AND losses; size positions smaller). Low = calmer, steadier.",
    why: "Tells you how much 'noise' to expect and how to size risk. A 2% move in a low-vol stock is a big deal; in a high-vol name it's just Tuesday."
  },
  atr: {
    term: "ATR — Average True Range",
    one: "The average distance price travels in a single day, in currency terms.",
    what: "Averages the daily high-to-low range (accounting for gaps) over 14 days. A raw measure of movement, not direction.",
    read: "A larger ATR means wider daily swings. Often used to set stop-losses (e.g. 2× ATR below entry) so normal wiggles don't stop you out.",
    why: "Turns 'this stock is jumpy' into an actual number you can size trades and risk around."
  },
  bollinger: {
    term: "Bollinger Bands %B",
    one: "Shows where price sits inside its volatility envelope.",
    what: "Bands are drawn 2 standard deviations above/below the 20-day average. %B tells you where price is: 0 = lower band, 1 = upper band, 0.5 = middle.",
    read: "Near 1 (upper band) = stretched high / strong. Near 0 (lower band) = stretched low / weak. Bands squeezing tight often precede a big move.",
    why: "Frames whether today's price is 'normal' or an extreme relative to its own recent volatility."
  },
  obv: {
    term: "OBV — On-Balance Volume",
    one: "Tracks whether volume is flowing into or out of the stock.",
    what: "Adds the day's volume when price closes up, subtracts it when price closes down, and keeps a running total.",
    read: "Rising OBV = buying pressure (accumulation). Falling OBV = selling pressure (distribution). If price rises but OBV doesn't, the rally may lack conviction.",
    why: "Volume is the fuel behind price. OBV helps you see if a move is backed by real participation or is running on fumes."
  },

  /* ---------- fundamentals ---------- */
  pe: {
    term: "P/E ratio (trailing)",
    one: "How many dollars you pay for each $1 of the company's past-year profit.",
    what: "Price per share ÷ earnings per share over the last 12 months. A basic valuation gauge.",
    read: "A high P/E (say 40+) means the market expects strong growth — you're paying up. A low P/E (under ~12) can mean cheap value OR a troubled business. Always compare within the same industry.",
    why: "The quickest sense of whether a stock is 'expensive' or 'cheap' relative to what it actually earns. Context is everything — a 30 P/E is cheap for fast growth, dear for a utility."
  },
  forward_pe: {
    term: "Forward P/E",
    one: "P/E based on expected NEXT-year profits instead of past profits.",
    what: "Price ÷ analysts' forecast earnings for the year ahead.",
    read: "If forward P/E is well below trailing P/E, the market expects profits to grow. If higher, it expects profits to shrink.",
    why: "Stocks are priced on the future, so forward P/E is often the more relevant valuation — but it relies on forecasts, which can be wrong."
  },
  market_cap: {
    term: "Market capitalization",
    one: "The total dollar value of all the company's shares — its 'size'.",
    what: "Share price × number of shares outstanding. Above ~$200B = mega-cap, $10–200B = large-cap, $2–10B = mid-cap, under $2B = small-cap.",
    read: "Bigger caps are generally more stable and liquid; smaller caps move more and are riskier but can grow faster.",
    why: "Size shapes risk, liquidity, and how much a stock can realistically grow from here."
  },
  profit_margins: {
    term: "Profit margin",
    one: "How many cents of profit the company keeps from each $1 of sales.",
    what: "Net profit ÷ revenue, as a %. A 25% margin means 25¢ of every sales dollar becomes profit.",
    read: "Higher = more efficient / more pricing power. Compare within an industry — software margins dwarf grocery margins by nature.",
    why: "High, stable margins usually signal a strong competitive position ('moat'). Falling margins are an early warning."
  },
  revenue_growth: {
    term: "Revenue growth",
    one: "How fast the company's sales are increasing year over year.",
    what: "The % change in revenue vs the same period last year.",
    read: "Strong positive growth = expanding business. Slowing or negative = maturing or struggling.",
    why: "Growth is a primary driver of stock returns, especially for younger companies where profits are still small."
  },
  dividend_yield: {
    term: "Dividend yield",
    one: "The annual cash payout to shareholders as a % of the share price.",
    what: "Yearly dividends per share ÷ share price. A $2 dividend on a $100 stock = 2% yield.",
    read: "Higher yield = more income, but a very high yield (8%+) can signal the market expects a cut. Many high-growth stocks pay nothing and reinvest instead.",
    why: "Matters if you want income. Steady, growing dividends also signal management confidence and financial health."
  },
  beta: {
    term: "Beta",
    one: "How much the stock moves relative to the overall market.",
    what: "Beta 1.0 = moves with the market. 1.5 = 50% bigger swings than the market. 0.5 = half as jumpy. Below 0 = tends to move opposite.",
    read: "High beta = amplifies both up and down markets (aggressive). Low beta = steadier, more defensive.",
    why: "Tells you how a stock will likely behave when the whole market rallies or sells off — key for managing portfolio risk."
  },

  /* ---------- concepts ---------- */
  overbought_oversold: {
    term: "Overbought / Oversold",
    one: "Shorthand for 'risen too far, too fast' vs 'fallen too far, too fast'.",
    what: "Momentum tools like RSI flag when a move looks stretched relative to recent history.",
    read: "Overbought = vulnerable to a pause or pullback (NOT an automatic sell). Oversold = candidate for a bounce (NOT an automatic buy). Strong trends can stay overbought/oversold for a long time.",
    why: "Helps you avoid chasing a move at its most extended point and spot potential mean-reversion opportunities."
  },
  bullish_bearish: {
    term: "Bullish / Bearish",
    one: "Bullish = expecting prices to rise. Bearish = expecting them to fall.",
    what: "A 'bull' charges upward; a 'bear' swipes downward. Applied to signals, sentiment, or a whole market.",
    read: "A bullish signal leans toward upside; a bearish one toward downside. 'Risk-on' markets are bullish; 'risk-off' are bearish/defensive.",
    why: "The basic vocabulary for describing which way the odds are tilting."
  }
};

/* ==========================================================================
   MARKET CONCEPTS — for someone with ZERO knowledge. What the board numbers
   even ARE, and what they mean. Surfaced as ⓘ on the Markets board + an
   "About this" teach-first block when you open any index/asset.
   ========================================================================== */
Object.assign(GLOSSARY, {
  index: {
    term: "Stock-market index",
    one: "A single number that tracks a whole basket of stocks, so you can see how a market is doing at a glance.",
    what: "Instead of checking hundreds of companies one by one, an index bundles them into one figure. When someone says 'the market went up today', they almost always mean an index — like the S&P 500 or the Nifty — rose.",
    read: "The index LEVEL (say 7,499) is just a running score — it is NOT a price in dollars or rupees, and the raw size of the number doesn't really matter. What matters is the % change day-to-day and the direction over weeks and months.",
    why: "It's the fastest read on whether stocks are broadly rising or falling, and on the overall mood of investors.",
    scale: "Watch the % change and the trend — not the raw level."
  },
  sp500: {
    term: "S&P 500 (the US market's scoreboard)",
    one: "The 500 biggest US public companies, rolled into one number.",
    what: "A 'market-cap-weighted' index (bigger companies count more) spanning tech, banks, healthcare, energy and more — Apple, Microsoft and Nvidia are among the largest members. It's the benchmark most US investors and funds measure themselves against.",
    read: "Up = large US companies broadly rose that day. A steadily rising S&P over months is the sign of a healthy 'bull' (upward) market.",
    why: "When people ask 'how did the market do?', this is usually the answer. It's the world's most-watched equity gauge.",
    scale: "For an index, a ±0.5% day is normal; ±1–2% is a notable move."
  },
  nasdaq: {
    term: "Nasdaq Composite (the tech gauge)",
    one: "A US index dominated by technology and high-growth companies.",
    what: "Heavy in tech — Apple, Nvidia, Microsoft, Amazon — so it tends to swing more than the S&P 500. When you hear 'tech led the market', this is where it shows up.",
    read: "When the Nasdaq outpaces the Dow, growth/tech is leading and investors are feeling bold ('risk-on'). When it lags, the mood is turning cautious.",
    why: "The quickest gauge of appetite for high-growth tech and AI names."
  },
  dow: {
    term: "Dow Jones (the old-economy blue-chips)",
    one: "30 large, well-established US companies.",
    what: "An older, narrower index of 30 big 'blue-chip' names, leaning more 'old economy' (industrials, banks, consumer) than the tech-heavy Nasdaq.",
    read: "When the Dow leads and the Nasdaq lags, money is rotating toward safer, established firms — often a more cautious signal.",
    why: "A traditional pulse of big, stable American business."
  },
  nifty: {
    term: "Nifty 50 (India's benchmark)",
    one: "The 50 biggest companies on India's National Stock Exchange (NSE).",
    what: "India's equivalent of the S&P 500 — includes Reliance, HDFC Bank, TCS and Infosys. It's the headline gauge for 'how did the Indian market do today'.",
    read: "Up = Indian large-caps broadly rose. Watch it alongside the Sensex; they usually move together.",
    why: "The single most-watched number for Indian equities."
  },
  sensex: {
    term: "Sensex (India's other headline index)",
    one: "30 large companies on the Bombay Stock Exchange (BSE).",
    what: "The older sibling of the Nifty — 30 blue-chips instead of 50. The Nifty and Sensex almost always move in the same direction.",
    read: "If the Nifty and Sensex ever diverge noticeably, look at which sectors are driving each. Otherwise, treat them as the same signal.",
    why: "Widely quoted in Indian media as the market's daily temperature."
  },
  banknifty: {
    term: "Bank Nifty (India's banking sector)",
    one: "An index of India's biggest banks.",
    what: "Tracks the leading NSE-listed banks (HDFC Bank, ICICI, SBI and others). Banks lend to businesses and consumers, so they're the backbone of the economy.",
    read: "Bank Nifty leading the market = confidence in the domestic economy. Lagging = caution about growth or bad loans.",
    why: "A strong banking sector usually means a strong, credit-fuelled economy — so it's a key 'internal' health check for India."
  },
  points_vs_price: {
    term: "Why an index is in 'points', not money",
    one: "An index level is a calculated score, not a price you can pay.",
    what: "Nifty at 24,006 or the S&P at 7,499 are index 'points' — a measure of the whole basket. You can't buy '24,006' of anything; the number just tracks the group.",
    read: "Don't compare an index level to a stock price, and don't read meaning into the raw size. Only the % change and the trend matter.",
    why: "Clears up the most common beginner confusion — an index level and a share price are completely different things."
  },
  percent_change: {
    term: "The % change (how big was the move?)",
    one: "How much a value rose or fell versus the day before.",
    what: "+1% means it's 1% higher than yesterday's close. Green/plus = up, red/minus = down. How BIG a % is depends on the asset.",
    read: "For a broad index: ±0.5% is a normal day, ±1–2% is notable, ±3%+ is a big, news-driven move. For Bitcoin, even 5% is routine. So always judge the % against what's normal for that thing.",
    why: "The % is how you compare moves across very different assets — an index, a single stock, gold, crypto — on the same footing.",
    scale: "Index: ±0.5% normal · ±1–2% notable · ±3%+ big.  Crypto: far larger swings are normal."
  },
  usdinr: {
    term: "USD / INR (the rupee's exchange rate)",
    one: "How many Indian rupees it takes to buy one US dollar.",
    what: "USD/INR = 95 means $1 costs ₹95. Crucially: when this number goes UP, the rupee is getting WEAKER (each dollar costs more rupees); when it goes down, the rupee is stronger.",
    read: "A rising number (weaker rupee) makes imports — oil, electronics, foreign travel, education abroad — more expensive and adds to inflation. It helps exporters (like IT firms) who earn in dollars.",
    why: "A core gauge of India's economic health, and something that hits your everyday cost of living directly.",
    scale: "Number UP = rupee weaker · number DOWN = rupee stronger."
  },
  gold_asset: {
    term: "Gold (the 'safe haven')",
    one: "Gold, priced per ounce in US dollars — where money hides when it's nervous.",
    what: "Investors buy gold when they're fearful or expect inflation to erode cash. Gold pays no interest, so when interest rates rise, gold becomes relatively less attractive (cash and bonds now pay you to wait).",
    read: "Gold rising often signals fear or inflation worries. Gold falling while interest rates rise is the textbook reaction.",
    why: "A barometer of fear, and a hedge many people hold to balance out riskier assets like stocks."
  },
  crude_asset: {
    term: "Crude oil (the economy's lifeblood)",
    one: "Oil, priced per barrel — it feeds into the cost of almost everything.",
    what: "Oil powers transport, factories and shipping, so its price ripples into the cost of goods everywhere. Wars and supply cuts push it up; slowing demand pushes it down.",
    read: "Rising oil = inflation pressure, and real pain for oil IMPORTERS like India (costlier fuel, weaker rupee). Falling oil = relief for importers and for inflation.",
    why: "One of the biggest single swing factors for inflation and for the world economy — and it hits India hard."
  },
  bitcoin_asset: {
    term: "Bitcoin (high-risk digital asset)",
    one: "The largest cryptocurrency — very high risk, very high volatility.",
    what: "A digital currency with no central bank behind it; its price is driven purely by demand, sentiment and interest rates. It swings far more violently than stocks.",
    read: "Bitcoin usually trades 'risk-on' — it rises when investors are bold and falls hard when they're fearful or when interest rates climb. A day of ±2% is calm for Bitcoin; 10%+ moves happen.",
    why: "A pure gauge of speculative risk appetite — when crypto diverges from stocks (like today), it's a warning sign worth noting.",
    scale: "Calm day ±2% · big day 10%+ — much wilder than stocks."
  },
  ethereum_asset: {
    term: "Ether / Ethereum (the #2 crypto)",
    one: "The second-largest cryptocurrency, powering the Ethereum network.",
    what: "Like Bitcoin, but tied to a platform used to build apps and 'smart contracts'. It's often even more volatile than Bitcoin.",
    read: "Usually moves in the same direction as Bitcoin and overall crypto risk appetite.",
    why: "A read on the broader crypto market beyond Bitcoin alone."
  },
  vix: {
    term: "VIX (the market's 'fear gauge')",
    one: "How much turbulence investors expect in the near future.",
    what: "The VIX rises when investors are scared and paying up for protection, and falls when they're calm. It's derived from options prices on the S&P 500.",
    read: "Below ~15 = calm/complacent; 20–30 = nervous; above 30 = fear; 40+ = panic. A LOW VIX during bad news can mean the market is underestimating the risk.",
    why: "A quick emotional read on the market — and a low VIX during a hot inflation scare (like today) is a notable disconnect.",
    scale: "<15 calm · 20–30 nervous · 30+ fear · 40+ panic"
  },
  risk_on_off: {
    term: "Risk-on vs Risk-off",
    one: "Two words that capture the market's whole mood.",
    what: "'Risk-on' = investors feeling bold: money flows into stocks (especially tech) and crypto. 'Risk-off' = investors playing safe: money flows into cash, government bonds, and often gold and the US dollar.",
    read: "Nasdaq up + crypto up + VIX low = risk-on. Stocks down + bonds/gold/dollar up = risk-off.",
    why: "Tells you, in two words, why unrelated assets are moving together — and which way the herd is leaning today."
  },
  yields: {
    term: "Bond yields (the hidden hand)",
    one: "The interest rate a government pays to borrow money.",
    what: "When bond yields rise, borrowing gets more expensive across the whole economy, and stocks — especially expensive, fast-growing tech — tend to fall, because safe bonds now pay you more to wait.",
    read: "Rising yields = headwind for stocks, gold and crypto. Falling yields = tailwind.",
    why: "Often the real reason behind a big market move, even when the headlines point elsewhere."
  },
  bull_bear_market: {
    term: "Bull market vs Bear market",
    one: "A 'bull' market trends up over time; a 'bear' market trends down.",
    what: "Rule of thumb: a bear market is a drop of 20%+ from the highs; a bull market is a sustained rise. Named for how the animals strike — a bull thrusts UP with its horns, a bear swipes DOWN with its paw.",
    read: "In a bull market, dips tend to get bought (buyers step in). In a bear market, rallies tend to get sold. The regime shapes how every individual move behaves.",
    why: "The single biggest piece of context for understanding any day's action."
  }
});

/* ==========================================================================
   MACRO & WORLD CONCEPTS — the ideas world-news stories teach. Referenced by
   each story's `concepts` chips (📚) so the news doubles as a course.
   ========================================================================== */
Object.assign(GLOSSARY, {
  inflation: {
    term: "Inflation",
    one: "The rate at which prices rise — money quietly losing its buying power.",
    what: "Measured by tracking the cost of a basket of everyday goods and services over time. 2% a year is what most central banks aim for; 4%+ starts to hurt; deflation (falling prices) brings its own problems.",
    read: "Rising inflation → central banks lean toward RAISING interest rates → borrowing costs up, stocks/gold/crypto usually pressured. Falling inflation → room to cut rates → usually good for assets.",
    why: "It's the single force behind most central-bank decisions, market swings, and your own cost of living. Most big market stories eventually trace back to inflation.",
    scale: "~2% target · 3–4% uncomfortable · 5%+ alarm bells"
  },
  interest_rates: {
    term: "Interest rates (the policy rate)",
    one: "The price of borrowing money, set at its base level by the central bank.",
    what: "The central bank sets a baseline rate that ripples into every loan, mortgage, and bond. Raising it cools spending and inflation; cutting it stimulates growth.",
    read: "Rates UP = headwind for stocks (especially growth/tech), gold and crypto, and stronger home currency. Rates DOWN = tailwind for risk assets.",
    why: "The gravity of finance: nearly every asset's value is priced against 'what could I safely earn in interest instead?'"
  },
  central_bank: {
    term: "Central bank (Fed / RBI / ECB)",
    one: "The institution that controls a country's money — its interest rates and currency stability.",
    what: "The US Federal Reserve ('Fed'), Reserve Bank of India (RBI), European Central Bank (ECB) etc. They set policy rates, manage inflation, backstop banks in crises, and often manage the currency.",
    read: "Markets parse every word central bankers say ('hawkish' = leaning to higher rates, 'dovish' = lower). A surprise from a big central bank moves every market on earth.",
    why: "No single actor moves markets more. Understanding what the Fed/RBI want is half of understanding any market day."
  },
  bond_market: {
    term: "Bonds & yields",
    one: "Loans to governments/companies that trade like assets; the 'yield' is the interest rate they pay.",
    what: "When you buy a bond you're lending money. Yields move opposite to bond prices: strong demand pushes yields down, fear of inflation or oversupply pushes them up.",
    read: "Rising yields = money can earn more 'safely' → expensive stocks, gold, and crypto look less attractive. Falling yields = the reverse. The 10-year US Treasury yield is the world's reference rate.",
    why: "The bond market is bigger than the stock market and often the real reason stocks move — even when headlines say otherwise."
  },
  tariffs: {
    term: "Tariffs & trade deals",
    one: "Taxes on imported goods — the main lever countries pull in trade disputes.",
    what: "A tariff makes foreign goods pricier, protecting local producers but raising costs for consumers and importers. Trade deals lower or remove them in exchange for access.",
    read: "New tariffs → exporters to that market get hurt, domestic rivals helped, prices rise (inflationary). A trade deal → exporters rally, currencies often strengthen.",
    why: "For India, US tariff decisions directly hit IT, pharma and textiles exporters — and the July-24-style deadlines you see in the news set real market catalysts."
  },
  sanctions: {
    term: "Sanctions & export controls",
    one: "Economic weapons: cutting a country or company off from money, goods, or technology.",
    what: "Sanctions block trade/finance with a target (e.g. Russia); export controls stop specific tech (e.g. advanced chips) from being sold to rivals. Both reshape global supply chains.",
    read: "Watch who's targeted and what's restricted: energy sanctions move oil; chip controls move semiconductor stocks; retaliation risk keeps markets nervous.",
    why: "They're how modern great-power conflict is fought — and they regularly reroute the flows of oil, chips, and money that markets price."
  },
  gdp: {
    term: "GDP & economic growth",
    one: "The total value of everything a country produces — the broadest economic scorecard.",
    what: "Gross Domestic Product. Its growth rate tells you if an economy is expanding (jobs, profits, tax revenue) or shrinking (recession = two negative quarters, roughly).",
    read: "India growing ~6–8% = world-leading. US ~2–3% = healthy. Below 0 = recession. Faster growth generally supports stocks and the currency.",
    why: "Growth is the tide that lifts (or drops) all boats — company profits, employment, and market confidence all ride on it."
  },
  fiscal_vs_monetary: {
    term: "Fiscal vs monetary policy",
    one: "The two levers that steer an economy: government spending/taxes vs central-bank interest rates.",
    what: "Fiscal = what the government does (budgets, taxes like GST, subsidies, infrastructure). Monetary = what the central bank does (rates, money supply). They can push together or against each other.",
    read: "Big spending + low rates = strong stimulus (watch inflation). Tight budget + high rates = braking hard (watch growth).",
    why: "Knowing which lever is being pulled tells you whether policy is helping or fighting the market you're watching."
  },
  supply_chain: {
    term: "Supply chains & chokepoints",
    one: "The global web that makes and moves everything — and the narrow points where it can break.",
    what: "Modern products cross many borders before reaching you. Chokepoints (Strait of Hormuz for oil, Taiwan for chips, Suez for shipping) concentrate risk: one disruption ripples worldwide.",
    read: "A chokepoint threat = prices of whatever flows through it spike (oil, freight, chips), inflation risk rises, and 'de-risking' (moving factories) accelerates.",
    why: "Most surprise inflation and many geopolitical market shocks are supply-chain stories at heart — including what India pays for oil."
  },
  fii_flows: {
    term: "FII/FPI flows (foreign money in India)",
    one: "Foreign investors' money moving into or out of Indian stocks and bonds.",
    what: "FII/FPI = Foreign Institutional/Portfolio Investors. Their buying pushes Indian markets and the rupee up; their selling ('outflows') pressures both. Driven largely by US interest rates and global risk appetite.",
    read: "High US rates or global fear → money flows OUT of emerging markets like India (rupee weakens, Nifty pressured). US rate cuts or optimism → flows return.",
    why: "One of the biggest day-to-day drivers of the Nifty, Sensex and USD/INR — India's markets breathe with global money."
  },
  crude_geopolitics: {
    term: "Oil & geopolitics (India's exposure)",
    one: "Why wars and chokepoints far away change what India pays at the pump.",
    what: "India imports ~85% of its oil, priced in dollars. Any supply threat (Hormuz, Russia sanctions, OPEC cuts) raises crude — which widens India's import bill, weakens the rupee, and fuels inflation.",
    read: "Crude UP = bad for India (inflation, rupee, current-account deficit); great for oil producers. Crude DOWN = a broad tax cut for the Indian economy.",
    why: "The single most direct line from world geopolitics to Indian household budgets and the Nifty."
  },
  currency_strength: {
    term: "Currency strength (why the rupee moves)",
    one: "What makes a currency rise or fall against the dollar — and who wins each way.",
    what: "A currency strengthens when money flows in (exports, investment, high local rates) and weakens when money flows out (imports, foreign selling, higher US rates). Central banks smooth the moves with reserves.",
    read: "Weak rupee: imports/fuel/foreign travel cost more, but IT exporters earn more per dollar. Strong rupee: the reverse. USD/INR rising = rupee weakening.",
    why: "The exchange rate is the price of your economy in the world's money — it touches inflation, corporate profits, and your cost of living."
  }
});

/* Which market concept explains a given board ticker (for the 'About this' teach block). */
const CONCEPT_FOR_TICKER = {
  "^GSPC": "sp500", "^IXIC": "nasdaq", "^DJI": "dow",
  "^NSEI": "nifty", "^BSESN": "sensex", "^NSEBANK": "banknifty",
  "BTC-USD": "bitcoin_asset", "ETH-USD": "ethereum_asset",
  "GC=F": "gold_asset", "CL=F": "crude_asset", "INR=X": "usdinr",
};
function conceptForTicker(ticker) {
  return CONCEPT_FOR_TICKER[(ticker || "").toUpperCase()] || null;
}

/* Map an indicator/fundamental name coming from the data to a glossary key. */
function glossaryKey(name, explicit) {
  if (explicit && GLOSSARY[explicit]) return explicit;
  const n = (name || "").toLowerCase();
  if (n.startsWith("rsi")) return "rsi";
  if (n.startsWith("macd")) return "macd";
  if (n.startsWith("stoch")) return "stochastic";
  if (n.startsWith("cci")) return "cci";
  if (n.startsWith("williams")) return "williams_r";
  if (n.startsWith("momentum")) return "momentum";
  if (n.startsWith("sma")) return "sma";
  if (n.startsWith("ema")) return "ema";
  if (n.includes("market cap")) return "market_cap";
  if (n.includes("p/e (fwd") || n.includes("forward")) return "forward_pe";
  if (n.includes("p/e")) return "pe";
  if (n.includes("margin")) return "profit_margins";
  if (n.includes("rev growth") || n.includes("revenue")) return "revenue_growth";
  if (n.includes("div yield") || n.includes("dividend")) return "dividend_yield";
  if (n.includes("beta")) return "beta";
  return null;
}

/* ==========================================================================
   INDIA CIVICS & INSTITUTIONS — plain-English so India news decodes itself.
   ========================================================================== */
Object.assign(GLOSSARY, {
  rbi: {
    term: "The RBI (Reserve Bank of India)",
    one: "India's central bank — it sets interest rates, guards the rupee, and regulates the banks.",
    what: "The Reserve Bank of India is the country's monetary authority. It sets the 'repo rate' (the rate at which it lends to banks), which flows into every home and business loan. It also manages India's foreign-currency reserves, issues rupee notes, and supervises banks so they don't blow up.",
    read: "When the RBI 'hikes' rates it's fighting rising prices; when it 'cuts' it's trying to boost growth. A 'hawkish' RBI is worried about inflation, a 'dovish' one about slow growth. Its moves shift home-loan EMIs, the rupee, and stocks the same day.",
    why: "No single Indian institution moves money more — reading what the RBI is trying to do is half of understanding any Indian market day.",
    scale: "Meets roughly every 2 months (via the MPC) to set the repo rate."
  },
  sebi: {
    term: "SEBI (the market regulator)",
    one: "India's stock-market watchdog — it polices companies, brokers, and fraud so investors can trust the market.",
    what: "The Securities and Exchange Board of India writes and enforces the rules for anyone raising money from the public or trading shares. It approves IPOs (a company's first sale of shares to the public), punishes insider trading and price manipulation, and sets the rules that mutual funds and brokers must follow.",
    read: "A SEBI 'probe', 'order', or 'ban' against a company or its owner is a red flag — it signals suspected wrongdoing and can crater a stock. New SEBI rules can reshape how a whole industry (say, mutual funds) works.",
    why: "It's the referee that makes India's markets safe enough for ordinary people to invest — its actions can make or break a stock overnight."
  },
  union_cabinet: {
    term: "The Union Cabinet",
    one: "The small top team of senior ministers who take the country's biggest decisions, led by the Prime Minister.",
    what: "The Cabinet is the core of India's central ('Union') government — the PM plus the most important ministers (finance, home, defence, and so on). It approves major policies, spending, and bills before they go to Parliament. 'The Cabinet cleared X' means this group formally decided it.",
    read: "'Cabinet approved/cleared' means a policy just crossed a real decision line — it's now government policy, not just a proposal. Watch the details: how much money, who benefits, when it starts.",
    why: "It's where the executive branch actually decides things — most big Indian policy stories begin with a Cabinet decision."
  },
  lok_sabha: {
    term: "The Lok Sabha (the lower house)",
    one: "The directly-elected house of Parliament — whoever controls it forms the government.",
    what: "The Lok Sabha ('House of the People') has 543 members, each elected by voters in a constituency. The party or alliance with a majority here picks the Prime Minister and runs the country. Most laws — and all budget/money bills — must pass here.",
    read: "A party's seat count here tells you whether a government is strong or shaky. A comfortable majority means bills pass easily; a thin one means every ally's support matters and reforms get harder.",
    why: "This is the house that decides who rules India — a party's Lok Sabha seat count is the single most important number in Indian politics.",
    scale: "543 seats · 272 = the majority needed to form a government."
  },
  rajya_sabha: {
    term: "The Rajya Sabha (the upper house)",
    one: "Parliament's second chamber — chosen indirectly by state legislatures, it reviews and can delay laws.",
    what: "The Rajya Sabha ('Council of States') represents India's states. Its members are elected by state lawmakers, not directly by voters, and serve staggered six-year terms so the whole house is never re-elected at once. Most bills must pass here too, but it cannot block money bills.",
    read: "A government can have a big Lok Sabha majority yet lack one here — which is why some bills stall or get watered down. Watch this house when a law is 'passed by Lok Sabha but stuck in Rajya Sabha'.",
    why: "It's the checkpoint that can slow or amend laws, so its seat math decides whether reforms actually become law."
  },
  parliament_india: {
    term: "Parliament (of India)",
    one: "India's national law-making body — two houses plus the President, where laws are debated and passed.",
    what: "Parliament is made up of the Lok Sabha (lower house), the Rajya Sabha (upper house), and the President. A proposed law ('bill') generally must pass both houses and get the President's assent to become an 'Act'. It meets in sessions — Budget, Monsoon, and Winter.",
    read: "'Parliament passed X' means a bill cleared both houses — it's now law or about to be. Watch whether the opposition walked out or whether it passed 'amid din', which tells you how contested it was.",
    why: "Every national law, tax, and budget flows through here — it's the formal engine of India's democracy."
  },
  supreme_court_india: {
    term: "The Supreme Court (of India)",
    one: "India's highest court — its rulings are final and bind the whole country.",
    what: "The Supreme Court sits at the top of India's judiciary. It hears the most important cases, settles disputes between states or between a state and the centre, and can strike down laws it finds unconstitutional. Its reading of the Constitution is the last word — no court or government can overrule it.",
    read: "A Supreme Court 'verdict', 'stay', or 'notice' can override government policy, halt a project, or protect a right nationwide. When the top court takes up a big issue, expect a ruling with country-wide consequences.",
    why: "It's the ultimate check on government power in India — a single judgment here can reshape law, business, and rights for everyone."
  },
  high_courts: {
    term: "High Courts (the state-level top courts)",
    one: "The highest courts within each state, sitting just below the Supreme Court.",
    what: "Each state (or group of states) has a High Court that handles serious cases and appeals within its territory. It can strike down state laws and hear challenges against a state government — but its rulings can be appealed further, up to the Supreme Court.",
    read: "A High Court order affects one state or region, not the whole country. Many big national cases start here and then travel up, so a High Court ruling is often 'round one', not the final word.",
    why: "Most legal action against state governments and local disputes plays out here — they're the workhorses of India's court system."
  },
  gst: {
    term: "GST (Goods and Services Tax)",
    one: "India's single, nationwide tax on most goods and services — 'one nation, one tax'.",
    what: "GST, launched in 2017, replaced a tangle of separate state and central taxes with one system. It's charged in slabs — different rates for different items, low on essentials and high on luxuries — and collected jointly by the centre and states. A 'GST Council' of finance ministers sets the rates.",
    read: "'GST collections hit ₹X lakh crore' is a live pulse of the economy — more spending and business activity means higher collections. 'GST Council cut/raised the rate on Y' directly changes what that item costs you.",
    why: "It's the backbone of India's indirect-tax revenue and a real-time gauge of activity — and rate changes hit the price of everyday things."
  },
  union_budget: {
    term: "The Union Budget",
    one: "The government's annual money plan — how much it will earn, spend, and borrow in the year ahead.",
    what: "Presented by the Finance Minister on 1 February each year, the Union Budget lays out spending on defence, roads, welfare and more, sets tax rules, and states how big the deficit (the gap between spending and income) will be. Parliament must approve it.",
    read: "Budget day moves markets: watch which sectors get more money (their stocks often rise), any change to income or capital-gains tax (hits your pocket), and the 'fiscal deficit' target (how disciplined the government plans to be).",
    why: "It's the clearest single statement of the government's priorities for the year — and it directly touches taxes, jobs, and dozens of industries."
  },
  psu: {
    term: "PSU (Public Sector Undertaking)",
    one: "A company owned wholly or mostly by the government, like SBI, ONGC, or the railways.",
    what: "PSUs are state-owned enterprises where the government is the main shareholder. They span banking (State Bank of India), energy (ONGC, NTPC), defence, and more. Many are listed, so you can buy shares — but the government stays in control.",
    read: "'PSU stocks rallied' usually reflects hopes about government policy, dividends, or 'disinvestment' (the government selling part of its stake). Because the government is the boss, politics moves PSU shares more than private firms.",
    why: "PSUs run big chunks of India's economy — banks, energy, defence — so their health and the government's plans for them matter to the whole market."
  },
  disinvestment: {
    term: "Disinvestment (selling state assets)",
    one: "When the government sells part or all of its stake in a state-owned company to raise money.",
    what: "Disinvestment (or 'privatisation' when it's a full sale) is the government offloading shares in a PSU — either to the public via the market, or to a private buyer. It raises cash to fund the budget and, supporters argue, lets the business run more efficiently under private hands.",
    read: "A disinvestment announcement usually lifts that PSU's stock (new demand, hope of better management) and signals the government needs revenue or wants to exit that business. A 'strategic sale' means handing over control, not just a small stake.",
    why: "It's a key way the government funds spending without borrowing more — and a recurring market catalyst for PSU shares."
  },
  fiscal_deficit: {
    term: "Fiscal deficit",
    one: "The gap between what the government spends and what it earns — the amount it must borrow to cover the difference.",
    what: "When a government spends more than it collects in taxes and other income, the shortfall is the fiscal deficit, filled by borrowing. It's usually stated as a percentage of GDP (the size of the whole economy) so you can judge whether it's large or manageable.",
    read: "A rising deficit means more government borrowing — which can push up interest rates, weaken the rupee, and worry bond investors. A shrinking one signals discipline. A 'wider than expected' number is a red flag.",
    why: "It's the headline gauge of whether the government's finances are sustainable — heavy borrowing can crowd out everyone else and stoke inflation.",
    scale: "Stated as % of GDP · India has aimed toward the ~4.5% area; higher = more borrowing."
  },
  cpi_wpi: {
    term: "CPI & WPI (India's inflation gauges)",
    one: "Two measures of how fast prices are rising — CPI at the shop, WPI at the wholesale level.",
    what: "CPI (Consumer Price Index) tracks the prices households actually pay — food, fuel, rent — and is the number the RBI targets. WPI (Wholesale Price Index) tracks prices between businesses, before goods reach you. Food and fuel swing both around a lot.",
    read: "'CPI inflation came in at X%' is the key one: above the RBI's comfort zone, expect it to lean toward higher rates; cooling, and rate cuts become likely. Rising WPI often foreshadows retail (CPI) inflation later.",
    why: "Inflation drives most RBI decisions and your cost of living — CPI is the number that decides whether loans get cheaper or dearer.",
    scale: "RBI aims for CPI at 4% (with a 2–6% tolerance band)."
  },
  forex_reserves: {
    term: "Forex reserves (India's war chest)",
    one: "The stockpile of foreign currency and gold the RBI holds to defend the rupee and pay for imports.",
    what: "Foreign-exchange reserves are mostly US dollars, plus gold and other currencies, held by the RBI. India uses them to pay for imports like oil, repay foreign debt, and steady the rupee — the RBI can sell dollars to stop the rupee falling too fast.",
    read: "Rising reserves = a stronger cushion and a more confident economy. Falling reserves often mean the RBI is spending dollars to prop up a weak rupee. Analysts also measure them in 'months of imports' they could cover.",
    why: "They're India's financial shock-absorber — a big buffer reassures foreign investors that India can weather oil spikes and global panics."
  },
  repo_rate: {
    term: "The repo rate",
    one: "The RBI's key interest rate — the rate at which it lends short-term cash to banks.",
    what: "'Repo' is the rate banks pay to borrow from the RBI. It's the anchor for the whole economy: when the RBI moves the repo rate, banks adjust the rates they charge you for home, car, and business loans, usually within weeks.",
    read: "Repo UP = loans and EMIs get costlier, spending slows, inflation cools — a brake. Repo DOWN = cheaper loans, more spending — a boost. A 'pause' means the RBI is waiting to see how things develop.",
    why: "It's the single most important number the RBI sets — it decides how expensive borrowing is for every household and business in India.",
    scale: "Moved in small steps, often 0.25% ('25 basis points') at a time."
  },
  monetary_policy_committee: {
    term: "The MPC (Monetary Policy Committee)",
    one: "The six-member panel at the RBI that votes on India's interest rates.",
    what: "The Monetary Policy Committee — three RBI officials and three government-appointed experts — meets roughly every two months and votes on the repo rate. Its legal job: keep CPI inflation near the 4% target while supporting growth.",
    read: "Watch the vote split (e.g. 4–2) and the 'stance' words ('accommodative' = ready to cut, 'neutral', or 'tightening' = ready to hike). A divided vote or a shift in stance hints at where rates go next.",
    why: "This small committee's decisions set borrowing costs for the entire country — markets hang on every meeting."
  },
  current_account_deficit: {
    term: "Current Account Deficit (CAD)",
    one: "When India buys more from the world than it sells — importing more than it exports.",
    what: "The current account tallies India's dealings with the world (goods, services, and money sent home by workers abroad). A deficit means more money flows out for imports (chiefly oil and gold) than comes in. It's shown as a % of GDP.",
    read: "A widening CAD pressures the rupee (India needs more dollars to pay for imports) and makes the economy more dependent on foreign money. Oil price spikes are the classic trigger. A narrow deficit or surplus is a sign of strength.",
    why: "It's a core gauge of India's external health — a large CAD can weaken the rupee and leave the economy exposed to global shocks.",
    scale: "Stated as % of GDP · under ~2–2.5% is generally seen as comfortable."
  },
  eci: {
    term: "The Election Commission (ECI)",
    one: "The independent body that runs India's elections — the world's largest democratic exercise.",
    what: "The Election Commission of India organises and referees national and state elections: it sets the schedule, enforces the 'Model Code of Conduct' (rules parties must follow once polls are announced), oversees voting and counting, and can penalise violations. It's designed to be independent of the government of the day.",
    read: "When the ECI 'announces the poll schedule', the Model Code kicks in and the government can't launch new schemes — a real freeze on policy. ECI notices or campaign bans signal how it's policing a heated contest.",
    why: "Free, credible elections are the foundation of Indian democracy, and the ECI is the referee that makes them work."
  },
  ordinance: {
    term: "An ordinance",
    one: "A temporary law the government can issue when Parliament isn't sitting — a fast-track, stopgap measure.",
    what: "When Parliament is not in session and something is urgent, the President (on the government's advice) can issue an ordinance that has the force of law immediately. But it's temporary: Parliament must approve it within about six weeks of reconvening, or it lapses.",
    read: "An ordinance signals the government wanted to act fast without waiting for Parliament — sometimes genuinely urgent, sometimes to skip debate. Watch whether Parliament later ratifies it; if not, it dies.",
    why: "It shows the executive moving quickly and on its own — a recurring, sometimes controversial, feature of Indian governance."
  },
  state_vs_centre: {
    term: "Centre vs State (India's federal split)",
    one: "The division of power between the national government and India's state governments.",
    what: "India is federal: some subjects (defence, foreign affairs, currency) belong to the central ('Union') government, some (police, health, land) to the states, and some are shared. States have their own elected governments and Chief Ministers. Money and power are constantly negotiated between the two levels.",
    read: "'Centre–state tension' or 'the state moved to court' usually means a fight over money (tax share), control, or a central law a state dislikes. Which level has authority over an issue tells you who can actually act on it.",
    why: "So much of Indian policy — welfare, infrastructure, law enforcement — depends on this tug-of-war between Delhi and the states."
  },
  coalition_government: {
    term: "A coalition government",
    one: "When no single party wins a majority, so several parties join forces to rule together.",
    what: "To govern, a party or alliance needs a majority in the Lok Sabha. If none gets there alone, parties form a coalition — pooling their seats behind a common Prime Minister and shared programme. The junior partners ('allies') get ministries and bargaining power in return.",
    read: "A coalition means the government must keep allies happy, so bold or divisive reforms get harder and every ally's demand matters. If a key ally threatens to walk out, the government's survival can be at stake.",
    why: "Coalition math shapes how stable a government is and how much it can actually push through — a recurring theme in Indian politics."
  },
  crore_lakh: {
    term: "Lakh & Crore (India's number system)",
    one: "The Indian way of counting large numbers: a lakh is 100 thousand, a crore is 10 million.",
    what: "Indian news counts in lakhs and crores instead of millions and billions. One lakh = 100,000. One crore = 100 lakh = 10,000,000 (ten million). So '10 lakh' is a million, and '100 crore' is a billion. '1 lakh crore' — a crore of crores — equals 1 trillion.",
    read: "To convert: 1 crore ≈ 10 million; 100 crore ≈ 1 billion; 1 lakh crore ≈ 1 trillion (very roughly US$12 billion at ₹83/$). So 'GST collections of ₹1.8 lakh crore' is ₹1.8 trillion — a genuinely huge, economy-scale number.",
    why: "Almost every Indian figure — budgets, company revenues, government schemes — is quoted this way, so you can't read Indian news without it.",
    scale: "1 lakh = 100,000 · 1 crore = 10 million · 100 crore = 1 billion · 1 lakh crore = 1 trillion."
  },
  msp: {
    term: "MSP (Minimum Support Price)",
    one: "A guaranteed floor price at which the government promises to buy certain crops from farmers.",
    what: "For key crops like wheat and rice, the government sets a Minimum Support Price — a rate it commits to pay so farmers aren't wiped out if market prices crash. Government agencies buy grain at MSP, which also stocks the public food-distribution system that feeds the poor.",
    read: "MSP is politically charged: farmers often demand a legal guarantee and higher rates. A big MSP hike helps farmers but can raise food prices and the government's subsidy bill — so it ripples into food inflation and the budget.",
    why: "It sits at the crossroads of farmer incomes, food security, inflation, and politics — which is why farm protests so often centre on it."
  },
  pli_scheme: {
    term: "PLI (Production-Linked Incentive) schemes",
    one: "Government cash rewards paid to companies for manufacturing more inside India.",
    what: "Under a Production-Linked Incentive scheme, the government pays companies a bonus tied to how much they actually produce and sell from Indian factories, in sectors like electronics, chips, pharma, and solar. The goal is to lure factories to India and cut reliance on imports (part of 'Make in India').",
    read: "A new PLI scheme, or a big company signing up, signals the government is pushing to build that industry at home — often a positive for firms in that sector. Watch whether targets are met, since incentives are paid on real output, not promises.",
    why: "It's a central plank of India's bid to become a manufacturing hub and reduce dependence on imports, especially from China."
  },
  cag: {
    term: "The CAG (Comptroller and Auditor General)",
    one: "India's independent auditor — it checks how the government spends public money.",
    what: "The Comptroller and Auditor General audits the accounts of the central and state governments and public bodies, then reports to Parliament. It's a constitutional post designed to be independent, so it can flag waste, irregularities, or losses without political interference.",
    read: "A CAG report flagging 'losses' or 'irregularities' in a scheme or contract can trigger big political rows and investigations — it's a watchdog's verdict on how tax money was used. Its findings often force accountability.",
    why: "It's a key check on government spending — the institution that tells Parliament and the public whether money was used properly."
  },
  judiciary_collegium: {
    term: "The Collegium (how judges are picked)",
    one: "The system where senior judges themselves choose who becomes a top judge.",
    what: "In India, senior Supreme Court judges led by the Chief Justice form a 'collegium' that recommends who should be appointed or promoted to the higher courts. The government processes the names but has limited power to reject them — an arrangement meant to keep the judiciary independent of politics.",
    read: "'Collegium recommended X' or 'the government sat on the names' points to the recurring tug-of-war between judges and government over who controls judicial appointments — a live debate about judicial independence versus accountability.",
    why: "Who becomes a judge shapes how laws are read for decades, so the fight over this process is really a fight over the courts' independence."
  },
  president_of_india: {
    term: "The President of India",
    one: "India's head of state — a mostly ceremonial role that formally signs off laws and appointments.",
    what: "The President is India's constitutional head, elected not by the public but by an 'electoral college' of MPs and state lawmakers. Real power rests with the Prime Minister and Cabinet; the President mostly acts on their advice — giving assent to bills, appointing the PM, and formally commanding the armed forces.",
    read: "Most presidential acts are formalities, but a few carry weight: assenting to or delaying a bill, or acting in a rare deadlock like a hung Parliament. 'The President gave assent' means a bill has officially become law.",
    why: "It's the ceremonial apex of the state and a constitutional backstop — worth knowing it's the PM, not the President, who actually governs."
  },
  governor_state: {
    term: "The Governor (of a state)",
    one: "The centre's appointed representative in each state — a largely ceremonial head who can clash with elected state governments.",
    what: "Each state has a Governor, appointed by the President (effectively the central government), as its ceremonial head. Like the President nationally, the Governor mostly acts on the advice of the elected state government — signing state bills and appointing the Chief Minister.",
    read: "Governors make news when they clash with a state government run by a rival party — sitting on bills, delaying decisions, or reserving laws for the President. That friction is really a centre-versus-state power struggle.",
    why: "The office sits on the fault line between the centre and the states, so a Governor's actions can become flashpoints in India's federal politics."
  },
  enforcement_directorate: {
    term: "The ED (Enforcement Directorate)",
    one: "The agency that investigates money-laundering and foreign-exchange crimes — and can seize assets and arrest.",
    what: "The Enforcement Directorate is a central agency that probes financial crimes, mainly money-laundering (hiding the source of illegal money) and foreign-exchange violations. It can summon people, freeze and seize property, and make arrests under tough laws where bail is hard to get.",
    read: "An ED 'raid', 'summons', or 'attachment' signals a serious financial-crime probe. Because targets are often politicians or business figures, opposition parties frequently allege it's used selectively — a contested, recurring debate. Note who's charged and with what.",
    why: "It's one of India's most powerful investigative agencies, and its high-profile cases regularly shape both business and politics."
  },
  cbi: {
    term: "The CBI (Central Bureau of Investigation)",
    one: "India's premier federal investigating agency — it handles major corruption, fraud, and high-profile crimes.",
    what: "The Central Bureau of Investigation is the central government's main police agency for serious cases: big corruption, complex fraud, and crimes courts hand to it. It often takes over cases too big or sensitive for state police, but usually needs a state's consent (or a court order) to operate there.",
    read: "A 'CBI probe' means a case has been escalated to the top federal level — a signal of seriousness. As with the ED, its independence is debated: opposition parties often claim it's steered by whoever is in power, so note who's targeted and who ordered the probe.",
    why: "It handles the country's biggest corruption and fraud cases, so its investigations regularly drive major political and legal news."
  },
});

/* ==========================================================================
   WORLD / GEOPOLITICS / SCIENCE / HEALTH / CLIMATE — non-market news terms.
   ========================================================================== */
Object.assign(GLOSSARY, {
  ceasefire_vs_truce: {
    term: "Ceasefire, truce & armistice",
    one: "Different levels of 'stop shooting' — from a short pause to a formal end of fighting.",
    what: "A ceasefire is an agreement to halt combat, often temporary and fragile. A truce is usually a brief, informal pause (for aid, evacuations, or holidays). An armistice is a formal, negotiated stop that can last indefinitely. But none of these is a peace treaty — the fighting stops, the underlying dispute is not settled.",
    read: "When you see 'ceasefire', ask three things: is it holding, who's monitoring it, and does it have an expiry. One that keeps getting 'violated' means the war isn't really over. A ceasefire is a pause either side can break, not peace.",
    why: "The word chosen tells you how durable the calm is — and whether markets, oil, and refugees can expect relief or just a lull."
  },
  sovereign_debt: {
    term: "Sovereign debt & default",
    one: "The money a national government owes — and what happens when it can't pay.",
    what: "Governments borrow by selling bonds (IOUs) to investors and other countries; that pile is 'sovereign debt'. A 'default' is when a country can't or won't make its payments — like Sri Lanka in 2022. Unlike a company, a country can't be shut down and sold off, so defaults get resolved through painful 'restructuring' — lenders accept less, or wait longer.",
    read: "Rising default worry shows up as soaring bond yields (lenders demand more to lend to a shaky borrower) and a falling currency. A bailout headline (see IMF) usually means a country is near the edge.",
    why: "A sovereign default can freeze a country's imports of fuel and medicine, spark inflation and unrest, and spill into neighbours — where economics and politics collide most violently.",
    scale: "Debt-to-GDP: under ~60% comfortable · ~90–100% elevated · well above 100% a red flag for weaker economies."
  },
  coup: {
    term: "Coup d'état",
    one: "A sudden, usually illegal seizure of a country's government — often by the military.",
    what: "A coup ('blow of state') is when a small group — frequently army officers — removes the sitting leaders by force or threat, outside any election. It's fast, and it grabs the levers of power: the capital, TV stations, the presidential palace. Unlike a revolution (a mass popular uprising), a coup is usually top-down and by insiders.",
    read: "After a coup, watch: is the army united behind it, are borders/airports/internet shut, and do big powers and neighbours recognise it or sanction it. 'Attempted coup' means it failed or is unresolved. Coups cluster — one in a region raises the odds of others.",
    why: "Coups reset a country's alliances, freeze investment, and often trigger sanctions — reshaping trade and security far beyond their borders."
  },
  referendum: {
    term: "Referendum (a public vote)",
    one: "A direct yes/no vote by the people on a single big question, not for a candidate.",
    what: "Instead of leaving a decision to parliament, the government puts one question straight to voters — 'should we leave the EU?' (Brexit, 2016), 'should we change the constitution?'. A referendum can be binding (the result becomes law) or advisory (guidance only). It's direct democracy on a single issue.",
    read: "When one is called, watch the exact wording (often loaded), any turnout threshold (some need a minimum turnout to count), and whether it's binding. A close result rarely settles anything — it usually deepens the divide.",
    why: "Referendums can redraw borders, rewrite constitutions, or pull a country out of an alliance overnight — high-stakes moments markets and neighbours watch nervously."
  },
  un_security_council: {
    term: "UN Security Council (UNSC)",
    one: "The UN's most powerful body — the only one that can order binding action like sanctions or force.",
    what: "The UN has 193 members, but real muscle sits in the 15-seat Security Council. Five are permanent members (the 'P5': US, UK, France, Russia, China); ten rotate. Only the UNSC can pass legally binding resolutions — authorising peacekeepers, sanctions, or military action.",
    read: "When a crisis reaches the UNSC, the story is usually whether the P5 agree. If one opposes, expect deadlock (see Veto). A resolution that passes signals rare global consensus; a blocked one signals the big powers are split.",
    why: "It's where the world's most serious conflicts get either contained or stalemated — and where you can read the real alignment of the great powers."
  },
  veto_power: {
    term: "Veto power (the P5's block button)",
    one: "The right of five countries to single-handedly kill any UN Security Council decision.",
    what: "Each of the five permanent members (US, UK, France, Russia, China) can veto — one 'no' vote defeats a resolution even if all 14 others agree. It's a legacy of who won World War II. It stops the UN acting against a great power's core interests, but also means the UN often can't act on the biggest conflicts.",
    read: "'Russia vetoed' or 'US vetoed' a resolution tells you a great power is protecting an ally or itself. Repeated vetoes on the same crisis (Syria, Gaza, Ukraine) mean the UN is paralysed and the issue will be fought out elsewhere.",
    why: "The veto is why the UN can feel powerless on the wars that matter most — understanding it explains a lot of global stalemate."
  },
  nato: {
    term: "NATO (the Western military alliance)",
    one: "A defence pact where an attack on one member is treated as an attack on all.",
    what: "The North Atlantic Treaty Organization is a group of 30-plus mostly Western nations (US, UK, most of Europe, Canada, Turkey). Its core promise is Article 5: if one member is attacked, the others come to its defence. It formed in 1949 to deter the Soviet Union and has since expanded eastward toward Russia's borders — a major source of today's tension.",
    read: "When you see 'NATO', the subtext is usually deterrence against Russia. 'Article 5' invoked = a member says it's under attack (used only once, after 9/11). New members joining (Finland, Sweden) signals fear of Russia; 'burden-sharing' talk is about who pays.",
    why: "NATO is the backbone of Western security — its cohesion or cracks shape whether conflicts in Europe stay contained or spread."
  },
  brics: {
    term: "BRICS (the non-Western bloc)",
    one: "A club of major developing economies positioning as a counterweight to the US-led West.",
    what: "Originally Brazil, Russia, India, China, South Africa — now expanded to include others (Iran, UAE, Egypt, Ethiopia and more). It's not a formal alliance like NATO; it's a loose grouping pushing for a bigger say in global affairs, more trade in local currencies (less dollar dependence), and its own development bank.",
    read: "Watch two themes: 'de-dollarisation' (trading oil and goods without the US dollar) and any move to add members or a shared payment system. BRICS is more talk than unified action — its members often disagree (India vs China especially) — so weigh announcements against real follow-through.",
    why: "It represents the 'Global South' wanting a seat at the table — and India is a central, and independent-minded, player."
  },
  g20: {
    term: "The G20 (top-20 economies forum)",
    one: "Where the world's 20 biggest economies meet to coordinate on the global economy.",
    what: "The Group of Twenty gathers the largest advanced and emerging economies (US, China, India, EU, and more) — together about 85% of world output. It has no army and passes no binding laws; it's a table for leaders and finance ministers to agree on shared approaches to crises, debt, climate finance, and trade. India hosted it in 2023.",
    read: "G20 summits produce a joint 'communiqué' (statement). Read what it does — and doesn't — say: a watered-down line on Ukraine or climate signals the members couldn't agree. It's a temperature check on whether the big economies can still cooperate.",
    why: "When the G20 pulls together (as in the 2008 crisis) it can steady the whole world economy; when it splinters, global problems go unmanaged."
  },
  imf_world_bank: {
    term: "IMF & World Bank",
    one: "The two big global lenders — one rescues economies in crisis, the other funds long-term development.",
    what: "The International Monetary Fund (IMF) is the world's financial firefighter: it lends emergency money to countries that can't pay their bills, but attaches strict conditions (spending cuts, reforms). The World Bank instead funds long-term projects — roads, power, schools — in poorer countries. Both were created after WWII and are heavily US/Western-influenced.",
    read: "An 'IMF bailout' or 'IMF programme' headline means a country is in serious financial trouble (Pakistan, Sri Lanka, Argentina are frequent cases). The conditions attached often spark protests. IMF growth forecasts are also widely cited as a global scorecard.",
    why: "The IMF is often the last line before a country defaults — its involvement signals both a lifeline and a loss of economic sovereignty."
  },
  proxy_war: {
    term: "Proxy war",
    one: "A conflict where big powers fight each other indirectly, through local forces instead of directly.",
    what: "Rather than attack each other openly (too dangerous, especially with nuclear weapons), rival powers back opposing sides in someone else's war — arming, funding, or advising local fighters. The Cold War was full of these (Vietnam, Afghanistan); today think of outside powers backing rival factions in the Middle East.",
    read: "When a local war has surprisingly advanced weapons or outside money on both sides, it's likely a proxy war. Ask 'who benefits' beyond the immediate fighters — the real contest is often between the sponsors, not the locals.",
    why: "Proxy wars let great powers compete without direct war — but they drag out conflicts, devastate the host country, and can escalate unexpectedly."
  },
  annexation: {
    term: "Annexation",
    one: "One country formally seizing and absorbing territory that belonged to another.",
    what: "Annexation is when a state takes over land and declares it its own — not just occupying it, but claiming it as permanent national territory (like Russia's claim over Crimea in 2014). Under international law it's generally illegal if done by force, so most of the world usually refuses to recognise it.",
    read: "Watch the gap between control and recognition: a country can hold land while almost no one accepts the annexation as legal. 'Referendums' held under occupation to justify it are usually dismissed as staged. It typically triggers sanctions.",
    why: "Annexation directly challenges the post-WWII rule that borders shouldn't be changed by force — which is why it provokes such strong global reactions."
  },
  nuclear_deterrence: {
    term: "Nuclear deterrence",
    one: "The grim logic that having nuclear weapons stops others from attacking you.",
    what: "Deterrence means preventing an attack by making the cost unbearable. With nukes, the idea is 'Mutually Assured Destruction': if either side launches, both are annihilated, so neither dares to start. This is why nuclear-armed states (US, Russia, China, India, Pakistan, and others) rarely fight each other directly.",
    read: "When a leader raises nuclear 'alert levels' or hints at using weapons, it's usually signalling — trying to scare an opponent into backing down without actually intending to launch. Still, each threat erodes the taboo. Watch for 'red lines' and whether they're being tested.",
    why: "Deterrence has kept the great powers from all-out war for 80 years — but it also pushes their conflicts into proxy wars and brinkmanship instead."
  },
  strait_chokepoint: {
    term: "Straits & maritime chokepoints",
    one: "Narrow sea passages that a huge share of world trade must squeeze through — and where it can be blocked.",
    what: "Much of global oil and goods travels by ship through a few narrow waterways: the Strait of Hormuz (a fifth of the world's oil), the Suez Canal, the Strait of Malacca, the Bab-el-Mandeb. Because so much flows through so little space, a blockage, attack, or grounded ship there (like the 2021 Suez blockage) can choke global supply.",
    read: "A threat to any of these means insurers charge more, ships reroute the long way (adding weeks and cost), and oil and shipped-goods prices jump. For India especially, Hormuz is the artery for its imported oil.",
    why: "These pinch-points are where distant geopolitics turns directly into higher fuel and shipping costs — and inflation — worldwide."
  },
  refugee_asylum: {
    term: "Refugees & asylum",
    one: "People forced to flee their country — and the legal right to seek safety in another.",
    what: "A refugee is someone who flees across a border to escape war, persecution, or disaster. 'Asylum' is the protection a person requests from another country; if granted, they can legally stay. A 'migrant' is broader — anyone moving, including for work — and the distinction matters legally and politically. (People who flee but stay inside their own country are 'internally displaced'.)",
    read: "A surge in refugee numbers signals a crisis worsening — war, famine, collapse. Watch how neighbouring countries respond (open borders, camps, or pushbacks), as it shapes both the humanitarian outcome and domestic politics, where migration is often a hot-button issue.",
    why: "Refugee flows are both a human tragedy and a political flashpoint — reshaping elections, budgets, and relations between countries."
  },
  extradition: {
    term: "Extradition",
    one: "One country handing over a wanted person to another country to face charges.",
    what: "When someone accused or convicted of a crime flees abroad, the country that wants them can request 'extradition' — a formal legal process to send them back. It depends on treaties between the two countries, and courts (sometimes politicians) must approve it. Countries often refuse if the charges look political, if the death penalty applies, or if there's no treaty.",
    read: "An extradition fight (like high-profile financial fugitives India seeks from the UK) is usually slow and political. Watch whether a treaty exists and whether courts see the case as genuine crime or political persecution — that decides the outcome as much as the evidence.",
    why: "Extradition is where one country's justice system meets another's sovereignty — a common friction point in cross-border crime, finance, and politics."
  },
  mrna: {
    term: "mRNA (the technology behind new vaccines)",
    one: "A molecule that carries instructions telling your cells to make a protein — used to train your immune system.",
    what: "mRNA ('messenger RNA') is a natural courier inside every cell, carrying a copy of a gene's instructions to the cell's protein factories. mRNA vaccines (like the Covid ones from Pfizer and Moderna) use a lab-made snippet to tell your cells to briefly make a harmless piece of a virus, so your immune system learns to fight the real thing. The mRNA breaks down quickly and doesn't change your DNA.",
    read: "'mRNA' in health news usually signals a fast, flexible new treatment — the same platform is now being tested against flu, cancer, and more. Its big advantage is speed: the recipe can be reprogrammed in weeks. Watch for the 'clinical trial' stage (see Vaccine platforms).",
    why: "mRNA is one of the century's biggest medical breakthroughs — a plug-and-play platform that could reshape how we fight many diseases."
  },
  vaccine_platform: {
    term: "Vaccine platforms & clinical trials",
    one: "The different technologies used to make vaccines — and the staged testing they must pass.",
    what: "A 'platform' is the underlying method: mRNA (instructions), viral-vector (a harmless carrier virus), or classic inactivated/protein vaccines. Before approval, any vaccine or drug goes through 'clinical trials' in phases — Phase 1 (safety, small group), Phase 2 (dosing, larger), Phase 3 (does it actually work, thousands of people) — then regulators review it.",
    read: "The phase tells you how far along and how proven something is: Phase 1 = very early, Phase 3 = nearly ready. 'Emergency use authorisation' means it was cleared faster than usual in a crisis. Be wary of hype around early-phase results.",
    why: "Knowing the phases lets you judge whether a 'breakthrough' headline is a real, tested treatment or an early experiment years from your pharmacy.",
    scale: "Phase 1 = safety (small) · Phase 2 = dosing (larger) · Phase 3 = does it work (thousands) · then regulatory review."
  },
  gene_editing: {
    term: "Gene editing",
    one: "Precisely changing the DNA 'instruction book' inside living cells to fix or alter traits.",
    what: "Every living thing runs on DNA — a long code of instructions. Gene editing is a set of lab tools that can cut, delete, or rewrite specific letters of that code. It's used to correct disease-causing mutations (sickle-cell disease now has an approved gene-editing cure), engineer hardier crops, or study biology. It's far more precise than older genetic modification.",
    read: "When gene editing is in the news, tell apart 'treating a patient' (widely accepted) from 'editing embryos' that pass changes to future generations (deeply controversial and largely banned). Watch the ethics debate and which regulator approved what.",
    why: "Gene editing could cure once-untreatable diseases and reshape agriculture — while raising profound questions about how far we should rewrite life."
  },
  crispr: {
    term: "CRISPR (the gene-editing tool)",
    one: "A cheap, precise molecular 'find-and-replace' for DNA that made gene editing mainstream.",
    what: "CRISPR is the best-known gene-editing technology — think of it as programmable scissors guided to an exact spot in the DNA, where it cuts so a faulty gene can be disabled or replaced. Borrowed from a natural bacterial defence system, it's dramatically cheaper and easier than earlier methods, which is why it won a Nobel Prize and sparked a research boom.",
    read: "'CRISPR' in a headline means gene editing specifically. The same phase and ethics questions apply (see Gene editing): is it a lab result, an animal study, or an approved human therapy? Its cheapness means many labs and companies are racing to use it.",
    why: "CRISPR turned gene editing from expensive and rare into fast and widespread — accelerating both medical cures and the ethical debates around them."
  },
  el_nino: {
    term: "El Niño & La Niña",
    one: "A natural warming (El Niño) or cooling (La Niña) of the Pacific that shifts weather worldwide.",
    what: "Every few years the surface of the tropical Pacific Ocean warms up (El Niño) or cools down (La Niña). This shifts where rain falls and where droughts hit across the whole planet — for India, an El Niño year often means a weaker monsoon (less rain), while La Niña tends toward more. It's a natural cycle, separate from long-term climate change though the two interact.",
    read: "When forecasters flag 'El Niño', expect stories about weaker Indian monsoons, drought risk, and pressure on crop prices and food inflation. La Niña flips the odds. Watch the official monsoon forecasts (India's IMD) that follow these signals.",
    why: "For India, where farming and food prices ride on the monsoon, an El Niño warning is an early flag for the whole economy — from rural incomes to inflation."
  },
  opec: {
    term: "OPEC & OPEC+ (the oil cartel)",
    one: "The group of major oil-producing nations that coordinates output to steer crude prices.",
    what: "OPEC (Organization of the Petroleum Exporting Countries), led by Saudi Arabia, is a club of big oil exporters. 'OPEC+' adds allies like Russia. By agreeing to pump more or less oil together, they influence the global oil price — cutting output pushes prices up, raising output pushes them down. It's effectively a cartel managing supply.",
    read: "When 'OPEC+ cuts production', expect oil prices to rise — bad for oil importers like India (higher fuel, inflation), good for producers. When they 'open the taps', the reverse. Watch whether members actually stick to agreed quotas, since cheating is common.",
    why: "OPEC+ decisions directly set what the world — and India — pays for fuel, making them a major, recurring driver of inflation and geopolitics."
  },
  carbon_credits: {
    term: "Carbon credits & carbon markets",
    one: "A permit to emit one tonne of CO₂ — turning pollution into something priced and traded.",
    what: "To fight climate change, governments cap how much carbon dioxide companies can emit and issue 'credits', each allowing a set amount of emissions. Firms that pollute less can sell their spare credits to firms that pollute more. The idea: put a price on carbon so polluting costs money and cutting emissions pays. Separate 'offset' credits fund projects (like planting forests) that absorb CO₂.",
    read: "A rising carbon price makes polluting industries costlier and clean energy relatively cheaper — watch its effect on power, steel, and cement firms. Be sceptical of cheap 'offsets': many have been criticised for not delivering the promised cuts.",
    why: "Carbon markets are one of the main tools the world uses to make climate goals bite economically — shaping which industries thrive or struggle."
  },
  cop_climate_summit: {
    term: "COP climate summits",
    one: "The annual UN meeting where nearly every country negotiates action on climate change.",
    what: "COP ('Conference of the Parties') is the yearly gathering — COP28, COP29, and so on — where governments haggle over cutting greenhouse gases, funding poorer nations, and limiting warming. The landmark 2015 Paris Agreement (from COP21) set the goal of keeping warming well below 2°C. Deals are made by consensus, so they're often watered down.",
    read: "COP produces pledges and a final text — read what's actually binding versus merely 'aspirational', and whether rich nations commit real 'climate finance' to poorer ones. Big fights recur over 'phasing out' fossil fuels and who pays for climate damage.",
    why: "COP is the main stage where the world tries — and often struggles — to coordinate on climate, setting targets that ripple into energy policy and business everywhere."
  },
  quantitative_easing: {
    term: "Quantitative easing (QE) & tightening (QT)",
    one: "A central bank creating new money to buy bonds — pumping cash into the economy, or reversing it.",
    what: "When cutting interest rates isn't enough, a central bank can do QE: create money digitally and use it to buy bonds, which pushes down long-term rates and floods the system with cash to encourage lending and investment. The reverse — selling those bonds and pulling money back out — is Quantitative Tightening (QT). Both are extraordinary tools used after 2008 and during Covid.",
    read: "'QE' or 'balance-sheet expansion' generally lifts stocks, bonds, gold, and crypto (more cheap money chasing assets). 'QT' or 'balance-sheet runoff' does the opposite — draining cash, a headwind for risky assets. Watch which way the big central banks lean.",
    why: "QE/QT is one of the most powerful forces on markets — the tide of money that can inflate or deflate asset prices across the whole world."
  },
  yield_curve: {
    term: "The yield curve (and inversion)",
    one: "A line comparing short-term and long-term interest rates — a famous recession warning when it flips.",
    what: "The yield curve plots the interest rate ('yield') a government pays on bonds of different lengths — 3-month, 2-year, 10-year, and so on. Normally longer loans pay more (an upward slope). When short-term rates rise above long-term ones, the curve 'inverts' — a signal investors expect the economy to slow and rates to be cut later. An inverted curve has preceded most US recessions.",
    read: "'Yield curve inverts' = a classic, if imperfect, recession warning: markets are betting on trouble ahead. It can invert months or even a year before any downturn, so it's an early flag, not a timer. A 'steepening' curve often signals recovery or rising inflation expectations.",
    why: "It's one of the most-watched signals in finance because it distils the bond market's collective bet on where the economy is heading.",
    scale: "Normal = long rates above short · Inverted = short above long (recession warning) · Steepening = the gap widening."
  },
  gdp_vs_gnp: {
    term: "GDP vs GNP vs GDP-per-capita",
    one: "Different ways to measure an economy's size — total output, citizens' output, and output per person.",
    what: "GDP (Gross Domestic Product) counts everything produced inside a country's borders. GNP (Gross National Product) counts everything produced by a country's people and companies, wherever they are. GDP-per-capita divides total output by population — a rough gauge of average prosperity. India has a huge GDP (top-5 in the world) but a modest GDP-per-capita, because of its enormous population.",
    read: "When you see a country 'ranked 5th by GDP', that says nothing about how rich its average citizen is — check per-capita for that. Big total GDP means global economic weight; high per-capita means individual prosperity. The two often diverge sharply.",
    why: "The distinction stops you misreading headlines: India can be an economic giant in total size while still being a developing country per person."
  },
  soft_power: {
    term: "Soft power",
    one: "A country's ability to get its way through attraction and influence, not force or money.",
    what: "Coined by scholar Joseph Nye, soft power is influence that comes from being admired or trusted — through culture (Bollywood, K-pop, Hollywood), values, diplomacy, aid, and education. It's the opposite of 'hard power' (military and economic coercion). A country with strong soft power gets others to want what it wants, without threats.",
    read: "Stories about a country's cultural exports, diaspora, foreign aid, or hosting global events are soft power at work — building goodwill that later turns into diplomatic and economic advantage. India's diaspora, cinema, and yoga are classic examples.",
    why: "Soft power shapes alliances and trade in quiet, long-term ways — often explaining why countries cooperate even without a formal deal or threat."
  },
  sovereign_wealth_fund: {
    term: "Sovereign wealth fund (SWF)",
    one: "A giant government-owned investment fund — a country's national savings pot invested worldwide.",
    what: "Some governments, especially oil-rich ones (Norway, Saudi Arabia, UAE, Singapore), take surplus national income and invest it globally — in stocks, companies, real estate, and infrastructure. These funds can be enormous (Norway's is worth over a trillion dollars) and are run to grow the nation's wealth for future generations or diversify away from oil.",
    read: "When an SWF takes a big stake in a company, stadium, or startup, it signals a government-backed, long-term investor with deep pockets — often reshaping industries or rescuing firms. Watch which ones invest in India (Gulf and Singapore funds are active here).",
    why: "SWFs move vast sums and can sway markets and whole industries — a way for resource-rich states to buy lasting global economic influence."
  },
  insurgency_militancy: {
    term: "Insurgency & militancy",
    one: "An armed rebellion against a government by non-state fighters, usually using guerrilla tactics.",
    what: "An insurgency is an organised armed movement trying to overthrow or resist a government from within — not a foreign army, but internal fighters ('militants' or 'rebels'). They avoid open battles and instead use ambushes, bombings, and hit-and-run raids ('guerrilla warfare'), often blending into the local population. Causes range from separatism to ideology.",
    read: "Words are contested here: one side's 'freedom fighters' are another's 'terrorists'. Watch whether a group controls territory (a sign of strength), and whether the government responds with force, talks, or both. Insurgencies tend to be long, grinding, and hard to end militarily.",
    why: "Insurgencies destabilise regions for years or decades — disrupting trade, displacing people, and often drawing in outside powers (turning into proxy wars)."
  },
  martial_law: {
    term: "Martial law",
    one: "When the military takes over running a country or region, suspending normal civilian law.",
    what: "In a severe crisis — war, coup, mass unrest — a government or the army itself can declare martial law, handing control to the military. Normal rights are suspended: curfews imposed, courts replaced by military tribunals, protests banned, media censored. It's meant to be temporary and extreme, and often signals a government losing control or seizing it.",
    read: "A martial-law declaration is a red flag: it signals either a genuine emergency or an authoritarian power grab. Watch how long it's meant to last, whether elections and courts are suspended, and how the population and army react.",
    why: "Martial law strips away the everyday checks on power — its declaration is one of the clearest signs a country's democracy or stability is in serious danger."
  },
  impeachment: {
    term: "Impeachment",
    one: "The formal process by which a legislature charges a top official (like a president) with serious wrongdoing.",
    what: "Impeachment is a constitutional way to hold leaders accountable. A legislature (parliament or congress) formally accuses a president, judge, or minister of grave misconduct. Crucially, 'impeached' means charged, not removed — a separate vote, usually needing a large majority, decides whether to actually remove them. Rules vary by country.",
    read: "Don't confuse 'impeached' with 'ousted' — many impeached leaders finish their terms because the removal vote fails. Watch the numbers: does the accusing side have the supermajority needed to actually remove the official? It's often as much a political weapon as a legal one.",
    why: "Impeachment is a core check on powerful leaders — its use, or failure, reveals how strong a country's institutions and rule of law really are."
  },
});
