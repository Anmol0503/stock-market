"""Free-licence photos for reel backdrops and player cards, from Wikipedia / Wikimedia Commons.

The writer names a Wikipedia article per scene (`image`: "Sheikh Hasina", "Abu Dhabi"). We take the article's
lead image, or if that's a logo, flag or seal (usually SVG), the first large photo used in the article. Only
files whose licence is Public domain, CC0, CC BY or CC BY-SA are used, never fair-use or unclear ones, and
every frame that shows one carries a credit line ("Photo: <artist>, <licence>, Wikimedia Commons").

Anything that goes wrong (network, odd metadata, a missing article) just returns None: the frame falls back
to a designed backdrop. A failed lookup must never fail a reel.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

API = "https://en.wikipedia.org/w/api.php"
# Wikimedia's API policy asks for a descriptive User-Agent with a contact URL.
UA = "TheBriefingReels/1.0 (https://github.com/Anmol0503/stock-market; automated news explainer videos)"
TIMEOUT = 12

# Public domain, CC0, CC BY, CC BY-SA, plus the two government attribution licences Commons hosts for official
# portraits (GODL-India for Indian government photos, the UK Open Government Licence).
_FREE = re.compile(r"^\s*(public\s+domain|pd([- ]|$)|cc0|cc[- ]?by(-sa)?([- ]\d(\.\d)?)?(\s|$)|godl-india|ogl\b)", re.I)
_NOT_A_PHOTO = re.compile(r"logo|flag|seal|emblem|coat[_ ]of[_ ]arms|icon|signature|map|locator|symbol|banner|"
                          r"wordmark|diagram|chart|graph", re.I)


@dataclass
class Photo:
    path: pathlib.Path
    credit: str          # "Photo: DelwarHossain, CC BY-SA 4.0, Wikimedia Commons"
    width: int
    height: int


def _strip(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return " ".join(html.unescape(s).split())


def licence_ok(meta: dict) -> bool:
    """Only clearly free licences. Fair use / non-free / missing licence -> False."""
    val = lambda k: str((meta.get(k) or {}).get("value") or "")    # noqa: E731
    if val("NonFree").strip().lower() in ("true", "1", "yes"):
        return False
    short = val("LicenseShortName") or val("License")
    if not short or re.search(r"fair\s*use|non-?free|all rights reserved", short, re.I):
        return False
    return bool(_FREE.match(short)) or short.strip().lower() in ("cc-by-sa-4.0", "cc-by-4.0", "cc-by-sa-3.0",
                                                                 "cc-by-3.0", "cc-by-2.0", "cc-by-sa-2.0", "pd", "cc0")


def credit(meta: dict) -> str:
    val = lambda k: _strip(str((meta.get(k) or {}).get("value") or ""))   # noqa: E731
    artist = val("Artist") or "Unknown"
    artist = artist[:48] + ("…" if len(artist) > 48 else "")
    lic = val("LicenseShortName") or "Public domain"
    return f"Photo: {artist}, {lic}, Wikimedia Commons"


def _http_json(params: dict) -> dict:
    q = urllib.parse.urlencode({"format": "json", "formatversion": 2, **params})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


class Resolver:
    """Resolves article titles to local photo files. One per reel render; results are cached by title."""

    def __init__(self, cache_dir: pathlib.Path, *, fetch: Callable[[dict], dict] = _http_json,
                 download: Callable[[str], bytes] = _http_get, width: int = 1600) -> None:
        self.dir = pathlib.Path(cache_dir)
        self.fetch, self.download, self.width = fetch, download, width
        self._cache: dict[tuple[str, int], Photo | None] = {}

    def resolve(self, title: str, *, min_width: int = 400) -> Photo | None:
        """A photo for this article, or None. Small ones (under ~1000 px) are shown framed, not full-bleed."""
        title = " ".join(str(title or "").split())[:200]
        if not title:
            return None
        key = (title.lower(), min_width)
        if key not in self._cache:
            try:
                self._cache[key] = self._resolve(title, min_width)
            except Exception:  # noqa: BLE001 - network/JSON/anything: fall back to a designed backdrop
                self._cache[key] = None
        return self._cache[key]

    # ------------------------------------------------------------------ internals
    def _resolve(self, title: str, min_width: int) -> Photo | None:
        d = self.fetch({"action": "query", "titles": title, "redirects": 1, "prop": "pageimages|pageprops",
                        "piprop": "name", "pilicense": "free"})
        pages = (d.get("query") or {}).get("pages") or []
        if not pages or pages[0].get("missing") or "disambiguation" in (pages[0].get("pageprops") or {}):
            return None
        page = pages[0]
        lead = page.get("pageimage")
        if lead and not _NOT_A_PHOTO.search(lead) and not lead.lower().endswith(".svg"):
            ph = self._file(lead, min_width)
            if ph:
                return ph
        # The lead image is a logo/flag/seal (or unusable): try the photos used in the article, in the order
        # they appear (the first ones are usually the infobox/top images, the most relevant).
        d = self.fetch({"action": "parse", "page": page.get("title") or title, "prop": "images", "redirects": 1})
        names = [n for n in ((d.get("parse") or {}).get("images") or [])
                 if n.lower().endswith((".jpg", ".jpeg")) and not _NOT_A_PHOTO.search(n)][:12]
        if not names:
            return None
        d = self.fetch({"action": "query", "titles": "|".join(f"File:{n}" for n in names), "prop": "imageinfo",
                        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": self.width})
        info = {(p.get("title") or "").split(":", 1)[-1].replace(" ", "_"): (p.get("imageinfo") or [{}])[0]
                for p in (d.get("query") or {}).get("pages") or []}
        for n in names:
            ph = self._from_info(n, info.get(n.replace(" ", "_"), {}), max(min_width, 1000))
            if ph:
                return ph
        return None

    def _file(self, name: str, min_width: int) -> Photo | None:
        d = self.fetch({"action": "query", "titles": f"File:{name}", "prop": "imageinfo",
                        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": self.width})
        pages = (d.get("query") or {}).get("pages") or []
        info = ((pages[0].get("imageinfo") or [{}]) if pages else [{}])[0]
        return self._from_info(name, info, min_width)

    def _from_info(self, name: str, info: dict, min_width: int) -> Photo | None:
        if info.get("mime") != "image/jpeg":                    # photos; PNG/SVG/WebP are mostly charts and logos
            return None
        w, h = int(info.get("width") or 0), int(info.get("height") or 0)
        if w < min_width or h < w * 0.5 or not licence_ok(info.get("extmetadata") or {}):
            return None
        url = info.get("thumburl") or info.get("url")
        if not url or not str(url).startswith("https://"):
            return None
        data = self.download(url)
        if len(data) < 5000:
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / (re.sub(r"[^A-Za-z0-9]+", "_", name)[:80] + ".jpg")
        path.write_bytes(data)
        tw, th = int(info.get("thumbwidth") or w), int(info.get("thumbheight") or h)
        return Photo(path=path, credit=credit(info.get("extmetadata") or {}), width=tw, height=th)
