"""Build one narrated vertical reel (1080×1920 MP4) from a story's reel script.

1. Photos: each scene's `image` (a Wikipedia article title) and each player's name resolve to free-licence
   photos (images.py). A scene without one reuses the story's last photo, blurred; a story with none gets a
   designed backdrop.
2. Frames: every scene is rendered by headless Chrome in layers (scenes.py): an oversized backdrop, the static
   chrome, and each content piece on its own transparent frame.
3. Narration (edge-tts) with word timings. Hinglish reels: the Hindi voice reads `speak` (Hindi words in
   Devanagari) while the captions show `say` (the same words in Roman script), mapped onto the voice's timings.
4. One ffmpeg pass per scene: a slow Ken Burns pan across the backdrop, content sliding/fading in (rows of a
   worked example or timeline arrive as the narration reaches them), word-by-word captions burned in, encoded
   once for phones. The scenes are then joined without re-encoding (faststart).

If the voice service fails three times, the reel is still rendered silent with captions timed at a reading pace.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from . import images, scenes

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE / "fonts"
VOICE = "en-IN-NeerjaNeural"
# Voice settings per voice. Swara is slowed a little and pitched slightly lower: the viewer picked this "calmer"
# version from samples on 2026-11-10 because the default sounded irritating. (Speed is also adjustable in the app.)
RATES = {"en-IN-NeerjaNeural": "+10%", "hi-IN-SwaraNeural": "-6%", "hi-IN-MadhurNeural": "-4%"}
PITCHES = {"hi-IN-SwaraNeural": "-3Hz", "hi-IN-MadhurNeural": "-2Hz"}
FPS = 30
PAD_S = 0.35                      # breath after each scene's narration
# Same labels as routine/briefing/config.CHAPTERS (video/ doesn't import the pipeline package).
CHAPTER_LABELS = {
    "hook": "The question", "what_happened": "What happened", "history": "How we got here",
    "so_far": "The story so far",
    "why": "Why it happened", "players": "Who's involved", "numbers": "By the numbers", "idea": "The idea",
    "example": "Worked example", "views": "Different views", "for_you": "What it means for you",
    "next": "What's next", "remember": "Remember this",
}
CAPTION_Y = 1390                  # caption centre (px from top): the band between the main visual and the headline


def _bin(name: str, *extra: str) -> str:
    for c in (os.environ.get(name.upper()), shutil.which(name), *extra):
        if c and (os.path.exists(c) or shutil.which(c)):
            return c
    raise FileNotFoundError(f"{name} not found")


def ffmpeg() -> str:
    return _bin("ffmpeg", os.path.expanduser("~/.local/bin/ffmpeg"))


def ffprobe() -> str:
    return _bin("ffprobe", os.path.expanduser("~/.local/bin/ffprobe"))


def chrome() -> str:
    return _bin("chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome",
                "google-chrome-stable", "chromium", "chromium-browser")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{pathlib.Path(cmd[0]).name} failed: {r.stderr.decode('utf-8', 'ignore')[-600:]}")
    return r


def duration(path: pathlib.Path) -> float:
    try:
        r = _run([ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
        return float(r.stdout.decode().strip())
    except FileNotFoundError:                     # no ffprobe (e.g. a static ffmpeg on the Mac): ask ffmpeg itself
        r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path), "-f", "null", "-"], capture_output=True)
        times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", r.stderr.decode("utf-8", "ignore"))
        if not times:
            raise RuntimeError(f"couldn't read the duration of {path.name}")
        h, m, sec = times[-1]
        return int(h) * 3600 + int(m) * 60 + float(sec)


# ---------------------------------------------------------------- narration
def speakable(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t.replace("&", " and ").replace("%", " per cent")


async def _tts_once(text: str, voice: str, out: pathlib.Path) -> list[tuple[str, float, float]]:
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=RATES.get(voice, "+0%"), pitch=PITCHES.get(voice, "+0Hz"),
                                boundary="WordBoundary")
    audio, words = bytearray(), []
    async for ch in comm.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append((ch["text"], ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7))
    if not audio:
        raise RuntimeError("no audio returned")
    out.write_bytes(bytes(audio))
    return words


def narrate(text: str, out: pathlib.Path, voice: str = VOICE) -> tuple[list, float] | None:
    """Returns (word timings, audio seconds), or None if the voice service failed 3 times."""
    for attempt in range(3):
        try:
            words = asyncio.run(_tts_once(speakable(text), voice, out))
            return words, duration(out)
        except Exception:  # noqa: BLE001 - network/service hiccups: retry, then fall back to silent
            if attempt == 2:
                return None
            import time
            time.sleep(2 * (attempt + 1))
    return None


def align(caption_text: str, timed: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
    """Put the caption words (Roman Hinglish) on the timings of the spoken words (mixed script). The two are
    written word for word, so counts usually match; if not, each caption word takes the proportional slot."""
    cap = speakable(caption_text).split()
    if not cap or not timed:
        return timed
    if len(cap) == len(timed):
        return [(c, s, e) for c, (_w, s, e) in zip(cap, timed)]
    n, m, out = len(cap), len(timed), []
    for i, c in enumerate(cap):
        a, b = timed[i * m // n], timed[min(m - 1, max(i * m // n, (i + 1) * m // n - 1))]
        out.append((c, a[1], b[2]))
    return out


def _even_words(text: str, start: float, secs_per_word: float = 0.4) -> list[tuple[str, float, float]]:
    out, t = [], start
    for w in speakable(text).split():
        out.append((w, t, t + secs_per_word))
        t += secs_per_word
    return out


# ---------------------------------------------------------------- frames
def render_png(html: str, out_png: pathlib.Path, *, scale: float = 1.0, transparent: bool = False) -> None:
    """Screenshot a 1080×1920 page (× scale). transparent: keep the alpha channel (overlay layers)."""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        page = pathlib.Path(f.name)
    try:
        _run([chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
              f"--force-device-scale-factor={scale}", f"--window-size={scenes.W},{scenes.H}",
              *(["--default-background-color=00000000"] if transparent else []),
              "--virtual-time-budget=2500", f"--screenshot={out_png}", page.as_uri()], timeout=90)
    finally:
        page.unlink(missing_ok=True)
    if not out_png.exists():
        raise RuntimeError(f"chrome produced no screenshot for {out_png.name}")


# ---------------------------------------------------------------- captions
def _ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _clean_word(w: str) -> str:
    return w.replace("{", "(").replace("}", ")").replace("\\", "")


def ass_captions(words: list[tuple[str, float, float]], total: float) -> str:
    """Two-to-three-word chunks, active word in yellow, white text with a dark outline, centred at CAPTION_Y."""
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n"
            "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n"
            "Style: Cap,Inter,74,&H00FFFFFF,&H00FFFFFF,&H00141414,&H78000000,1,0,0,0,100,100,0,0,1,6,2,5,70,70,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) == 3 or re.search(r"[.,;:?!]$", w[0]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    lines = []
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0][1] if ci + 1 < len(chunks) else total
        for wi, (w, start, end) in enumerate(ch):
            stop = ch[wi + 1][1] if wi + 1 < len(ch) else min(max(end + 0.15, start + 0.2), nxt)
            txt = " ".join(("{\\c&H00D7FF&}" + _clean_word(x) + "{\\c&HFFFFFF&}") if j == wi else _clean_word(x)
                           for j, (x, _s, _e) in enumerate(ch))
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(stop)},Cap,,0,0,0,,{{\\pos(540,{CAPTION_Y})}}{txt}")
    return head + "\n".join(lines) + "\n"


# ---------------------------------------------------------------- assembly
# Ken Burns pans, as fractions of the backdrop's slack (x0, y0) -> (x1, y1). Consecutive scenes alternate.
PANS = [(0.15, 0.2, 0.85, 0.6), (0.8, 0.7, 0.2, 0.25), (0.25, 0.85, 0.7, 0.15), (0.75, 0.15, 0.3, 0.8)]
SLIDE_PX, SLIDE_S, FADE_S = 46, 0.6, 0.45
# Size: ten 6-minute reels a day, three days kept on Pages (1 GB limit): aim for ~3 MB per minute.
CRF, MAXRATE = os.environ.get("REEL_CRF", "30"), os.environ.get("REEL_MAXRATE", "1200k")   # ~9-min reels: keep 2 days of 10 under the 1 GB Pages limit


def _photos(sc_list: list[dict], resolver) -> tuple[list, list[bool], dict]:
    """Per scene: (photo, reused?) and the player-name photos. A scene without its own photo borrows the
    story's last one (or the first one, before any has appeared); it is then shown blurred."""
    titles = list(dict.fromkeys(sc.get("image") for sc in sc_list if sc.get("image")))
    names = list(dict.fromkeys(p.get("name") for sc in sc_list if sc.get("kind") == "players"
                               for p in sc.get("players") or [] if p.get("name")))
    with ThreadPoolExecutor(4) as ex:
        got = dict(zip(titles, ex.map(resolver.resolve, titles)))
        avs = dict(zip(names, ex.map(lambda n: resolver.resolve(n, min_width=200), names)))
    own = [got.get(sc.get("image")) if sc.get("image") else None for sc in sc_list]
    last = next((p for p in own if p is not None), None)
    photos, reused = [], []
    for p in own:
        if p is not None:
            last = p
        photos.append(p if p is not None else last)
        reused.append(p is None and last is not None)
    return photos, reused, {k: v for k, v in avs.items() if v is not None}


