"""
Adaptive Action Agent: LangGraph agent that uses the Swytchcode CLI as its
execution kernel. Discovers enabled tools at runtime, provisions missing
services on demand, and delegates all execution to `swytchcode exec`.

Requires: langgraph, langchain_openai, langchain-core, python-dotenv, pydantic
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()

SWYTCHCODE_BIN = shutil.which("swytchcode") or "swytchcode"
SUBPROCESS_TIMEOUT = int(os.getenv("SWYTCHCODE_TIMEOUT", "120"))


# ---------------------------------------------------------------------------
# CLI wrapper
# ---------------------------------------------------------------------------
class SwytchcodeCLIError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"swytchcode failed (exit {returncode}): "
            f"{' '.join(shlex.quote(c) for c in cmd)}\n"
            f"stderr: {stderr.strip()}\nstdout: {stdout.strip()}"
        )


def _run_swytchcode(args: list[str], stdin: str | None = None) -> str:
    cmd = [SWYTCHCODE_BIN, *args]
    proc = subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ,
        timeout=SUBPROCESS_TIMEOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise SwytchcodeCLIError(cmd, proc.returncode, proc.stdout, proc.stderr)
    return proc.stdout


def _run_swytchcode_json(args: list[str], stdin: str | None = None) -> Any:
    raw = _run_swytchcode(args, stdin=stdin)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SwytchcodeCLIError(
            [SWYTCHCODE_BIN, *args], 0, raw, f"invalid JSON from CLI: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Dynamic discovery — enabled tooling only
# ---------------------------------------------------------------------------
def list_swytch_tools() -> list[dict]:
    """Return the agent's current skill set: tools enabled in tooling.json.

    Uses `swytchcode list tooling --json`, which scans only what the user has
    explicitly enabled via `swytchcode add`. That is the right "current skill
    set" for the agent — the full `swytchcode list` inventory can be thousands
    of tools and exceeds LLM per-call tool limits.
    """
    data = _run_swytchcode_json(["list", "tooling", "--json"])
    methods = data.get("methods", []) if isinstance(data, dict) else []
    workflows = data.get("workflows", []) if isinstance(data, dict) else []
    return [*methods, *workflows]


def _safe_tool_name(canonical_id: str) -> str:
    # Tool names must match ^[a-zA-Z0-9_-]+$ and stay under 64 chars.
    cleaned = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in canonical_id)
    return cleaned[:64] or "swytch_tool"


class _PassthroughArgs(BaseModel):
    """Permissive schema: collects whatever keys the LLM passes (body, header, ...)."""

    model_config = ConfigDict(extra="allow")

    body: dict | None = Field(
        default=None, description="Request body object (maps to HTTP body)."
    )
    header: dict | None = Field(
        default=None, description="Header key/value pairs."
    )
    param: dict | None = Field(
        default=None, description="Query parameter key/value pairs."
    )
    input: dict | None = Field(
        default=None, description="Path / input key/value pairs."
    )


def _make_exec_tool(tool_def: dict) -> StructuredTool:
    canonical_id = tool_def["canonical_id"]
    integration = tool_def.get("integration", "unknown")
    description = (
        f"Execute Swytchcode tool `{canonical_id}` (integration: {integration}). "
        f"Pass a `body` object with the tool's input fields. "
        f"Call get_tool_info('{canonical_id}') first if you do not know the input schema."
    )

    def _invoke(**kwargs: Any) -> str:
        payload = {k: v for k, v in kwargs.items() if v is not None}
        return execute_action.invoke(
            {"action_id": canonical_id, "tool_args": payload}
        )

    return StructuredTool.from_function(
        func=_invoke,
        name=_safe_tool_name(canonical_id),
        description=description,
        args_schema=_PassthroughArgs,
    )


def build_dynamic_tools() -> list[StructuredTool]:
    tools: list[StructuredTool] = []
    seen: set[str] = set()
    for tool_def in list_swytch_tools():
        if not isinstance(tool_def, dict):
            continue
        cid = tool_def.get("canonical_id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        try:
            tools.append(_make_exec_tool(tool_def))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] skipping tool {cid!r}: {exc}")
    return tools


# ---------------------------------------------------------------------------
# Bridge tools exposed to the LLM
# ---------------------------------------------------------------------------
@tool
def search_services(keyword: str = "") -> str:
    """List matching integration project names in the remote registry.

    Coarse-grained: matches on project name only. For intent-based discovery
    of specific methods/workflows, prefer `discover_capabilities`.
    Empty keyword lists all available integrations.
    """
    try:
        data = _run_swytchcode_json(["search", keyword, "--json"] if keyword else ["search", "--json"])
    except SwytchcodeCLIError as exc:
        return f"ERROR: {exc}"
    return json.dumps(data, indent=2)[:8000]


@tool
def discover_capabilities(intent: str, top: int = 5) -> str:
    """Find Swytchcode methods/workflows matching a natural-language intent.

    Wraps `swytchcode discover "<intent>" --json --top <n>`. Use this to
    locate a canonical_id when the user's request is phrased in natural
    language and you do not already have a matching tool bound.
    """
    if not intent.strip():
        return "ERROR: intent must be a non-empty string"
    try:
        data = _run_swytchcode_json(
            ["discover", intent, "--top", str(top), "--json"]
        )
    except SwytchcodeCLIError as exc:
        return f"ERROR: {exc}"
    return json.dumps(data, indent=2)[:8000]


@tool
def plan_workflow(canonical_id: str) -> str:
    """Return the ordered step list for a Swytchcode workflow.

    Wraps `swytchcode plan <canonical_id> --json`. Use before executing a
    workflow to understand which methods will run and in what order.
    """
    try:
        data = _run_swytchcode_json(["plan", canonical_id, "--json"])
    except SwytchcodeCLIError as exc:
        return f"ERROR: {exc}"
    return json.dumps(data, indent=2)[:8000]


@tool
def get_tool_info(canonical_id: str) -> str:
    """Return the input/output contract for a Swytchcode tool (method or workflow).

    Use this before execute_action to learn the exact input schema for a tool.
    Wraps `swytchcode info <canonical_id> --json`.
    """
    try:
        data = _run_swytchcode_json(["info", canonical_id, "--json"])
    except SwytchcodeCLIError as exc:
        return f"ERROR: {exc}"
    return json.dumps(data, indent=2)[:8000]


@tool
def provision_service(service_name: str, action_id: str) -> str:
    """Fetch a Swytchcode integration and enable a method/workflow locally.

    Runs `swytchcode get <service_name>` then `swytchcode add <action_id>`.
    Use when the task requires a service that is not in the current tool list.
    """
    try:
        get_out = _run_swytchcode(["get", service_name])
        add_out = _run_swytchcode(["add", action_id])
    except SwytchcodeCLIError as exc:
        return f"ERROR: {exc}"
    return (
        f"Provisioned {service_name} and enabled {action_id}.\n"
        f"get: {get_out.strip()}\nadd: {add_out.strip()}"
    )


@tool
def execute_action(action_id: str, tool_args: dict) -> str:
    """Execute a Swytchcode tool by canonical id.

    `tool_args` must match the tool's input schema (see get_tool_info).
    Typically contains sub-objects like `body`, `header`, `param`, `input`.
    Credentials are sourced from the local `.env` — do not pass API keys here.

    Invokes the kernel via JSON stdin: `{"tool": action_id, "args": tool_args}`.
    """
    if not isinstance(tool_args, dict):
        return f"ERROR: tool_args must be a JSON object, got {type(tool_args).__name__}"
    try:
        payload = json.dumps({"tool": action_id, "args": tool_args}, default=str)
    except (TypeError, ValueError) as exc:
        return f"ERROR: could not serialise tool_args to JSON: {exc}"
    try:
        raw = _run_swytchcode(["exec", "--json"], stdin=payload)
    except SwytchcodeCLIError as exc:
        return f"ERROR: {exc}"
    try:
        return json.dumps(json.loads(raw), indent=2)
    except json.JSONDecodeError:
        return raw.strip()


@tool
def refresh_tools() -> str:
    """Re-run `swytchcode list tooling --json` and report the enabled tool set."""
    try:
        defs = list_swytch_tools()
    except SwytchcodeCLIError as exc:
        return f"ERROR: {exc}"
    ids = [d.get("canonical_id") for d in defs if isinstance(d, dict)]
    return json.dumps({"count": len(ids), "canonical_ids": ids}, indent=2)


# ---------------------------------------------------------------------------
# LangGraph wiring
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are an Adaptive Action Agent. You use Swytchcode CLI to interact with "
    "the world. Your process is: Discover -> Provision -> Execute. If a task "
    "requires a service you don't see in your current list, try to provision "
    "it using the service name. Use the `.env` file for all credentials—never "
    "ask the user for API keys.\n\n"
    "Workflow rules:\n"
    "1. Prefer a tool already bound to you (each has a canonical_id in its name/description).\n"
    "2. If no bound tool matches, call discover_capabilities(intent) to find candidate "
    "canonical_ids, then get_tool_info(canonical_id) for the input schema.\n"
    "3. If a needed canonical_id is not yet enabled, call provision_service(service, action_id) "
    "then refresh_tools, then execute. Use search_services only when you need to list projects.\n"
    "4. For workflow-type tools, call plan_workflow(canonical_id) first to see the steps.\n"
    "5. Never invent canonical_ids. If discovery returns nothing usable, say so and stop."
)


def build_agent(model: str = "gpt-4o-mini"):
    dynamic_tools = build_dynamic_tools()
    bridge_tools = [
        discover_capabilities,
        search_services,
        get_tool_info,
        plan_workflow,
        provision_service,
        execute_action,
        refresh_tools,
    ]
    all_tools = [*bridge_tools, *dynamic_tools]

    llm = ChatOpenAI(model=model, temperature=0).bind_tools(all_tools)

    def call_model(state: MessagesState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(all_tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    graph.add_edge("agent", END)
    return graph.compile()


# ---------------------------------------------------------------------------
# REPL entry point
# ---------------------------------------------------------------------------
def main() -> None:
    agent = build_agent(os.getenv("SWYTCHCODE_AGENT_MODEL", "gpt-4o-mini"))
    print("Adaptive Action Agent ready. Type a request (Ctrl-C to exit).")
    history: list = []
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not user_input:
            continue
        history.append(("user", user_input))
        result = agent.invoke({"messages": history})
        history = result["messages"]
        print(f"\n{history[-1].content}")


if __name__ == "__main__":
    main()
