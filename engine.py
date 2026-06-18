"""Always-on engine.

GitHub's built-in cron proved unreliable (it skipped almost every scheduled slot),
so instead of depending on it we run ONE long GitHub Actions job that loops on its
own: checking ESPN for goals every ~60s and running the briefing poller every
~5 min, during match hours. engine.yml re-launches this job before it times out, so
it runs continuously from a single manual start. All sends are deduped via the Gist,
so this coexists safely with the older poll/live workflows.
"""
from __future__ import annotations
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import store
import live
import run as briefing

ET = ZoneInfo("America/Toronto")
RUN_SECONDS = 5 * 3600 + 18 * 60   # ~5h18m — comfortably under the 6h job limit
GOAL_EVERY = 60                    # poll ESPN for goals this often (seconds)
BRIEF_EVERY = 5 * 60               # run the briefing poller this often (seconds)


def _active(now_et: datetime) -> bool:
    """True during match hours: 11:00 AM - 12:59 AM ET."""
    return now_et.hour >= 11 or now_et.hour == 0


def main() -> None:
    deadline = time.time() + RUN_SECONDS
    last_brief = 0.0
    goals_day = None
    goals: dict = {}
    while time.time() < deadline:
        now = datetime.now(ET)
        if _active(now):
            today = now.date().isoformat()
            if goals_day != today:
                goals = store.get("goals.json", {"date": today, "announced": []})
                if goals.get("date") != today:
                    goals = {"date": today, "announced": []}
                goals_day = today
            # Goals — every loop (~60s)
            try:
                subs = store.get("subscribers.json", {})
                live.sweep(subs, goals)
                store.put("goals.json", goals)
            except Exception as e:  # noqa: BLE001 - never let one error kill the loop
                print("goal sweep error:", e)
            # Briefings — every ~5 min (handles subscriber sync + welcomes too)
            if time.time() - last_brief >= BRIEF_EVERY:
                try:
                    briefing.main()
                except Exception as e:  # noqa: BLE001
                    print("briefing error:", e)
                last_brief = time.time()
        time.sleep(GOAL_EVERY)
    print("engine cycle complete — engine.yml will re-launch the next one")


if __name__ == "__main__":
    main()
