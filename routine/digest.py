#!/usr/bin/env python3
"""📰 The Daily Digest — one aggregated newsletter per IST day, folded together every ~3 hours.

Instead of a firehose of 20+ stories per tab, each run folds what's NEW since the last run into a single
running digest per day: a few sections (World, India, Affects you, Markets, Tech & AI, Science, F1, Cricket),
each with a running summary + at most 6 items. The 11 PM IST run marks the day FINAL.

Pure Python around ONE editor step (Claude). In the cloud routine the cloud agent IS the editor; on the Mac
`run-local` calls the headless CLI (Max subscription, Sonnet via config/usage.json).

  python3 routine/digest.py prepare     # raw feed (output/world-raw-latest.json) -> output/digest-context.json
  #   ...editor follows routine/digest_prompt.md -> writes output/digest-update.json
  python3 routine/digest.py merge       # validate -> dashboard/digest/digest-<date>.json + index.json
  python3 routine/digest.py run-local   # prepare -> headless Claude editor -> merge (Mac / testing)

dashboard/digest/ is PUBLIC (GitHub Pages): only news summaries + source links ever go there.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "routine"))

OUT = ROOT / "output"
RAW = OUT / "world-raw-latest.json"
CONTEXT = OUT / "digest-context.json"
UPDATE = OUT / "digest-update.json"
DIGEST_DIR = ROOT / "dashboard" / "digest"
INDEX = DIGEST_DIR / "index.json"
PROMPT = ROOT / "routine" / "digest_prompt.md"

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
FINAL_FROM = dt.time(22, 30)          # a run at/after 22:30 IST produces the day's FINAL edition
MAX_ITEMS = 6                         # per section — the whole point is that it stays readable
MAX_CANDIDATES = 22                   # raw leads handed to the editor per section bucket
LOOKBACK_FALLBACK_H = 12              # no previous run known -> look back this far

# section key -> (emoji, title). Order here is the reading order everywhere (page, Kindle).
SECTIONS = {
    "world":       ("🌍", "World"),
    "india":       ("🇮🇳", "India"),
    "affects_you": ("⚠️", "Affects you"),
    "markets":     ("📈", "Markets & money"),
    "tech_ai":     ("🤖", "Tech & AI"),
    "science":     ("🔬", "Science, health & climate"),
    "f1":          ("🏎️", "Formula 1"),
    "cricket":     ("🏏", "Cricket — the masala"),
}
# raw feed category -> digest bucket (the editor may still move a story to a better section)
BUCKET = {
    "geopolitics": "world", "economy": "markets", "markets": "markets", "technology": "tech_ai",
    "science": "science", "health": "science", "climate": "science", "india": "india",
    "affects_you": "affects_you", "f1": "f1", "cricket": "cricket",
}
DISCLAIMER = ("Not financial advice. A personal, automated news digest — summaries of public reporting "
              "with links to the original sources. Verify anything important before acting on it.")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


# ---------------------------------------------------------------- helpers
def _now() -> dt.datetime:
    return dt.datetime.now(IST)


def _load(p: pathlib.Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _write(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def _ts(s) -> dt.datetime | None:
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=IST)


def _day_file(date: str) -> pathlib.Path:
    return DIGEST_DIR / f"digest-{date}.json"


def _edition(now: dt.datetime, final: bool) -> str:
    return "Final · 11 PM" if final else "Updated " + now.strftime("%-I:%M %p")


def _sig(text: str) -> set:
    import build_dashboard as bd                     # reuse the feed's significant-word tokenizer
    return bd._sig_tokens({"title": text})


def _near_dup(toks: set, seen: list) -> bool:
    import build_dashboard as bd
    return bd._is_near_dup(toks, seen)


# ---------------------------------------------------------------- prepare
def _since(today: str, now: dt.datetime) -> dt.datetime:
    """Collect news published after the most recent digest run (today's, else yesterday's), so overnight
    news between yesterday's 11 PM final and today's first run is never lost."""
    yday = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
    for d in (today, yday):
        doc = _load(_day_file(d))
        t = _ts((doc or {}).get("updated_at"))
        if t:
            return t - dt.timedelta(minutes=30)       # small overlap: feeds stamp items late
    return now - dt.timedelta(hours=LOOKBACK_FALLBACK_H)


def prepare() -> int:
    raw = _load(RAW)
    if not raw:
        print(f"digest: no raw feed at {RAW.relative_to(ROOT)} — run fetch_world.py first", file=sys.stderr)
        return 1
    now = _now()
    today = now.date().isoformat()
    current = _load(_day_file(today))
    since = _since(today, now)

    buckets: dict[str, list[dict]] = {k: [] for k in SECTIONS}
    seen: dict[str, list[set]] = {k: [] for k in SECTIONS}
    items = sorted(raw.get("all_headlines") or [], key=lambda x: str(x.get("published_iso") or ""), reverse=True)
    for it in items:
        t = _ts(it.get("published_iso"))
        if t is None or t < since or t > now + dt.timedelta(hours=1):
            continue                                    # recency is a hard rule; undated items are skipped
        b = BUCKET.get(it.get("category"), "world")
        if len(buckets[b]) >= MAX_CANDIDATES:
            continue
        toks = _sig(it.get("headline") or "")
        if _near_dup(toks, seen[b]):
            continue                                    # same event from another outlet
        seen[b].append(toks)
        buckets[b].append({
            "headline": it.get("headline"), "source": it.get("source"), "url": it.get("url"),
            "published_iso": it.get("published_iso"), "summary": (it.get("summary") or "")[:260],
        })

    ctx = {
        "date": today,
        "now_ist": now.isoformat(timespec="minutes"),
        "is_final": now.time() >= FINAL_FROM,
        "since": since.isoformat(timespec="minutes"),
        "sections": {k: {"emoji": e, "title": t} for k, (e, t) in SECTIONS.items()},
        "max_items_per_section": MAX_ITEMS,
        "current_digest": current,                      # null on the first run of the day
        "candidates": buckets,
    }
    _write(CONTEXT, ctx)
    UPDATE.unlink(missing_ok=True)                      # never merge a stale update from a previous run
    n = sum(len(v) for v in buckets.values())
    print(f"digest: prepared {today} ({'FINAL' if ctx['is_final'] else 'update'}) — {n} new leads since "
          f"{since.strftime('%d %b %H:%M')} IST: " + ", ".join(f"{k}:{len(v)}" for k, v in buckets.items()))
    return 0


# ---------------------------------------------------------------- merge
def _validate(upd: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(upd, dict):
        return ["update is not a JSON object"]
    if not str(upd.get("top_line") or "").strip():
        errs.append("top_line is empty")
    top5 = upd.get("top5")
    if not isinstance(top5, list) or not (1 <= len(top5) <= 5):
        errs.append("top5 must be a list of 1–5 entries")
    else:
        for i, t in enumerate(top5):
            if not (isinstance(t, dict) and t.get("title") and t.get("why") and t.get("section") in SECTIONS):
                errs.append(f"top5[{i}] needs title, why and a valid section")
    secs = upd.get("sections")
    if not isinstance(secs, list):
        errs.append("sections must be a list")
        secs = []
    elif len(secs) < 3:
        errs.append("sections must have at least 3 sections")
    keys = set()
    for s in secs:
        k = s.get("key") if isinstance(s, dict) else None
        if k not in SECTIONS:
            errs.append(f"unknown section key {k!r}")
            continue
        if k in keys:
            errs.append(f"duplicate section {k}")
        keys.add(k)
        if not str(s.get("summary") or "").strip():
            errs.append(f"{k}: summary is empty")
        its = s.get("items")
        if not isinstance(its, list) or not its:
            errs.append(f"{k}: needs at least one item (omit the section if there's nothing)")
            continue
        if len(its) > MAX_ITEMS:
            errs.append(f"{k}: {len(its)} items > {MAX_ITEMS}")
        for j, it in enumerate(its):
            for f in ("headline", "what", "why_it_matters"):
                if not str((it or {}).get(f) or "").strip():
                    errs.append(f"{k}.items[{j}]: {f} is empty")
            srcs = (it or {}).get("sources") or []
            if not any(isinstance(x, dict) and str(x.get("url") or "").startswith("http") for x in srcs):
                errs.append(f"{k}.items[{j}]: needs at least one source with a url")
    blob = json.dumps(upd, ensure_ascii=False)
    if "/Users/" in blob or _EMAIL.search(blob):
        errs.append("contains a local path or an email address (public page!)")
    return errs


def merge() -> int:
    ctx = _load(CONTEXT)
    upd = _load(UPDATE)
    if not ctx:
        print("digest: no context — run `prepare` first", file=sys.stderr)
        return 1
    if upd is None:
        print(f"digest: {UPDATE.relative_to(ROOT)} missing or not valid JSON — keeping the previous digest",
              file=sys.stderr)
        return 1
    errs = _validate(upd)
    if errs:
        print("digest: update REJECTED — keeping the previous digest:\n  - " + "\n  - ".join(errs[:20]),
              file=sys.stderr)
        return 1

    now = _now()
    date = ctx["date"]                                  # the day prepare opened (a run can straddle midnight)
    final = bool(ctx.get("is_final"))
    prev = _load(_day_file(date)) or {}
    first_seen = {}                                     # keep an item's first-seen stamp across runs
    for s in prev.get("sections") or []:
        for it in s.get("items") or []:
            first_seen[_norm(it.get("headline"))] = it.get("first_seen")

    stamp = now.isoformat(timespec="minutes")
    sections = []
    for s in sorted(upd["sections"], key=lambda s: list(SECTIONS).index(s["key"])):
        emoji, title = SECTIONS[s["key"]]
        items = []
        for it in s["items"][:MAX_ITEMS]:
            items.append({
                "headline": it["headline"].strip(),
                "what": it["what"].strip(),
                "why_it_matters": it["why_it_matters"].strip(),
                "status": it.get("status") if it.get("status") in ("new", "developing") else "new",
                "first_seen": it.get("first_seen") or first_seen.get(_norm(it["headline"])) or stamp,
                "updated_at": it.get("updated_at") or stamp,
                "sources": [{"name": x.get("name") or "Source", "url": x["url"]}
                            for x in it["sources"] if isinstance(x, dict) and str(x.get("url", "")).startswith("http")][:3],
            })
        sections.append({"key": s["key"], "emoji": emoji, "title": title,
                         "summary": s["summary"].strip(), "items": items})

    doc = {
        "date": date,
        "updated_at": stamp,
        "final": final,
        "edition": _edition(now, final),
        "runs": (prev.get("runs") or []) + [stamp],
        "top_line": upd["top_line"].strip(),
        "top5": [{"title": t["title"], "why": t["why"], "section": t["section"]} for t in upd["top5"][:5]],
        "sections": sections,
        "watch_tomorrow": [str(x) for x in (upd.get("watch_tomorrow") or []) if str(x).strip()][:5],
        "disclaimer": DISCLAIMER,
    }
    _write(_day_file(date), doc)
    _rebuild_index()
    n = sum(len(s["items"]) for s in sections)
    print(f"digest: wrote dashboard/digest/digest-{date}.json — {doc['edition']}, {len(sections)} sections, "
          f"{n} items (" + ", ".join(f"{s['key']}:{len(s['items'])}" for s in sections) + ")")
    return 0


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _rebuild_index() -> None:
    days = []
    for p in sorted(DIGEST_DIR.glob("digest-*.json"), reverse=True):
        d = _load(p) or {}
        if not d.get("date"):
            continue
        days.append({"date": d["date"], "edition": d.get("edition"), "final": bool(d.get("final")),
                     "updated_at": d.get("updated_at"),
                     "items": sum(len(s.get("items") or []) for s in d.get("sections") or []),
                     "top_line": (d.get("top_line") or "")[:180]})
    _write(INDEX, {"generated_at": _now().isoformat(timespec="minutes"), "days": days})


# ---------------------------------------------------------------- run-local (Mac / testing)
def run_local() -> int:
    import usage
    if prepare() != 0:
        return 1
    claude = os.environ.get("CLAUDE_BIN") or str(pathlib.Path.home() / ".local" / "bin" / "claude")
    if not pathlib.Path(claude).exists():
        claude = "claude"
    task = PROMPT.read_text() + (
        "\n\n---\nNOW: read output/digest-context.json, do the editing described above, and write the result to "
        "output/digest-update.json. That file is the only deliverable.\n")
    res = usage.run_claude(task, claude_bin=claude, cwd=ROOT, label="digest",
                           allowed=["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"],
                           retries=1, timeout=1500)
    if res is None:
        print("digest: editor step failed", file=sys.stderr)
        return 1
    print((res or "").strip()[-400:])
    return merge()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"prepare": prepare, "merge": merge, "run-local": run_local}.get(cmd)
    if not fn:
        print(__doc__)
        sys.exit(2)
    sys.exit(fn())
