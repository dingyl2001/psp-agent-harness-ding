#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp", "httpx"]
# ///
"""Telegram MCP server: send a message, and long-poll for new ones, from
exactly one configured chat. Talks to the Telegram Bot API by polling
(getUpdates), so nothing on this computer is reachable from the internet
-- the bot reaches out to Telegram, never the other way around.

Config comes from environment variables (set in .mcp.json, which reads
them from .env):
  TELEGRAM_BOT_TOKEN   the bot token from @BotFather
  TELEGRAM_CHAT_ID     the only chat this server will send to or accept
                        messages from
"""
import logging
import os
import sys

import httpx

from mcp.server import MCPServer

log = logging.getLogger("telegram-plugin")
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stderr))
log.propagate = False  # don't configure the root logger: that would also
# turn on INFO-level logging in libraries like httpx, which logs full
# request URLs -- and the Telegram Bot API puts the token in the URL.

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
MAX_MESSAGE_CHARS = 4096
MAX_POLL_SECONDS = 50

_offset = None  # next update_id to fetch; set by _skip_backlog() at startup


def _require_config():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set. Check .env "
            "in the harness folder, and that .mcp.json passes them through."
        )


def _skip_backlog():
    """Fetch and discard any pending updates so messages sent while this
    server was off don't replay as fresh orders when it starts.
    """
    global _offset
    if not TELEGRAM_BOT_TOKEN:
        _offset = 0
        return
    try:
        resp = httpx.get(f"{API_BASE}/getUpdates", params={"timeout": 0}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("result", [])
        _offset = (results[-1]["update_id"] + 1) if results else 0
        log.info("Startup: skipped %d backlog update(s)", len(results))
    except Exception as e:
        log.warning("Could not fetch backlog on startup: %s", e)
        _offset = 0


mcp = MCPServer("telegram", log_level="WARNING")  # the SDK's own default
# ("INFO") configures the root logger, which would also turn on httpx's
# INFO-level request logging -- and the Telegram Bot API puts the token
# in the request URL
_skip_backlog()


@mcp.tool()
def send_message(text: str) -> str:
    """Send a text message to the user's Telegram chat.

    Args:
        text: the message to send. Split into multiple Telegram messages
            automatically if over 4,096 characters.
    """
    _require_config()
    chunks = [text[i:i + MAX_MESSAGE_CHARS] for i in range(0, len(text), MAX_MESSAGE_CHARS)]
    if not chunks:
        chunks = [""]

    for i, chunk in enumerate(chunks):
        try:
            resp = httpx.post(
                f"{API_BASE}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk},
                timeout=15,
            )
        except httpx.RequestError as e:
            return f"Send failed after {i} of {len(chunks)} part(s): {e}"
        if resp.status_code != 200:
            return f"Send failed after {i} of {len(chunks)} part(s): HTTP {resp.status_code} {resp.text}"

    return f"Sent ({len(chunks)} part{'s' if len(chunks) != 1 else ''})."


@mcp.tool()
def wait_for_messages(seconds: int = 30) -> str:
    """Long-poll for new Telegram messages from the user's configured
    chat, for up to `seconds` (capped at 50). Returns the new message
    text(s), newest last, or "No new messages." if none arrived in time.
    Each message is returned exactly once.

    Args:
        seconds: how long to wait for a new message, in seconds (default
            30, max 50).
    """
    _require_config()
    global _offset
    wait = max(1, min(seconds, MAX_POLL_SECONDS))

    try:
        resp = httpx.get(
            f"{API_BASE}/getUpdates",
            params={"timeout": wait, "offset": _offset},
            timeout=wait + 10,
        )
        resp.raise_for_status()
    except httpx.RequestError as e:
        return f"Poll failed: {e}"
    results = resp.json().get("result", [])

    texts = []
    for update in results:
        _offset = update["update_id"] + 1
        message = update.get("message")
        if not message:
            continue
        chat_id = str(message.get("chat", {}).get("id", ""))
        if chat_id != str(TELEGRAM_CHAT_ID):
            log.info("Dropped message from chat id %s (not the configured chat)", chat_id)
            continue
        text = message.get("text")
        if text:
            texts.append(text)

    return "\n".join(texts) if texts else "No new messages."


if __name__ == "__main__":
    mcp.run()
