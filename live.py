"""Live goal watcher — run during match hours by GitHub Actions.

Polls ESPN's public World Cup scoreboard (no API key) every ~60s and broadcasts
each new goal (scorer, minute, running score) to all subscribers. Dedupes against
goals.json in the private Gist. The job stays alive ~9 min while any match is live,
then exits; the next scheduled run (overlapping, serialized by `concurrency`) keeps
coverage continuous.
"""
from __future__ import annotations
import json, time, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import store
import tg

ET = ZoneInfo("America/Toronto")
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/soccer/"
              "fifa.world/scoreboard?dates={date}")
WATCH_SECONDS = 9 * 60   # stay alive up to ~9 min per job (cron re-launches)
POLL_SECONDS = 60


def _fetch(date_str: str) -> dict:
    req = urllib.request.Request(SCOREBOARD.format(date=date_str),
                                 headers={"User-Agent": "fifa4u-bot"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _goals(ev: dict) -> list[tuple[str, str]]:
    """Return [(signature, message)] for every goal in an event, in order.

    The running score is counted goal-by-goal (not read from the final tally), so
    each alert shows the score as it stood the moment that goal went in.
    """
    comp = ev["competitions"][0]
    by_id = {c["team"]["id"]: c for c in comp["competitors"]}
    home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
    away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
    hname, aname = home["team"]["displayName"], away["team"]["displayName"]
    home_id, away_id = home["team"]["id"], away["team"]["id"]
    hs = as_ = 0
    out: list[tuple[str, str]] = []
    for d in comp.get("details", []):
        if not d.get("scoringPlay"):
            continue
        tid = d.get("team", {}).get("id")
        if tid == home_id:      # own goals are already attributed to the benefiting team
            hs += 1
        elif tid == away_id:
            as_ += 1
        clock = d.get("clock", {}).get("displayValue", "")
        scorer = (d.get("athletesInvolved") or [{}])[0].get("displayName", "Unknown")
        tag = " (pen)" if d.get("penaltyKick") else (" (OG)" if d.get("ownGoal") else "")
        team = by_id.get(tid, {}).get("team", {}).get("displayName", "")
        sig = f'{ev["id"]}|{clock}|{scorer}|{tid}'
        msg = (f"⚽ GOAL{tag} — {scorer} {clock} ({team})\n"
               f"{hname} {hs}-{as_} {aname}")
        out.append((sig, msg))
    return out


def sweep(subs: dict, goals: dict) -> bool:
    """One pass over today's scoreboard. Returns True if any match is live."""
    announced = set(goals.get("announced", []))
    any_live = False
    try:
        data = _fetch(datetime.now(ET).strftime("%Y%m%d"))
    except Exception as e:  # noqa: BLE001 - never let one bad fetch kill the loop
        print("espn fetch error:", e)
        return False
    for ev in data.get("events", []):
        state = ev.get("status", {}).get("type", {}).get("state")
        if state == "in":
            any_live = True
        elif state != "post":
            continue
        seen_event = any(s.startswith(ev["id"] + "|") for s in announced)
        # Don't cold-announce every goal of a match that was already finished when
        # we first looked — only report ongoing matches and the final goals of ones
        # we were already watching.
        if state == "post" and not seen_event:
            continue
        for sig, msg in _goals(ev):
            if sig in announced:
                continue
            announced.add(sig)
            ok, _, _ = tg.broadcast(subs, msg)
            print(f"announced -> {ok} ok: {msg.splitlines()[0]}")
    goals["announced"] = sorted(announced)
    return any_live


def main() -> None:
    today = datetime.now(ET).date().isoformat()
    subs = store.get("subscribers.json", {})
    goals = store.get("goals.json", {"date": today, "announced": []})
    if goals.get("date") != today:
        goals = {"date": today, "announced": []}

    deadline = time.time() + WATCH_SECONDS
    while True:
        live = sweep(subs, goals)
        store.put("goals.json", goals)
        if not live or time.time() >= deadline:
            break
        time.sleep(POLL_SECONDS)
    print(f"done; {len(goals['announced'])} goals announced today so far")


if __name__ == "__main__":
    main()
