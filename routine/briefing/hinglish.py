"""Hinglish reel narration.

The writer's English reel script is what the checker verifies. This step re-voices it as spoken Hinglish:
- `say`: Roman script, shown as the captions and the transcript;
- `speak`: the same words with Hindi in Devanagari, read by the Hindi voice (it can't read Romanised Hindi).

Code checks that nothing changed on the way: same scenes, the same numbers in both scripts, no number that
isn't in the story, no relative dates, nothing the voice can't read. If the output fails twice, the reel
stays in English with the English voice; a reel is never dropped because of this step.
"""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from . import build, prompting, schemas

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_DV = r"ऀ-ॿ"
RELATIVE_HI = re.compile(
    r"\b(aaj|kal|parso|parson|is hafte|pichhle hafte|agle hafte|abhi kal)\b"
    rf"|(?<![{_DV}])(आज|कल|परसों)(?![{_DV}])|इस हफ़्ते|इस हफ्ते", re.I)

# "10 November ke agle hafte" (the week after 10 November) is anchored to a date, so it isn't relative.
ANCHORED = re.compile(r"\d{1,2} \w+(?: \d{4})? (?:ke|se|के|से) (?:agle|pichhle|अगले|पिछले) (?:hafte|हफ़्ते|हफ्ते)", re.I)


def relative(text: str) -> bool:
    return bool(RELATIVE_HI.search(ANCHORED.sub(" ", text)))


Ask = Callable[[str, str, dict], Awaitable[dict]]     # (system, prompt, schema) -> dict


def problems(en_scenes: list[dict], out: dict, corpus: set[str], year: int) -> list[str]:
    """Why a Hinglish version can't replace the English one (empty list = good to use)."""
    hi = (out or {}).get("scenes") or []
    if len(hi) != len(en_scenes):
        return [f"returned {len(hi)} scenes; the English has {len(en_scenes)}. Return exactly one per scene."]
    P = []
    for i, (en, h) in enumerate(zip(en_scenes, hi)):
        say, speak = (h.get("say") or "").strip(), (h.get("speak") or "").strip()
        tag = f"scene {i + 1}"
        if not say or not speak:
            P.append(f"{tag}: say and speak must both be filled")
            continue
        if DEVANAGARI.search(say):
            P.append(f"{tag}: `say` must be Roman script only")
        if not DEVANAGARI.search(speak):
            P.append(f"{tag}: `speak` must have its Hindi words in Devanagari")
        for field, text in (("say", say), ("speak", speak)):
            if build.UNSPEAKABLE.search(text):
                P.append(f"{tag}: `{field}` has symbols; write rupaye, percent, dollar, aur")
            if build.RELATIVE.search(text) or relative(text):
                P.append(f"{tag}: `{field}` has a relative date; use the absolute date")
        if build._nums(say) != build._nums(speak):
            P.append(f"{tag}: the numbers in `say` and `speak` differ ({sorted(build._nums(say))} vs "
                     f"{sorted(build._nums(speak))}); they must be the same words")
        bad = build.unverified_numbers(say, corpus, year)
        if bad:
            P.append(f"{tag}: numbers not in the English script or the story: {', '.join(bad)}")
        n_en, n_say, n_speak = len((en.get("say") or "").split()), len(say.split()), len(speak.split())
        if n_en >= 8 and not 0.6 <= n_say / n_en <= 1.7:
            P.append(f"{tag}: {n_say} words for {n_en} English words; keep about the same length")
        if n_say >= 6 and not 0.7 <= n_speak / n_say <= 1.4:
            P.append(f"{tag}: `speak` has {n_speak} words but `say` has {n_say}; they must match word for word")
    return P


def prompt(story: dict, en_scenes: list[dict]) -> str:
    lesson = story.get("lesson") or {}
    rows = [{"scene": i + 1, "kind": sc.get("kind"), "show": sc.get("show", ""), "say": sc.get("say", "")}
            for i, sc in enumerate(en_scenes)]
    return (f"Story: {prompting.safe(story.get('headline', ''))}\n"
            f"Idea the reel teaches: {prompting.safe(lesson.get('concept', ''))}\n\n"
            f"<story>\n{prompting.safe(json.dumps(rows, ensure_ascii=False, indent=1))}\n</story>\n\n"
            "Return the Hinglish narration: one {say, speak} per scene, in order.")


async def adapt(ask: Ask, story: dict, en_scenes: list[dict], corpus: set[str], year: int) -> tuple[list | None, list]:
    """Returns (hinglish scenes or None, last problems). One retry with the problems as feedback."""
    system = prompting.system("hinglish")
    base, feedback, P = prompt(story, en_scenes), "", []
    for _attempt in range(2):
        out = await ask(system, base + feedback, schemas.HINGLISH)
        P = problems(en_scenes, out, corpus, year)
        if not P:
            return out["scenes"], []
        feedback = "\n\nYOUR PREVIOUS ATTEMPT had these problems; fix every one:\n- " + "\n- ".join(P[:12])
    return None, P


def apply(scenes: list[dict], hi: list[dict]) -> list[dict]:
    """English scenes + Hinglish narration -> scenes that keep the English as `say_en`."""
    return [{**sc, "say_en": sc.get("say", ""), "say": h["say"].strip(), "speak": h["speak"].strip()}
            for sc, h in zip(scenes, hi)]


def story_corpus(story: dict, extra: set[str] | None = None) -> set[str]:
    """Numbers the Hinglish may use: everything in the story itself (blocks, lesson, reel data) plus extras."""
    return build._nums(json.dumps(story, ensure_ascii=False)) | (extra or set())
