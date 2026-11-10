"""HTML templates for reel scenes (1080×1920). The model supplies data; these templates own the layout.

Layout bands (heights): 0–9% top bar · 9–43% main visual · 45–54% captions (burned in later by ffmpeg) ·
57–96% headline + progress (seen in Play all; the app's card overlay covers the bottom 45%).
"""
from __future__ import annotations

import base64
import functools
import html
import json
import math
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
W, H = 1080, 1920

# section -> (light, dark) gradient colours, matching dashboard/reels/app.css
COLORS = {
    "world": ("#4f8cf7", "#3346c9"), "india": ("#f7a14b", "#dd5a2b"), "affects_you": ("#e9a126", "#b85a14"),
    "markets": ("#2fc58c", "#128066"), "tech_ai": ("#9b7cf8", "#5b3fd6"), "science": ("#2cc3c0", "#157c9c"),
    "f1": ("#f45b5b", "#b3223a"), "cricket": ("#58c56a", "#23804a"),
}
LABELS = {"world": "World", "india": "India", "affects_you": "Money & life", "markets": "Markets", "tech_ai": "Tech & AI",
          "science": "Science", "f1": "Formula 1", "cricket": "Cricket"}


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


BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden}
body{font-family:'Inter',system-ui,sans-serif;color:#fff;background:#0b1020;position:relative}
.bg{position:absolute;inset:0;background:radial-gradient(120% 70% at 20% 0%,var(--a) 0%,var(--b) 45%,#0b1020 100%)}
.grain{position:absolute;inset:0;background:radial-gradient(60% 40% at 85% 30%,rgba(255,255,255,.10),transparent 70%)}
.top{position:absolute;left:64px;right:64px;top:64px;height:96px;display:flex;align-items:center;justify-content:space-between}
.pill{display:flex;align-items:center;gap:14px;padding:16px 28px;border-radius:999px;background:rgba(255,255,255,.16);
  backdrop-filter:blur(6px);font-weight:700;font-size:30px;letter-spacing:.08em;text-transform:uppercase}
.brand{font-family:'Fraunces',serif;font-weight:700;font-size:34px;opacity:.9}
.vis{position:absolute;left:64px;right:64px;top:190px;height:640px;display:flex;flex-direction:column;justify-content:center}
.capband{position:absolute;left:0;right:0;top:850px;height:200px;background:linear-gradient(180deg,transparent,rgba(0,0,0,.28) 30%,rgba(0,0,0,.28) 70%,transparent)}
.low{position:absolute;left:64px;right:64px;top:1110px;bottom:80px;display:flex;flex-direction:column;justify-content:flex-end;gap:28px}
.hl{font-family:'Fraunces',serif;font-weight:700;font-size:60px;line-height:1.12;text-shadow:0 2px 18px rgba(0,0,0,.35)}
.meta{font-size:30px;font-weight:600;opacity:.8;letter-spacing:.02em}
.dots{display:flex;gap:12px}.dots i{flex:1;max-width:44px;height:8px;border-radius:8px;background:rgba(255,255,255,.28)}.dots i.on{background:#fff}
.chap{font-weight:800;font-size:28px;letter-spacing:.12em;text-transform:uppercase;padding:14px 24px;border-radius:999px;
  background:rgba(0,0,0,.28);border:2px solid rgba(255,255,255,.22);white-space:nowrap}
.vw{display:flex;flex-direction:column;gap:24px}.vw .card{display:flex;flex-direction:column;gap:12px;padding:30px 36px}
.vw .who{font-size:30px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;opacity:.85}
.vw .say{font-family:'Fraunces',serif;font-weight:700;line-height:1.18}
.show{font-family:'Fraunces',serif;font-weight:800;line-height:1.05;letter-spacing:-.01em;text-shadow:0 4px 30px rgba(0,0,0,.35)}
.kick{font-size:34px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;opacity:.85;margin-bottom:26px}
.under{width:180px;height:12px;border-radius:12px;background:#fff;margin-top:38px;opacity:.9}
.big{font-weight:900;font-size:220px;line-height:1;letter-spacing:-.03em;text-shadow:0 6px 40px rgba(0,0,0,.35)}
.lbl{font-size:52px;font-weight:600;line-height:1.2;margin-top:26px;opacity:.95}
.card{background:rgba(255,255,255,.12);border:2px solid rgba(255,255,255,.18);border-radius:36px;padding:34px 40px}
.tl{display:flex;flex-direction:column;gap:22px}.tl .row{display:flex;gap:28px;align-items:baseline}
.tl .when{flex:0 0 250px;font-weight:800;font-size:36px;opacity:.9}.tl .what{font-size:40px;font-weight:600;line-height:1.25}
.pl{display:grid;grid-template-columns:1fr 1fr;gap:24px}.pl .card{display:flex;flex-direction:column;gap:12px}
.pl .av{width:92px;height:92px;border-radius:50%;background:rgba(255,255,255,.9);color:var(--b);font-weight:900;font-size:44px;
  display:flex;align-items:center;justify-content:center}.pl .nm{font-size:38px;font-weight:800;line-height:1.15}.pl .rl{font-size:30px;opacity:.85}
.sx{display:flex;flex-direction:column;gap:20px}
.sx .row{display:flex;gap:26px;align-items:center;background:rgba(255,255,255,.12);border:2px solid rgba(255,255,255,.18);
  border-radius:30px;padding:24px 30px}
.sx .n{flex:0 0 68px;height:68px;border-radius:50%;background:#fff;color:var(--b);font-weight:900;font-size:36px;
  display:flex;align-items:center;justify-content:center}
.sx .lb{font-size:28px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;opacity:.8;margin-bottom:6px}
.sx .cl{font-weight:800;line-height:1.15;letter-spacing:-.01em}
.sx .row.last{background:#fff;color:#111}.sx .row.last .n{background:var(--b);color:#fff}
"""


def _page(section: str, body: str, *, headline: str, idx: int, total: int, meta: str, chapter: str = "") -> str:
    a, b = COLORS.get(section, COLORS["world"])
    dots = "".join(f"<i class='{'on' if i <= idx else ''}'></i>" for i in range(total))
    right = f"<div class='chap'>{esc(chapter)}</div>" if chapter else "<div class='brand'>The Briefing</div>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_font_css()}{BASE_CSS}
:root{{--a:{a};--b:{b}}}</style></head><body>
<div class="bg"></div><div class="grain"></div>
<div class="top"><div class="pill">{esc(LABELS.get(section, section))}</div>{right}</div>
<div class="vis">{body}</div>
<div class="capband"></div>
<div class="low"><div class="hl">{esc(headline)}</div><div class="meta">{esc(meta)}</div><div class="dots">{dots}</div></div>
</body></html>"""


def _fit_size(text: str, base: int, *, per_line: int, max_lines: int) -> int:
    """Shrink display text that would wrap past max_lines (rough: chars per line at the base size)."""
    n = len(text)
    lines = math.ceil(n / per_line)
    if lines <= max_lines:
        return base
    return max(54, int(base * math.sqrt(max_lines / lines)))


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
    vw, vh = 952, 600
    scale = min(vw / (span_x * k), vh / span_y)

    def proj(x, y):
        return (vw / 2 + (x - cx) * k * scale, vh / 2 - (y - cy) * scale)
    paths = []
    x0, x1, y0, y1 = cx - span_x, cx + span_x, cy - span_y, cy + span_y
    for code, c in countries.items():
        for ring in c["rings"]:
            if not any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in ring):
                continue
            d = "M" + "L".join(f"{px:.1f},{py:.1f}" for px, py in (proj(x, y) for x, y in ring)) + "Z"
            hi = code in codes
            paths.append(f"<path d='{d}' fill='{'#ffffff' if hi else 'rgba(255,255,255,.16)'}' "
                         f"stroke='{accent if hi else 'rgba(255,255,255,.35)'}' stroke-width='{3 if hi else 1.5}'/>")
    pin = ""
    if lon is not None and lat is not None and (lon or lat):
        px, py = proj(lon, lat)
        raw = (sc.get("map", {}).get("label") or "")[:26]
        pin = (f"<circle cx='{px:.1f}' cy='{py:.1f}' r='34' fill='none' stroke='#fff' stroke-width='5' opacity='.55'/>"
               f"<circle cx='{px:.1f}' cy='{py:.1f}' r='16' fill='{accent}' stroke='#fff' stroke-width='6'/>")
        if raw:
            wpx = 40 + len(raw) * 19                      # pill sized to the text (~19 px per char at 32 px Inter)
            tx = min(max(px, wpx / 2 + 12), vw - wpx / 2 - 12)
            ty = py - 104 if py > 130 else py + 44         # flip below the pin near the top edge
            pin += (f"<rect x='{tx - wpx / 2:.1f}' y='{ty:.1f}' width='{wpx}' height='62' rx='31' fill='#fff'/>"
                    f"<text x='{tx:.1f}' y='{ty + 42:.1f}' text-anchor='middle' font-family='Inter' font-weight='800' "
                    f"font-size='32' fill='#111'>{esc(raw)}</text>")
    return (f"<svg width='{vw}' height='{vh}' viewBox='0 0 {vw} {vh}' style='border-radius:36px;"
            f"background:rgba(0,0,0,.18)'>{''.join(paths)}{pin}</svg>")


def _chart_svg(sc: dict, kind: str) -> str:
    ch = sc.get("chart") or {}
    pts = [p for p in ch.get("points") or [] if isinstance(p.get("value"), (int, float))][:8]
    if len(pts) < 2:
        return ""
    vw, vh, pad = 952, 500, 60
    vals = [p["value"] for p in pts]
    lo, hi = min(0, min(vals)), max(vals) or 1
    rng = (hi - lo) or 1
    n = len(pts)
    out = []
    if kind == "bar":
        bw = (vw - pad * 2) / n * 0.62
        for i, p in enumerate(pts):
            x = pad + (vw - pad * 2) * (i + 0.5) / n
            hgt = (p["value"] - lo) / rng * (vh - 170)
            out.append(f"<rect x='{x - bw / 2:.1f}' y='{vh - 90 - hgt:.1f}' width='{bw:.1f}' height='{hgt:.1f}' rx='14' fill='#fff' opacity='{0.55 + 0.45 * (i == n - 1)}'/>")
            out.append(f"<text x='{x:.1f}' y='{vh - 90 - hgt - 18:.1f}' text-anchor='middle' font-family='Inter' font-weight='800' font-size='34' fill='#fff'>{_fmt(p['value'])}</text>")
            out.append(_label(x, vh - 40, p.get("label"), per_line=max(7, int((vw - pad * 2) / n / 15))))
    else:
        xy = [(pad + (vw - pad * 2) * i / (n - 1), vh - 90 - (p["value"] - lo) / rng * (vh - 170)) for i, p in enumerate(pts)]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
        out.append(f"<polyline points='{line}' fill='none' stroke='#fff' stroke-width='10' stroke-linejoin='round' stroke-linecap='round'/>")
        for (x, y), p in zip(xy, pts):
            out.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='13' fill='#fff'/>")
            out.append(_label(x, vh - 40, p.get("label"), per_line=max(7, int((vw - pad * 2) / n / 15))))
        x, y = xy[-1]
        out.append(f"<text x='{x:.1f}' y='{y - 30:.1f}' text-anchor='end' font-family='Inter' font-weight='900' font-size='44' fill='#fff'>{_fmt(pts[-1]['value'])}</text>")
    title = esc(ch.get("title") or "")
    unit = esc(ch.get("unit") or "")
    return (f"<div class='kick'>{title}{(' · ' + unit) if unit else ''}</div>"
            f"<svg width='{vw}' height='{vh}' viewBox='0 0 {vw} {vh}'>{''.join(out)}</svg>")


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
    spans = "".join(f"<tspan x='{x:.1f}' dy='{0 if i == 0 else 32}'>{esc(t)}</tspan>" for i, t in enumerate(lines))
    return (f"<text x='{x:.1f}' y='{y - (16 if len(lines) > 1 else 0):.1f}' text-anchor='middle' font-family='Inter' "
            f"font-weight='600' font-size='27' fill='#fff' opacity='.88'>{spans}</text>")


def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def scene_html(sc: dict, *, section: str, headline: str, idx: int, total: int, meta: str, chapter: str = "") -> str:
    """idx/total: position in the progress dots (chapters for a chaptered reel, else scenes)."""
    kind = sc.get("kind")
    show = sc.get("show") or ""
    a, _b = COLORS.get(section, COLORS["world"])
    if kind == "hook":
        size = _fit_size(show, 120, per_line=13, max_lines=4)
        kick = "" if chapter else "<div class='kick'>The question</div>"   # the chapter pill already says it
        body = (f"{kick}<div class='show' style='font-size:{size}px'>{esc(show)}</div>"
                "<div class='under'></div>")
    elif kind == "big_number" and (sc.get("number") or {}).get("value"):
        val = sc["number"]["value"]
        size = 220 if len(val) <= 6 else max(120, int(220 * 6 / len(val)))
        body = (f"<div class='big' style='font-size:{size}px'>{esc(val)}</div>"
                f"<div class='lbl'>{esc(sc['number'].get('label') or show)}</div>")
    elif kind == "map" and (svg := _map_svg(sc, a)):
        body = f"<div class='kick'>{esc(show)}</div>{svg}"
    elif kind in ("bar", "line") and (svg := _chart_svg(sc, kind)):
        body = svg
    elif kind == "timeline" and sc.get("timeline"):
        rows = "".join(f"<div class='row'><div class='when'>{esc(t.get('when'))}</div><div class='what'>{esc(t.get('what'))}</div></div>"
                       for t in sc["timeline"][:5])
        body = f"<div class='kick'>{esc(show) or 'How we got here'}</div><div class='card tl'>{rows}</div>"
    elif kind == "players" and sc.get("players"):
        cards = "".join(f"<div class='card'><div class='av'>{esc((p.get('name') or '?')[:1])}</div>"
                        f"<div class='nm'>{esc(p.get('name'))}</div><div class='rl'>{esc(p.get('role'))}</div></div>"
                        for p in sc["players"][:4])
        body = f"<div class='kick'>{esc(show) or 'Who is involved'}</div><div class='pl'>{cards}</div>"
    elif kind == "steps" and sc.get("steps"):
        rows = sc["steps"][:4]
        longest = max(len(str(r.get("calc") or "")) for r in rows)
        size = (56 if longest <= 22 else 48 if longest <= 30 else 40) - (6 if len(rows) == 4 else 0)
        tight = " style='gap:14px'" if len(rows) == 4 else ""
        body = (f"<div class='kick'>{esc(show) or 'Worked example'}</div><div class='sx'{tight}>"
                + "".join(f"<div class='row{' last' if i == len(rows) - 1 else ''}'><div class='n'>{i + 1}</div><div>"
                          f"<div class='lb'>{esc(r.get('label'))}</div><div class='cl' style='font-size:{size}px'>"
                          f"{esc(r.get('calc'))}</div></div></div>" for i, r in enumerate(rows))
                + "</div>")
    elif kind == "views" and sc.get("views"):
        rows = sc["views"][:4]
        size = 50 if len(rows) <= 2 else 42 if len(rows) == 3 else 36
        body = (f"<div class='kick'>{esc(show) or 'Different views'}</div><div class='vw'>"
                + "".join(f"<div class='card'><div class='who'>{esc(v.get('who'))}</div>"
                          f"<div class='say' style='font-size:{size}px'>{esc(v.get('view'))}</div></div>" for v in rows)
                + "</div>")
    elif kind == "outro":
        size = _fit_size(show, 104, per_line=15, max_lines=4)
        kick = "" if chapter else "<div class='kick'>Remember</div>"
        body = (f"{kick}<div class='show' style='font-size:{size}px'>{esc(show)}</div>"
                "<div class='under'></div>")
    else:                                            # kinetic (and any data scene missing its data)
        size = _fit_size(show, 132, per_line=12, max_lines=4)
        body = f"<div class='show' style='font-size:{size}px'>{esc(show)}</div><div class='under'></div>"
    return _page(section, body, headline=headline, idx=idx, total=total, meta=meta, chapter=chapter)
