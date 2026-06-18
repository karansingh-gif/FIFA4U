"""Briefing poller — run every ~15 min by GitHub Actions during match hours.

Each run: capture + welcome new subscribers, make sure today's fixtures are known,
and for any match kicking off in ~30 min that hasn't been sent, generate + broadcast
its briefing. All state lives in the private Gist via store.py.
"""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import store
import tg
import brief

ET = ZoneInfo("America/Toronto")
# Send when kickoff is this many minutes away. Window is deliberately wide (most
# of the hour before kickoff) so GitHub's best-effort cron — which can run late or
# skip — still catches the match; dedup via sent.json prevents repeats.
LO_MIN, HI_MIN = 2, 45
SEASON_START = "2026-06-11"
SEASON_END = "2026-07-19"


def fixtures_for_today(today: str) -> list[dict]:
    fx = store.get("fixtures.json", {})
    if fx.get("date") == today:
        return fx.get("matches", [])
    matches = brief.get_today_fixtures(today)
    store.put("fixtures.json", {"date": today, "matches": matches})
    return matches


def main() -> None:
    now = datetime.now(timezone.utc)
    today = now.astimezone(ET).date().isoformat()

    subs = store.get("subscribers.json", {})
    new = tg.sync_new(subs)
    store.put("subscribers.json", subs)
    print(f"subscribers: {len(subs)} (+{len(new)} new)")

    if not (SEASON_START <= today <= SEASON_END):
        print(f"{today}: outside the tournament window — nothing to do.")
        return

    sent = store.get("sent.json", {"date": today, "sent": []})
    if sent.get("date") != today:
        sent = {"date": today, "sent": []}

    matches = fixtures_for_today(today)
    print(f"{today}: {len(matches)} match(es)")

    for m in matches:
        home, away, ko = m.get("home"), m.get("away"), m.get("kickoff_utc")
        if not (home and away and ko):
            continue
        key = f"{home}|{away}|{ko}"
        if key in sent["sent"]:
            continue
        try:
            kickoff = datetime.fromisoformat(ko.replace("Z", "+00:00"))
        except ValueError:
            continue
        mins = (kickoff - now).total_seconds() / 60
        if not (LO_MIN <= mins <= HI_MIN):
            continue
        local = kickoff.astimezone(ET).strftime("%-I:%M %p")
        print(f"due ({mins:.0f} min): {home} vs {away}")
        text = brief.generate_briefing(home, away, local)
        ok, fail, blocked = tg.broadcast(subs, text)
        print(f"  broadcast -> {ok} ok, {fail} failed")
        if blocked:
            for b in blocked:
                subs.pop(b, None)
            store.put("subscribers.json", subs)
        sent["sent"].append(key)
        store.put("sent.json", sent)


if __name__ == "__main__":
    main()
