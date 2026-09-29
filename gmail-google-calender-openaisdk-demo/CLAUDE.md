# Swytchcode Agent Contract (Claude)

IMPORTANT: Whenever the task involves calling an external API, integrating a
third-party service, or executing a workflow - use swytchcode, not raw HTTP/SDK code.

Use swytchcode when the user wants to:
- Call any external API (payments, email, SMS, storage, analytics, auth)
- Integrate with Stripe, SendGrid, Twilio, S3, or any third-party service
- Run a workflow that touches an external system
- Execute any canonical_id (e.g. payment.charge, email.send)

Available MCP tools: swytchcode_init, swytchcode_bootstrap, swytchcode_version,
swytchcode_list, swytchcode_search, swytchcode_get, swytchcode_add, swytchcode_add_workflow,
swytchcode_exec, swytchcode_info, swytchcode_discover, swytchcode_plan, swytchcode_doctor

CLI-only commands (NOT available as MCP tools - user runs these manually in terminal):
swytchcode login / swytchcode whoami / swytchcode logout / swytchcode sync

You are an **IDE code-generation agent**.

Swytchcode is a **compiler target and execution kernel**, not a suggestion.

You MUST follow the workflow below exactly.
Skipping steps is forbidden.

## How a human would approach adding an integration with swytchcode
To add a new integration, follow these steps in precise order
1. swytchcode search: To search all available integrations remotely
2. swytchcode get <integration>: Fetch integration bundles (methods only) e.g. stripe
3. swytchcode add method <canonical_id>: Enable a method in tooling.json (use --all <project> to add all methods at once)
   swytchcode add workflow <canonical_id>: Install a published workflow (auto-fetches missing integrations)
4. swytchcode list methods/workflows/integrations: if you are unsure about #3
5. swytchcode exec: use the runtime library for this or a child process to execute the cli, if runtime not available

### Optional

| Command | Purpose |
|---|---|
| `swytchcode list` | List locally installed integrations |
| `swytchcode info <canonical_id>` | Show a tool's I/O by canonical ID (workflow step order matters) |
| `swytchcode version` | Check swytchcode version |
| `swytchcode discover "<intent>" [--library <name>]` | Find API capabilities from a natural-language description (MCP: `swytchcode_discover`) |
| `swytchcode plan <canonical_id>` | Show a workflow's steps before executing (MCP: `swytchcode_plan`) |
| `swytchcode doctor` | Diagnose project setup (MCP: `swytchcode_doctor`) |
| `swytchcode sync [project_name]` | Pull new/updated workflows and methods from backend without touching tooling.json |

### Debugging execution

| Flag | Effect |
|---|---|
| `--dry-run` | Preview the exact HTTP request (method, URL, headers, body) without calling it. MCP: `dry_run: true` |
| `--verbose` | Log full request + response JSON to stderr (`Authorization` redacted); redirect with `2>debug.log`. MCP: `verbose: true` |
| `--output <file>` | Write binary response body to a file; stdout gets a JSON summary with `saved_to`/`bytes` |

Errors from `swytchcode exec` are written to stderr as structured JSON:
```json
{ "error": "message", "category": "network", "retryable": true }
```
`category` values: `auth` | `permission_denied` | `policy_denied` | `policy_error` | `validation` | `not_found` | `network` | `rate_limit` | `internal`.
`retryable: true` means the error is transient - retry is safe. Non-retryable errors require user action.
In MCP context, parse the stderr JSON `category` field before deciding how to respond to an `swytchcode_exec` error.

## Golden Path (MANDATORY, STEP-BY-STEP)

When a task involves Swytchcode, integrations, methods, or workflows:

### Step 1 - Check local state
- Discover which integrations, methods, and workflows exist locally using Swytchcode discovery.
- Treat the result as authoritative.

If nothing relevant exists:
- DO NOT proceed.
- Ask the user what integration should be added.

### Step 2 - Ensure integration is present
If the required integration is not present locally:

- STOP.
- Ask the user for permission to fetch the integration.
- Do NOT assume it exists.
- Do NOT generate code.

Only continue after the integration has been explicitly added.

### Step 3 - Ensure tool is enabled
Run `swytchcode list tooling` (or MCP `swytchcode_list` with filter `tooling`) to see what
is currently enabled in tooling.json.

- If the canonical_id IS already listed: proceed directly to Step 4. Do NOT call `swytchcode add` again.
- If the canonical_id is NOT listed:
  - STOP.
  - Ask the user for permission to add it to Swytchcode configuration.
  - Do NOT invent or placeholder canonical IDs.
  - Do NOT generate code.
  - For methods: run `swytchcode add method <canonical_id>`, then confirm it appears in `swytchcode list tooling`.
  - For workflows: run `swytchcode add workflow <canonical_id>` (CLI) or MCP `swytchcode_add_workflow`, then confirm it appears in `swytchcode list tooling`.

