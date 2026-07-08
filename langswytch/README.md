# Langswytch

> A LangGraph agent that turns natural language into real API calls, with [Swytchcode](https://cli.swytchcode.com) as the execution kernel that actually runs them.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Built on LangGraph](https://img.shields.io/badge/built%20on-LangGraph-1c3c3c)](https://langchain-ai.github.io/langgraph/)
[![Execution kernel: Swytchcode](https://img.shields.io/badge/execution-Swytchcode-5b2bd6)](https://cli.swytchcode.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

You write a prompt. Langswytch picks the right tool, reads its real schema, builds the request, and hands execution to Swytchcode, which handles auth, retries, and the HTTP call. The agent never touches a third-party API directly.

---

## Why not just call APIs directly?

An LLM that calls APIs straight from its own reasoning hallucinates endpoints, invents field names, and leaves no record of what it did. Langswytch removes that whole class of failure: the agent decides *what* to do, and Swytchcode owns *how* it runs. Every operation is a stable canonical ID looked up from a schema registry, so the agent calls real methods with validated inputs instead of guessing. The result is one conversational interface over 2,000+ integrations (Stripe, Resend, Circle, Persona, Slack, and more) without a single hand-written API wrapper.

---

## How it works

Langswytch follows the same three phases Swytchcode uses internally:

```
Discover  ──►  Provision  ──►  Execute
   │              │               │
   │              │               └─ run the tool through `swytchcode exec`;
   │              │                  Swytchcode handles auth, HTTP, retries
   │              └─ if a needed canonical ID isn't enabled yet, fetch the
   │                 integration (`swytchcode get`) and add it (`swytchcode add`)
   └─ find the right canonical ID: check bound tools first, then semantic
      search (`discover_capabilities`), then project search (`search_services`)
```

At startup the agent reads `.swytchcode/tooling.json`, binds each enabled canonical ID to the LLM as a typed tool, and adds seven bridge tools for introspection and provisioning. On every turn it picks a tool, optionally reads the live schema with `get_tool_info`, then executes. The full tool-call trace lives in `result["messages"]` as an audit record.

```
user prompt
     │
     ▼
LangGraph agent (OpenAI)
     │  • 7 bridge tools (discover, search, info, plan, provision, execute, refresh)
     │  • N dynamic tools, one per enabled canonical ID
     ▼
Swytchcode CLI (execution kernel) ── auth · HTTP · retries
     │
     ▼
Upstream API (Resend, Stripe, Circle, Persona, Slack, ...)
```

---

## Quickstart

### Prerequisites

- Python 3.10+
- Node.js (the Swytchcode CLI installs via npm)
- An OpenAI API key for a model that supports tool calls

### Install and run

```bash
# 1. From the project directory:
cd langswytch

# 2. Install the Swytchcode CLI
npm install -g swytchcode

# 3. Fetch the integrations declared in .swytchcode/tooling.json
swytchcode bootstrap

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Create your .env from the template, then set OPENAI_API_KEY
cp .env.example .env

# 6. Start the agent
python langgraph_swytchcode_agent.py
```

### Use it from the REPL

```
Adaptive Action Agent ready. Type a request (Ctrl-C to exit).

> List the canonical IDs you currently have enabled, grouped by service.

> Send an email from onboarding@resend.dev to me@example.com with
  subject "test" and body "hello from the agent".
```

The agent answers capability questions from the tool set it bound at startup (no external call), and runs real operations against whatever you have enabled. It will not invent a canonical ID. If it can't find a matching tool, it searches the registry or tells you it can't proceed.

> **Windows note:** run in a real terminal, not piped/redirected stdin. `input()` buffering on Windows pipes swallows output. The programmatic API below is unaffected.

### Use it from Python

```python
from langgraph_swytchcode_agent import build_agent

agent = build_agent()  # compiles once; reuse across requests

result = agent.invoke({
    "messages": [
        ("user", "Send an email from onboarding@resend.dev to me@example.com "
                 "with subject 'hi' and body 'hello'."),
    ]
})

print(result["messages"][-1].content)  # natural-language summary from the LLM
```

`build_agent()` returns a standard compiled LangGraph whose state is `MessagesState`. Keep the same `messages` list across turns to preserve history, stream with `.stream()`, or attach a checkpointer. It reads the enabled tool set at call time, so rebuild the agent (or have it call `refresh_tools()`) after you add or remove tools via the CLI.

---

## Configuration

All variables are read from `.env`. Only `OPENAI_API_KEY` is required.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | (none) | Auth for the LLM. |
| `SWYTCHCODE_AGENT_MODEL` | No | `gpt-4o-mini` | Any OpenAI model that supports tool calls. |
| `SWYTCHCODE_TIMEOUT` | No | `120` | Subprocess timeout in seconds for each CLI call. |

Service credentials (`RESEND_API_KEY`, `STRIPE_API_KEY`, `CIRCLE_API_KEY`, and so on) also go in `.env`, matching what is enabled in `.swytchcode/tooling.json`. `python-dotenv` loads them into `os.environ` and the CLI subprocess inherits them. Keep test-mode keys in development and never commit a real `.env`.

---

## Adding a new integration

```bash
swytchcode search stripe                        # find matching projects
swytchcode discover "create a payment intent"   # semantic search by intent
swytchcode get stripe                           # fetch the integration bundle
swytchcode add payment_intents.payment_intent.create   # enable a specific method
python langgraph_swytchcode_agent.py            # restart; tooling.json is re-read
```

Or let the agent do it live: ask it to *"provision stripe and enable payment_intents.payment_intent.create"* and it will call `provision_service` then `refresh_tools` itself.

---

## Documentation

This README is the orientation. For the full reference, see [DOCUMENTATION.md](./DOCUMENTATION.md):

- Core concepts: canonical IDs, methods vs workflows, the `tooling.json` contract
- Guides: add a service, embed in FastAPI, customize the system prompt, swap the LLM provider
- API reference: `build_agent`, the seven bridge tools, environment variables, the internal CLI commands
- Operations: keeping integrations current, security, production concerns
- Troubleshooting and glossary

---

## Demo collection

Langswytch is part of the Swytchcode demo collection. Related runnable examples:

- [openclaw-swytchcode-demo](https://github.com/swytchcodehq/openclaw-swytchcode-demo): OpenClaw agent plus Swytchcode for GitHub issue triage (Go)
- [Stripe-Subscriptions](https://github.com/swytchcodehq/Stripe-Subscriptions): subscription lifecycle services on the Swytchcode runtime (TypeScript)
- [swytchcode-google-analytics](https://github.com/swytchcodehq/swytchcode-google-analytics): Google Analytics reporting built on the Swytchcode CLI (TypeScript)
- [Weekly-Reporting-Langgraph](https://github.com/swytchcodehq/Weekly-Reporting-Langgraph), [Customer-Onboarding-Langgraph](https://github.com/swytchcodehq/Customer-Onboarding-Langgraph), [Lead-Qualification-Langgraph](https://github.com/swytchcodehq/Lead-Qualification-Langgraph), [Bug-Escalation-Langgraph](https://github.com/swytchcodehq/Bug-Escalation-Langgraph), [Create-And-Send-Payment-Langgraph](https://github.com/swytchcodehq/Create-And-Send-Payment-Langgraph): single-purpose LangGraph agents

---

## License

MIT. See [LICENSE](./LICENSE).
