#!/usr/bin/env python3
"""Resolve news lead-images on the MAC (which has real network) into the committed image cache.

The cloud sandbox that publishes the hourly news can't reach arbitrary article hosts to read <meta og:image>,
so it can't find pictures on its own. This laptop can — so every hourly tick we fetch og:image for the
current stories' sources into dashboard/image-cache.json (a plain {url: image_url} map, no secrets). The
cloud's build_reels then attaches those images with zero network. Fast + idempotent: only new URLs fetch.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "routine"))
import media   # noqa: E402


def main() -> int:
    total, new = media.resolve_all(ROOT / "dashboard" / "world.json", cap=40)
    print(f"image-cache: {total} urls cached ({new} newly resolved this run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
