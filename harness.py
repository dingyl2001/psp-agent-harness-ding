"""A minimal agent harness: one built-in tool (bash), plugin-provided MCP
tools, a loop, asks before running anything. This is the terminal version
-- the web interface in app.py reuses the same core functions.
"""
import asyncio
import json
import os
import subprocess
import sys

from dotenv import load_dotenv
from openai import OpenAI

from plugins_loader import call_mcp_tool, load_plugins

load_dotenv()

client = OpenAI(base_url=os.environ["BASE_URL"], api_key=os.environ["API_KEY"])
MODEL = os.environ["MODEL"]

with open("system_prompt.md") as f:
    SYSTEM_PROMPT = f.read()

# Step 3: the bash tool. One JSON-schema definition the model sees, plus
# the actual implementation below.
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
MAX_TOOL_ROUNDS = 20  # per question, so a confused model can't loop forever


def run_bash(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SEC,
        )
        output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
        return f"(exit code {result.returncode})\n{output}"
    except subprocess.TimeoutExpired:
        return f"(timed out after {COMMAND_TIMEOUT_SEC}s)"


def call_model(messages, tools):
    """One API call. Returns (message, usage_dict). Shared by the terminal
    loop below and the web app in app.py, so there is exactly one place
    that talks to the model.
    """
    resp = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
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


async def ask_approval(tool_name: str, args: dict) -> bool:
    # Step 5: ask before every tool call. Terminal version uses input();
    # the web version (app.py) uses Approve/Deny buttons; Telegram mode
    # (ask_approval_telegram, below) asks by reply instead.
    try:
        answer = input(f"\nRun this? {_describe_call(tool_name, args)}\n[y/N] ").strip().lower()
    except EOFError:
        return False  # no input available -- default to declining, not crashing
    return answer == "y"


async def agent_loop(messages, tools, loaded, approve=ask_approval, log=print):
    """Runs model + tool-call rounds until the model replies with plain
    text, or the round cap is hit. Mutates `messages` in place (this is
    the "every call resends everything" list from class). Dispatches
    `bash` locally and every other tool name to `loaded`'s MCP plugins.
    """
    for _ in range(MAX_TOOL_ROUNDS):
        msg, usage = call_model(messages, tools)
        log(f"[tokens: {usage['prompt_tokens']} in, "
            f"{usage['cached_tokens']} cached, {usage['completion_tokens']} out]")

        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            return msg.content

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })

        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            if await approve(name, args):
                if name == "bash":
                    result = run_bash(args["command"])
                elif name in loaded.dispatch:
                    result = await call_mcp_tool(loaded, name, args)
                else:
                    result = f"Unknown tool: {name}"
            else:
                result = "The user declined to run this."
            log(result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return "(stopped: too many tool-call rounds for one question)"


def make_telegram_approval(loaded):
    """Step 5: approvals by reply. Sends the pending command to Telegram
    and waits for a yes/no reply instead of using input().
    """
    async def ask_approval_telegram(tool_name: str, args: dict) -> bool:
        prompt = f"Run this? {_describe_call(tool_name, args)}\nReply yes or no."
        print(f"\n[approval requested via Telegram] {prompt}")
        await call_mcp_tool(loaded, "telegram__send_message", {"text": prompt})
        while True:
            reply = await call_mcp_tool(loaded, "telegram__wait_for_messages", {"seconds": 50})
            if reply == "No new messages.":
                continue  # keep waiting -- the harness owns this channel
            print(f"[reply received] {reply!r}")
            return reply.strip().lower() == "yes"
    return ask_approval_telegram


async def telegram_loop(loaded):
    """Step 5: Telegram mode. The harness itself calls wait_for_messages
    in a loop and treats each message as a user turn, replying with
    send_message. wait_for_messages is NOT offered to the model here (it
    might swallow the next real message); the model keeps send_message
    so it can send progress updates on a long task if it wants to.
    """
    if "telegram__send_message" not in loaded.dispatch:
        print("Telegram mode needs the telegram plugin (plugins/<user>-telegram/). Not loaded.")
        return

    tools = [BASH_TOOL] + [
        t for t in loaded.tool_schemas
        if t["function"]["name"] != "telegram__wait_for_messages"
    ]
    system_prompt = SYSTEM_PROMPT
    if loaded.skill_lines:
        system_prompt += "\n\nAvailable skills:\n" + "\n".join(loaded.skill_lines)
    messages = [{"role": "system", "content": system_prompt}]
    approve = make_telegram_approval(loaded)

    print("Telegram mode: waiting for messages on your phone (Ctrl+C to quit).")
    try:
        while True:
            update = await call_mcp_tool(loaded, "telegram__wait_for_messages", {"seconds": 50})
            if update == "No new messages.":
                continue
            if update.strip() == "/new":
                messages = [{"role": "system", "content": system_prompt}]
                await call_mcp_tool(loaded, "telegram__send_message",
                                     {"text": "Started a new conversation."})
                continue
            print("you (telegram):", update)
            messages.append({"role": "user", "content": update})
            reply = await agent_loop(messages, tools, loaded, approve=approve)
            await call_mcp_tool(loaded, "telegram__send_message", {"text": reply})
    except KeyboardInterrupt:
        print("\nbye")


async def main():
    async with await load_plugins() as loaded:
        tools = [BASH_TOOL] + loaded.tool_schemas
        system_prompt = SYSTEM_PROMPT
        if loaded.skill_lines:
            system_prompt += "\n\nAvailable skills:\n" + "\n".join(loaded.skill_lines)

        print(f"Loaded plugins: {', '.join(loaded.plugin_names) or '(none)'}")
        print(f"Tools: bash, {', '.join(loaded.dispatch) or '(none)'}")

        if len(sys.argv) > 1 and sys.argv[1] == "--telegram":
            await telegram_loop(loaded)
            return

        messages = [{"role": "system", "content": system_prompt}]

        if len(sys.argv) > 1:
            # One-shot mode: `uv run harness.py "a message"` sends one
            # message and exits, useful for scripting (e.g. sending the
            # week-4 hello email) without the interactive loop.
            user_input = sys.argv[1]
            print("you:", user_input)
            messages.append({"role": "user", "content": user_input})
            reply = await agent_loop(messages, tools, loaded)
            print("assistant:", reply)
            return

        print("Chat with the agent (Ctrl+C to quit).")
        try:
            while True:
                user_input = input("\nyou: ")
                messages.append({"role": "user", "content": user_input})
                reply = await agent_loop(messages, tools, loaded)
                print("assistant:", reply)
        except (EOFError, KeyboardInterrupt):
            print("\nbye")


if __name__ == "__main__":
    asyncio.run(main())
