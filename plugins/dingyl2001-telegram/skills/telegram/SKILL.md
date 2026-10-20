---
name: telegram
description: Use when the user is talking through Telegram (replies are read on a phone), or wants a message sent to their Telegram chat. Covers the send_message and wait_for_messages tools.
---

# Telegram

The user may be reading your replies on their phone. Keep them short and
plain — no long walls of text, no heavy Markdown that renders oddly in a
chat bubble.

- For a long-running task, send a short one-line progress update rather
  than going silent for a long time.
- Never send secrets, tokens, passwords or whole files over Telegram.
- `send_message(text)` always goes to the user's own configured chat —
  there is no way to send anywhere else.
- `wait_for_messages(seconds=30)` is normally called by the harness itself
  in Telegram mode, not by you — don't call it unless you've specifically
  been asked to check for a new message right now.
