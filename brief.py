"""Claude side: fetch today's fixtures and generate per-match briefings.

The 2026 World Cup is live and postdates the model's training cutoff, so every
fact comes from the server-side web_search / web_fetch tools, never model memory.
"""
from __future__ import annotations
import json, re
import anthropic

MODEL = "claude-opus-4-8"
TOOLS = [
    {"type": "web_search_20260209", "name": "web_search"},
    {"type": "web_fetch_20260209", "name": "web_fetch"},
]
_client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env


def _run(prompt: str, max_tokens: int = 4000) -> str:
    """Single-prompt call that lets Claude drive web_search/web_fetch server-side."""
    messages = [{"role": "user", "content": prompt}]
    text = ""
    for _ in range(8):  # bound the server-tool (pause_turn) loop
        resp = _client.messages.create(
            model=MODEL, max_tokens=max_tokens, tools=TOOLS, messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    return text.strip()


def get_today_fixtures(today_str: str) -> list[dict]:
    """Return [{home, away, kickoff_utc}] for today's WC2026 matches (UTC ISO)."""
    prompt = (
        f"Today is {today_str} in the America/Toronto timezone. Use web search to find "
        "EVERY FIFA World Cup 2026 match scheduled for today. The tournament runs "
        "June 11 - July 19, 2026 across USA/Canada/Mexico. Cross-check a reliable source "
        "(official FIFA schedule or a major outlet) for accurate kickoff times.\n\n"
        "Return ONLY a JSON array (no prose, no code fences). Each element:\n"
        '{"home": "<team>", "away": "<team>", "kickoff_utc": "YYYY-MM-DDTHH:MM:SSZ"}\n'
        "kickoff_utc must be the exact UTC instant of kickoff. If there are no matches "
        "today, return []."
    )
    raw = _run(prompt, max_tokens=1500)
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def generate_briefing(home: str, away: str, kickoff_local: str) -> str:
    """Produce the Telegram-ready briefing text for one match."""
    return _run(
        f"Create a FIFA World Cup 2026 pre-match briefing for {home} vs {away} "
        f"(kickoff {kickoff_local} ET). The tournament is in progress; use live web "
        "data only, never prior knowledge.\n\n"
        "Gather:\n"
        "1. Each team's FIFA ranking ONLY from the official per-country FIFA page "
        "https://inside.fifa.com/fifa-world-ranking/<FIFA_CODE>?gender=men (3-letter "
        "codes, e.g. MEX, KOR, BRA; web-search the code if unsure). web_fetch that page "
        'and read the "Current rank" value. Never use news/power-ranking sites for the '
        'ranking. If it cannot be read, write "ranking unavailable".\n'
        "2. Top 2-3 players to watch on each team.\n"
        "3. Which players on each team have ALREADY SCORED in this 2026 World Cup so far "
        "(and how many). If it's a team's first match, say so.\n"
        "4. Head-to-head history (all-time record + notable past World Cup meetings).\n\n"
        "Then output ONLY the final Telegram message (plain text + emojis, NO markdown "
        "characters), under 3500 chars, with these lines:\n"
        f"⏰ Today {kickoff_local} ET: {home} vs {away}\n"
        "\U0001f4ca FIFA Ranking: <home> #X · <away> #Y\n"
        "⭐ Watch out for: ...\n"
        "⚽ Scored so far this World Cup: ...\n"
        "\U0001f91d Head-to-head: ...\n"
        "\U0001f525 Why it's worth watching: <1-3 sentences>\n\n"
        "Output the message text only — no preamble, no explanation.",
        max_tokens=4000,
    )
