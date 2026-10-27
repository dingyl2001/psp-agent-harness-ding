"""Subagents: a plain system of the kind Claude Code and Codex have. A
subagent runs the same loop as the main agent, with a fresh conversation
(its own system prompt, the task it was given, its own tools). It never
sees the main agent's conversation; the main agent never sees its work,
only its report (its last message).

Two tools, added to the MAIN agent only (never to a subagent):
  delegate(agent, task)   -- hand work over, wait, return the report
  subagent(action, ...)   -- start/list/send/wait/read/stop background
                             subagents (start/list/send/wait/read/stop)

This harness is async (the week-3 MCP client is async), so subagents run
as asyncio.Task objects with an asyncio.Queue inbox each, task.cancel()
for stop, and a shared asyncio.Lock around the approval prompt so two
subagents (or a subagent and the main agent) never ask to approve a
command at the same time.
"""
import asyncio
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from plugins_loader import call_mcp_tool

MAX_OUTPUT_CHARS = 10_000
COMMAND_TIMEOUT_SEC = 60
MAX_TURNS_DEFAULT = 20
TIME_LIMIT_SEC = 600  # 10 minutes
MAX_CONCURRENT_SUBAGENTS = 4
LOG_DIR = Path(__file__).parent / "logs"

APPROVAL_LOCK = asyncio.Lock()


# ---------------------------------------------------------------------------
# Agent: one running (or finished) loop, main or sub-
# ---------------------------------------------------------------------------
@dataclass
class Agent:
    id: str
    type_name: str
    tools: list
    max_turns: int = MAX_TURNS_DEFAULT
    model: str | None = None
    messages: list = field(default_factory=list)
    state: str = "running"  # running -> idle -> running (on send) | stopped | failed
    inbox: "asyncio.Queue" = field(default_factory=asyncio.Queue)
    turns: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    start_time: float = field(default_factory=time.time)
    deadline: float = 0.0
    log_path: Path = None
    task: "asyncio.Task | None" = None
    current_procs: list = field(default_factory=list)
    last_report: str = ""
    fail_reason: str = ""
    task_text: str = ""

    def __post_init__(self):
        if not self.deadline:
            self.deadline = self.start_time + TIME_LIMIT_SEC


def _log(agent: Agent, kind: str, content) -> None:
    agent.log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"t": time.time(), "kind": kind, "content": content}
    with open(agent.log_path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------------------
# Agent types: agents/*.md, frontmatter + system prompt body
# ---------------------------------------------------------------------------
@dataclass
class AgentType:
    name: str
    description: str
    tool_names: list
    model: str | None
    max_turns: int
    system_prompt: str


def parse_agent_types(loaded, agents_dir="agents") -> dict[str, AgentType]:
    """Load agents/*.md. A missing 'tools:' line means bash plus every
    plugin tool. An unknown tool name is an error at start, naming the
    file and the name.
    """
    types = {}
    path = Path(agents_dir)
    if not path.exists():
        return types

    known_tool_names = {"bash"} | set(loaded.dispatch.keys())
    for md_file in sorted(path.glob("*.md")):
        text = md_file.read_text()
        if not text.startswith("---"):
            raise ValueError(f"{md_file}: missing '---' frontmatter")
        _, front, body = text.split("---", 2)
        fields = {}
        for line in front.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip()] = v.strip()

        name = fields.get("name", md_file.stem)
        description = fields.get("description", "")
        tools_field = fields.get("tools")
        if tools_field:
            tool_names = [t.strip() for t in tools_field.split(",") if t.strip()]
            for tn in tool_names:
                if tn not in known_tool_names:
                    raise ValueError(
                        f"{md_file}: unknown tool '{tn}' in 'tools:' line "
                        f"(known: {', '.join(sorted(known_tool_names))})"
                    )
        else:
            tool_names = ["bash"] + sorted(loaded.dispatch.keys())

        types[name] = AgentType(
            name=name,
            description=description,
            tool_names=tool_names,
            model=fields.get("model") or None,
            max_turns=int(fields.get("max_turns", MAX_TURNS_DEFAULT)),
            system_prompt=body.strip(),
        )
    return types


