# Demo 4: stop a running subagent

(session `20261027-162750`)

## main

**[   0.0s] tool call:** `subagent({"agent":"long-task-worker","task":"Run the command: sleep 600 && echo done sleeping","action":"start"})`

**[   0.0s] tool result (subagent):**
```
Started sa-1 (long-task-worker).
```

**[   2.6s] assistant:** Started subagent **sa-1** (long-task-worker). It's running `sleep 600 && echo done sleeping` in the background — that's 10 minutes, so it'll be a while. I'll let you know when it finishes (or you can ask me to check on it).

**[   3.6s] tool call:** `subagent({"action":"list"})`

**[   3.6s] tool result (subagent):**
```
main  type=main  state=idle  turns=1  tokens=13225  21s  task: 
sa-1  type=long-task-worker  state=running  turns=1  tokens=0  4s  task: Run the command: sleep 600 && echo done sleeping
```

**[   5.4s] tool call:** `subagent({"id":"sa-1","action":"read"})`

**[   5.4s] tool result (subagent):**
```
{"t": 1793143692.9614651, "kind": "usage", "content": {"prompt_tokens": 368, "cached_tokens": 0, "completion_tokens": 337}}
{"t": 1793143692.9622972, "kind": "assistant_tool_calls", "content": [{"name": "bash", "args": "{\"command\":\"sleep 600 && echo done sleeping\"}"}]}
```

**[   7.2s] assistant:** Subagent **sa-1** (long-task-worker) is running. Its last log step shows it launched the command:

```bash
sleep 600 && echo done sleeping
```

It's been ~4 seconds, so it's still in the middle of that 600-second sleep. Nothing to report yet — it'll finish in about 9.5 minutes.

**[   8.5s] tool call:** `subagent({"action":"stop","id":"sa-1"})`

**[   8.5s] tool result (subagent):**
```
Stopped sa-1 (long-task-worker). It was: Run the command: sleep 600 && echo done sleeping
```

**[   9.9s] assistant:** Stopped **sa-1**. It was killed mid-sleep — never reached the `echo done sleeping` part.

## sa-1

**[   0.0s] tool call:** `bash({"command":"sleep 600 && echo done sleeping"})`

