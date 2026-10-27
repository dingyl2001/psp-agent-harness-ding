"""A minimal agent harness: one built-in tool (bash), plugin-provided MCP
tools, subagents (delegate + background subagent control), a loop, asks
before running anything. This is the terminal version -- the web
interface in app.py reuses the call_model/run_bash core (bash-only; the
subagent system is not ported to the web UI).
"""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from plugins_loader import load_plugins
from subagents import (
    DELEGATE_TOOL, SUBAGENT_TOOL, TIME_LIMIT_SEC,
    Agent, SubagentManager, parse_agent_types, run_loop,
)

load_dotenv()

client = OpenAI(base_url=os.environ["BASE_URL"], api_key=os.environ["API_KEY"])
MODEL = os.environ["MODEL"]

with open("system_prompt.md") as f:
    SYSTEM_PROMPT = f.read()

# Step 3 (week 2): the bash tool. One JSON-schema definition the model
# sees, plus the actual implementation below.
BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Run a shell command on the user's computer and return its "
            "stdout, stderr and exit code. Commands time out after 60 "
            "seconds. Long output is cut to the last ~10,000 characters."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."}
            },
            "required": ["command"],
        },
    },
}

MAX_OUTPUT_CHARS = 10_000
COMMAND_TIMEOUT_SEC = 60
MAX_TOOL_ROUNDS = 20  # used by app.py's web UI (bash-only, no subagents)


def run_bash(command: str) -> str:
    """Plain (non-stoppable) version, used only by the web UI (app.py),
    which doesn't have subagents. The terminal/Telegram interfaces use
    subagents.run_bash_stoppable via subagents.run_loop instead.
    """
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SEC,
        )
        output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
        return f"(exit code {result.returncode})\n{output}"
    except subprocess.TimeoutExpired:
        return f"(timed out after {COMMAND_TIMEOUT_SEC}s)"


def call_model(messages, tools, model=None):
    """One API call. Returns (message, usage_dict). Shared by every
    agent (main and every subagent) -- there is exactly one place that
    talks to the model. `model` overrides the default for this call (an
    agent type's optional `model:` frontmatter field).
    """
    resp = client.chat.completions.create(model=model or MODEL, messages=messages, tools=tools)
    msg = resp.choices[0].message
    usage = resp.usage
    cached = usage.prompt_tokens_details.cached_tokens if usage.prompt_tokens_details else 0
    usage_dict = {
        "prompt_tokens": usage.prompt_tokens,
        "cached_tokens": cached or 0,
        "completion_tokens": usage.completion_tokens,
    }
    return msg, usage_dict


def _describe_call(tool_name: str, args: dict) -> str:
    if tool_name == "bash":
        return args["command"]
    return f"{tool_name}({json.dumps(args)})"


def _label(agent: Agent) -> str:
    return "" if agent.id == "main" else f"[{agent.id} · {agent.type_name}] "


async def ask_approval(agent: Agent, tool_name: str, args: dict) -> bool:
    # Step 5 (week 2/3): ask before every tool call, labeled with the
    # subagent if it isn't the main agent. Runs input() in a real thread
    # so background subagents keep making progress while we wait.
    prompt = f"\n{_label(agent)}Run this? {_describe_call(tool_name, args)}\n[y/N] "
    try:
        answer = await asyncio.to_thread(input, prompt)
    except EOFError:
        return False  # no input available -- default to declining, not crashing
    return answer.strip().lower() == "y"


def make_telegram_approval(loaded):
    """Step 5 (week 3): approvals by reply. Sends the pending command
    (labeled with the subagent, if any) to Telegram and waits for a
    yes/no reply instead of using input().
    """
    from plugins_loader import call_mcp_tool  # local import, avoids a cycle at module load

    async def ask_approval_telegram(agent: Agent, tool_name: str, args: dict) -> bool:
        prompt = f"{_label(agent)}Run this? {_describe_call(tool_name, args)}\nReply yes or no."
        print(f"\n[approval requested via Telegram] {prompt}")
        await call_mcp_tool(loaded, "telegram__send_message", {"text": prompt})
        while True:
            reply = await call_mcp_tool(loaded, "telegram__wait_for_messages", {"seconds": 50})
            if reply == "No new messages.":
                continue  # keep waiting -- the harness owns this channel
            print(f"[reply received] {reply!r}")
            return reply.strip().lower() == "yes"
    return ask_approval_telegram


def build_system_prompt(loaded, agent_types):
    system_prompt = SYSTEM_PROMPT
    if loaded.skill_lines:
        system_prompt += "\n\nAvailable skills:\n" + "\n".join(loaded.skill_lines)
    if agent_types:
        lines = [f"- {t.name}: {t.description}" for t in agent_types.values()]
        system_prompt += (
            "\n\nAvailable subagent types (use delegate or subagent to run one):\n"
            + "\n".join(lines)
        )
    return system_prompt


