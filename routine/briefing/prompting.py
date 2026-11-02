"""Builds the text each model step receives. Inputs are wrapped in tags and passed through engine.safe()
so scraped text can't pose as instructions."""
from __future__ import annotations

import json

from . import config
from .engine import safe


def prompt_file(name: str) -> str:
    return (config.PROMPTS / f"{name}.md").read_text()


def system(*names: str, **subs) -> str:
    text = "\n\n".join(prompt_file(n) for n in names)
    for k, v in subs.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def _sig_line(c: dict) -> str:
    s = c.get("signals") or {}
    bits = []
    if s.get("wiki"):
        bits.append("on Wikipedia's curated daily page")
    if s.get("kagi"):
        bits.append(f"Kagi: {s['kagi']} sites")
    if s.get("beats"):
        bits.append("beat: " + ", ".join(s["beats"]))
    if s.get("primary"):
        bits.append("official source")
    if s.get("scout"):
        bits.append("found by scout search")
    if c.get("thread_hint"):
        bits.append(f"may continue {c['thread_hint']}")
    return "; ".join(bits) or "none"


def best_summary(c: dict, n: int = 280) -> str:
    for m in c.get("members") or []:
        if len(m.get("summary") or "") > 60:
            return m["summary"][:n]
    return (c.get("wiki_text") or c.get("kagi_summary") or "")[:n]


def triage_item(c: dict) -> str:
    pubs = ", ".join(c.get("publisher_names") or [])[:160]
    return (f'<item id="{c["id"]}">\ntitle: {safe(c["title"])}\noutlets: {c["publishers"]} ({safe(pubs)})\n'
            f'section hint: {c["section_hint"]}\nsignals: {_sig_line(c)}\nsummary: {safe(best_summary(c))}\n</item>')


def triage(batch: list[dict], *, date: str, covered: list[str], threads: list[dict]) -> str:
    cov = "\n".join(f"- {safe(h)}" for h in covered[:60]) or "- (none)"
    thr = "\n".join(f"- {t['id']}: {t['title']} (keywords: {', '.join(t.get('keywords') or [])})"
                    for t in threads) or "- (none)"
    items = "\n".join(triage_item(c) for c in batch)
    return (f"Edition date: {date} (IST).\n\nAlready covered in the previous edition:\n{cov}\n\n"
            f"Ongoing threads:\n{thr}\n\nStories to sort ({len(batch)}):\n{items}")


def same_story(cands: list[dict]) -> str:
    return "Headlines:\n" + "\n".join(f"{c['id']} | {c['section']} | {safe(c['title'])}" for c in cands)


def scout(gaps: list[dict], window: dict) -> str:
    lines = "\n".join(f"- [{g['gap']}] {g['ask']}" for g in gaps)
    return (f"News window: {window['start']} to {window['end']} (IST). Only reports published inside this window "
            f"count as found.\n\nGaps to check:\n{lines}")


def editor(*, date: str, window: dict, cands: list[dict], threads: list[dict], due: list[dict],
           upcoming: list[dict], misses: list[dict], covered: list[str]) -> str:
    out = [f"Edition date: {date} (IST). News window: {window['start']} to {window['end']}.", "",
           "## Candidate stories (best first)"]
    for c in cands:
        t = c.get("triage") or {}
        out.append(f"[{c['id']}] {c['section']} · score {c.get('score')} · outlets {c['publishers']} · tier {c['tier']} · "
                   f"scale {t.get('scale')} sev {t.get('severity')} dur {t.get('durability')} new {t.get('novelty')} "
                   f"india {t.get('india')}{' · interest' if t.get('interest') else ''} · {_sig_line(c)}")
        out.append(f"   {safe(c['title'])}")
        if t.get("line"):
            out.append(f"   {safe(t['line'])}")
    out += ["", "## Active threads (every one needs an action)"]
    for th in threads:
        out.append(f"- {th['id']}: {th['title']} · day {th.get('days')} · last covered {th.get('last_covered')}\n"
                   f"  so far: {safe(th.get('summary', ''))[:400]}\n  watch: {json.dumps(th.get('watch') or [])}")
    if not threads:
        out.append("- (none yet)")
    out += ["", "## Calendar: events due in this window (must be covered or explained)"]
    out += [f"- {e['id']}: {e['date']} {e.get('time_ist') or ''} {e['title']}" for e in due] or ["- (none)"]
    out += ["", "## Coming up in the next 7 days (for watch_today)"]
    out += [f"- {e['id']}: {e['date']} {e.get('time_ist') or ''} {e['title']}" for e in upcoming] or ["- (none)"]
    out += ["", "## Missed by the previous edition (recall check)"]
    out += [f"- {'MAJOR ' if m.get('major') else ''}{safe(m['event'])}" for m in misses] or ["- (none)"]
    out += ["", "## Already covered in the previous edition (judge novelty against this)"]
    out += [f"- {safe(h)}" for h in covered[:60]] or ["- (none)"]
    return "\n".join(out)


