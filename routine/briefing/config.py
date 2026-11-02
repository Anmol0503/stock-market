"""Settings for the Morning Briefing: sections, quotas, word limits, models per role, and IST time helpers.

Everything tunable lives here so the pipeline code stays free of magic numbers.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:          # so `import fetch_world` / `build_dashboard` work from anywhere
    sys.path.insert(0, str(ROOT))

# Dry runs can redirect both (BRIEFING_OUT_DIR / BRIEFING_PUB_DIR) so nothing lands in the repo.
OUT_ROOT = pathlib.Path(os.environ.get("BRIEFING_OUT_DIR") or ROOT / "output" / "briefing")   # working files
PUB = pathlib.Path(os.environ.get("BRIEFING_PUB_DIR") or ROOT / "dashboard" / "briefing")     # PUBLIC output
CONFIG_DIR = ROOT / "config"
PROMPTS = pathlib.Path(__file__).resolve().parent / "prompts"

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
UTC = dt.timezone.utc

# ---------------------------------------------------------------- sections (reading order everywhere)
SECTIONS: dict[str, tuple[str, str]] = {
    "world":       ("🌍", "World"),
    "india":       ("🇮🇳", "India"),
    "affects_you": ("🧾", "Your money & life"),
    "markets":     ("📈", "Markets & money"),
    "tech_ai":     ("🤖", "Tech & AI"),
    "science":     ("🔬", "Science, health & climate"),
    "f1":          ("🏎️", "Formula 1"),
    "cricket":     ("🏏", "Cricket — the masala"),
}
SECTION_KEYS = list(SECTIONS)
NEVER_QUIET = {"world", "india", "markets"}      # these always have at least 2 briefs
INTEREST_SECTIONS = {"f1", "cricket"}            # personal-interest beats: scored separately, never crowd out news

# raw feed category -> section (the editor may move a story)
CATEGORY_SECTION = {
    "geopolitics": "world", "economy": "markets", "markets": "markets", "technology": "tech_ai",
    "science": "science", "health": "science", "climate": "science", "india": "india",
    "affects_you": "affects_you", "f1": "f1", "cricket": "cricket",
}

# ---------------------------------------------------------------- edition shape
TIER1_TARGET = 5          # big stories: reel + full explainer (~4.5 min each) — fits the 30–45 min budget
TIER1_MIN_COMPLETE = 4    # fewer than this = "partial" edition
TIER1_MAX = 6
TIER1_RESERVES = 2
BRIEFS_MIN, BRIEFS_MAX = 16, 32
BRIEFS_PER_SECTION = (2, 6)
ALSO_MIN, ALSO_MAX = 6, 15
QUIZ_N = 3
INDIA_SUBSTANTIAL_MIN = 3
US_DOMESTIC_TIER1_MAX = 2
TRIAGE_CAP = 320          # clusters sent to triage (cheap pre-filter in code first)
TRIAGE_BATCH = 40
EDITOR_CANDIDATES = 80    # clusters shown to the editor

# word ranges (min, max) per field — enforced by build.py, mirrored in the prompts
WORDS = {
    "headline": (5, 12), "question": (6, 18), "dek": (15, 35),
    "so_far": (40, 110), "what_happened": (50, 110), "why_step": (8, 25), "for_you": (25, 70),
    "analogy": (20, 60), "analogy_breaks": (8, 30), "next": (20, 50), "changed": (10, 40),
    "thread_summary": (20, 80), "view": (8, 40), "myth": (5, 20), "fact": (8, 40),
    "brief_text": (50, 120), "brief_background": (8, 30), "brief_why": (8, 25), "also": (8, 25),
    "top_line": (15, 40), "change": (5, 22), "watch": (4, 20), "gist": (8, 25), "quiet_note": (5, 25),
    "term_meaning": (4, 20), "check_q": (6, 25), "check_why": (5, 30),
    "story_total": (450, 850), "reel_total": (130, 190), "scene_say": (6, 50), "scene_show": (0, 8),
}
EXCERPT_MAX_CHARS = 200   # public excerpts stay short (copyright)

# ---------------------------------------------------------------- run timing
WINDOW_FALLBACK_H = 26    # first run / no previous edition: look back this far
WINDOW_OVERLAP_MIN = 60   # each window starts an hour before the previous one ended
DEADLINE_IST = dt.time(5, 40)     # scheduled runs stop model work here and publish what passed
MANUAL_RUN_MINUTES = 95           # a run started at another time gets this long
CONCURRENCY = int(os.environ.get("BRIEFING_CONCURRENCY", "6"))
NEXT_TICK_SECONDS = 510           # `next` waits at most 8.5 min (Bash tool limit is 10)

# ---------------------------------------------------------------- models per role
SONNET = os.environ.get("BRIEFING_SONNET", "claude-sonnet-5-5")
OPUS = os.environ.get("BRIEFING_OPUS", "claude-opus-5-5")
FALLBACK_MODEL = SONNET

# role -> model, effort, tools ("" = none), per-call budget cap (USD, API-equivalent), timeout (s)
ROLES: dict[str, dict] = {
    "triage":     {"model": SONNET, "effort": "low",    "tools": "",                   "budget": 0.8, "timeout": 420},
    "same_story": {"model": SONNET, "effort": "low",    "tools": "",                   "budget": 0.6, "timeout": 300},
    "recall":     {"model": SONNET, "effort": "low",    "tools": "",                   "budget": 0.6, "timeout": 300},
    "bootstrap":  {"model": SONNET, "effort": "medium", "tools": "",                   "budget": 1.0, "timeout": 420},
    "scout":      {"model": SONNET, "effort": "medium", "tools": "WebSearch",          "budget": 1.5, "timeout": 600},
    "editor":     {"model": OPUS,   "effort": "high",   "tools": "",                   "budget": 3.0, "timeout": 600},
    "research":   {"model": SONNET, "effort": "medium", "tools": "WebSearch,WebFetch", "budget": 1.5, "timeout": 600},
    "writer":     {"model": OPUS,   "effort": "high",   "tools": "",                   "budget": 2.0, "timeout": 600},
    "checker":    {"model": SONNET, "effort": "medium", "tools": "",                   "budget": 0.8, "timeout": 420},
    "fixer":      {"model": OPUS,   "effort": "high",   "tools": "",                   "budget": 1.5, "timeout": 600},
    "section":    {"model": SONNET, "effort": "medium", "tools": "WebSearch,WebFetch", "budget": 1.2, "timeout": 600},
    "briefs":     {"model": OPUS,   "effort": "high",   "tools": "",                   "budget": 2.0, "timeout": 600},
    "cover":      {"model": OPUS,   "effort": "medium", "tools": "",                   "budget": 1.0, "timeout": 420},
}
for _role, _cfg in ROLES.items():       # env overrides, e.g. BRIEFING_MODEL_WRITER=claude-sonnet-5-5
    _cfg["model"] = os.environ.get(f"BRIEFING_MODEL_{_role.upper()}", _cfg["model"])

# reel voice (Phase 2)
REEL_VOICE = "en-IN-NeerjaNeural"

DISCLAIMER = ("Not financial advice. A personal, automated news briefing: explanations of public reporting with "
              "links to the original sources. Check anything important before acting on it.")


# ---------------------------------------------------------------- time helpers
def now_ist() -> dt.datetime:
    fake = os.environ.get("BRIEFING_NOW")          # tests / dry runs can pin the clock
    if fake:
        t = dt.datetime.fromisoformat(fake)
        return (t if t.tzinfo else t.replace(tzinfo=IST)).astimezone(IST)
    return dt.datetime.now(IST)


def edition_date(now: dt.datetime | None = None) -> str:
    """The edition is named for the IST morning it's read on. Never use dt.date.today(): that's UTC in the cloud."""
    return (now or now_ist()).astimezone(IST).date().isoformat()


def parse_ts(s) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def iso(t: dt.datetime) -> str:
    return t.astimezone(IST).isoformat(timespec="minutes")


def deadline_for(start: dt.datetime) -> dt.datetime:
    """Scheduled early-morning runs stop at 05:40 IST; any other run gets MANUAL_RUN_MINUTES."""
    s = start.astimezone(IST)
    d = s.replace(hour=DEADLINE_IST.hour, minute=DEADLINE_IST.minute, second=0, microsecond=0)
    if dt.time(3, 0) <= s.time() < dt.time(5, 0):
        return d
    return s + dt.timedelta(minutes=MANUAL_RUN_MINUTES)


def day_dir(date: str) -> pathlib.Path:
    p = OUT_ROOT / date
    p.mkdir(parents=True, exist_ok=True)
    return p
