"""Build one narrated vertical reel (1080×1920 MP4) from a story's reel script.

Per scene:
1. Narration (edge-tts) with word timings. Hinglish reels: the Hindi voice reads `speak` (Hindi words in
   Devanagari) while the captions show `say` (the same words in Roman script), mapped onto the voice's timings.
2. The scene's designed frame, rendered by headless Chrome from scenes.py.
3. A slow push-in on the frame plus its audio.

Then the scenes are joined, word-by-word captions are burned in (ASS via libass, active word highlighted), and
the result is encoded for phones (H.264, AAC, faststart).

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

from . import scenes

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE / "fonts"
VOICE = "en-IN-NeerjaNeural"
RATES = {"en-IN-NeerjaNeural": "+10%", "hi-IN-SwaraNeural": "+8%", "hi-IN-MadhurNeural": "+8%"}   # a touch brisker
FPS = 30
PAD_S = 0.35                      # breath after each scene's narration
# Same labels as routine/briefing/config.CHAPTERS (video/ doesn't import the pipeline package).
CHAPTER_LABELS = {
    "hook": "The question", "what_happened": "What happened", "so_far": "The story so far",
    "why": "Why it happened", "players": "Who's involved", "numbers": "By the numbers", "idea": "The idea",
    "example": "Worked example", "views": "Different views", "for_you": "What it means for you",
    "next": "What's next", "remember": "Remember this",
}
CAPTION_Y = 950                   # caption centre (px from top): inside the 45–54% band the app leaves visible


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
    comm = edge_tts.Communicate(text, voice, rate=RATES.get(voice, "+0%"), boundary="WordBoundary")
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
def render_png(html: str, out_png: pathlib.Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        page = pathlib.Path(f.name)
    try:
        _run([chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
              "--force-device-scale-factor=1", f"--window-size={scenes.W},{scenes.H}",
              "--virtual-time-budget=2000", f"--screenshot={out_png}", page.as_uri()], timeout=90)
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
def build(story: dict, out_dir: pathlib.Path, *, date_label: str, voice: str = VOICE) -> dict:
    """Render story['reel'] into out_dir/<id>-<slug>.mp4 (+ .jpg poster). Returns metadata for the manifest."""
    reel = story.get("reel") or {}
    sc_list = reel.get("scenes") or []
    if not sc_list:
        raise ValueError("story has no reel script")
    voice = reel.get("voice") or voice
    name = f"{story['id']}-{(story.get('slug') or 'story')[:40]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"reel-{story['id']}-"))
    words_all: list[tuple[str, float, float]] = []
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
    try:
        for i, sc in enumerate(sc_list):
            png, mp3, seg = work / f"s{i}.png", work / f"s{i}.mp3", work / f"seg{i}.mp4"
            if chaptered and i in runs:
                chapters.append({"t": round(t0, 2), "key": keys[i], "label": CHAPTER_LABELS.get(keys[i], keys[i])})
            render_png(scenes.scene_html(sc, section=story.get("section", "world"), headline=story.get("headline", ""),
                                         idx=chap_idx[i] if chaptered else i, total=len(runs) if chaptered else len(sc_list),
                                         meta=meta, chapter=CHAPTER_LABELS.get(keys[i], "") if chaptered else ""), png)
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
            words_all += [(w, s + t0, e + t0) for w, s, e in words]
            frames = int(round(dur * FPS))
            # A still designed frame with a soft fade-in; the word-by-word captions carry the motion. (A zoompan
            # push-in looked nice but is single-threaded and timed out on GitHub's shared runners.)
            vf = "fade=t=in:st=0:d=0.25,format=yuv420p"
            _run([ffmpeg(), "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(png), *audio_in,
                  "-filter_complex", f"[0:v]{vf}[v];[1:a]aresample=44100,apad,atrim=0:{dur:.3f},asetpts=N/SR/TB[a]",
                  "-map", "[v]", "-map", "[a]", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
                  "-tune", "stillimage", "-crf", "18", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1",
                  "-shortest", str(seg)], timeout=180)
            segs.append(seg)
            t0 += frames / FPS
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        joined = work / "joined.mp4"
        _run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], timeout=300)
        ass = work / "captions.ass"
        ass.write_text(ass_captions(words_all, t0))
        mp4, jpg = out_dir / f"{name}.mp4", out_dir / f"{name}.jpg"
        sub = f"subtitles=filename='{ass}':fontsdir='{FONTS}'"   # quoted: the repo path contains a space
        _run([ffmpeg(), "-y", "-i", str(joined), "-vf", sub, "-c:v", "libx264", "-preset", "medium", "-crf", "26",
              "-maxrate", "2500k", "-bufsize", "5000k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
              "-movflags", "+faststart", str(mp4)], timeout=600)
        _run([ffmpeg(), "-y", "-i", str(work / "s0.png"), "-vf", "scale=720:-2", "-q:v", "4", str(jpg)], timeout=60)
        return {"story": story["id"], "reel_hash": story.get("reel_hash"), "file": mp4.name, "poster_file": jpg.name,
                "duration_s": round(duration(mp4), 1), "bytes": mp4.stat().st_size, "narrated": narrated,
                "chapters": chapters}
    finally:
        shutil.rmtree(work, ignore_errors=True)
