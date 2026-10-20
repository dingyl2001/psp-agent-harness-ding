# dingyl2001-telegram

A Telegram MCP server: message the agent from your phone. Week 3 of
UCLA's AI in Research (EPSS 254).

## What it is

Two tools, in `server.py` (a `uv` script, no project setup needed), both
scoped to exactly one Telegram chat:

- `send_message(text)` — send a message to the user's chat, split
  automatically over Telegram's 4,096-character limit.
- `wait_for_messages(seconds=30)` — long-poll (`getUpdates`) for up to
  `seconds` for a new message from that chat; returns new text, or "No
  new messages." Messages from any other chat are dropped and logged to
  stderr. On startup, any backlog of old updates is skipped so they don't
  replay as fresh orders.

Nothing on this computer is reachable from the internet: the bot polls
Telegram, Telegram never connects to us.

`skills/telegram/SKILL.md` tells the agent replies may be read on a
phone (keep them short), never to send secrets, and that
`wait_for_messages` is normally the harness's job, not the model's.

## Environment variables

Set these in `.env` in the harness/project folder (never commit `.env`):

```
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

Create the bot with [@BotFather](https://t.me/BotFather) (`/newbot`).
Find your chat id by sending the bot a message, then:

```
set -a; . ./.env; set +a
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" \
  | python3 -c "import json,sys; [print(u['message']['chat']['id'], u['message']['from'].get('username')) for u in json.load(sys.stdin)['result'] if 'message' in u]"
```

The token is a password: anyone with it can read and send as the bot.
If it ever leaks, `/revoke` in BotFather.

## Load it

Claude Code:
```
set -a; . ./.env; set +a
claude --plugin-dir plugins/dingyl2001-telegram
```

Codex: `codex mcp add dingyl2001-telegram --env TELEGRAM_BOT_TOKEN=... --env TELEGRAM_CHAT_ID=... -- uv run --script /absolute/path/to/server.py`
(check `codex mcp add --help` for current flags).

## Check it works

Ask the agent to send "hello from Claude Code" to Telegram and confirm
it arrives on your phone.
