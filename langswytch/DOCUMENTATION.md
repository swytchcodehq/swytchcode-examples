# Langswytch Documentation

**Langswytch** is a LangGraph-based adaptive agent that uses the [Swytchcode](https://swytchcode.com) execution kernel to interact with external APIs through natural language. You write a prompt, Langswytch picks the right tool, formats the request, calls the upstream service via Swytchcode, and returns a human-readable result.

This document is the complete reference for using, extending, and operating Langswytch. For a one-page orientation, see the project [README](./README.md).

---

## Table of contents

- [Introduction](#introduction)
- [Quickstart](#quickstart)
- [Core concepts](#core-concepts)
- [Guides](#guides)
  - [Run your first action](#guide-run-your-first-action)
  - [Add a new service](#guide-add-a-new-service)
  - [Embed Langswytch in your app](#guide-embed-langswytch-in-your-app)
  - [Customize the system prompt](#guide-customize-the-system-prompt)
  - [Use a different LLM provider](#guide-use-a-different-llm-provider)
- [API reference](#api-reference)
  - [Python API](#python-api)
  - [Environment variables](#environment-variables)
  - [Swytchcode CLI commands used internally](#swytchcode-cli-commands-used-internally)
- [Operations](#operations)
  - [Keeping integrations current](#keeping-integrations-current)
  - [Security](#security)
  - [Production considerations](#production-considerations)
- [Troubleshooting](#troubleshooting)
- [Glossary](#glossary)
- [Changelog](#changelog)

---

## Introduction

### What is Langswytch

Langswytch is a thin integration layer: a LangGraph agent on top of the Swytchcode CLI. It does three things:

1. **Discovers** which tools are available locally (from `.swytchcode/tooling.json`).
2. **Binds** each discovered tool to the LLM as a typed function call.
3. **Executes** tool calls by shelling out to `swytchcode exec`, which handles authentication, retries, and protocol details.

You get a single conversational interface to every API you've added to Swytchcode — Resend, Stripe, Circle, Persona, Binance, Slack, and 60+ others.

### Who it's for

- **Application developers** who want to replace hand-written API wrappers with a declarative agent.
- **Platform teams** standardizing how internal services integrate with third-party APIs.
- **Researchers and prototypers** exploring tool-using LLM agents against real APIs.

### How it works

```
┌────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  User      │     │  Langswytch         │     │  Swytchcode CLI  │
│  prompt    │────▶│  (LangGraph agent)  │────▶│  (execution      │
└────────────┘     │                     │     │   kernel)        │
                   │  • OpenAI LLM       │     │                  │
                   │  • 7 bridge tools   │     │  • Auth          │
                   │  • N dynamic tools  │     │  • HTTP          │
                   │    from tooling.json│     │  • Retries       │
                   └─────────────────────┘     └────────┬─────────┘
                                                        │
                                                        ▼
                                               ┌──────────────────┐
                                               │  Upstream API    │
                                               │  (Resend, Stripe,│
                                               │   Circle, ...)   │
                                               └──────────────────┘
```

Every external call passes through Swytchcode. Langswytch never calls third-party APIs directly.

---

## Quickstart

### Prerequisites

- Python 3.10 or newer
- Node.js (for installing the Swytchcode CLI via npm)
- An OpenAI API key with access to a tool-calling model

### Install and run

```bash
# 1. Unzip (or clone) the project, then:
cd langswytch

# 2. Install the Swytchcode CLI
npm install -g swytchcode

# 3. Fetch the integrations declared in tooling.json
swytchcode bootstrap

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Create .env from the template
cp .env.example .env
#    Edit .env and set at minimum:
#      OPENAI_API_KEY=sk-...

# 6. Start the agent
python langgraph_swytchcode_agent.py
```

### Your first prompt

Ask the agent what it can currently do. No external API is called — the LLM answers from the tool set it bound at startup.

```
Adaptive Action Agent ready. Type a request (Ctrl-C to exit).

> List the canonical IDs you currently have enabled, grouped by service.
```

The response is a categorized list of every canonical ID in your `tooling.json`. This is your authoritative view of the agent's current capabilities — it reflects whatever you provisioned, not a fixed menu.

### Your first real call

Pick any canonical ID from the previous list and ask for a concrete action in plain English. Langswytch works the same way for every service — email, payments, wallets, KYC, messaging, data queries. The pattern is:

```
> <natural-language request referencing a capability in your tooling.json>
```

Concrete examples (replace the service with whatever you have enabled):

```text
> Create a Stripe payment intent for 5000 USD with automatic payment methods.

> Create a Circle developer wallet set named "demo" on ETH-SEPOLIA.

> Start a Persona inquiry with template itmpl_... for reference user-42.

> Send a Slack message to channel #general saying "deploy complete".

> Send an email from onboarding@resend.dev to me@example.com with
  subject "test" and body "hello".
```

Behind the scenes, for **any** of the above, Langswytch:

1. Selects the bound dynamic tool for the right canonical ID (e.g. `payment_intents_payment_intent_create`, `w3s_developer_walletSets_create`, `inquiries_inquiry_create`).
2. Calls `get_tool_info(<canonical_id>)` to read the input schema.
3. Builds a request payload from the schema and the user's natural-language intent.
4. Invokes `swytchcode exec --json` with that payload on stdin.
5. Swytchcode handles auth (from `.env`), makes the HTTP call, and returns the response JSON.
6. The LLM summarizes the result for the user.

Langswytch is service-agnostic. The same six steps run whether the target is Stripe, Circle, Persona, Slack, or anything else in your `tooling.json`.

---

## Core concepts

### Canonical IDs

A **canonical ID** is a stable, globally unique identifier for a single API operation. Examples:

- `emails.email.create` — send an email through Resend.
- `payment_intents.payment_intent.create` — create a Stripe PaymentIntent.
- `w3s.developer.wallets.create` — create a Circle developer wallet.

Canonical IDs are the primary key in Swytchcode. Langswytch never invents them — it discovers them from the local `tooling.json` and calls them by the exact ID. If you ask the agent to do something it doesn't have a canonical ID for, it will either try `discover_capabilities` to search the registry, or tell you it can't proceed.

### Methods and workflows

Both are executable tools:

- **Method** — maps to a single API operation (one HTTP request).
- **Workflow** — an ordered sequence of methods packaged as one callable. The individual steps are hidden from the caller.

Call `swytchcode plan <canonical_id>` to see a workflow's step list. Langswytch exposes a bridge tool `plan_workflow` that wraps this.

### The tooling.json contract

`.swytchcode/tooling.json` is the authoritative declaration of which canonical IDs are enabled for this project. It is:

- Committed to source control.
- Populated by `swytchcode add <canonical_id>` and `swytchcode get <project>`.
- Read on agent startup to build the dynamic tool list.
- Restored from scratch on a fresh checkout with `swytchcode bootstrap`.

You should think of `tooling.json` as a permission boundary. If a canonical ID is not in it, the agent has no way to call that operation.

### The Discover → Provision → Execute model

Langswytch follows the same three-phase pattern Swytchcode uses internally:

1. **Discover** — figure out which canonical ID to use. Preferred order:
   a. Check the currently bound tools (they are listed in the LLM's system prompt automatically).
   b. Call `discover_capabilities(intent)` for semantic search.
   c. Call `search_services(keyword)` for project-name search.
2. **Provision** — if a needed canonical ID is not yet enabled, call `provision_service(service, action_id)`. This runs `swytchcode get <service>` then `swytchcode add <action_id>`.
3. **Execute** — call the tool. Either use the bound dynamic tool directly or call `execute_action(canonical_id, tool_args)`.

The system prompt instructs the LLM to follow this order and never invent canonical IDs.

### Bridge tools versus dynamic tools

Two kinds of tools are bound to the LLM:

| Kind | Count | Purpose | Example |
|------|-------|---------|---------|
| Bridge | 7 | Introspection and lifecycle. Fixed. | `get_tool_info`, `execute_action` |
| Dynamic | Variable | One per enabled canonical ID. Generated at startup from `tooling.json`. | `emails_email_create`, `payment_intents_payment_intent_create` |

Dynamic tools share a permissive args schema (`body`, `header`, `param`, `input`) so the LLM can populate whichever parts of the HTTP request the operation needs. The agent uses `get_tool_info` to learn each tool's actual field requirements on demand.

---

## Guides

### Guide: Run your first action

The flow is identical for every service. Three prerequisites before any real call:

1. The canonical ID you want is enabled in `.swytchcode/tooling.json` (check with `swytchcode list tooling`).
2. The upstream service's credentials are in `.env` (the env-var names Swytchcode expects are listed in the integration's `swytchcode info` output under `http_headers` / auth).
3. Your `OPENAI_API_KEY` is in `.env`.

**Interactive.** Describe the task in plain English, referencing what the target service does. The agent picks the tool.

```
# Stripe
> Create a Stripe payment intent for 5000 USD with automatic payment methods.

# Circle
> Create a Circle developer wallet set named "demo".

# Persona
> Start a Persona inquiry with template itmpl_abc123 for reference user-42.

# Resend
> Send an email from onboarding@resend.dev to me@example.com with
  subject "hello" and body "first test".
```

**Programmatic.** Exact same graph, invoked from Python. Swap the prompt for your target service:

```python
from langgraph_swytchcode_agent import build_agent

agent = build_agent()
result = agent.invoke({
    "messages": [("user", "<your natural-language request>")]
})
print(result["messages"][-1].content)
```

**Discovering what a specific tool wants.** If you're unsure which fields a canonical ID requires, ask the agent:

```
> What are the required input fields for payment_intents.payment_intent.create?
```

The agent calls `get_tool_info` and answers from the live schema. This works for any canonical ID in your `tooling.json` — the agent never guesses; it always reads the real schema from Swytchcode.

**Sandbox notes.** Most providers restrict what you can do with test-mode keys (Stripe refuses live charges, Resend restricts sender domains, Persona limits inquiry templates). If an external call returns a provider-specific validation error, it's almost always a sandbox constraint, not a Langswytch bug. Read the error message — it points to the relevant provider documentation.

### Guide: Add a new service

Say you want the agent to create Stripe PaymentIntents.

```bash
# 1. Find the project in the remote registry
swytchcode search stripe

# 2. (Optional) Find the specific canonical ID by intent
swytchcode discover "create a payment intent"

# 3. Fetch the integration bundle
swytchcode get stripe

# 4. Enable the specific method
swytchcode add payment_intents.payment_intent.create

# 5. Add credentials to .env
echo "STRIPE_API_KEY=sk_test_..." >> .env

# 6. Restart the agent (it re-reads tooling.json at startup)
python langgraph_swytchcode_agent.py
```

Or let the agent provision it live:

```
> I need to create Stripe payment intents. Can you provision that?
```

The LLM will call `provision_service("stripe", "payment_intents.payment_intent.create")` and then `refresh_tools()` on its own.

### Guide: Embed Langswytch in your app

Langswytch is a standard LangGraph graph — you can drop it into any Python service.

**FastAPI example:**

```python
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph_swytchcode_agent import build_agent

app = FastAPI()
agent = build_agent()  # compile once at startup

class ChatRequest(BaseModel):
    message: str
    history: list = []

@app.post("/chat")
def chat(req: ChatRequest):
    messages = req.history + [("user", req.message)]
    result = agent.invoke({"messages": messages})
    # Serialize LangChain messages back to (role, content) tuples for the client
    history = [
        (msg.type if hasattr(msg, "type") else "user", msg.content)
        for msg in result["messages"]
    ]
    return {"reply": result["messages"][-1].content, "history": history}
```

**Streaming:**

```python
for chunk in agent.stream({"messages": [("user", "...")]}):
    print(chunk)
```

**Persistent memory across sessions:**

```python
from langgraph.checkpoint.memory import MemorySaver

graph = build_agent()  # ... or modify build_agent to accept a checkpointer
# See LangGraph docs for attaching a checkpointer to a compiled graph.
```

### Guide: Customize the system prompt

The default system prompt enforces the Discover → Provision → Execute model and forbids inventing canonical IDs. To customize, edit `SYSTEM_PROMPT` at the top of the wiring section in `langgraph_swytchcode_agent.py`.

Common customizations:

- **Domain scoping.** "You only handle tools from the `stripe.*` and `circle.*` projects. Refuse requests targeting other services."
- **Tone.** "Respond in formal business English."
- **Safety.** "Never execute any tool whose canonical_id starts with `raw.`. Always ask for explicit confirmation before running tools that move money."
- **Defaults.** "When a required field is missing, first check the user's earlier messages for the value. If still absent, ask — do not assume."
- **Idempotency.** "For any mutating tool, include an `Idempotency-Key` header derived from the user's turn ID."

Keep the core rules (don't invent canonical IDs, use `.env` for secrets, call `get_tool_info` before executing unfamiliar tools) — removing them degrades reliability.

### Guide: Use a different LLM provider

The agent hard-codes `ChatOpenAI`. To swap:

```python
# Anthropic (Claude)
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0).bind_tools(all_tools)

# Azure OpenAI
from langchain_openai import AzureChatOpenAI
llm = AzureChatOpenAI(azure_deployment="gpt-4o-mini", api_version="2024-10-21").bind_tools(all_tools)

# Local model via Ollama
from langchain_ollama import ChatOllama
llm = ChatOllama(model="llama3.1", temperature=0).bind_tools(all_tools)
```

Requirements for the chosen model:

- Supports LangChain's `bind_tools` / `tool_calls` interface.
- Capable enough to plan multi-step tool invocations (GPT-4o, Claude Sonnet/Haiku 4.5+, Llama 3.1 70B+ work; smaller models will struggle).

---

## API reference

### Python API

All public functions live in `langgraph_swytchcode_agent.py`.

#### `build_agent(model: str = "gpt-4o-mini") -> CompiledGraph`

Builds and returns a compiled LangGraph agent with all bound tools.

- **`model`** — any OpenAI model ID that supports tool calls.
- **Returns** — a `CompiledGraph`. Call `.invoke({"messages": [...]})` or `.stream(...)`.

The graph state is LangGraph's `MessagesState`. Pass messages as either `(role, content)` tuples or `HumanMessage`/`AIMessage`/`ToolMessage` objects.

#### `list_swytch_tools() -> list[dict]`

Returns the currently enabled tools from `.swytchcode/tooling.json`. Each entry is `{"canonical_id": str, "integration": str}`.

#### `build_dynamic_tools() -> list[StructuredTool]`

Returns a list of `StructuredTool` objects — one per enabled canonical ID. The tool name is the canonical ID with non-alphanumeric characters replaced by underscores and truncated to 64 chars.

#### Bridge tools

All seven are regular `@tool`-decorated functions. You can call them directly, or rely on the LLM to call them through the graph.

| Tool | Signature | Wraps |
|------|-----------|-------|
| `discover_capabilities` | `(intent: str, top: int = 5) -> str` | `swytchcode discover <intent> --json --top <n>` |
| `search_services` | `(keyword: str = "") -> str` | `swytchcode search [<keyword>] --json` |
| `get_tool_info` | `(canonical_id: str) -> str` | `swytchcode info <id> --json` |
| `plan_workflow` | `(canonical_id: str) -> str` | `swytchcode plan <id> --json` |
| `provision_service` | `(service_name: str, action_id: str) -> str` | `swytchcode get <svc>` + `swytchcode add <id>` |
| `execute_action` | `(action_id: str, tool_args: dict) -> str` | `swytchcode exec --json` (stdin JSON) |
| `refresh_tools` | `() -> str` | `swytchcode list tooling --json` |

Each returns a JSON string or an `ERROR: ...` message. JSON is always pretty-printed with `indent=2` and truncated to 8000 chars for very large responses.

### Environment variables

| Variable | Required | Default | Meaning |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | — | OpenAI credential for the LLM. |
| `SWYTCHCODE_AGENT_MODEL` | No | `gpt-4o-mini` | Override the model. |
| `SWYTCHCODE_TIMEOUT` | No | `120` | Subprocess timeout (seconds) for each CLI call. |

Service credentials (`RESEND_API_KEY`, `STRIPE_API_KEY`, `CIRCLE_API_KEY`, etc.) must also be in `.env`. `python-dotenv` loads them into `os.environ`; the subprocess inherits them via `env=os.environ`.

### Swytchcode CLI commands used internally

Langswytch invokes the following commands. You don't call them directly — they're documented here for debugging.

| Command | When called | Purpose |
|---------|-------------|---------|
| `swytchcode list tooling --json` | Startup, `refresh_tools()` | Enumerate enabled tools. |
| `swytchcode info <id> --json` | `get_tool_info(...)` | Fetch input/output schema. |
| `swytchcode discover <intent> --json --top <n>` | `discover_capabilities(...)` | Semantic search. |
| `swytchcode search <kw> --json` | `search_services(...)` | Project-name search. |
| `swytchcode plan <id> --json` | `plan_workflow(...)` | Workflow step list. |
| `swytchcode get <svc>` + `swytchcode add <id>` | `provision_service(...)` | Fetch + enable a tool. |
| `swytchcode exec --json` (stdin JSON) | `execute_action(...)` | Run a tool. |

Stdin payload format for `exec`:

```json
{"tool": "<canonical_id>", "args": {"body": {...}, "header": {...}, "param": {...}}}
```

---

## Operations

### Keeping integrations current

Swytchcode's TinyFish agent monitors upstream API changes and produces upgrade proposals.

```bash
# Check for pending proposals. Exit 0 = clean, exit 1 = breaking change.
swytchcode check

# Inspect a proposal before accepting.
swytchcode inspect <library>

# Approve an upgrade (requires swytchcode login).
swytchcode upgrade <library>
```

Guidelines:

- Run `swytchcode check` in CI. Treat exit 1 as a build signal.
- Never auto-approve upgrades. A human should read each proposal.
- After `swytchcode upgrade`, restart the agent so it re-reads schemas.
- Pin the CLI version in CI. Schema evolution can subtly change behavior.

### Security

The agent autonomously executes any tool enabled in `tooling.json` based on LLM decisions driven by user input. **User-provided text can trigger real side effects** — sent emails, created wallets, live payments, sent Slack messages.

Treat agent input the way you treat any untrusted input hitting a privileged action.

**Principle of least privilege.**  Enable only the canonical IDs a given deployment needs. `tooling.json` is the permission boundary. If a surface is not needed, don't add it.

**Separate sandbox and production.**  Use test-mode keys in development (`sk_test_*`, Resend sandbox, Persona sandbox). Maintain separate `.env` files per environment. Never commit real `.env` files.

**Don't expose the raw REPL to end users.**  If you build a user-facing chat UI on top of Langswytch, add your own authorization layer, rate limits, and an allow-list of operations each user is permitted to trigger.

**Mitigate prompt injection.**  If the agent summarizes content it fetched (emails, webhook payloads, scraped pages, KYC document extracts), that content may contain instructions the LLM will follow. Never feed untrusted retrieved data back into the agent's message history without a guard. Sanitize or isolate.

**Audit every call.**  `result["messages"]` contains a complete tool-call trace — which tool, with what arguments, and what it returned. Log this to an append-only store. Alert on anomalies (unexpected tools called, unusual recipients, unexpectedly high-value operations).

**Rotate credentials regularly.**  If an API key is committed to git by accident, rotate immediately. Use your provider's key-scanning (GitHub secret scanning, GitGuardian, TruffleHog) to catch leaks proactively.

### Production considerations

**Concurrency.**  `build_agent()` returns a compiled graph that is safe to share across threads for `.invoke()` calls. Each invocation spawns fresh subprocesses for any tool calls it makes.

**Latency.**  Every tool call forks a `swytchcode` process. On Windows this adds 100–300 ms per call. For high-throughput services, use the Swytchcode MCP server (`swytchcode mcp serve`) and connect via `langchain-mcp-adapters`. Persistent connection eliminates the fork overhead.

**Cost.**  The LLM may make 2–6 tool calls per user turn (discover, info, execute, sometimes retries). A `gpt-4o-mini` conversation averages ~2–5k tokens. Set a `recursion_limit` on the graph if you want to cap worst-case spending per turn.

**Observability.**  Instrument three places:
1. LLM calls — use LangSmith or OpenTelemetry via LangChain's built-in callbacks.
2. Subprocess calls — log command, exit code, duration in `_run_swytchcode`.
3. Upstream API calls — Swytchcode's `--verbose` flag surfaces request and response headers (with secrets redacted).

**Deployment.**  Package the whole project (including `.swytchcode/tooling.json` but not `.swytchcode/integrations/`) into your container. Run `swytchcode bootstrap` in the image build so the integration bundles are present at runtime. Mount `.env` or use your cloud's secret manager.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `openai.OpenAIError: The api_key client option must be set` | No `OPENAI_API_KEY` in `.env` | Add it and restart. |
| `list tooling` returns empty methods/workflows | Fresh checkout without `bootstrap` | Run `swytchcode bootstrap`. |
| Agent answers "no matching tool" for a known service | Canonical ID not enabled | `swytchcode add <canonical_id>` or ask the agent to provision it. |
| Resend returns 403 "domain is not verified" | Unverified sender domain in sandbox | Use `onboarding@resend.dev` as `from`, or verify your domain at [resend.com/domains](https://resend.com/domains). |
| `'charmap' codec can't decode byte ...` on Windows | Python subprocess using cp1252 | Already handled in `_run_swytchcode`. If you see it, your checkout is out of date — pull the latest. |
| Agent retries the same tool 3+ times with empty args | Dynamic tool schema confusion | Already fixed (permissive `_PassthroughArgs`). If it recurs, check `_make_exec_tool` for regressions. |
| REPL shows prompt but no output when piping stdin | Windows `input()` buffering on pipes | Run in an interactive terminal, or use the programmatic API. |
| `swytchcode exec` returns `context canceled` | Upstream HTTP abort (often after rapid retries) | Restart the CLI. Check network. Reduce retry churn with a stricter system prompt. |
| `swytchcode check` exits 1 in CI | Breaking integration update available | Review with `swytchcode inspect <library>`, then `swytchcode upgrade <library>` after testing. |

---

## Glossary

- **Agent** — the compiled LangGraph returned by `build_agent()`. Stateful within a turn, stateless across turns unless you attach a checkpointer.
- **Bridge tool** — a Python `@tool` function that wraps a Swytchcode CLI command. Seven of them; fixed.
- **Canonical ID** — globally unique identifier for an API operation (e.g. `emails.email.create`).
- **Dynamic tool** — a `StructuredTool` generated at startup, one per enabled canonical ID.
- **Integration** — a Swytchcode package for a single upstream service (e.g. `resend.resend@v1.5.0`).
- **Langswytch** — this project. The LangGraph + Swytchcode adapter.
- **Method** — a canonical ID that maps to one API operation (one HTTP call).
- **Provision** — the act of fetching an integration bundle (`swytchcode get`) and enabling a specific operation (`swytchcode add`).
- **Swytchcode** — the underlying CLI and execution kernel. Langswytch shells out to it for every real call.
- **Tooling.json** — `.swytchcode/tooling.json`. Declares which canonical IDs are enabled in this project.
- **Workflow** — a canonical ID that maps to an ordered sequence of methods.

---

## Changelog

**v0.1.0** — Initial release.
- LangGraph agent with OpenAI LLM.
- Dynamic tool binding from `tooling.json`.
- Seven bridge tools: discover, search, info, plan, provision, execute, refresh.
- Permissive dynamic-tool args schema (`body`, `header`, `param`, `input`).
- Windows-safe subprocess encoding.

---

## Further reading

- [Swytchcode documentation](https://docs.swytchcode.com) — CLI reference, MCP server, integration catalog.
- [LangGraph documentation](https://langchain-ai.github.io/langgraph/) — graph patterns, checkpointing, streaming.
- [LangChain tool-calling guide](https://python.langchain.com/docs/concepts/tool_calling/) — how `bind_tools` works under the hood.
