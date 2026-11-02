"""Structured sport data: the F1 calendar, last result and standings (Jolpica, the Ergast successor).

Cricket comes through the RSS feeds and beats; there's no reliable free cricket API.
"""
from __future__ import annotations

import requests

from . import sources


def _get(path: str) -> dict:
    r = requests.get(f"{sources.JOLPICA}/{path}", timeout=15, headers={"User-Agent": sources.API_AGENT})
    r.raise_for_status()
    return r.json().get("MRData") or {}


def f1() -> tuple[dict, dict]:
    """Returns ({last_race, next_race, standings_top5, schedule}, health). Never raises."""
    out: dict = {"last_race": None, "next_race": None, "standings": [], "schedule": []}
    health = {"name": "Jolpica F1", "kind": "sport", "ok": False, "items": 0, "error": None}
    try:
        last = (_get("current/last/results.json").get("RaceTable") or {}).get("Races") or []
        if last:
            race = last[0]
            out["last_race"] = {
                "name": race.get("raceName"), "date": race.get("date"), "round": race.get("round"),
                "podium": [f"{r['Driver']['givenName']} {r['Driver']['familyName']} ({r['Constructor']['name']})"
                           for r in (race.get("Results") or [])[:3]],
            }
        sched = (_get("current.json").get("RaceTable") or {}).get("Races") or []
        out["schedule"] = [{"round": r.get("round"), "name": r.get("raceName"), "date": r.get("date"),
                            "time_utc": r.get("time")} for r in sched]
        last_round = int((out["last_race"] or {}).get("round") or 0)
        nxt = next((r for r in out["schedule"] if int(r["round"] or 0) > last_round), None)
        out["next_race"] = nxt
        st = ((_get("current/driverStandings.json").get("StandingsTable") or {}).get("StandingsLists") or [{}])[0]
        out["standings"] = [{"pos": d.get("position"), "driver": f"{d['Driver']['givenName']} {d['Driver']['familyName']}",
                             "team": (d.get("Constructors") or [{}])[0].get("name"), "points": d.get("points")}
                            for d in (st.get("DriverStandings") or [])[:5]]
        health.update(ok=True, items=len(out["schedule"]))
    except Exception as e:  # noqa: BLE001
        health["error"] = f"{type(e).__name__}: {e}"[:200]
    return out, health
