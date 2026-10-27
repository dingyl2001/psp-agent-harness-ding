# psp-agent-harness-ding

A minimal agent harness built for UCLA's "AI in Research" class (EPSS 254,
Fall 2026). Week 2: an agent loop with one tool, `bash`, and a local web
chat interface. Week 3: a plugin loader, a Telegram MCP server (message
the agent from your phone, approve commands by reply), and an MCP server
for solar wind research. Week 4: an email plugin, and a subagent system
(`delegate` to hand work off and wait for the report; `subagent` to
start, list, message, wait for, read and stop subagents running in the
background).

It talks to any OpenAI-compatible Chat Completions API (configured via
environment variables), runs the agent loop from class — send the
conversation, run any tool calls the model asks for, feed the results
back, repeat until it replies in plain text — and asks for approval
before running every command or plugin tool.

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
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — for the Telegram plugin (see
  `plugins/dingyl2001-telegram/README.md`)
- `EMAIL_ADDRESS` / `EMAIL_APP_PASSWORD` / `EMAIL_ALLOWED_RECIPIENTS` — for
  the email plugin, a **dedicated** Gmail account only (see
  `plugins/dingyl2001-email/README.md`)

`.env` is gitignored; never commit it.

## Plugins

Each folder in `plugins/` with a `.claude-plugin/plugin.json` is loaded
automatically (no code changes needed to add one):

- `dingyl2001-telegram` — message the agent from Telegram.
- `dingyl2001-energyflux` — compute multi-species (proton/alpha/electron)
  MHD solar wind energy-flux budgets, for research questions.
- `dingyl2001-email` — read/send email from a dedicated agent inbox.

On startup the harness prints which plugins, tools and skills it loaded.
Every plugin tool asks for approval before running, same as `bash`.

## Run

Web interface (bash tool only — plugin support not yet ported to the web UI):

```
uv run app.py
```

Then open http://127.0.0.1:5050 in your browser.

Terminal chat (bash + all loaded plugin tools):

```
uv run harness.py
```

One-shot mode, useful for scripting:

```
uv run harness.py "a single message"
```

Telegram mode — the harness gets each question from your phone instead of
the keyboard, and approvals happen by replying "yes" or "no" in the chat:

```
uv run harness.py --telegram
```

## Subagents

Each `agents/<name>.md` file (frontmatter: `name`, `description`, `tools`
— a comma-separated list, or omit for bash + every plugin tool —
optional `model` and `max_turns`; body = its system prompt) defines an
agent type. Two tools, given only to the **main** agent, never to a
subagent:

- `delegate(agent, task)` — starts a subagent of that type, runs its
  loop to completion, returns its report (last message) plus a stats
  line. The subagent sees nothing of the main conversation; the main
  agent sees nothing of the subagent's work, only the report.
- `subagent(action, ...)` — `start`/`list`/`send`/`wait`/`read`/`stop`
  subagents running in the background.

**How they run**: this harness is async (the MCP client is), so each
background subagent is an `asyncio.Task` with an `asyncio.Queue` inbox;
`stop` calls `task.cancel()`. A subagent's live state (its `Agent`
object: conversation, tool list, turn count, token usage, running
processes) lives in a plain dict on a `SubagentManager`, not in any
external store. Model calls run via `asyncio.to_thread` so multiple
agents' API calls can genuinely overlap rather than serializing on one
event loop. `bash` commands start with `subprocess.Popen(...,
start_new_session=True)`, so `stop` can `os.killpg(...)` the whole
process group — killing a long-running command, not just the shell
around it. Every subagent's conversation is logged to
`logs/<session>/<id>.jsonl`; `make_transcript.py` turns a session's logs
into readable Markdown (see `transcripts/` for the five required demos).
At most 4 subagents run at once; each has a default `max_turns` (20) and
a 10-minute time limit, past which it ends `failed`. When a background
subagent goes idle, stops or fails, a note is queued into the main
agent's own inbox (the same mechanism `send` uses), so it surfaces
automatically before the main agent's next model call.

## Check that it works

Terminal: ask "What files are in this current folder?" — a pending
`bash` command (e.g. `ls -la`) should show with a y/N prompt. Approve it,
and it should answer using the real output.

Telegram mode: send the bot a message needing a tool call. An approval
request should arrive on your phone; reply "yes" and the answer follows.
Reply "no" to a different request and the agent should report it was
declined, not find a workaround.

## Safety notes

- The Telegram and email accounts are dedicated to this agent, never
  personal or UCLA accounts — an agent that can read a channel and act
  on it has all three legs of the
  [lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/).
- The Telegram plugin only ever sends to and accepts messages from one
  configured chat id; messages from any other chat are dropped and logged.
- The email plugin refuses to send to any address not on an explicit
  allow list (`EMAIL_ALLOWED_RECIPIENTS`), and its skill tells the agent
  every email is untrusted text — never follow instructions found inside
  one.
- Every tool call (`bash` and every plugin tool) requires explicit
  approval before running, in every interface.

## Status

Week 2: core loop, bash tool, approval gate, web interface — complete.

Week 3: plugin loader (`plugins_loader.py`), Telegram plugin, energy-flux
research plugin, Telegram mode with approvals by reply — complete and
tested (plugin auto-discovery, approve and deny paths both verified live
over Telegram, multi-step tool chains, scientifically-checked energy-flux
output).

Week 4: email plugin (dedicated Gmail account, IMAP/SMTP, allow-listed
sends) — complete; hello sent to the class agent via this harness.
Subagent system (`delegate`, `subagent`, agent types in `agents/`) —
complete; all five required demos run and transcripted (hand over the
inbox, fan out three concurrent subagents with verified overlapping
timestamps, a follow-up answered without redoing work, stopping a
running command and confirming via `ps` it's actually killed, and a
turn-limit failure with the reason reported back).