def _articles(clusters: list[dict]) -> str:
    rows = []
    for c in clusters:
        for m in c.get("members") or []:
            rows.append(f'<source pub="{safe(m["pub"])}" published="{m.get("published") or "unknown"}" url="{m["url"]}">\n'
                        f'{safe(m["title"])}\n{safe(m.get("summary") or "")}\n</source>')
        if c.get("wiki_text"):
            rows.append(f"<source pub=\"Wikipedia Current events\" published=\"(curated daily page)\" url=\"\">\n"
                        f"{safe(c['wiki_text'])}\n</source>")
        if c.get("kagi_summary"):
            rows.append(f"Lead summary from an aggregator (unverified; find the original sources):\n{safe(c['kagi_summary'])}")
    return "\n".join(rows)


def research(slot: dict, clusters: list[dict], *, date: str, window: dict, thread: dict | None) -> str:
    must = "\n".join(f"- {q}" for q in slot.get("must_answer") or [])
    out = [f"Edition date: {date} (IST). News window: {window['start']} to {window['end']}.",
           f"Question: {slot['question']}", f"Must answer:\n{must}",
           f"Section: {slot['section']}. India angle: {slot.get('india_angle')}. Contested: {slot.get('contested')}."]
    if thread:
        out.append("This continues an ongoing story. What we reported before (find what CHANGED):\n"
                   f"Summary: {safe(thread['summary'])}\nLast known state: {json.dumps(thread['last_state'])}\n"
                   f"Recent: {json.dumps(thread['recent'])}")
    out.append("## Articles already found (you may cite these directly)\n" + _articles(clusters))
    return "\n\n".join(out)


def writer(slot: dict, research: dict, *, date: str, thread: dict | None) -> str:
    out = [f"Edition date: {date}. Write absolute dates only.",
           f"Question to answer: {slot['question']}",
           f"India angle: {slot.get('india_angle')}. Contested (needs named views): {slot.get('contested')}."]
    if thread:
        out.append(f"This continues an ongoing story (day {thread['days'] + 1}). Previously reported: "
                   f"{safe(thread['summary'])}\nLast known state: {json.dumps(thread['last_state'])}\n"
                   "Write `changed` (what is new) and lead with the development, not a recap.")
    else:
        out.append("This is a new story: leave `changed` empty.")
    out.append("## Claims: the ONLY facts you may use (cite their cids)\n" + json.dumps(_slim_research(research),
                                                                                         ensure_ascii=False))
    return "\n\n".join(out)


def _slim_research(r: dict) -> dict:
    return {
        "claims": [{k: c.get(k) for k in ("cid", "text", "kind", "pub", "published", "type", "confidence")}
                   for c in r.get("claims") or []],
        "numbers": r.get("numbers") or [], "timeline": r.get("timeline") or [], "players": r.get("players") or [],
        "views": r.get("views") or [], "current_facts": r.get("current_facts") or [], "unknowns": r.get("unknowns") or [],
    }


def checker(story: dict, research: dict, *, thread: dict | None, code_problems: list[dict]) -> str:
    claims = [{k: c.get(k) for k in ("cid", "text", "pub", "published", "excerpt")} for c in research.get("claims") or []]
    out = ["<story>\n" + json.dumps(story, ensure_ascii=False) + "\n</story>",
           "<claims>\n" + json.dumps(claims, ensure_ascii=False) + "\n</claims>"]
    if thread:
        out.append("Previous state of this story: " + json.dumps(thread["last_state"]))
    if code_problems:
        out.append("Automatic checks already found (include them if real): " + json.dumps(code_problems))
    return "\n\n".join(out)