def _trim(png: pathlib.Path) -> tuple[int, int, pathlib.Path]:
    """Crop a transparent layer to its visible box (overlaying a small image is much cheaper per frame)."""
    try:
        from PIL import Image
    except ImportError:                                    # still correct, just slower
        return 0, 0, png
    with Image.open(png) as im:
        box = im.getchannel("A").getbbox() if im.mode == "RGBA" else None
        if not box:
            return 0, 0, png
        x0, y0 = max(0, box[0] - 2), max(0, box[1] - 2)
        out = png.with_name(png.stem + "-t.png")
        im.crop((x0, y0, min(im.width, box[2] + 2), min(im.height, box[3] + 2))).save(out)
        return x0, y0, out


def _render_layers(html: str, work: pathlib.Path, i: int) -> dict:
    """bg (oversized), ui and each content layer as PNGs for scene i."""
    n = scenes.layer_count(html)
    bg, ui = work / f"s{i}-bg.png", work / f"s{i}-ui.png"
    render_png(scenes.with_pass(html, "bg"), bg, scale=scenes.BG_SCALE)
    render_png(scenes.with_pass(html, "ui"), ui, transparent=True)
    layers = []
    for k in range(1, n + 1):
        png = work / f"s{i}-l{k}.png"
        render_png(scenes.with_pass(html, str(k)), png, transparent=True)
        layers.append(_trim(png))
    return {"bg": bg, "ui": _trim(ui), "layers": layers, "html": html}


