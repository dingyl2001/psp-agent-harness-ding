"""Plugin loader: finds plugins/, starts their MCP servers, and offers
their tools and skills to the agent loop. A minimal slice of what week 3
calls for -- just enough for the harness to load and use an MCP-based
plugin like plugins/dingyl2001-email/.
"""
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import Client, StdioServerParameters

PLUGINS_DIR = Path(__file__).parent / "plugins"


def find_plugins():
    """Each folder in plugins/ with a .claude-plugin/plugin.json."""
    if not PLUGINS_DIR.exists():
        return []
    return sorted(
        p for p in PLUGINS_DIR.iterdir()
        if (p / ".claude-plugin" / "plugin.json").exists()
    )


def _expand(value, plugin_root):
    """Replace ${CLAUDE_PLUGIN_ROOT} with the plugin's absolute path and
    ${VAR} with values from the environment -- the same substitution
    Claude Code does for .mcp.json.
    """
    if isinstance(value, str):
        value = value.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
        for key, val in os.environ.items():
            value = value.replace("${" + key + "}", val)
        return value
    if isinstance(value, list):
        return [_expand(v, plugin_root) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v, plugin_root) for k, v in value.items()}
    return value


def _read_skill(skill_path):
    text = skill_path.read_text()
    if not text.startswith("---"):
        return None
    front = text.split("---", 2)[1]
    fields = {}
    for line in front.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return fields.get("name", skill_path.parent.name), fields.get("description", "")


class LoadedPlugins:
    """Holds the open MCP client sessions, the OpenAI-format tool schemas
    (ready to merge with `bash`), a dispatch table from tool name to
    (client, real tool name), and skill summary lines for the system
    prompt. Use as an async context manager so every server shuts down
    cleanly on exit.
    """

    def __init__(self):
        self.stack = AsyncExitStack()
        self.tool_schemas = []
        self.dispatch = {}
        self.skill_lines = []
        self.plugin_names = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.stack.aclose()


async def load_plugins() -> LoadedPlugins:
    loaded = LoadedPlugins()

    for plugin_dir in find_plugins():
        loaded.plugin_names.append(plugin_dir.name)

        mcp_config_path = plugin_dir / ".mcp.json"
        if mcp_config_path.exists():
            config = json.loads(mcp_config_path.read_text())
            for server_name, server_config in config.get("mcpServers", {}).items():
                server_config = _expand(server_config, plugin_dir)
                params = StdioServerParameters(
                    command=server_config["command"],
                    args=server_config.get("args", []),
                    env={**os.environ, **server_config.get("env", {})},
                )
                client = await loaded.stack.enter_async_context(Client(params))
                result = await client.list_tools()
                for tool in result.tools:
                    full_name = f"{server_name}__{tool.name}"
                    loaded.dispatch[full_name] = (client, tool.name)
                    loaded.tool_schemas.append({
                        "type": "function",
                        "function": {
                            "name": full_name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    })

        skills_dir = plugin_dir / "skills"
        if skills_dir.exists():
            for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
                parsed = _read_skill(skill_file)
                if parsed:
                    name, desc = parsed
                    loaded.skill_lines.append(
                        f"- {name}: {desc} "
                        f"(to use this skill, read {skill_file} with bash first)"
                    )

    return loaded


async def call_mcp_tool(loaded: LoadedPlugins, full_name: str, arguments: dict) -> str:
    """Calls one MCP tool and returns its text content as a plain string."""
    client, tool_name = loaded.dispatch[full_name]
    result = await client.call_tool(tool_name, arguments)
    texts = [block.text for block in result.content if hasattr(block, "text")]
    text = "\n".join(texts) if texts else "(no text content returned)"
    if result.is_error:
        return f"Error: {text}"
    return text
