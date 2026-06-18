# FIFA World Cup 2026 Telegram bot

Sends pre-match briefings **and live goal alerts** to everyone who has started
**@FIFA4U_bot** — running entirely on GitHub Actions, no server.

## Features
- **Welcome** — first-timers get a quick peppy intro.
- **Match briefing** ~30 min before each kickoff: FIFA rankings (official source), top players, current-tournament scorers, head-to-head, and why it's worth watching (Claude + live web search).
- **Live goal alerts** — every goal, with scorer, minute and running score, in near-real-time from ESPN's public scoreboard.

## Architecture
- `poll.yml` (every 15 min, match hours) → `run.py`: welcomes new subscribers, fetches today's fixtures once, and broadcasts a briefing for any match 10–40 min from kickoff. Briefings use the Claude API (`brief.py`) with the server-side web-search/fetch tools.
- `live.yml` (match hours) → `live.py`: watches ESPN every ~60s for up to ~9 min while a match is live, broadcasting each new goal. Overlapping runs (serialized by `concurrency`) give continuous coverage. No Anthropic key needed — ESPN is keyless.
- **State** (subscribers, sent-markers, goal-dedup, fixtures) lives in a **private GitHub Gist** via `store.py`, so this **public** repo holds zero personal data. The two workflows write different gist files, so they never race.

## One-time setup

This repo is **public** (required for unlimited free Actions minutes to run the live
watcher). Personal data is therefore kept out of it — in a private Gist.

1. **Create a private Gist** at https://gist.github.com — set it to **secret**, filename `subscribers.json`, content `{}` (or seed it with known subscribers). Note the Gist ID from its URL (`gist.github.com/<user>/<THIS_ID>`).
2. **Create a fine-grained token** for the Gist at https://github.com/settings/tokens — a classic token with the **`gist`** scope is simplest. Copy it.
3. In the repo, **Settings → Secrets and variables → Actions**, add four secrets:
   - `ANTHROPIC_API_KEY` — your Anthropic API key (briefings)
   - `TELEGRAM_BOT_TOKEN` — the @FIFA4U_bot token
   - `GIST_ID` — the Gist ID from step 1
   - `GIST_TOKEN` — the token from step 2
4. Make the repo **public**: **Settings → General → Danger Zone → Change visibility → Public**.
5. Test: **Actions → WC2026 briefing poll → Run workflow**, and **WC2026 live goals → Run workflow**.

## Sharing
Share **@FIFA4U_bot**. New people who tap **Start** are captured within ~15 min,
get the welcome message, and receive every briefing and goal alert thereafter.

## Notes
- Telegram has no "list all bot users" API and `getUpdates` only retains ~24h, so the durable list in the Gist (`subscribers.json`) is the source of truth.
- Actions cron is best-effort (UTC); the wide briefing window and overlapping live runs absorb that. Goal alerts arrive within ~1–2 min of the real thing.
- FIFA rankings come only from `inside.fifa.com/fifa-world-ranking/<CODE>?gender=men`. Live scores/goals come from ESPN's public `site.api.espn.com` scoreboard.
- Local dev: with `GIST_*` unset, `store.py` falls back to JSON files under `state/` (git-ignored).