def _segment(fr: dict, sc: dict, i: int, dur: float, audio_in: list[str], ass: pathlib.Path,
             out: pathlib.Path) -> None:
    """One scene: panning backdrop + static chrome + content layers sliding in + captions, encoded once."""
    bw, bh = round(scenes.W * scenes.BG_SCALE), round(scenes.H * scenes.BG_SCALE)
    x0, y0, x1, y1 = PANS[i % len(PANS)]
    sx, sy = bw - scenes.W, bh - scenes.H
    X = f"{sx * x0:.1f}+{sx * (x1 - x0):.1f}*t/{dur:.3f}"
    Y = f"{sy * y0:.1f}+{sy * (y1 - y0):.1f}*t/{dur:.3f}"
    nf = int(round(dur * FPS))
    # Each PNG is decoded and converted ONCE, then repeated in memory (`-loop 1` would decode it every frame).
    hold = f"loop=loop={nf - 1}:size=1:start=0,setpts=N/{FPS}/TB"
    ux, uy, ui = fr["ui"]
    args = ["-i", str(fr["bg"]), "-i", str(ui)]
    for _lx, _ly, png in fr["layers"]:
        args += ["-i", str(png)]
    args += audio_in
    times = scenes.reveal_times(sc, len(fr["layers"]), dur)
    g = [f"[0:v]format=yuv420p,{hold},crop={scenes.W}:{scenes.H}:x='{X}':y='{Y}'[b]",
         f"[1:v]format=yuva420p,{hold}[u]", f"[b][u]overlay={ux}:{uy}:format=yuv420[c0]"]
    prev = "c0"
    for k, ((lx, ly, _png), s) in enumerate(zip(fr["layers"], times)):
        g.append(f"[{k + 2}:v]format=yuva420p,{hold},fade=t=in:st={s:.2f}:d={FADE_S}:alpha=1[l{k}]")
        g.append(f"[{prev}][l{k}]overlay=x={lx}:y='{ly}+{SLIDE_PX}*pow(1-clip((t-{s:.2f})/{SLIDE_S},0,1),3)'"
                 f":eval=frame:format=yuv420[c{k + 1}]")
        prev = f"c{k + 1}"
    g.append(f"[{prev}]subtitles=filename='{ass}':fontsdir='{FONTS}',format=yuv420p[v]")
    a = len(fr["layers"]) + 2
    g.append(f"[{a}:a]aresample=44100,apad,atrim=0:{dur:.3f},asetpts=N/SR/TB[a]")
    _run([ffmpeg(), "-y", *args, "-filter_complex", ";".join(g), "-map", "[v]", "-map", "[a]",
          "-frames:v", str(int(round(dur * FPS))), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
          "-crf", CRF, "-maxrate", MAXRATE, "-bufsize", "4000k", "-g", str(FPS * 2), "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1", str(out)], timeout=900)


