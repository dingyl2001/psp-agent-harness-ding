"""A minimal agent harness: one tool (bash), a loop, asks before running
anything. This is the terminal version -- the web interface in app.py
reuses the same core functions.
"""
import json
import os
import subprocess

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(base_url=os.environ["BASE_URL"], api_key=os.environ["API_KEY"])
MODEL = os.environ["MODEL"]

with open("system_prompt.md") as f:
    SYSTEM_PROMPT = f.read()

# Step 3: the bash tool. One JSON-schema definition the model sees, plus
# the actual implementation below.
TOOLS = [
    {
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
]

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


def call_model(messages):
    """One API call. Returns (message, usage_dict). Shared by the terminal
    loop below and the web app in app.py, so there is exactly one place
    that talks to the model.
    """
    resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
    msg = resp.choices[0].message
    usage = resp.usage
    cached = usage.prompt_tokens_details.cached_tokens if usage.prompt_tokens_details else 0
    usage_dict = {
        "prompt_tokens": usage.prompt_tokens,
        "cached_tokens": cached or 0,
        "completion_tokens": usage.completion_tokens,
    }
    return msg, usage_dict


def ask_approval(command: str) -> bool:
    # Step 5: ask before every command. Terminal version uses input();
    # the web version (app.py) uses Approve/Deny buttons instead.
    answer = input(f"\nRun this command?\n  {command}\n[y/N] ").strip().lower()
    return answer == "y"


def agent_loop(messages, approve=ask_approval, log=print):
    """Runs model + tool-call rounds until the model replies with plain
    text, or the round cap is hit. Mutates `messages` in place (this is
    the "every call resends everything" list from class).
    """
    for _ in range(MAX_TOOL_ROUNDS):
        msg, usage = call_model(messages)
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
            command = json.loads(call.function.arguments)["command"]
            if approve(command):
                result = run_bash(command)
            else:
                result = "The user declined to run this command."
            log(result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return "(stopped: too many tool-call rounds for one question)"


if __name__ == "__main__":
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Chat with the agent (Ctrl+C to quit).")
    try:
        while True:
            user_input = input("\nyou: ")
            messages.append({"role": "user", "content": user_input})
            reply = agent_loop(messages)
            print("assistant:", reply)
    except (EOFError, KeyboardInterrupt):
        print("\nbye")
