# Demo 5: turn limit exceeded

(session `20261027-162846`)

## main

**[   0.0s] tool call:** `delegate({"task":"Run these five commands, each as its own SEPARATE bash tool call (do not combine them into one command):\n1. echo step1\n2. echo step2\n3. echo step3\n4. echo step4\n5. echo step5\n\nReport all five outputs together at the end.","agent":"limited-worker"})`

**[   3.4s] tool result (delegate):**
```
exceeded max_turns (3)
[sa-1 · limited-worker · 3 turns · 1460 tokens · 3s]
```

**[   8.1s] assistant:** Hmph. The limited-worker hit its hard turn limit of 3 before it could run all five commands. It managed three steps, then got cut off — that's literally what "limited" means in its name.

If you actually need all five commands run, use the regular `long-task-worker` instead, or just let me run them directly. Want me to do that now?

## sa-1

**[   0.0s] tool call:** `bash({"command":"echo step1"})`

**[   0.0s] tool result (bash):**
```
(exit code 0)
step1

```

**[   1.1s] tool call:** `bash({"command":"echo step2"})`

**[   1.1s] tool result (bash):**
```
(exit code 0)
step2

```

**[   2.1s] tool call:** `bash({"command":"echo step3"})`

**[   2.1s] tool result (bash):**
```
(exit code 0)
step3

```

**[   2.1s] FAILED:** exceeded max_turns (3)