def build(story: dict, out_dir: pathlib.Path, *, date_label: str, voice: str = VOICE, resolver=None) -> dict:
    """Render story['reel'] into out_dir/<id>-<slug>.mp4 (+ .jpg poster). Returns metadata for the manifest."""
    reel = story.get("reel") or {}
    sc_list = reel.get("scenes") or []
    if not sc_list:
        raise ValueError("story has no reel script")
    voice = reel.get("voice") or voice
    name = f"{story['id']}-{(story.get('slug') or 'story')[:40]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"reel-{story['id']}-"))
    segs, t0, narrated = [], 0.0, True
    # Chapters: runs of consecutive scenes with the same chapter key. Their start times go to the manifest so
    # the app can skip and jump by chapter; the frame shows the chapter name and chapter progress.
    keys = [sc.get("chapter") or "" for sc in sc_list]
    chaptered = all(keys)
    runs = [i for i, k in enumerate(keys) if chaptered and (i == 0 or k != keys[i - 1])]
    chap_idx = [sum(1 for r in runs if r <= i) - 1 for i in range(len(sc_list))]
    chapters: list[dict] = []
    meta = f"{date_label} · {len(runs) if chaptered else len(sc_list)} {'chapters' if chaptered else 'scenes'}"
    thread = story.get("thread") or {}
    if thread.get("day", 1) > 1:
        meta = f"{date_label} · Day {thread['day']} of this story"
    section, headline = story.get("section", "world"), story.get("headline", "")
    clock, mark = {}, time.monotonic()

    def lap(name):
        nonlocal mark
        now = time.monotonic()
        clock[name] = round(now - mark, 1)
        mark = now
    try:
        resolver = resolver or images.Resolver(work / "img")
        photos, reused, avatars = _photos(sc_list, resolver)
        lap("photos")
        pages = [scenes.scene_html(sc, section=section, headline=headline,
                                   idx=chap_idx[i] if chaptered else i,
                                   total=len(runs) if chaptered else len(sc_list), meta=meta,
                                   chapter=CHAPTER_LABELS.get(keys[i], "") if chaptered else "",
                                   photo=photos[i], reused=reused[i], avatars=avatars)
                 for i, sc in enumerate(sc_list)]
        with ThreadPoolExecutor(4) as ex:                  # Chrome screenshots, several at a time
            frames = list(ex.map(lambda a: _render_layers(a[1], work, a[0]), enumerate(pages)))
        lap("frames")
        encodes = ThreadPoolExecutor(2)                    # encode scene i while narrating scene i+1
        jobs = []
        for i, sc in enumerate(sc_list):
            mp3, seg, ass = work / f"s{i}.mp3", work / f"seg{i}.mp4", work / f"s{i}.ass"
            if chaptered and i in runs:
                chapters.append({"t": round(t0, 2), "key": keys[i], "label": CHAPTER_LABELS.get(keys[i], keys[i])})
            res = narrate(sc.get("speak") or sc.get("say", ""), mp3, voice) if narrated else None
            if res is None:
                narrated = False
                words = _even_words(sc.get("say", ""), 0.0)
                dur = (words[-1][2] if words else 2.0) + PAD_S
                audio_in = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=mono"]
            else:
                words, adur = res
                if sc.get("speak"):
                    words = align(sc.get("say", ""), words)
                dur = adur + PAD_S
                audio_in = ["-i", str(mp3)]
            dur = round(int(round(dur * FPS)) / FPS, 4)
            ass.write_text(ass_captions(words, dur))
            jobs.append(encodes.submit(_segment, frames[i], sc, i, dur, audio_in, ass, seg))
            segs.append(seg)
            if i == 0:
                first_dur = dur
            t0 += dur
        encodes.shutdown(wait=True)
        for j in jobs:
            j.result()                                     # re-raise any encode failure
        lap("voice+encode")
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        mp4, jpg = out_dir / f"{name}.mp4", out_dir / f"{name}.jpg"
        _run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
              str(mp4)], timeout=300)
        n0 = len(frames[0]["layers"])
        at = min(max(0.1, first_dur - 0.2), (scenes.reveal_times(sc_list[0], n0, first_dur) or [0])[-1] + 1.2)
        _run([ffmpeg(), "-y", "-ss", f"{at:.2f}", "-i", str(segs[0]), "-frames:v", "1", "-vf", "scale=720:-2",
              "-q:v", "4", str(jpg)], timeout=60)
        return {"story": story["id"], "reel_hash": story.get("reel_hash"), "file": mp4.name, "poster_file": jpg.name,
                "duration_s": round(duration(mp4), 1), "bytes": mp4.stat().st_size, "narrated": narrated,
                "chapters": chapters, "timing": clock,
                "photos": sum(1 for p, r in zip(photos, reused) if p is not None and not r)}
    finally:
        shutil.rmtree(work, ignore_errors=True)