# ---------------------------------------------------------------------------
# bash, stoppable: a process group so `stop` can kill the whole thing, not
# just the shell
# ---------------------------------------------------------------------------
def _run_bash_blocking(agent: Agent, command: str) -> str:
    try:
        proc = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
    except Exception as e:
        return f"Failed to start: {e}"

    agent.current_procs.append(proc)
    try:
        out, _ = proc.communicate(timeout=COMMAND_TIMEOUT_SEC)
        return f"(exit code {proc.returncode})\n{out[-MAX_OUTPUT_CHARS:]}"
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return f"(timed out after {COMMAND_TIMEOUT_SEC}s)"
    finally:
        if proc in agent.current_procs:
            agent.current_procs.remove(proc)


async def run_bash_stoppable(agent: Agent, command: str) -> str:
    return await asyncio.to_thread(_run_bash_blocking, agent, command)


# ---------------------------------------------------------------------------
# The loop itself, generalized to run on any Agent (main or sub-)
# ---------------------------------------------------------------------------
async def run_loop(agent: Agent, loaded, approve, call_model_fn, manager=None) -> str:
    """Runs model + tool-call rounds until the agent replies with plain
    text (-> idle, returns the report), or a limit is hit (-> failed).
    `approve(agent, tool_name, args) -> bool` is awaited under a shared
    lock so concurrent subagents never prompt at the same time. `manager`
    (a SubagentManager) is only needed on the main agent, whose tools
    include delegate/subagent; pass None for a subagent's own loop (it
    never has those tools anyway -- this is just defense in depth).
    """
    while True:
        if agent.turns >= agent.max_turns:
            agent.state = "failed"
            agent.fail_reason = f"exceeded max_turns ({agent.max_turns})"
            _log(agent, "failed", agent.fail_reason)
            return agent.fail_reason
        if time.time() > agent.deadline:
            agent.state = "failed"
            agent.fail_reason = f"exceeded time limit ({TIME_LIMIT_SEC}s)"
            _log(agent, "failed", agent.fail_reason)
            return agent.fail_reason

        # A running subagent takes everything in its inbox as one user
        # message before its next model call.
        pending = []
        while not agent.inbox.empty():
            pending.append(agent.inbox.get_nowait())
        if pending:
            text = "\n".join(pending)
            agent.messages.append({"role": "user", "content": text})
            _log(agent, "user", text)

        agent.turns += 1
        # Run the (synchronous) model call in a real thread, so multiple
        # agents' model calls can genuinely overlap instead of serializing
        # on the single asyncio event loop.
        msg, usage = await asyncio.to_thread(call_model_fn, agent.messages, agent.tools,
                                              model=agent.model)
        agent.tokens_in += usage["prompt_tokens"]
        agent.tokens_out += usage["completion_tokens"]
        _log(agent, "usage", usage)

        if not msg.tool_calls:
            agent.messages.append({"role": "assistant", "content": msg.content})
            _log(agent, "assistant", msg.content)
            agent.state = "idle"
            agent.last_report = msg.content or ""
            return agent.last_report

        agent.messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })
        _log(agent, "assistant_tool_calls",
             [{"name": tc.function.name, "args": tc.function.arguments} for tc in msg.tool_calls])

        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            async with APPROVAL_LOCK:
                ok = await approve(agent, name, args)
            if ok:
                if name == "bash":
                    result = await run_bash_stoppable(agent, args["command"])
                elif manager and name == "delegate":
                    result = await manager.run_delegate(args.get("agent"), args.get("task"))
                elif manager and name == "subagent":
                    action = args.pop("action", None)
                    result = await manager.dispatch(action, **args)
                elif name in loaded.dispatch:
                    result = await call_mcp_tool(loaded, name, args)
                else:
                    result = f"Unknown tool: {name}"
            else:
                result = "The user declined to run this."
            _log(agent, "tool_result", {"name": name, "result": result})
            agent.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})


