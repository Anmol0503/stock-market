#!/usr/bin/env python3
"""Auto-generate ready-to-post Instagram CAROUSELS from the decoded feed.

Turns each day's top decoded stories (dashboard/reels.json) into branded 1080×1350 slide images plus a
caption — one carousel for Global, one for India — reusing the reels design (social/post.html) rendered
with headless Google Chrome. Output lands in social/out/<date>/{global,india}/ (gitignored, local only).

MVP posts MANUALLY: open the images, read caption.txt, post to Instagram (or the Update Center /posts
gallery). Monetization hooks (bio link, sponsor/affiliate line) are env-gated and OFF by default.

Run:  python make_social.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass

ROOT = pathlib.Path(__file__).resolve().parent
DASH = ROOT / "dashboard"
SOCIAL = ROOT / "social"
TEMPLATE = (SOCIAL / "post.html").read_text()

TOP_N = 5
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

CAT = {"geopolitics": ("Geopolitics", "🌍"), "economy": ("Economy", "💵"),
       "technology": ("Technology", "⚙️"), "science": ("Science", "🔬"), "health": ("Health", "🩺"),
       "climate": ("Climate", "🌱"), "india": ("India", "🇮🇳"), "markets": ("Markets", "📈")}

# monetization + brand config (env, safe defaults) — never hard-code secrets
HANDLE = os.getenv("SOCIAL_HANDLE", "@daily.decoded")
BIO_LINK = os.getenv("SOCIAL_BIO_LINK", "Full decoded feed → link in bio")
SPONSOR_LINE = os.getenv("SPONSOR_LINE", "").strip()          # off unless set
AFFILIATE_URL = os.getenv("AFFILIATE_URL", "").strip()        # off unless set
DISCLAIMER = ("Decoded from public reporting for general understanding. "
              "Verify before relying on any single claim. Not financial advice.")

CHROME = next((p for p in [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chrome"),
] if p and pathlib.Path(p).exists()), None)
FFMPEG = shutil.which("ffmpeg")

# rendering formats — post = 4:5 carousel, reel = 9:16 full-screen, avatar = 1:1 profile pic
POST = (1080, 1350)
REEL = (1080, 1920)
SQUARE = (1080, 1080)
# CSS overrides so one template renders at any height (heights are hard-coded to 1350 in post.html)
REEL_CSS = ("html,body{height:1920px!important}"
            ".slide{height:1920px!important;padding-top:132px;padding-bottom:132px}"
            ".slide::before{height:780px!important}"
            ".cover .kick{margin-top:96px}")
SQUARE_CSS = "html,body{height:1080px!important}.slide{height:1080px!important}"


def render_slide(slide: dict, out_png: pathlib.Path, workdir: pathlib.Path,
                 size=POST, extra_css: str = "") -> bool:
    html = TEMPLATE.replace("/*__SLIDE__*/",
                            "window.__SLIDE__ = " + json.dumps(slide, ensure_ascii=False) + ";")
    if extra_css:
        html = html.replace("</style>", extra_css + "</style>", 1)
    tmp = workdir / f"_slide_{out_png.stem}.html"
    tmp.write_text(html)
    try:
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", f"--window-size={size[0]},{size[1]}",
             "--virtual-time-budget=2500", f"--screenshot={out_png}", tmp.as_uri()],
            capture_output=True, timeout=90,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  ! render failed for {out_png.name}: {e}", file=sys.stderr)
        return False
    finally:
        tmp.unlink(missing_ok=True)
    return out_png.exists()


def build_reel(frames: list[pathlib.Path], durs: list[float], out_mp4: pathlib.Path,
               xfade: float = 0.5) -> bool:
    """Stitch reel frames into a vertical MP4 with crossfades (ffmpeg, no moviepy)."""
    if not FFMPEG or not frames:
        return False
    inputs: list[str] = []
    for f, d in zip(frames, durs):
        inputs += ["-loop", "1", "-t", f"{d:.3f}", "-i", str(f)]
    parts = [f"[{i}:v]scale=1080:1920,setsar=1,fps=30,format=yuv420p[v{i}]"
             for i in range(len(frames))]
    prev, offset, chain = "v0", durs[0] - xfade, []
    for i in range(1, len(frames)):
        out = f"x{i}"
        chain.append(f"[{prev}][v{i}]xfade=transition=fade:duration={xfade}:offset={offset:.3f}[{out}]")
        prev, offset = out, offset + durs[i] - xfade
    filt = ";".join(parts + chain)
    cmd = [FFMPEG, "-y", *inputs, "-filter_complex", filt, "-map", f"[{prev}]",
           "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  ! reel render failed: {e}", file=sys.stderr)
        return False
    if r.returncode != 0:
        print(f"  ! ffmpeg error: {r.stderr.decode('utf-8','ignore')[-400:]}", file=sys.stderr)
        return False
    return out_mp4.exists()


def _hashtags(region: str, stories: list[dict]) -> str:
    tags = ["#decoded", "#explained", "#newsexplained", "#currentaffairs"]
    tags += (["#india", "#indianews", "#currentaffairsindia"] if region == "india"
             else ["#worldnews", "#geopolitics", "#globalnews"])
    for c in {s.get("category") for s in stories}:
        if c and c not in ("india",):
            tags.append("#" + c)
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return " ".join(out)


def build_caption(region: str, stories: list[dict], day_label: str) -> str:
    top = stories[0]
    L = []
    L.append((top.get("moot") or top.get("title") or "").strip())      # the hook
    L.append("")
    L.append(f"{'🇮🇳 India' if region == 'india' else '🌍 The world'} today — top "
             f"{len(stories)}, decoded ({day_label}):")
    for i, s in enumerate(stories, 1):
        emoji = CAT.get(s.get("category"), ("", "•"))[1]
        L.append(f"{i}. {emoji} {(s.get('title') or '').strip()}")
    L.append("")
    L.append(BIO_LINK)
    if SPONSOR_LINE:
        L.append("")
        L.append(SPONSOR_LINE + (f" {AFFILIATE_URL}" if AFFILIATE_URL else ""))
    L.append("")
    L.append(DISCLAIMER)
    L.append("")
    L.append(_hashtags(region, stories))
    return "\n".join(L).strip() + "\n"


def _short_date(deck: dict) -> str:
    raw = deck.get("date") or ""
    try:
        d = dt.date.fromisoformat(raw)
        return d.strftime("%a %-d %b").upper()          # e.g. "WED 15 JUL"
    except ValueError:
        return (deck.get("day_label") or "").upper()


def build_carousel(region: str, stories: list[dict], deck: dict, out_dir: pathlib.Path,
                   make_reel: bool = True) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    cat = "india" if region == "india" else "markets"
    emoji = "🇮🇳" if region == "india" else "🌍"
    n = len(stories)
    total = n + 2  # cover + stories + cta

    cover = {
        "type": "cover", "category": cat, "emoji": emoji,
        "kicker": f"{'India' if region == 'india' else 'Global'} briefing · {_short_date(deck)}",
        "hook": f"Today's {n} biggest\nstories,",
        "teasers": [(s.get("title") or "").strip() for s in stories[:3]],
        "more": f"+{n - 3} more inside ↓" if n > 3 else "",
    }
    slides = [cover]
    for i, s in enumerate(stories, 1):
        slides.append({
            "type": "story", "category": s.get("category"),
            "title": s.get("title"), "moot": s.get("moot"),
            "key_points": s.get("key_points") or [],
            "published_iso": s.get("published_iso"), "source": s.get("source"),
            "importance": s.get("importance"),
            "handle": HANDLE, "page": f"{i + 1} / {total}",
        })
    slides.append({
        "type": "cta", "category": cat, "handle": HANDLE, "link": BIO_LINK,
        "big": "The world & markets,\ndecoded for beginners.",
        "sub": "What happened → why it matters → what to watch. Every day.",
        "sponsor": SPONSOR_LINE, "disclaimer": DISCLAIMER,
    })

    names = ["cover"] + [f"story-{i}" for i in range(1, n + 1)] + ["cta"]
    made = 0
    for slide, name in zip(slides, names):
        if render_slide(slide, out_dir / f"{name}.png", out_dir):
            made += 1
    (out_dir / "caption.txt").write_text(build_caption(region, stories, deck.get("day_label") or ""))

    # A postable vertical Reel (9:16 MP4) from the same slides — silent; add trending audio in-app.
    if make_reel and FFMPEG:
        fdir = out_dir / "reel_frames"
        fdir.mkdir(exist_ok=True)
        frames, durs = [], []
        for slide, name in zip(slides, names):
            fp = fdir / f"{name}.png"
            if render_slide(slide, fp, fdir, size=REEL, extra_css=REEL_CSS):
                frames.append(fp)
                durs.append(2.8 if slide["type"] == "cover" else 3.2 if slide["type"] == "cta" else 4.0)
        if build_reel(frames, durs, out_dir / "reel.mp4"):
            made += 1
            print(f"  ✓ reel.mp4 ({sum(durs):.0f}s, {len(frames)} frames)")
        shutil.rmtree(fdir, ignore_errors=True)
    return made


def main() -> int:
    if not CHROME:
        print("  ! Google Chrome not found — can't render slides (install Chrome).", file=sys.stderr)
        return 1
    reels = DASH / "reels.json"
    if not reels.exists():
        print("  ! no dashboard/reels.json — run the pipeline first.", file=sys.stderr)
        return 1
    deck = json.loads(reels.read_text())
    stories = [c for c in deck.get("cards", []) if c.get("type") == "story"]
    glob = [s for s in stories if s.get("category") != "india"][:TOP_N]
    ind = [s for s in stories if s.get("category") == "india"][:TOP_N]
    if not glob and not ind:
        print("  ! no story cards to post.", file=sys.stderr)
        return 1

    date = deck.get("date") or dt.date.today().isoformat()
    base = SOCIAL / "out" / date
    total = 0
    if glob:
        total += build_carousel("global", glob, deck, base / "global")
    if ind:
        total += build_carousel("india", ind, deck, base / "india")

    # One-time brand asset: a square profile picture to upload to Instagram.
    brand = base / "brand"
    brand.mkdir(parents=True, exist_ok=True)
    if render_slide({"type": "avatar"}, brand / "profile.png", brand,
                    size=SQUARE, extra_css=SQUARE_CSS):
        total += 1

    print(f"Generated {total} assets → {base.relative_to(ROOT)}/  (global:{len(glob)} india:{len(ind)}"
          f"{', +reels' if FFMPEG else ''}, +profile pic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
