"""Telegram side: greet first-timers, broadcast to all subscribers.

The bot token comes from TELEGRAM_BOT_TOKEN. The subscriber dict ({chat_id: name})
is owned by the caller and persisted via store.py — these helpers never read or
write state directly, so the briefing and live workflows can't race on it.
"""
from __future__ import annotations
import os, json, urllib.request, urllib.parse

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

WELCOME = (
    "⚽\U0001f389 Welcome to FIFA4U — your World Cup 2026 hype buddy!\n"
    "I'll drop a match briefing ~30 min before every kickoff and ping you the "
    "moment anyone scores. Game on! \U0001f3c6"
)


def _api(method: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def sync_new(subs: dict) -> list[str]:
    """Add any new chat_ids from getUpdates into `subs` (in place) and welcome
    each first-timer once. Returns the list of newly added ids.

    No offset is advanced: re-reading the same ~24h buffer is idempotent, so a
    skipped run never loses a subscriber.
    """
    new_ids: list[str] = []
    for u in _api("getUpdates", {"timeout": 0}).get("result", []):
        chat = (u.get("message") or u.get("my_chat_member") or {}).get("chat", {})
        cid = chat.get("id")
        if cid is None:
            continue
        cid = str(cid)
        if cid not in subs:
            new_ids.append(cid)
        subs[cid] = chat.get("username") or chat.get("first_name") or "?"
    for cid in new_ids:
        _api("sendMessage", {"chat_id": cid, "text": WELCOME,
                             "disable_web_page_preview": "true"})
    return new_ids


def broadcast(subs: dict, text: str) -> tuple[int, int, list[str]]:
    """Send `text` to every subscriber. Returns (ok, fail, blocked_ids).

    Pure send — does not mutate/persist `subs`. `blocked_ids` are chats that
    blocked or deleted the bot; the caller decides whether to prune them.
    """
    ok = fail = 0
    blocked: list[str] = []
    for cid in list(subs):
        r = _api("sendMessage", {"chat_id": cid, "text": text,
                                 "disable_web_page_preview": "true"})
        if r.get("ok"):
            ok += 1
        else:
            fail += 1
            desc = (r.get("description") or "").lower()
            if r.get("error_code") == 403 or "chat not found" in desc:
                blocked.append(cid)
    return ok, fail, blocked