# ---------------------------------------------------------------------------
# SubagentManager: builds Agents from types, runs delegate (inline) and
# the six subagent actions (background)
# ---------------------------------------------------------------------------
class SubagentManager:
    def __init__(self, agent_types, loaded, approve, call_model_fn, bash_tool,
                 session_id, main_agent: Agent):
        self.agent_types = agent_types
        self.loaded = loaded
        self.approve = approve
        self.call_model_fn = call_model_fn
        self.bash_tool = bash_tool
        self.session_id = session_id
        self.main_agent = main_agent
        self.agents: dict[str, Agent] = {"main": main_agent}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"sa-{self._counter}"

    def _resolve_tools(self, tool_names) -> list:
        tools = []
        for name in tool_names:
            if name == "bash":
                tools.append(self.bash_tool)
                continue
            match = next((t for t in self.loaded.tool_schemas
                          if t["function"]["name"] == name), None)
            if match:
                tools.append(match)
        return tools

    def _build_agent(self, type_name: str, task: str) -> Agent:
        t = self.agent_types.get(type_name)
        if not t:
            raise ValueError(
                f"Unknown agent type '{type_name}'. Known types: "
                f"{', '.join(self.agent_types) or '(none defined)'}"
            )
        agent_id = self._next_id()
        agent = Agent(
            id=agent_id,
            type_name=type_name,
            tools=self._resolve_tools(t.tool_names),
            max_turns=t.max_turns,
            model=t.model,
            messages=[
                {"role": "system", "content": t.system_prompt},
                {"role": "user", "content": task},
            ],
            task_text=task,
            log_path=LOG_DIR / self.session_id / f"{agent_id}.jsonl",
        )
        self.agents[agent.id] = agent
        return agent

    def running_count(self) -> int:
        return sum(1 for a in self.agents.values()
                    if a.id != "main" and a.state == "running")

    def add_note(self, agent: Agent) -> None:
        """Queue a note for the main agent -- reuses the same inbox the
        agent already drains at the top of every loop iteration, so it
        shows up before the main agent's next model call automatically,
        and (printed by the caller) in the interface right away too.
        """
        detail = agent.last_report or agent.fail_reason or "(no report)"
        note = (f"[subagent notes] {agent.id} ({agent.type_name}) is {agent.state} "
                f"after {agent.turns} turns: {detail[:500]}")
        self.main_agent.inbox.put_nowait(note)
        print(f"\n{note}")

    # -- delegate: synchronous-style hand-off, in the same task --------
    async def run_delegate(self, type_name: str, task: str) -> str:
        try:
            agent = self._build_agent(type_name, task)
        except ValueError as e:
            return str(e)
        result = await run_loop(agent, self.loaded, self.approve, self.call_model_fn, manager=None)
        elapsed = time.time() - agent.start_time
        stats = (f"[{agent.id} · {agent.type_name} · {agent.turns} turns · "
                 f"{agent.tokens_in + agent.tokens_out} tokens · {elapsed:.0f}s]")
        return f"{result}\n{stats}"

    # -- the six subagent() actions --------------------------------------
    async def _background_run(self, agent: Agent) -> None:
        try:
            await run_loop(agent, self.loaded, self.approve, self.call_model_fn, manager=None)
        except asyncio.CancelledError:
            agent.state = "stopped"
        finally:
            self.add_note(agent)

    async def start(self, type_name: str, task: str) -> str:
        if self.running_count() >= MAX_CONCURRENT_SUBAGENTS:
            return (f"{MAX_CONCURRENT_SUBAGENTS} subagents are running: "
                     "wait for one or stop one.")
        try:
            agent = self._build_agent(type_name, task)
        except ValueError as e:
            return str(e)
        agent.task = asyncio.create_task(self._background_run(agent))
        return f"Started {agent.id} ({agent.type_name})."

    def list_(self) -> str:
        if not self.agents:
            return "No subagents."
        lines = []
        for a in self.agents.values():
            elapsed = time.time() - a.start_time
            lines.append(
                f"{a.id}  type={a.type_name}  state={a.state}  turns={a.turns}  "
                f"tokens={a.tokens_in + a.tokens_out}  {elapsed:.0f}s  "
                f"task: {a.task_text[:60]}"
            )
        return "\n".join(lines)

    async def send(self, id: str, message: str) -> str:
        agent = self.agents.get(id)
        if not agent:
            return f"No subagent {id}."
        if agent.state in ("stopped", "failed"):
            return f"{id} is {agent.state}; start a new one instead."
        agent.inbox.put_nowait(message)
        if agent.state == "idle":
            agent.state = "running"
            agent.task = asyncio.create_task(self._background_run(agent))
        return f"Sent to {id}."

    async def wait(self, ids: list, timeout: float | None = 60) -> str:
        timeout = max(1, min(timeout or 60, 600))
        tasks = [self.agents[i].task for i in ids
                 if i in self.agents and self.agents[i].task and not self.agents[i].task.done()]
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)
        results = []
        for i in ids:
            agent = self.agents.get(i)
            if not agent:
                results.append(f"{i}: unknown subagent id")
                continue
            report = (agent.last_report or agent.fail_reason or "(still running)")[:4000]
            note = " (full report in its log)" if len(report) >= 4000 else ""
            results.append(f"{i} ({agent.state}): {report}{note}")
        return "\n\n".join(results)

    def read(self, id: str, last: int = 5) -> str:
        agent = self.agents.get(id)
        if not agent:
            return f"No subagent {id}."
        if not agent.log_path.exists():
            return f"No log yet for {id}."
        lines = agent.log_path.read_text().splitlines()[-max(1, last):]
        out = []
        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(json.dumps(entry, default=str)[:500])
        return "\n".join(out) if out else "(empty log)"

    async def stop(self, id: str) -> str:
        agent = self.agents.get(id)
        if not agent:
            return f"No subagent {id}."
        for proc in list(agent.current_procs):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if agent.task and not agent.task.done():
            agent.task.cancel()
        agent.state = "stopped"
        return f"Stopped {id} ({agent.type_name}). It was: {agent.task_text[:80]}"

    async def dispatch(self, action: str, **kwargs) -> str:
        if action == "start":
            return await self.start(kwargs.get("agent"), kwargs.get("task"))
        if action == "list":
            return self.list_()
        if action == "send":
            return await self.send(kwargs.get("id"), kwargs.get("message"))
        if action == "wait":
            return await self.wait(kwargs.get("ids") or [], kwargs.get("timeout"))
        if action == "read":
            return self.read(kwargs.get("id"), kwargs.get("last") or 5)
        if action == "stop":
            return await self.stop(kwargs.get("id"))
        return f"Unknown action: {action}"

    async def stop_all(self) -> None:
        for id in list(self.agents):
            if self.agents[id].state == "running":
                await self.stop(id)