def fixer(story: dict, research: dict, problems: list[dict], *, date: str) -> str:
    return (f"Edition date: {date}. Revise the story to fix EVERY problem below. Keep everything that is fine. "
            "Cut what you can't support. Return the complete story in the same shape.\n\n"
            f"Problems:\n{json.dumps(problems, ensure_ascii=False, indent=1)}\n\n"
            f"<story>\n{json.dumps(story, ensure_ascii=False)}\n</story>\n\n"
            f"## Claims (the only facts you may use)\n{json.dumps(_slim_research(research), ensure_ascii=False)}")


def section_research(section: str, items: list[dict], clusters: dict, *, window: dict) -> str:
    title = config.SECTIONS[section][1]
    out = [f"Section: {title}. News window: {window['start']} to {window['end']} (IST)."]
    for it in items:
        cl = [clusters[c] for c in it["cluster_ids"] if c in clusters]
        out.append(f'<item id="{it["id"]}">\nangle: {safe(it.get("angle") or "")}\n{_articles(cl)}\n</item>')
    return "\n\n".join(out)


def briefs(sections: list[str], items_by_sec: dict, facts: dict, threads_ctx: dict, *, date: str) -> str:
    out = [f"Edition date: {date}. Write gists for these sections: {', '.join(sections)}."]
    for sec in sections:
        out.append(f"## Section: {config.SECTIONS[sec][1]} ({sec})")
        for it in items_by_sec.get(sec, []):
            f = facts.get(it["id"]) or []
            thr = threads_ctx.get(it.get("thread_id") or "")
            t_line = f"\ncontinues thread: {thr['title']}. Previously: {safe(thr['summary'])[:300]}" if thr else ""
            out.append(f'<item id="{it["id"]}">{t_line}\nangle: {safe(it.get("angle") or "")}\nfacts: '
                       f"{json.dumps(f, ensure_ascii=False)}\n</item>")
    return "\n\n".join(out)


def briefs_check(briefs: list[dict], facts: dict) -> str:
    rows = [f'<item id="{b["item_id"]}">\nbrief: {json.dumps(b, ensure_ascii=False)}\nfacts: '
            f'{json.dumps(facts.get(b["item_id"]) or [], ensure_ascii=False)}\n</item>' for b in briefs]
    return "\n\n".join(rows)


def cover(stories: list[dict], briefs: list[dict], *, date: str, today_events: list[dict], watch: list[dict]) -> str:
    out = [f"Edition date: {date}.", "## Big stories"]
    out += [f"- {s['id']}: {safe(s['headline'])}. {safe(s['dek'])}" for s in stories]
    out += ["", "## Briefs"]
    out += [f"- {b['id']} ({b['section']}): {safe(b['headline'])}" for b in briefs]
    out += ["", "## On the calendar for the edition date"]
    out += [f"- {e['date']} {e.get('time_ist') or ''} {safe(e['title'])}" for e in today_events] or ["- (none)"]
    out += ["", "## Editor's watch list"]
    out += [f"- {safe(w.get('text', ''))} {w.get('time_ist', '')}" for w in watch] or ["- (none)"]
    return "\n".join(out)


def recall(items: list[str], events: list[dict]) -> str:
    ed = "\n".join(f"- {safe(h)}" for h in items)
    ev = "\n".join(f"- [{e['category']}] {safe(e['text'])[:300]}" for e in events)
    return f"## The edition covered\n{ed}\n\n## Reference events\n{ev}"


def bootstrap(editions: list[dict]) -> str:
    out = []
    for d in editions:
        out.append(f"## Edition {d.get('date')}\nTop line: {safe(d.get('top_line') or '')}")
        for s in d.get("sections") or []:
            for it in s.get("items") or []:
                out.append(f"- [{s.get('key')}] {safe(it.get('headline') or it.get('title') or '')}: "
                           f"{safe((it.get('what') or it.get('summary') or '')[:240])}")
    return "\n".join(out)
