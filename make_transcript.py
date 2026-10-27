#!/usr/bin/env python3
"""Turn a session's logs (logs/<session_id>/main.jsonl + sa-*.jsonl) into
a readable Markdown transcript. Usage: uv run make_transcript.py <session_id> [title]
"""
import json
import sys
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"


def render_file(path: Path, label: str) -> str:
    lines = [f"## {label}\n"]
    if not path.exists():
        return f"## {label}\n\n(no log)\n"
    t0 = None
    for raw in path.read_text().splitlines():
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        t0 = t0 or entry["t"]
        dt = entry["t"] - t0
        kind = entry["kind"]
        content = entry["content"]
        if kind == "usage":
            continue  # token counts aren't interesting in a readable transcript
        elif kind == "user":
            lines.append(f"**[{dt:6.1f}s] user:** {content}\n")
        elif kind == "assistant":
            lines.append(f"**[{dt:6.1f}s] assistant:** {content}\n")
        elif kind == "assistant_tool_calls":
            for call in content:
                lines.append(f"**[{dt:6.1f}s] tool call:** `{call['name']}({call['args']})`\n")
        elif kind == "tool_result":
            result = content["result"] if isinstance(content, dict) else content
            result = str(result)
            if len(result) > 800:
                result = result[:800] + "... [truncated]"
            lines.append(f"**[{dt:6.1f}s] tool result ({content.get('name', '?')}):**\n```\n{result}\n```\n")
        elif kind == "failed":
            lines.append(f"**[{dt:6.1f}s] FAILED:** {content}\n")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run make_transcript.py <session_id> [title]")
        sys.exit(1)
    session_id = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else session_id
    session_dir = LOGS_DIR / session_id
    if not session_dir.exists():
        print(f"No such session: {session_dir}")
        sys.exit(1)

    out = [f"# {title}\n", f"(session `{session_id}`)\n"]
    main_log = session_dir / "main.jsonl"
    if main_log.exists():
        out.append(render_file(main_log, "main"))
    for sa_log in sorted(session_dir.glob("sa-*.jsonl")):
        out.append(render_file(sa_log, sa_log.stem))

    print("\n".join(out))


if __name__ == "__main__":
    main()