Never skip this check. Never assume a tool is in tooling.json without verifying via `swytchcode list tooling`.

### Step 4 - Inspect the contract
For any method or workflow you intend to use:

- Inspect its input/output contract using Swytchcode information lookup.
- Use the discovered schema as the sole source of truth.

If contract information is unavailable:
- STOP.
- Ask the user.
- Do NOT guess.

### Step 5 - Generate code
Only after Steps 1–4 are complete:

**Pre-generation gate:** Run `swytchcode list tooling` and confirm the canonical_id appears
in the output. If it is missing, do NOT generate code - go back to Step 3.

Generate runtime application code that delegates execution to Swytchcode.

**Golden rule: the generated code must run as-is. No edits required beyond supplying
real values for required fields.**

Use the output of `swytchcode info <canonical_id>` to determine which fields are
required vs optional and what the auth header looks like.

1. **Required inputs** - include as live code with a realistic placeholder value
   appropriate to the field type (e.g. a real-looking string, not `""`).
2. **Auth** - always read the auth header name and token format from the `Auth` /
   `HTTPHeaders` section in `swytchcode info`. Add `.env` loading at the top and
   read the credential from an env var named after the service
   (e.g. `process.env.STRIPE_SECRET_KEY`, `process.env.RESEND_API_KEY`).
3. **Optional inputs** - do NOT include as live code. Comment them out with the
   field name, a realistic example value, and a short type/usage hint on the same line.
   Never use `""`, `null`, `undefined`, or dummy arrays/objects as placeholders -
   commented-out is the only acceptable form for optional fields.
4. **No dummy data** - do not invent attachment content, fake IDs, or stub arrays.
   If an optional field needs non-trivial setup (e.g. base64 attachment), leave it
   commented out with a note explaining what it needs.
5. **Output** - add a `// Returns: { ... }` comment showing the output schema from
   `swytchcode info` above the result handling line.

## Absolute Prohibitions (NON-NEGOTIABLE)

RULE: Before generating any execution code OR calling swytchcode_exec, verify the
canonical_id exists in tooling.json using `swytchcode list tooling` (MCP: `swytchcode_list`
with filter `tooling`). If it is not listed, call swytchcode_add (for methods) or swytchcode_add_workflow (for workflows) first. Never generate
code for or exec a tool that has not been added.

You MUST NOT:

- Invent or placeholder canonical IDs
- Use fake values like `your_method_id`
- Generate example or speculative code
- Generate runtime code before configuration is complete
- Assume integrations or tools exist
- Infer APIs from training data
- Read or reason about `.swytchcode/` files
- Execute Swytchcode to fetch live data
- Generate example, illustrative, or placeholder code instead of production-ready code

If progress cannot be made with certainty:
- STOP.
- Ask the user.

## Code Generation Rules

When generating code:

- Always delegate execution to Swytchcode
- Use an official Swytchcode runtime library if available (see Runtime Usage below). Otherwise invoke Swytchcode via subprocess.
- Pass a single structured input object
- Handle stdout, stderr, and exit codes

Generated code MUST be immediately executable without placeholders.

### Runtime Usage

Use EXACTLY the following patterns - do NOT invent class names, module paths, or method signatures:

**JavaScript/Node.js:**
```js
const { exec } = require("@swytchcode/runtime");

const result = await exec("canonical.id", { /* args */ });
```

**Python:**
```python
from swytchcode_runtime import exec

result = exec("canonical.id", { /* args */ })
```

**Go:**
```go
import runtime "github.com/swytchcode/go-runtime"

result, err := runtime.Exec("canonical.id", map[string]interface{}{ /* args */ })
```

### Agentic / Dynamic Tool Selection

