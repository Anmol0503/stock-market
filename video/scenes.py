"""HTML templates for reel scenes (1080×1920). The model supplies data; these templates own the layout.

Each scene is drawn in LAYERS so reel.py can animate it cheaply in ffmpeg:
- `bg`   the backdrop: a free-licence photo (full-bleed, or blurred behind a framed photo when it's small) or a
         designed backdrop (section-colour glows, dot grid, grain, a big outlined section word). Rendered
         ~10% oversize so ffmpeg can slowly pan across it (Ken Burns).
- `ui`   static chrome: section + chapter pills, the photo credit, headline, meta and chapter progress.
- `1..n` content pieces (`.ly.lyK`): a kicker, the big text, each card/row/bar. Each is rendered on its own
         transparent frame and slides/fades in at its own time (rows of a worked example or a timeline appear
         as the narration reaches them; see reveal_times).
`scene_html()` alone returns the whole frame with everything visible (posters, tests, the old renderer).

Layout bands (y, px): 56–150 pills · 190–1250 main visual · ~1300–1480 burned-in captions (reel.CAPTION_Y) ·
1500–1860 credit, headline, meta, chapter progress. The app shows the frame whole (never cropped).
"""
from __future__ import annotations

import base64
import functools
import html
import json
import math
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
W, H = 1080, 1920
BG_SCALE = 1.1                     # the backdrop is rendered 10% larger, then panned inside the 1080×1920 frame

# section -> (light, dark) gradient colours, matching dashboard/reels/app.css
COLORS = {
    "world": ("#4f8cf7", "#3346c9"), "india": ("#f7a14b", "#dd5a2b"), "affects_you": ("#e9a126", "#b85a14"),
    "markets": ("#2fc58c", "#128066"), "tech_ai": ("#9b7cf8", "#5b3fd6"), "science": ("#2cc3c0", "#157c9c"),
    "f1": ("#f45b5b", "#b3223a"), "cricket": ("#58c56a", "#23804a"),
}
LABELS = {"world": "World", "india": "India", "affects_you": "Money & life", "markets": "Markets", "tech_ai": "Tech & AI",
          "science": "Science", "f1": "Formula 1", "cricket": "Cricket"}
# Scenes whose backdrop photo is shown clearly; data scenes blur and darken it behind their cards.
HERO_KINDS = ("hook", "kinetic", "outro", "big_number")


@functools.lru_cache(maxsize=None)
def _font_css() -> str:
    out = []
    for fam, fn in (("Inter", "Inter.ttf"), ("Fraunces", "Fraunces.ttf")):
        b64 = base64.b64encode((HERE / "fonts" / fn).read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{fam}';src:url(data:font/ttf;base64,{b64}) format('truetype');"
                   "font-weight:100 900;font-style:normal}")
    return "".join(out)


@functools.lru_cache(maxsize=None)
def _world() -> dict:
    return json.loads((HERE / "assets" / "world-ind-pov.json").read_text())


def esc(s) -> str:
    return html.escape(str(s or ""))


def _rgb(hex_: str) -> str:
    h = hex_.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


GRAIN = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>"
         "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/>"
         "<feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 0'/></filter>"
         "<rect width='100%' height='100%' filter='url(%23n)'/></svg>\")")

BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden}
body{font-family:'Inter',system-ui,sans-serif;color:#fff;background:#070912;position:relative}
/* ---------- backdrop */
.bgl{position:absolute;inset:0;overflow:hidden;background:#070912}
.bgl .ph{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 28%}
.bgl .ph.hero{filter:saturate(1.08) contrast(1.06) brightness(.92)}
.bgl .ph.soft{filter:blur(16px) saturate(1.3) brightness(.66);transform:scale(1.08)}
.bgl .ph.deep{filter:blur(24px) saturate(1.4) brightness(.66);transform:scale(1.14)}
.bgl .hue{position:absolute;inset:0;background:radial-gradient(90% 55% at 15% 8%,rgba(var(--ar),.55),transparent 70%),
  radial-gradient(80% 50% at 95% 60%,rgba(var(--br),.45),transparent 70%);mix-blend-mode:soft-light}
.bgl .scrim{position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,6,14,.62) 0%,rgba(4,6,14,0) 13%,
  rgba(4,6,14,0) 30%,rgba(4,6,14,.5) 47%,rgba(4,6,14,.88) 62%,rgba(4,6,14,.95) 76%,#05070f 100%)}
.bgl .scrim.dark{background:linear-gradient(180deg,rgba(4,6,14,.5) 0%,rgba(4,6,14,.22) 22%,rgba(4,6,14,.32) 52%,
  rgba(4,6,14,.86) 68%,rgba(4,6,14,.95) 80%,#05070f 100%)}
.bgl .scrim.low{background:linear-gradient(180deg,transparent 0%,transparent 55%,rgba(4,6,14,.75) 68%,rgba(4,6,14,.94) 80%,#05070f 100%)}
.bgl .base{position:absolute;inset:0;background:linear-gradient(165deg,rgba(var(--br),.55) 0%,#0a0d1d 48%,#06070f 100%)}
.bgl .glow1{position:absolute;width:1500px;height:1500px;left:-520px;top:-560px;border-radius:50%;
  background:radial-gradient(circle,rgba(var(--ar),.95),rgba(var(--ar),.25) 40%,rgba(var(--ar),0) 68%)}
.bgl .glow2{position:absolute;width:1300px;height:1300px;right:-600px;top:330px;border-radius:50%;
  background:radial-gradient(circle,rgba(var(--br),.9),rgba(var(--br),0) 65%)}
.bgl .glow3{position:absolute;width:900px;height:900px;left:-200px;bottom:-300px;border-radius:50%;
  background:radial-gradient(circle,rgba(var(--ar),.35),rgba(var(--ar),0) 65%)}
.bgl .grid{position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.2) 2px,transparent 2.6px);
  background-size:44px 44px;-webkit-mask-image:linear-gradient(160deg,#000 0%,rgba(0,0,0,.35) 45%,transparent 75%)}
.bgl .rays{position:absolute;inset:-20%;background:repeating-linear-gradient(115deg,rgba(255,255,255,.035) 0 2px,
  transparent 2px 90px)}
.bgl .word{position:absolute;left:-30px;top:560px;font-family:'Fraunces',serif;font-weight:900;font-size:330px;
  line-height:.9;letter-spacing:-.02em;color:transparent;-webkit-text-stroke:3px rgba(255,255,255,.075);
  text-transform:uppercase;white-space:nowrap;transform:rotate(-8deg);-webkit-text-stroke:3px rgba(255,255,255,.1)}
.bgl .grain{position:absolute;inset:0;background-image:GRAIN;opacity:.09;mix-blend-mode:overlay}
.bgl .vig{position:absolute;inset:0;background:radial-gradient(130% 90% at 50% 40%,transparent 55%,rgba(0,0,0,.55) 100%)}
/* ---------- chrome */
.top{position:absolute;left:56px;right:56px;top:56px;height:94px;display:flex;align-items:center;justify-content:space-between;gap:20px}
.pill{display:flex;align-items:center;gap:14px;padding:16px 28px;border-radius:999px;background:rgba(var(--ar),.92);
  color:#fff;font-weight:800;font-size:28px;letter-spacing:.1em;text-transform:uppercase;box-shadow:0 8px 30px rgba(0,0,0,.3)}
.pill i{width:12px;height:12px;border-radius:50%;background:#fff}
.chap{font-weight:800;font-size:26px;letter-spacing:.12em;text-transform:uppercase;padding:15px 26px;border-radius:999px;
  background:rgba(8,10,20,.55);border:2px solid rgba(255,255,255,.28);white-space:nowrap;box-shadow:0 8px 30px rgba(0,0,0,.25)}
.brand{font-family:'Fraunces',serif;font-weight:700;font-size:34px;opacity:.9}
.credit{position:absolute;right:56px;top:1488px;max-width:900px;font-size:20px;font-weight:500;color:rgba(255,255,255,.5);
  text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.low{position:absolute;left:56px;right:56px;top:1530px;bottom:60px;display:flex;flex-direction:column;justify-content:flex-end;gap:20px}
.hl{font-family:'Fraunces',serif;font-weight:700;font-size:46px;line-height:1.14;max-height:106px;overflow:hidden;
  text-shadow:0 2px 18px rgba(0,0,0,.4)}
.meta{font-size:26px;font-weight:600;opacity:.7;letter-spacing:.02em}
.dots{display:flex;gap:10px}.dots i{flex:1;max-width:60px;height:8px;border-radius:8px;background:rgba(255,255,255,.22)}
.dots i.on{background:rgb(var(--ar))}
/* ---------- content */
.vis{position:absolute;left:64px;right:64px;top:190px;height:1060px;display:flex;flex-direction:column;justify-content:center}
.vis.end{justify-content:flex-end}
.show{font-family:'Fraunces',serif;font-weight:800;line-height:1.04;letter-spacing:-.015em;text-shadow:0 6px 40px rgba(0,0,0,.45)}
mark{background:none;color:rgb(var(--ar));position:relative;text-shadow:none;white-space:nowrap}
.bar{width:120px;height:12px;border-radius:12px;background:rgb(var(--ar));margin-bottom:40px}
.kick{font-size:34px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#fff;margin-bottom:30px;
  text-shadow:0 2px 16px rgba(0,0,0,.5);
  display:flex;align-items:center;gap:18px}
.kick:before{content:'';width:46px;height:6px;border-radius:6px;background:rgb(var(--ar))}
.frame{width:640px;height:780px;border-radius:44px;overflow:hidden;margin-bottom:56px;box-shadow:0 30px 80px rgba(0,0,0,.55);
  border:3px solid rgba(255,255,255,.18);flex:0 0 auto}
.frame img{width:100%;height:100%;object-fit:cover;object-position:50% 25%}
.panel{background:rgba(9,12,24,.66);border:2px solid rgba(255,255,255,.14);border-radius:40px;padding:40px 42px;
  box-shadow:0 30px 80px rgba(0,0,0,.4)}
.big{font-weight:900;line-height:.95;letter-spacing:-.04em;background:linear-gradient(180deg,#fff 30%,rgb(var(--ar)) 130%);
  -webkit-background-clip:text;color:transparent;filter:drop-shadow(0 10px 40px rgba(0,0,0,.45))}
.lbl{font-family:'Fraunces',serif;font-size:68px;font-weight:700;line-height:1.15;margin-top:34px;max-width:900px}
/* timeline */
.tl{position:relative;padding-left:58px}
.tl:before{content:'';position:absolute;left:17px;top:20px;bottom:20px;width:6px;border-radius:6px;background:rgba(255,255,255,.18)}
.tl .row{position:relative;display:flex;flex-direction:column;gap:6px}
.tl .row:before{content:'';position:absolute;left:-54px;top:8px;width:32px;height:32px;border-radius:50%;
  background:#0b0e1a;border:6px solid rgb(var(--ar))}
.tl .row.last:before{background:rgb(var(--ar));box-shadow:0 0 0 10px rgba(var(--ar),.25)}
.tl .when{font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:rgb(var(--ar))}
.tl .what{font-weight:600;line-height:1.25}
/* players */
.pl{display:flex;flex-direction:column;gap:24px}
.pl .row{display:flex;align-items:center;gap:34px;padding:var(--pd) 34px}
.pl .av{flex:0 0 var(--av);height:var(--av);border-radius:50%;overflow:hidden;background:rgb(var(--ar));display:flex;
  align-items:center;justify-content:center;font-weight:900;font-size:64px;color:#fff;border:4px solid rgba(255,255,255,.85)}
.pl .av img{width:100%;height:100%;object-fit:cover;object-position:50% 22%}
.pl .nm{font-family:'Fraunces',serif;font-size:var(--nm);font-weight:800;line-height:1.1}
.pl .rl{font-size:var(--rl);font-weight:500;opacity:.8;line-height:1.3;margin-top:8px}
/* worked example */
.sx{display:flex;flex-direction:column;gap:26px}
.sx .row{display:flex;gap:30px;align-items:center;padding:36px 36px}
.sx .n{flex:0 0 88px;height:88px;border-radius:50%;background:rgb(var(--ar));color:#fff;font-weight:900;font-size:38px;
  display:flex;align-items:center;justify-content:center}
.sx .lb{font-size:30px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;opacity:.7;margin-bottom:8px}
.sx .cl{font-weight:800;line-height:1.15;letter-spacing:-.01em}
.sx .row.last{background:#fff;color:#0b0e1a;border-color:#fff}.sx .row.last .lb{opacity:.6}
/* views */
.vw{display:flex;flex-direction:column;gap:26px}
.vw .panel{display:flex;flex-direction:column;gap:14px;position:relative;padding-left:96px}
.vw .q{position:absolute;left:30px;top:16px;font-family:'Fraunces',serif;font-size:120px;font-weight:900;line-height:1;
  color:rgb(var(--ar))}
.vw .who{font-size:28px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:rgb(var(--ar))}
.vw .say{font-family:'Fraunces',serif;font-weight:700;line-height:1.18}
/* map + charts */
.map svg{display:block;width:100%;height:auto}
"""
BASE_CSS = BASE_CSS.replace("GRAIN", GRAIN)

# Pass CSS: which layers a render shows. `bg` keeps only the backdrop; the others are transparent overlays.
_TRANSPARENT = "html,body{background:transparent!important}.bgl{display:none!important}"


def pass_css(name: str) -> str:
    if name == "bg":                     # the backdrop pans, so nothing else may be drawn into it
        return ".ui,.vis,.ly{visibility:hidden!important}"
    if name == "ui":
        return _TRANSPARENT + ".ly{visibility:hidden!important}"
    if name.isdigit():
        return _TRANSPARENT + ".ui,.ly{visibility:hidden!important}" + f".ly{name}{{visibility:visible!important}}"
    return ""


def with_pass(page: str, name: str) -> str:
    return page.replace("</head>", f"<style>{pass_css(name)}</style></head>", 1)


def layer_count(page: str) -> int:
    nums = [int(n) for cls in re.findall(r"class='([^']*)'", page) for n in re.findall(r"\bly(\d+)\b", cls)]
    return max(nums) if nums else 0


def reveal_times(sc: dict, n: int, dur: float) -> list[float]:
    """Start time of content layers 1..n. Rows of a worked example, timeline, views or players arrive spread
    over the scene (as the narration reaches them); everything else arrives in a quick stagger."""
    kind = sc.get("kind")
    if n <= 0:
        return []
    spread = {"steps": 0.8, "timeline": 0.72, "views": 0.55, "players": 0.5, "bar": 0.35}.get(kind)
    if not spread or n <= 2:
        return [round(0.12 + 0.3 * k, 2) for k in range(n)]
    rows = n - 1                                          # layer 1 is the kicker/title, rows follow
    gap = max(0.35, min(4.0, spread * max(dur, 1.0) / rows))
    return [0.12] + [round(0.5 + gap * k, 2) for k in range(rows)]


# ---------------------------------------------------------------- text helpers
_NUM = re.compile(r"(?:[₹$€£]\s?)?\d[\d,.]*(?:\s?(?:%|°C|per cent|percent|crore|lakh|billion|million|trillion|bn|"
                  r"km|kmph|years?|days?|x|×))?", re.I)
_STOP = {"the", "and", "for", "with", "from", "that", "this", "what", "when", "where", "which", "into", "about",
         "after", "before", "their", "there", "they", "will", "would", "could", "should", "have", "been", "were"}


def marked(text: str) -> str:
    """Escape `text` and highlight its key part in the accent colour: the first number with its unit, else the
    longest meaningful word."""
    text = str(text or "").strip()
    m = _NUM.search(text)
    if m and m.group(0).strip():
        a, b = m.span()
        while b > a and text[b - 1] in ".,":
            b -= 1
        return f"{esc(text[:a])}<mark>{esc(text[a:b])}</mark>{esc(text[b:])}"
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]{3,}", text) if w.lower() not in _STOP]
    if not words:
        return esc(text)
    key = max(words, key=len)
    i = text.find(key)
    return f"{esc(text[:i])}<mark>{esc(key)}</mark>{esc(text[i + len(key):])}"


def _fit_size(text: str, base: int, *, per_line: int, max_lines: int, floor: int = 54) -> int:
    """Shrink display text that would wrap past max_lines (rough: chars per line at the base size)."""
    n = len(str(text or ""))
    lines = math.ceil(n / per_line)
    if lines <= max_lines:
        return base
    return max(floor, int(base * math.sqrt(max_lines / lines)))


def _uri(p) -> str:
    return pathlib.Path(p).resolve().as_uri() if p else ""


# ---------------------------------------------------------------- backdrop
def _backdrop(kind: str, section: str, photo, reused: bool = False) -> str:
    word = esc(LABELS.get(section, section))
    if photo is None:
        return (f"<div class='bgl'><div class='base'></div><div class='glow1'></div><div class='glow2'></div>"
                f"<div class='glow3'></div><div class='rays'></div><div class='grid'></div><div class='word'>{word}</div>"
                f"<div class='grain'></div><div class='vig'></div><div class='scrim low'></div></div>")
    big = getattr(photo, "width", 0) >= 1000
    hero = kind in HERO_KINDS and big and not reused        # a reused photo is only ever a blurred backdrop
    cls = "hero" if hero else ("soft" if kind in HERO_KINDS and not reused else "deep")
    return (f"<div class='bgl'><img class='ph {cls}' src='{_uri(photo.path)}'><div class='hue'></div>"
            f"<div class='scrim{'' if hero else ' dark'}'></div><div class='grain'></div><div class='vig'></div></div>")


# ---------------------------------------------------------------- data visuals
def _map_svg(sc: dict, accent: str) -> str:
    wd = _world()
    countries, alias = wd["countries"], wd.get("alias", {})
    codes = [alias.get(c, c) for c in (sc.get("map", {}).get("iso3") or []) if alias.get(c, c) in countries]
    lon, lat = (sc.get("map", {}).get("pin") or [None, None])[:2]
    pts = [(x, y) for c in codes for ring in countries[c]["rings"] for x, y in ring]
    if lon is not None and lat is not None and (lon or lat):
        pts.append((lon, lat))
    if not pts:
        return ""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    span_x = max(max(xs) - min(xs), 14) * 1.35
    span_y = max(max(ys) - min(ys), 9) * 1.35
    k = math.cos(math.radians(cy))
    vw, vh = 952, 860
    scale = min(vw / (span_x * k), vh / span_y)

    def proj(x, y):
        return (vw / 2 + (x - cx) * k * scale, vh / 2 - (y - cy) * scale)
    paths, hi_paths = [], []
    x0, x1, y0, y1 = cx - span_x, cx + span_x, cy - span_y, cy + span_y
    for code, c in countries.items():
        for ring in c["rings"]:
            if not any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in ring):
                continue
            d = "M" + "L".join(f"{px:.1f},{py:.1f}" for px, py in (proj(x, y) for x, y in ring)) + "Z"
            if code in codes:
                hi_paths.append(f"<path d='{d}' fill='{accent}' stroke='#fff' stroke-width='3.5' stroke-linejoin='round'/>")
            else:
                paths.append(f"<path d='{d}' fill='rgba(255,255,255,.13)' stroke='rgba(255,255,255,.38)' stroke-width='1.6'/>")
    pin = ""
    if lon is not None and lat is not None and (lon or lat):
        px, py = proj(lon, lat)
        raw = (sc.get("map", {}).get("label") or "")[:26]
        pin = (f"<circle cx='{px:.1f}' cy='{py:.1f}' r='70' fill='{accent}' opacity='.18'/>"
               f"<circle cx='{px:.1f}' cy='{py:.1f}' r='42' fill='none' stroke='#fff' stroke-width='5' opacity='.6'/>"
               f"<circle cx='{px:.1f}' cy='{py:.1f}' r='18' fill='#fff' stroke='{accent}' stroke-width='8'/>")
        if raw:
            wpx = 48 + len(raw) * 20
            tx = min(max(px, wpx / 2 + 12), vw - wpx / 2 - 12)
            ty = py - 122 if py > 150 else py + 58
            pin += (f"<rect x='{tx - wpx / 2:.1f}' y='{ty:.1f}' width='{wpx}' height='68' rx='34' fill='#fff'/>"
                    f"<text x='{tx:.1f}' y='{ty + 46:.1f}' text-anchor='middle' font-family='Inter' font-weight='800' "
                    f"font-size='34' fill='#0b0e1a'>{esc(raw)}</text>")
    glow = "<filter id='g'><feGaussianBlur stdDeviation='14'/></filter>"
    return (f"<svg width='{vw}' height='{vh}' viewBox='0 0 {vw} {vh}'><defs>{glow}</defs>{''.join(paths)}"
            f"<g filter='url(#g)' opacity='.7'>{''.join(hi_paths)}</g>{''.join(hi_paths)}{pin}</svg>")


def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def _label(x: float, y: float, text, *, per_line: int) -> str:
    """Axis label wrapped onto at most two lines (never silently cut to the same prefix)."""
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > per_line:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])[: per_line - 1] + "…"]
    spans = "".join(f"<tspan x='{x:.1f}' dy='{0 if i == 0 else 38}'>{esc(t)}</tspan>" for i, t in enumerate(lines))
    return (f"<text x='{x:.1f}' y='{y - (17 if len(lines) > 1 else 0):.1f}' text-anchor='middle' font-family='Inter' "
            f"font-weight='600' font-size='33' fill='#fff' opacity='.85'>{spans}</text>")


def _chart(sc: dict, kind: str, accent: str) -> str:
    ch = sc.get("chart") or {}
    pts = [p for p in ch.get("points") or [] if isinstance(p.get("value"), (int, float))][:8]
    if len(pts) < 2:
        return ""
    vw, vh, pad = 872, 820, 40
    vals = [p["value"] for p in pts]
    lo, hi = min(0, min(vals)), max(vals) or 1
    rng = (hi - lo) or 1
    n = len(pts)
    per = max(7, int((vw - pad * 2) / n / 16))
    base_y, top_y = vh - 110, 90
    title = esc(ch.get("title") or "")
    unit = esc(ch.get("unit") or "")
    defs = (f"<defs><linearGradient id='bf' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#fff'/>"
            f"<stop offset='1' stop-color='#fff' stop-opacity='.55'/></linearGradient>"
            f"<linearGradient id='ba' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{accent}'/>"
            f"<stop offset='1' stop-color='{accent}' stop-opacity='.7'/></linearGradient>"
            f"<linearGradient id='la' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{accent}' stop-opacity='.45'/>"
            f"<stop offset='1' stop-color='{accent}' stop-opacity='0'/></linearGradient></defs>")
    axis = f"<line x1='{pad}' y1='{base_y}' x2='{vw - pad}' y2='{base_y}' stroke='rgba(255,255,255,.3)' stroke-width='3'/>"
    head = f"<div class='kick ly ly1'>{title}{(' · ' + unit) if unit else ''}</div>"
    if kind == "bar":
        bw = (vw - pad * 2) / n * 0.6
        span = base_y - top_y
        zero_y = base_y - (0 - lo) / rng * span            # the zero line (above the axis when values go negative)
        bars = []
        for i, p in enumerate(pts):
            x = pad + (vw - pad * 2) * (i + 0.5) / n
            v = p["value"]
            y_v = base_y - (v - lo) / rng * span
            top, hgt = (y_v, zero_y - y_v) if v >= 0 else (zero_y, y_v - zero_y)
            hgt = max(6, hgt)
            last = i == n - 1
            fs = 50 if n <= 4 else 40 if n <= 6 else 32
            ty = top - 22 if v >= 0 else zero_y - 22          # a negative value sits just above the zero line
            g = (f"<rect x='{x - bw / 2:.1f}' y='{top:.1f}' width='{bw:.1f}' height='{hgt:.1f}' rx='16' "
                 f"fill='url(#{'ba' if last else 'bf'})' opacity='{1 if v >= 0 else .75}'/>"
                 f"<text x='{x:.1f}' y='{ty:.1f}' text-anchor='middle' font-family='Inter' font-weight='900' "
                 f"font-size='{fs}' fill='{accent if last else '#fff'}'>{esc(_fmt(v))}</text>"
                 + _label(x, base_y + 50, p.get("label"), per_line=per))
            # each bar is its own layer so the bars rise in one after another
            bars.append(f"<svg class='ly ly{i + 2}' width='{vw}' height='{vh}' viewBox='0 0 {vw} {vh}' "
                        f"style='position:absolute;left:42px;top:42px'>{defs}{g}</svg>")
        if lo < 0:
            axis += (f"<line x1='{pad}' y1='{zero_y:.1f}' x2='{vw - pad}' y2='{zero_y:.1f}' stroke='rgba(255,255,255,.55)' "
                     f"stroke-width='3' stroke-dasharray='10 10'/>")
        return (head + f"<div class='panel' style='position:relative;height:{vh + 84}px'>"
                f"<svg width='{vw}' height='{vh}' viewBox='0 0 {vw} {vh}' style='position:absolute;left:42px;top:42px'>"
                f"{axis}</svg>{''.join(bars)}</div>")
    xy = [(pad + 20 + (vw - pad * 2 - 40) * i / (n - 1), base_y - (p["value"] - lo) / rng * (base_y - top_y))
          for i, p in enumerate(pts)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    area = f"{xy[0][0]:.1f},{base_y} " + line + f" {xy[-1][0]:.1f},{base_y}"
    out = [axis, f"<polygon points='{area}' fill='url(#la)'/>",
           f"<polyline points='{line}' fill='none' stroke='{accent}' stroke-width='12' stroke-linejoin='round' stroke-linecap='round'/>"]
    for (x, y), p in zip(xy, pts):
        out.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='14' fill='#fff' stroke='{accent}' stroke-width='6'/>")
        out.append(_label(x, base_y + 50, p.get("label"), per_line=per))
    x, y = xy[-1]
    out.append(f"<text x='{x:.1f}' y='{y - 34:.1f}' text-anchor='end' font-family='Inter' font-weight='900' font-size='48' "
               f"fill='#fff'>{esc(_fmt(pts[-1]['value']))}</text>")
    return (head + f"<div class='panel ly ly2' style='padding:42px'><svg width='{vw}' height='{vh}' "
            f"viewBox='0 0 {vw} {vh}'>{defs}{''.join(out)}</svg></div>")


# ---------------------------------------------------------------- page
def _page(section: str, body: str, *, headline: str, idx: int, total: int, meta: str, chapter: str = "",
          kind: str = "", photo=None, reused: bool = False, align_end: bool = False) -> str:
    a, b = COLORS.get(section, COLORS["world"])
    dots = "".join(f"<i class='{'on' if i <= idx else ''}'></i>" for i in range(total))
    right = f"<div class='chap'>{esc(chapter)}</div>" if chapter else "<div class='brand'>The Briefing</div>"
    cred = f"<div class='credit'>{esc(photo.credit)}</div>" if photo is not None and getattr(photo, "credit", "") else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_font_css()}{BASE_CSS}
:root{{--a:{a};--b:{b};--ar:{_rgb(a)};--br:{_rgb(b)}}}</style></head><body>
{_backdrop(kind, section, photo, reused)}
<div class="ui"><div class="top"><div class="pill"><i></i>{esc(LABELS.get(section, section))}</div>{right}</div>{cred}
<div class="low"><div class="hl">{esc(headline)}</div><div class="meta">{esc(meta)}</div><div class="dots">{dots}</div></div></div>
<div class="vis{' end' if align_end else ''}">{body}</div>
</body></html>"""


def scene_html(sc: dict, *, section: str, headline: str, idx: int, total: int, meta: str, chapter: str = "",
               photo=None, reused: bool = False, avatars: dict | None = None) -> str:
    """One scene. idx/total: position in the progress dots (chapters for a chaptered reel, else scenes).
    photo: an images.Photo (or anything with .path/.width/.credit) for the backdrop; avatars: player name ->
    Photo for the players scene; reused: the photo is borrowed from an earlier scene (shown blurred only)."""
    kind = sc.get("kind")
    show = sc.get("show") or ""
    a, _b = COLORS.get(section, COLORS["world"])
    avatars = avatars or {}
    small_photo = photo is not None and not reused and getattr(photo, "width", 0) < 1000
    frame = (f"<div class='frame ly ly1'><img src='{_uri(photo.path)}'></div>"
             if small_photo and kind in ("hook", "kinetic") else "")
    n0 = 2 if frame else 1                        # first text layer after an optional framed photo
    end = False
    if kind == "hook":
        size = _fit_size(show, 118 if not frame else 92, per_line=13, max_lines=4 if not frame else 3)
        kick = "" if chapter else f"<div class='kick ly ly{n0}'>The question</div>"
        body = (f"{frame}{kick}<div class='bar ly ly{n0}'></div>"
                f"<div class='show ly ly{n0 + 1}' style='font-size:{size}px'>{marked(show)}</div>")
        end = True
    elif kind == "big_number" and (sc.get("number") or {}).get("value"):
        val = sc["number"]["value"]
        size = 300 if len(val) <= 5 else max(150, int(300 * 5 / len(val)))
        body = (f"<div class='big ly ly1' style='font-size:{size}px'>{esc(val)}</div>"
                f"<div class='lbl ly ly2'>{esc(sc['number'].get('label') or show)}</div>")
    elif kind == "map" and (svg := _map_svg(sc, a)):
        body = (f"<div class='kick ly ly1'>{esc(show) or 'Where'}</div>"
                f"<div class='panel map ly ly2' style='padding:0;overflow:hidden'>{svg}</div>")
    elif kind in ("bar", "line") and (svg := _chart(sc, kind, a)):
        body = svg
    elif kind == "timeline" and sc.get("timeline"):
        rows = sc["timeline"][:8]
        n = len(rows)
        fw, fs, gap = (40, 56, 50) if n <= 4 else (36, 48, 36) if n <= 6 else (31, 39, 22)
        body = (f"<div class='kick ly ly1'>{esc(show) or 'How we got here'}</div><div class='tl' style='display:flex;"
                f"flex-direction:column;gap:{gap}px'>"
                + "".join(f"<div class='row ly ly{i + 2}{' last' if i == n - 1 else ''}'>"
                          f"<div class='when' style='font-size:{fw}px'>{esc(t.get('when'))}</div>"
                          f"<div class='what' style='font-size:{fs}px'>{esc(t.get('what'))}</div></div>"
                          for i, t in enumerate(rows))
                + "</div>")
    elif kind == "players" and sc.get("players"):
        rows = sc["players"][:4]

        def av(p):
            ph = avatars.get(p.get("name") or "")
            if ph is not None:
                return f"<div class='av'><img src='{_uri(ph.path)}'></div>"
            return f"<div class='av'>{esc((p.get('name') or '?')[:1])}</div>"
        # 4 rows must still fit the 1060 px content band: shrink the rows, not the band
        tight = {4: "--av:132px;--nm:46px;--rl:30px;--pd:22px", 3: "--av:160px;--nm:52px;--rl:33px;--pd:28px"}.get(
            len(rows), "--av:184px;--nm:56px;--rl:35px;--pd:32px")
        body = (f"<div class='kick ly ly1'>{esc(show) or 'Who is involved'}</div><div class='pl' style='{tight}'>"
                + "".join(f"<div class='panel row ly ly{i + 2}'>{av(p)}<div><div class='nm'>{esc(p.get('name'))}</div>"
                          f"<div class='rl'>{esc(p.get('role'))}</div></div></div>" for i, p in enumerate(rows))
                + "</div>")
    elif kind == "steps" and sc.get("steps"):
        rows = sc["steps"][:4]
        longest = max(len(str(r.get("calc") or "")) for r in rows)
        size = (70 if longest <= 22 else 58 if longest <= 30 else 50) - (6 if len(rows) == 4 else 0)
        body = (f"<div class='kick ly ly1'>{esc(show) or 'Worked example'}</div><div class='sx'>"
                + "".join(f"<div class='panel row ly ly{i + 2}{' last' if i == len(rows) - 1 else ''}'><div class='n'>{i + 1}</div>"
                          f"<div><div class='lb'>{esc(r.get('label'))}</div><div class='cl' style='font-size:{size}px'>"
                          f"{esc(r.get('calc'))}</div></div></div>" for i, r in enumerate(rows))
                + "</div>")
    elif kind == "views" and sc.get("views"):
        rows = sc["views"][:4]
        size = 58 if len(rows) <= 2 else 48 if len(rows) == 3 else 40
        body = (f"<div class='kick ly ly1'>{esc(show) or 'Different views'}</div><div class='vw'>"
                + "".join(f"<div class='panel ly ly{i + 2}'><div class='q'>“</div><div class='who'>{esc(v.get('who'))}</div>"
                          f"<div class='say' style='font-size:{size}px'>{esc(v.get('view'))}</div></div>"
                          for i, v in enumerate(rows))
                + "</div>")
    elif kind == "outro":
        size = _fit_size(show, 104, per_line=15, max_lines=4)
        kick = "" if chapter else f"<div class='kick ly ly1'>Remember</div>"
        body = (f"{kick}<div class='bar ly ly1'></div><div class='show ly ly2' style='font-size:{size}px'>{marked(show)}</div>"
                f"<div class='meta ly ly3' style='margin-top:44px;font-family:Fraunces,serif;font-size:34px;opacity:.75'>"
                f"The Briefing</div>")
        end = True
    else:                                            # kinetic (and any data scene missing its data)
        size = _fit_size(show, 124 if not frame else 92, per_line=12, max_lines=4 if not frame else 3)
        body = (f"{frame}<div class='bar ly ly{n0}'></div>"
                f"<div class='show ly ly{n0 + 1}' style='font-size:{size}px'>{marked(show)}</div>")
        end = True
    return _page(section, body, headline=headline, idx=idx, total=total, meta=meta, chapter=chapter, kind=kind,
                 photo=photo, reused=reused, align_end=end)