def build_main_tools(loaded):
    return [BASH_TOOL, DELEGATE_TOOL, SUBAGENT_TOOL] + loaded.tool_schemas


async def run_turn(main_agent, loaded, approve, manager, user_input, log=print):
    """One user turn for the main agent: cap tool-call rounds and the
    time limit fresh each turn (not across the whole session -- a
    subagent's limits are its whole lifetime, but the main agent's reset
    every message, matching week 2's per-question MAX_TOOL_ROUNDS).
    """
    main_agent.messages.append({"role": "user", "content": user_input})
    main_agent.turns = 0
    main_agent.deadline = time.time() + TIME_LIMIT_SEC
    reply = await run_loop(main_agent, loaded, approve, call_model, manager=manager)
    log(f"[tokens so far: {main_agent.tokens_in} in, {main_agent.tokens_out} out]")
    if len(manager.agents) > 1:
        log(f"[subagents]\n{manager.list_()}")
    return reply


async def telegram_loop(main_agent, loaded, manager):
    """Step 5 (week 3): Telegram mode. The harness itself calls
    wait_for_messages in a loop and treats each message as a user turn,
    replying with send_message. wait_for_messages is NOT offered to the
    model here (it might swallow the next real message); the model keeps
    send_message so it can send progress updates if it wants to.
    """
    from plugins_loader import call_mcp_tool  # local import, avoids a cycle at module load

    if "telegram__send_message" not in loaded.dispatch:
        print("Telegram mode needs the telegram plugin (plugins/<user>-telegram/). Not loaded.")
        return

    main_agent.tools = [t for t in main_agent.tools
                         if t["function"]["name"] != "telegram__wait_for_messages"]
    approve = make_telegram_approval(loaded)

    print("Telegram mode: waiting for messages on your phone (Ctrl+C to quit).")
    try:
        while True:
            update = await call_mcp_tool(loaded, "telegram__wait_for_messages", {"seconds": 50})
            if update == "No new messages.":
                continue
            if update.strip() == "/new":
                main_agent.messages = main_agent.messages[:1]  # keep only the system prompt
                await call_mcp_tool(loaded, "telegram__send_message",
                                     {"text": "Started a new conversation."})
                continue
            print("you (telegram):", update)
            reply = await run_turn(main_agent, loaded, approve, manager, update)
            await call_mcp_tool(loaded, "telegram__send_message", {"text": reply})
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        await manager.stop_all()


async def main():
    async with await load_plugins() as loaded:
        agent_types = parse_agent_types(loaded)
        system_prompt = build_system_prompt(loaded, agent_types)
        tools = build_main_tools(loaded)

        print(f"Loaded plugins: {', '.join(loaded.plugin_names) or '(none)'}")
        print(f"Tools: bash, delegate, subagent, {', '.join(loaded.dispatch) or '(none)'}")
        print(f"Subagent types: {', '.join(agent_types) or '(none)'}")

        session_id = time.strftime("%Y%m%d-%H%M%S")
        main_agent = Agent(
            id="main", type_name="main", tools=tools, max_turns=10_000,
            messages=[{"role": "system", "content": system_prompt}],
            log_path=Path("logs") / session_id / "main.jsonl",
        )
        manager = SubagentManager(agent_types, loaded, ask_approval, call_model,
                                   BASH_TOOL, session_id, main_agent)

        if len(sys.argv) > 1 and sys.argv[1] == "--telegram":
            await telegram_loop(main_agent, loaded, manager)
            return

        if len(sys.argv) > 1:
            # One-shot mode: `uv run harness.py "msg1" "msg2" ...` sends
            # each message as its own turn, in the same process (so
            # subagents started in msg1 are still alive for msg2), and
            # exits. Useful for scripting multi-turn demos: pipe approval
            # answers via stdin (e.g. `yes y | uv run harness.py ...`)
            # since those are separate from the argv messages.
            for user_input in sys.argv[1:]:
                print("\nyou:", user_input)
                reply = await run_turn(main_agent, loaded, ask_approval, manager, user_input)
                print("assistant:", reply)
            await manager.stop_all()
            return

        print("Chat with the agent (Ctrl+C to quit).")
        try:
            while True:
                user_input = await asyncio.to_thread(input, "\nyou: ")
                reply = await run_turn(main_agent, loaded, ask_approval, manager, user_input)
                print("assistant:", reply)
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
        finally:
            await manager.stop_all()


if __name__ == "__main__":
    asyncio.run(main())
