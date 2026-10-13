# psp-agent-harness-ding

A minimal agent harness built for UCLA's "AI in Research" class (EPSS 254,
Fall 2026), week 2: an agent loop with exactly one tool, `bash`, and a
local web chat interface.

It talks to any OpenAI-compatible Chat Completions API (configured via
environment variables), runs the agent loop from class — send the
conversation, run any tool calls the model asks for, feed the results
back, repeat until it replies in plain text — and asks for approval
before running every command.

## Install

```
git clone https://github.com/dingyl2001/psp-agent-harness-ding.git
cd psp-agent-harness-ding
uv sync
```

## Configure

```
cp .env.example .env
```

Edit `.env` and fill in:

- `BASE_URL` — the API's base URL (e.g. `https://openrouter.ai/api/v1`)
- `API_KEY` — your API key for that provider
- `MODEL` — a model name that supports tool calling

`.env` is gitignored; never commit it.

## Run

Web interface (recommended):

```
uv run app.py
```

Then open http://127.0.0.1:5050 in your browser.

Terminal chat instead:

```
uv run harness.py
```

## Check that it works

Ask it: "What files are in this current folder?" It should show a pending
`bash` command (e.g. `ls -la`) with Approve/Deny buttons (web) or a y/N
prompt (terminal). Approve it, and it should answer using the real output.

## Status

Week 2 homework: core loop, bash tool, approval gate, and web interface
are complete and tested (single tool call, multi-call questions, failing
commands, and denied commands).
