"""Tiny JSON state store.

Backed by a **private GitHub Gist** when GIST_ID + GIST_TOKEN are set, so the
public code repo never contains subscriber data. Falls back to local files under
state/ when those env vars are absent (handy for local testing).

Files are independent (subscribers.json, sent.json, goals.json, fixtures.json) and
a PATCH updates only the named file — so the briefing workflow (writes subscribers/
sent/fixtures) and the live workflow (writes goals) never clobber each other.
"""
from __future__ import annotations
import json, os, urllib.request
from pathlib import Path

GIST_ID = os.environ.get("GIST_ID")
GIST_TOKEN = os.environ.get("GIST_TOKEN")
_LOCAL = Path(__file__).parent / "state"
_HDRS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "fifa4u-bot",
}


def _gist_files() -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        headers={**_HDRS, "Authorization": f"Bearer {GIST_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("files", {})


def get(name: str, default):
    if GIST_ID and GIST_TOKEN:
        f = _gist_files().get(name)
        if not f or not f.get("content"):
            return default
        try:
            return json.loads(f["content"])
        except json.JSONDecodeError:
            return default
    try:
        return json.loads((_LOCAL / name).read_text())
    except FileNotFoundError:
        return default


def put(name: str, obj) -> None:
    content = json.dumps(obj, indent=2, ensure_ascii=False)
    if GIST_ID and GIST_TOKEN:
        body = json.dumps({"files": {name: {"content": content}}}).encode()
        req = urllib.request.Request(
            f"https://api.github.com/gists/{GIST_ID}", data=body, method="PATCH",
            headers={**_HDRS, "Authorization": f"Bearer {GIST_TOKEN}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30):
            return
    _LOCAL.mkdir(exist_ok=True)
    (_LOCAL / name).write_text(content)
