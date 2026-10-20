"""Step 6: the web interface. A local page (served on 127.0.0.1 only)
with a chat box, Approve/Deny buttons for each tool call, its output, and
token counts per call. Reuses the exact same call_model/run_bash/TOOLS
from harness.py -- this file is only the HTTP layer on top of that loop.

The core loop in harness.py blocks on input() for approval, which does
not work over HTTP (a browser click can't answer a function call waiting
inside a request handler). So this version breaks the loop into two
endpoints instead:
  POST /chat    - send a user message, get back either a final reply or
                  a list of pending tool calls awaiting approval
  POST /resolve - approve or deny one pending tool call; once every call
                  from the current assistant turn is resolved, the model
                  is called again automatically (continuing the loop)
"""
import json

from flask import Flask, jsonify, request, send_from_directory

from harness import BASH_TOOL, SYSTEM_PROMPT, MAX_TOOL_ROUNDS, call_model, run_bash

# The web UI only offers the built-in bash tool for now; plugin (MCP) tool
# support was added to the terminal harness (harness.py) and Telegram mode
# in week 3, not yet ported to this HTTP layer.
TOOLS = [BASH_TOOL]

app = Flask(__name__, static_folder="static", static_url_path="")

# Single-user, single-conversation state (this is a local tool for one
# person, so one global session is enough -- no multi-user accounts).
STATE = {
    "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
    "queue": [],       # pending tool calls for the in-progress assistant turn
    "rounds_left": MAX_TOOL_ROUNDS,
}


def usage_payload(usage):
    return {
        "prompt_tokens": usage["prompt_tokens"],
        "cached_tokens": usage["cached_tokens"],
        "completion_tokens": usage["completion_tokens"],
    }


def advance():
    """Calls the model once. If it wants to run tools, fills STATE['queue']
    and returns a 'pending' response; otherwise returns the final 'text'
    reply. This is the same branch as the terminal agent_loop, just
    returning instead of blocking for approval.
    """
    if STATE["rounds_left"] <= 0:
        return {"type": "text",
                "content": "(stopped: too many tool-call rounds for one question)"}

    STATE["rounds_left"] -= 1
    msg, usage = call_model(STATE["messages"], TOOLS)

    if not msg.tool_calls:
        STATE["messages"].append({"role": "assistant", "content": msg.content})
        return {"type": "text", "content": msg.content, "usage": usage_payload(usage)}

    STATE["messages"].append({
        "role": "assistant",
        "content": msg.content,
        "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
    })
    STATE["queue"] = [
        {"id": tc.id, "command": json.loads(tc.function.arguments)["command"]}
        for tc in msg.tool_calls
    ]
    return {"type": "pending", "calls": STATE["queue"], "usage": usage_payload(usage)}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json["message"]
    STATE["messages"].append({"role": "user", "content": user_message})
    STATE["rounds_left"] = MAX_TOOL_ROUNDS
    return jsonify(advance())


@app.route("/resolve", methods=["POST"])
def resolve():
    call_id = request.json["id"]
    approved = request.json["approved"]

    call = next((c for c in STATE["queue"] if c["id"] == call_id), None)
    if call is None:
        return jsonify({"error": "unknown or already-resolved call id"}), 400

    if approved:
        result = run_bash(call["command"])
    else:
        result = "The user declined to run this command."

    STATE["messages"].append({"role": "tool", "tool_call_id": call_id, "content": result})
    STATE["queue"] = [c for c in STATE["queue"] if c["id"] != call_id]

    response = {"output": result, "queue_remaining": len(STATE["queue"])}
    if STATE["queue"]:
        # still waiting on other calls from this same assistant turn
        return jsonify(response)

    # every call from this turn is resolved -- continue the loop
    response["next"] = advance()
    return jsonify(response)


if __name__ == "__main__":
    print("Harness running at http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=False)