# ---------------------------------------------------------------------------
# Tool schemas for the main agent (never given to a subagent)
# ---------------------------------------------------------------------------
DELEGATE_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate",
        "description": (
            "Hand a self-contained job to a fresh subagent and wait for its "
            "report. The subagent sees NOTHING of this conversation -- the "
            "task must say everything it needs to know, and exactly what to "
            "put in the report. Use for one job whose answer you need "
            "before continuing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string",
                           "description": "Agent type name, e.g. 'mail-reader'."},
                "task": {"type": "string",
                          "description": "The full, self-contained task for the subagent."},
            },
            "required": ["agent", "task"],
        },
    },
}

SUBAGENT_TOOL = {
    "type": "function",
    "function": {
        "name": "subagent",
        "description": (
            "Start and control background subagents, for jobs that can run "
            "while you keep going or run side by side with each other. "
            "action='start' (needs agent, task): start a subagent, return "
            "its id at once. action='list': one line per subagent (id, "
            "type, state, turns, tokens, time running). action='send' "
            "(needs id, message): message a subagent; a running one reads "
            "it before its next step, an idle one wakes up with its "
            "conversation intact. action='wait' (needs ids, optional "
            "timeout seconds, default 60, max 600): block until those "
            "subagents finish or the timeout elapses, return their "
            "reports. action='read' (needs id, optional last, default 5): "
            "its last few log steps, to look without stopping it. "
            "action='stop' (needs id): stop it now, killing any command it "
            "is running; it can't be woken again."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string",
                            "enum": ["start", "list", "send", "wait", "read", "stop"]},
                "agent": {"type": "string", "description": "Agent type name (action=start)."},
                "task": {"type": "string", "description": "Task for the new subagent (action=start)."},
                "id": {"type": "string", "description": "Subagent id, e.g. 'sa-1' (send/read/stop)."},
                "ids": {"type": "array", "items": {"type": "string"},
                         "description": "Subagent ids to wait for (action=wait)."},
                "message": {"type": "string", "description": "Message text (action=send)."},
                "timeout": {"type": "number",
                             "description": "Seconds to wait (action=wait), default 60, max 600."},
                "last": {"type": "integer",
                          "description": "Number of log steps to show (action=read), default 5."},
            },
            "required": ["action"],
        },
    },
}