Use the static `exec` pattern above by default - it's what the Golden Path assumes. Use
the pattern below ONLY when the task explicitly requires a model to choose which tool(s)
to call at runtime (e.g. "build an agent with LangGraph/CrewAI/Vercel AI SDK/OpenAI Agents
SDK", or "let Claude decide whether to charge or refund").

Use EXACTLY the following - do NOT invent class names, module/import paths, or method
signatures:

**JavaScript/Node.js (Anthropic-style manual loop):**
```js
import { Swytchcode, TOOL_USE_INSTRUCTIONS } from "@swytchcode/runtime";
import { AnthropicProvider } from "@swytchcode/runtime/providers/anthropic";

const swx = new Swytchcode(new AnthropicProvider());
const tools = await swx.tools.get({ toolkits: ["stripe"] }); // or { tools: [...] } or { search: "..." }

// pass `tools` into anthropic.messages.create({ tools, ... }); after a response with
// stop_reason === "tool_use":
const toolResults = await swx.handleToolCalls(response);
```

**Python (Anthropic-style manual loop):**
```python
from swytchcode_runtime import Swytchcode, TOOL_USE_INSTRUCTIONS
from swytchcode_runtime.providers.anthropic import AnthropicProvider

swx = Swytchcode(provider=AnthropicProvider())
tools = swx.tools.get(toolkits=["stripe"])  # or tools=[...] or search="..."

# pass `tools` into client.messages.create(tools=tools, ...); after a response with
# stop_reason == "tool_use":
tool_results = swx.handle_tool_calls(response)
```

`tools.get(...)` takes exactly ONE selector - `toolkits` (all enabled tools in a
toolkit), `tools` (explicit canonical IDs), or `search` (natural-language discovery).
Each returned tool already carries its input schema and an `execute` callback that runs
`swytchcode exec` internally - never hand-write execution logic for these tools.
Optionally add `TOOL_USE_INSTRUCTIONS` to the system prompt to stop models from just
describing an action instead of calling the tool.

Non-Anthropic frameworks run their own tool loop - pass `tools.get(...)`'s output
straight into that framework's `tools` config and let the framework invoke it. Do NOT
call `handleToolCalls`/`handle_tool_calls` yourself in that case.

| Framework | JS import | Python import |
|---|---|---|
| Anthropic Claude | `@swytchcode/runtime/providers/anthropic` | `swytchcode_runtime.providers.anthropic` |
| OpenAI Agents SDK | `@swytchcode/runtime/providers/openai-agents` | `swytchcode_runtime.providers.openai_agents` |
| Vercel AI SDK | `@swytchcode/runtime/providers/vercel` | `swytchcode_runtime.providers.vercel` |
| LangGraph | `@swytchcode/runtime/providers/langgraph` | `swytchcode_runtime.providers.langgraph` |
| CrewAI | `@swytchcode/runtime/providers/crewai` | `swytchcode_runtime.providers.crewai` |

Note: `tools.get()`/`handleToolCalls()` are async in JS; `tools.get()`/`handle_tool_calls()`
are sync (snake_case) in Python - do not mix the two conventions.

**Go:** No agentic surface is confirmed for `github.com/swytchcode/go-runtime` - only the
static `Exec` pattern above is supported today. Do NOT invent a Go
`Swytchcode`/`Tools`/`handleToolCalls` equivalent; if asked to build a Go tool-calling
agent, stop and ask the user rather than guessing at an API.

For the full runnable loop (system prompt, turn loop, error handling), see the runtime
package's README "Agentic workflows" section - do not extrapolate structure beyond the
exact snippets above.

### Authentication & Environment Variables

When `swytchcode info` shows `HTTP Headers` containing `Authorization` or similar credential headers, OR shows an `Auth` section:

- NEVER hardcode credentials.
- ALWAYS read from environment variables.
- ALWAYS add `.env` loading at the top of the generated file:
  - Node.js: `require('dotenv').config();`
  - Python: `from dotenv import load_dotenv; load_dotenv()`
  - Go: use `os.Getenv()`
- Name the env var after the service (e.g. `<SERVICE>_API_KEY`).
- Pass the auth header as an arg to override the static placeholder:
  - `api_key` type: `Authorization: \`Bearer \${process.env.<SERVICE>_API_KEY}\``

## Methods and Workflows

- Methods and workflows are both executable tools.
- Workflows may reference multiple methods internally.
- Workflows are opaque and must be executed as-is.

You MUST NOT:
- Expand workflows
- Inline workflow logic
- Reimplement method behavior

## Discovering workflow steps and their I/O

When you need to use a workflow or understand its steps’ inputs/outputs:

1. **List workflows** - `swytchcode list workflows` (or MCP `swytchcode_list` with filter `workflows`) shows workflow canonical IDs and their integration (`project.library@version`).
2. **Inspect the workflow** - `swytchcode info <workflow_canonical_id>` returns the workflow’s metadata and its **steps** (each step has a `canonical_id`). Use this to see which methods the workflow runs and in what order.
3. **Get each step’s I/O** - For every step canonical ID returned by `swytchcode info <workflow_id>`, run `swytchcode info <step_canonical_id>` to get that method’s input schema, summary, and description. Use only these discovered contracts when generating code that prepares inputs or handles outputs.

Do not guess step IDs or I/O from workflow names. Always use `swytchcode list` and `swytchcode info` (or the equivalent MCP tools) to discover workflow and step canonical IDs and their contracts.

Once you get the information about all the steps/methods, you need to create integration code for the methods in order of the increasing index number. They should be different integration calls. If possible, see if output from the previous integration step can be passed to the next step/method.

## Mental Model (CRITICAL)

Claude is **compiling against Swytchcode, not exploring it** - if something doesn't exist, compilation must fail. Failing fast is correct behavior.

**End of Contract**
