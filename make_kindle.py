#!/usr/bin/env python3
"""Send the 🎓 Learn course to your Kindle as a clean, reflowable EPUB.

The reels' Learn tab is a JS app — no good on e-ink. But the lessons themselves are long-form reading,
which is exactly what a Kindle is for. This renders the lesson catalog (dashboard/lessons.json) into an
EPUB and e-mails it to your Kindle's @kindle.com address (Amazon delivers it over WiFi).

It sends only parts you haven't received yet (tracked in output/kindle-sent.json), so each day's new
lesson lands as its own tidy document. First run sends the whole course so far.

Env (.env, gitignored — NEVER commit these): GMAIL_ADDRESS, GMAIL_APP_PASSWORD, KINDLE_EMAIL.
  • KINDLE_EMAIL is your device's Send-to-Kindle address (Amazon → Manage Your Content & Devices → Devices).
  • GMAIL_ADDRESS must be on your Amazon "approved sender" list, or Amazon silently drops the mail.

Run:  python make_kindle.py            # send any new parts
      python make_kindle.py --force    # rebuild + resend the latest part even if already sent
      python make_kindle.py --all      # resend the WHOLE course as one EPUB
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import smtplib
import ssl
import sys
import zipfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001 - dotenv optional; env may already be set
    pass

ROOT = pathlib.Path(__file__).resolve().parent
DASH = ROOT / "dashboard"
CATALOG = DASH / "lessons.json"
PUBLISHED = DASH / "learn-course.epub"              # public download (lessons are already public — safe)
STATE = ROOT / "output" / "kindle-sent.json"        # {last_seq} — gitignored
OUT_DIR = ROOT / "output"

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL", "").strip()


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _paras(text) -> str:
    """Turn a detail blob (string with breaks, or a list) into <p> paragraphs."""
    if isinstance(text, list):
        items = [str(t).strip() for t in text if str(t).strip()]
    else:
        raw = str(text or "").replace("\r\n", "\n")
        items = [p.strip() for p in raw.split("\n\n") if p.strip()] or \
                [p.strip() for p in raw.split("\n") if p.strip()]
    return "".join(f"<p>{_esc(p)}</p>" for p in items)


# ---------- EPUB rendering ----------

CSS = """
body{font-family:Georgia,'Times New Roman',serif;line-height:1.55;margin:0 6% ;}
h1{font-size:1.5em;line-height:1.25;margin:1.2em 0 .2em}
h2{font-size:1.2em;margin:1.4em 0 .3em}
.eyebrow{font-size:.8em;letter-spacing:.08em;text-transform:uppercase;color:#666;margin-top:1.4em}
.recap-so-far{font-style:italic;color:#333;border-left:3px solid #bbb;padding:.2em 0 .2em 1em;margin:1em 0}
.idea{font-weight:bold}
.example{background:#f4f4f0;border:1px solid #ddd;border-radius:6px;padding:.6em .9em;margin:.9em 0}
.example .lbl,.takeaway .lbl,.terms .lbl{font-size:.75em;letter-spacing:.08em;text-transform:uppercase;color:#777;display:block;margin-bottom:.25em}
.takeaway{background:#fbf6e8;border:1px solid #e6d9a8;border-radius:6px;padding:.6em .9em;margin:.9em 0}
.terms dt{font-weight:bold;margin-top:.5em}
.terms dd{margin:0 0 .3em 1em;color:#333}
.recap li{margin:.2em 0}
.check{border-top:1px solid #ccc;margin-top:1.6em;padding-top:.8em}
.check .q{font-weight:bold}
.check .a{color:#333;margin-top:1.2em}
.sources{font-size:.9em;color:#444;margin-top:1.4em}
.nextup{font-size:.9em;color:#666;font-style:italic;margin-top:1.2em}
hr{border:0;border-top:1px solid #ddd;margin:1.4em 0}
""".strip()


def _chunk_html(ch: dict) -> str:
    h = [f'<h2>{_esc(ch.get("heading") or ("Idea " + str(ch.get("n",""))))}</h2>']
    if ch.get("idea"):
        h.append(f'<p class="idea">{_esc(ch["idea"])}</p>')
    if ch.get("detail"):
        h.append(_paras(ch["detail"]))
    if ch.get("example"):
        h.append(f'<div class="example"><span class="lbl">Example</span>{_paras(ch["example"])}</div>')
    pts = ch.get("points") or []
    if pts:
        h.append("<ul>" + "".join(f"<li>{_esc(p)}</li>" for p in pts) + "</ul>")
    if ch.get("key_takeaway"):
        h.append(f'<div class="takeaway"><span class="lbl">Key takeaway</span>{_esc(ch["key_takeaway"])}</div>')
    terms = ch.get("key_terms") or []
    if terms:
        dl = "".join(f"<dt>{_esc(t.get('term'))}</dt><dd>{_esc(t.get('definition'))}</dd>"
                     for t in terms if isinstance(t, dict) and t.get("term"))
        if dl:
            h.append(f'<div class="terms"><span class="lbl">Key terms</span><dl>{dl}</dl></div>')
    return "".join(h)


def _part_html(part: dict) -> str:
    subj = part.get("subject_title") or "Lesson"
    ptitle = f'Part {part.get("part")} of {part.get("total_parts")}'
    body = [f'<div class="eyebrow">{_esc(part.get("emoji",""))} {_esc(subj)} · {_esc(ptitle)}</div>',
            f'<h1>{_esc(part.get("session_title") or subj)}</h1>']
    if part.get("recap_so_far"):
        body.append(f'<div class="recap-so-far">{_esc(part["recap_so_far"])}</div>')
    for ch in (part.get("chunks") or []):
        body.append(_chunk_html(ch))
    recap = part.get("recap") or []
    if recap:
        body.append("<hr/><h2>Recap</h2><ul class='recap'>"
                    + "".join(f"<li>{_esc(r)}</li>" for r in recap) + "</ul>")
    chk = part.get("check") or {}
    if chk.get("question"):
        body.append('<div class="check"><p class="q">Check yourself: ' + _esc(chk["question"]) + "</p>")
        if chk.get("answer"):
            body.append('<p class="a"><strong>Answer:</strong> ' + _esc(chk["answer"]) + "</p>")
        body.append("</div>")
    srcs = part.get("sources") or []
    if srcs:
        items = "".join(
            f'<li>{_esc(s.get("title") or s.get("name") or s.get("url"))}'
            f'{" — " + _esc(s.get("url")) if s.get("url") else ""}</li>'
            for s in srcs if isinstance(s, dict))
        if items:
            body.append(f'<div class="sources"><strong>Sources &amp; further reading</strong><ul>{items}</ul></div>')
    if part.get("next_up"):
        body.append(f'<div class="nextup">Next up: {_esc(part["next_up"])}</div>')
    return "".join(body)


def _xhtml(title: str, inner: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>{_esc(title)}</title>'
            '<link rel="stylesheet" type="text/css" href="style.css"/>'
            '<meta charset="utf-8"/></head><body>' + inner + '</body></html>')


def build_epub(parts: list[dict], book_title: str, out_path: pathlib.Path) -> pathlib.Path:
    subj_emoji = (parts[0].get("emoji") or "🎓") if parts else "🎓"
    subj = (parts[0].get("subject_title") or "Your Course") if parts else "Your Course"
    cover = _xhtml(book_title,
                   f'<div style="text-align:center;margin-top:22%">'
                   f'<div style="font-size:3em">{_esc(subj_emoji)}</div>'
                   f'<h1 style="margin:.3em 6%">{_esc(subj)}</h1>'
                   f'<p style="color:#666">{_esc(book_title)}</p></div>')

    chapters = []   # (id, filename, title, xhtml)
    for i, p in enumerate(parts, 1):
        fn = f"part{i}.xhtml"
        ctitle = f'Part {p.get("part")} — {p.get("session_title") or ""}'.strip(" —")
        chapters.append((f"c{i}", fn, ctitle, _xhtml(ctitle, _part_html(p))))

    manifest = ['<item id="css" href="style.css" media-type="text/css"/>',
                '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>']
    spine = ['<itemref idref="cover"/>']
    navpoints = []
    for idx, (cid, fn, ctitle, _x) in enumerate(chapters, 1):
        manifest.append(f'<item id="{cid}" href="{fn}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{cid}"/>')
        navpoints.append(f'<navPoint id="nav{idx}" playOrder="{idx}"><navLabel><text>{_esc(ctitle)}</text>'
                         f'</navLabel><content src="{fn}"/></navPoint>')

    # content-based id (NOT today's date) so an unchanged course rebuilds to identical bytes — avoids a
    # fresh commit every run.
    uid = f"dailylearn-{parts[0].get('seq','') if parts else '0'}-{parts[-1].get('seq','') if parts else '0'}"
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">'
           f'<dc:title>{_esc(book_title)}</dc:title>'
           '<dc:language>en</dc:language>'
           f'<dc:identifier id="bookid">{_esc(uid)}</dc:identifier>'
           '<dc:creator>Daily Intelligence — Learn</dc:creator>'
           '</metadata>'
           f'<manifest>{"".join(manifest)}</manifest>'
           f'<spine toc="ncx">{"".join(spine)}</spine></package>')

    ncx = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{_esc(uid)}"/></head>'
           f'<docTitle><text>{_esc(book_title)}</text></docTitle>'
           f'<navMap>{"".join(navpoints)}</navMap></ncx>')

    # fixed timestamp on every entry → identical content yields byte-identical zips (no timestamp churn).
    FIXED = (1980, 1, 1, 0, 0, 0)

    def _w(z, name, data, stored=False):
        zi = zipfile.ZipInfo(name, date_time=FIXED)
        zi.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        z.writestr(zi, data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as z:
        # mimetype MUST be first and stored (uncompressed)
        _w(z, "mimetype", "application/epub+zip", stored=True)
        _w(z, "META-INF/container.xml",
           '<?xml version="1.0" encoding="utf-8"?>\n'
           '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
           '<rootfiles><rootfile full-path="OEBPS/content.opf" '
           'media-type="application/oebps-package+xml"/></rootfiles></container>')
        _w(z, "OEBPS/content.opf", opf)
        _w(z, "OEBPS/toc.ncx", ncx)
        _w(z, "OEBPS/style.css", CSS)
        _w(z, "OEBPS/cover.xhtml", cover)
        for cid, fn, ctitle, xh in chapters:
            _w(z, f"OEBPS/{fn}", xh)
    return out_path


# ---------- delivery ----------

def send_to_kindle(epub_path: pathlib.Path, title: str) -> bool:
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD and KINDLE_EMAIL):
        print("  ! missing GMAIL_ADDRESS / GMAIL_APP_PASSWORD / KINDLE_EMAIL in .env — built the EPUB "
              f"({epub_path}) but did not send.", file=sys.stderr)
        return False
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = KINDLE_EMAIL
    msg["Subject"] = title            # Amazon shows this in the delivery; EPUB's own title wins on-device
    msg.attach(MIMEText("Your latest Learn lesson is attached.", "plain"))
    part = MIMEApplication(epub_path.read_bytes(), _subtype="epub+zip")
    part.add_header("Content-Disposition", "attachment", filename=epub_path.name)
    msg.attach(part)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [KINDLE_EMAIL], msg.as_string())
    print(f"Sent '{title}' to {KINDLE_EMAIL}.")
    return True


def _load(p: pathlib.Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def main(argv: list[str]) -> int:
    force = "--force" in argv
    send_all = "--all" in argv
    cat = _load(CATALOG) or {}
    parts = sorted((cat.get("parts") or []), key=lambda p: p.get("seq") or 0)
    if not parts:
        print("No lessons in the catalog yet — nothing to build.", file=sys.stderr)
        return 0

    # 1) ALWAYS publish the whole course as a downloadable EPUB (works with zero setup: grab it and use
    #    Amazon's free "Send to Kindle" app). Lessons are already public, so this is public-safe.
    subj = parts[0].get("subject_title") or "Your Course"
    whole_title = f"{subj} — full course ({len(parts)} parts)"
    build_epub(parts, whole_title, PUBLISHED)
    print(f"Published {PUBLISHED.relative_to(ROOT)} ({len(parts)} parts, {PUBLISHED.stat().st_size//1024} KB) "
          f"— downloadable for Send-to-Kindle.")

    # 2) OPTIONALLY auto-email new parts to the Kindle (only if creds are configured in .env).
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD and KINDLE_EMAIL):
        print("  · auto-email not configured (need GMAIL_ADDRESS / GMAIL_APP_PASSWORD / KINDLE_EMAIL in "
              ".env) — the published EPUB above is ready to download + Send-to-Kindle manually.")
        return 0

    # Deliver ONE COMPLETE SUBJECT per calendar day — ALL its parts together as a single document (the
    # reader wants whole lessons, not one session at a time). A subject is "ready" only once EVERY one of
    # its parts is authored; a partial subject waits. Sent subjects are tracked by slug so none repeats.
    #   normal run : the next unsent complete subject (at most one per calendar day)
    #   --force    : send the newest complete subject right now (bypasses the daily gate)
    #   --all      : resend every complete subject (each as its own document)
    today = dt.date.today().isoformat()
    st = _load(STATE) or {}
    sent = set(st.get("sent_subjects") or [])

    groups = {}                                  # subject_slug -> [parts], in catalog (seq) order
    for p in parts:
        groups.setdefault(p.get("subject_slug"), []).append(p)
    complete = [(slug, sorted(ps, key=lambda x: x.get("part") or 0))
                for slug, ps in groups.items()
                if ps and len({p.get("part") for p in ps}) >= (ps[0].get("total_parts") or len(ps))]

    if send_all:
        to_send = complete
    elif force:
        unsent = [g for g in complete if g[0] not in sent]
        to_send = [(unsent or complete)[-1]] if complete else []
    else:
        if st.get("last_sent_date") == today:
            print("Kindle already received today's subject — one complete lesson per day.")
            return 0
        to_send = [g for g in complete if g[0] not in sent][:1]   # earliest unsent complete subject
    if not to_send:
        print("No new complete subject ready to e-mail (a partial subject waits for all its parts).")
        return 0

    ok_any = False
    for slug, ps in to_send:
        stitle = ps[0].get("subject_title") or "Lesson"
        title = f'{ps[0].get("emoji","")} {stitle} — complete ({len(ps)} parts)'.strip()
        epub = build_epub(ps, title, OUT_DIR / "kindle-learn.epub")
        print(f"Built '{stitle}' — {len(ps)} parts, {epub.stat().st_size//1024} KB")
        if send_to_kindle(epub, title):
            sent.add(slug); ok_any = True
    if ok_any:
        STATE.write_text(json.dumps({
            "sent_subjects": sorted(sent),
            "last_seq": max((p.get("seq") or 0 for p in parts if p.get("subject_slug") in sent),
                            default=int(st.get("last_seq") or 0)),
            "last_sent_date": today,
            "sent_at": dt.datetime.now().isoformat(timespec="seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
