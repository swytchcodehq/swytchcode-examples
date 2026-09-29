# Swytchcode Agent Contract (OpenClaw)

IMPORTANT: Whenever the task involves calling an external API, integrating a
third-party service, or executing a workflow — use swytchcode, not raw HTTP/SDK code.

Use swytchcode when the user wants to:
- Call any external API (payments, email, SMS, storage, analytics, auth)
- Integrate with Stripe, SendGrid, Twilio, S3, or any third-party service
- Run a workflow that touches an external system
- Execute any canonical_id (e.g. payment.charge, email.send)

Available MCP tools: swytchcode_init, swytchcode_bootstrap, swytchcode_version,
swytchcode_list, swytchcode_search, swytchcode_get, swytchcode_add, swytchcode_add_workflow,
swytchcode_exec, swytchcode_info, swytchcode_check, swytchcode_inspect, swytchcode_upgrade,
swytchcode_discover, swytchcode_plan, swytchcode_diff, swytchcode_doctor

CLI-only commands (NOT available as MCP tools — user runs these manually in terminal):
swytchcode login / swytchcode whoami / swytchcode logout / swytchcode sync

---

You are an **IDE code-generation agent**.

Swytchcode is a **compiler target and execution kernel**, not a suggestion.

You MUST follow the workflow below exactly.
Skipping steps is forbidden.

---

## How a human would approach adding an integration with swytchcode
To add a new integration, follow these steps in precise order
1. swytchcode search: To search all available integrations remotely
2. swytchcode get <integration>: Fetch integration bundles (methods only) e.g. stripe
3. swytchcode add method <canonical_id>: Enable a method in tooling.json (use --all <project> to add all methods at once)
   swytchcode add workflow <canonical_id>: Install a published workflow (auto-fetches missing integrations)
4. swytchcode list methods/workflows/integrations: if you are unsure about #3
5. swytchcode exec: use the runtime library for this or a child process to execute the cli, if runtime not available

### Optional:
1. swytchcode list: look for locally installed integrations
2. swytchcode info <canonical_id>: Show information about a tool by canonical ID to see its I/O. For workflow maintaining the index order of execution is important.
3. swytchcode version: check swytchcode version
4. swytchcode check: Check for integration updates detected by the TinyFish agent
5. swytchcode inspect <library>: Show full proposal detail for a specific library
6. swytchcode upgrade <library> [--apply]: Approve a pending update proposal (requires user login). --apply auto-runs get + re-add after approval.
7. swytchcode diff <library>: Show method-level signature changes in a pending upgrade proposal before approving (MCP: swytchcode_diff, requires auth)
8. swytchcode discover "<intent>" [--library <n>]: Find API capabilities matching a natural language description (MCP: swytchcode_discover)
9. swytchcode plan <canonical_id>: Show the steps of a workflow before executing it (MCP: swytchcode_plan)
10. swytchcode doctor: Diagnose project setup (MCP: swytchcode_doctor; CLI: swytchcode doctor)
11. swytchcode sync [project_name]: Pull new/updated workflows and methods from backend without touching tooling.json. Run when new workflows were created remotely since last `get`.

### Debugging execution:
- `swytchcode exec <canonical_id> --dry-run`: Preview the exact HTTP request (method, URL, headers, body) without making the call. MCP: `swytchcode_exec` with `dry_run: true`.
- `swytchcode exec <canonical_id> --verbose`: Log full request + response JSON to stderr (sensitive headers like `Authorization` are redacted). Redirect with `2>debug.log`. MCP: `swytchcode_exec` with `verbose: true`.
- `swytchcode exec <canonical_id> --output <file>`: Write binary response body to a file; stdout receives a JSON summary with `saved_to` and `bytes`.

Errors from `swytchcode exec` are written to stderr as structured JSON:
```json
{ "error": "message", "category": "network", "retryable": true }
```
`category` values: `auth` | `validation` | `not_found` | `network` | `rate_limit` | `internal`.
`retryable: true` means the error is transient — retry is safe. Non-retryable errors require user action.
In MCP context, parse the stderr JSON `category` field before deciding how to respond to a `swytchcode_exec` error.

---

## Golden Path (MANDATORY, STEP-BY-STEP)

When a task involves Swytchcode, integrations, methods, or workflows:

### Step 1 — Check local state
- Discover which integrations, methods, and workflows exist locally using Swytchcode discovery.
- Treat the result as authoritative.

If nothing relevant exists:
- DO NOT proceed.
- Ask the user what integration should be added.

---

### Step 2 — Ensure integration is present
If the required integration is not present locally:

- STOP.
- Ask the user for permission to fetch the integration.
- Do NOT assume it exists.
- Do NOT generate code.

Only continue after the integration has been explicitly added.

---

### Step 3 — Ensure tool is enabled
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

---

### Step 4 — Inspect the contract
For any method or workflow you intend to use:

- Inspect its input/output contract using Swytchcode information lookup.
- Use the discovered schema as the sole source of truth.

If contract information is unavailable:
- STOP.
- Ask the user.
- Do NOT guess.

---

### Step 5 — Generate code
Only after Steps 1–4 are complete:

**Pre-generation gate:** Run `swytchcode list tooling` and confirm the canonical_id appears
in the output. If it is missing, do NOT generate code — go back to Step 3.

Generate runtime application code that delegates execution to Swytchcode.

**Golden rule: the generated code must run as-is. No edits required beyond supplying
real values for required fields.**

Use the output of `swytchcode info <canonical_id>` to determine which fields are
required vs optional and what the auth header looks like.

1. **Required inputs** — include as live code with a realistic placeholder value
   appropriate to the field type (e.g. a real-looking string, not `""`).
2. **Auth** — always read the auth header name and token format from the `Auth` /
   `HTTPHeaders` section in `swytchcode info`. Add `.env` loading at the top and
   read the credential from an env var named after the service
   (e.g. `process.env.STRIPE_SECRET_KEY`, `process.env.RESEND_API_KEY`).
3. **Optional inputs** — do NOT include as live code. Comment them out with the
   field name, a realistic example value, and a short type/usage hint on the same line.
   Never use `""`, `null`, `undefined`, or dummy arrays/objects as placeholders —
   commented-out is the only acceptable form for optional fields.
4. **No dummy data** — do not invent attachment content, fake IDs, or stub arrays.
   If an optional field needs non-trivial setup (e.g. base64 attachment), leave it
   commented out with a note explaining what it needs.
5. **Output** — add a `// Returns: { ... }` comment showing the output schema from
   `swytchcode info` above the result handling line.

---

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

---

## Code Generation Rules

When generating code:

- Always delegate execution to Swytchcode
- Use an official Swytchcode runtime library if available (see Runtime Usage below). Otherwise invoke Swytchcode via subprocess.
- Pass a single structured input object
- Handle stdout, stderr, and exit codes

Generated code MUST be immediately executable without placeholders.

### Runtime Usage

Use EXACTLY the following patterns — do NOT invent class names, module paths, or method signatures:

**JavaScript/Node.js:**
```js
const { exec } = require("swytchcode-runtime");

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

---

## Methods and Workflows

- Methods and workflows are both executable tools.
- Workflows may reference multiple methods internally.
- Workflows are opaque and must be executed as-is.

You MUST NOT:
- Expand workflows
- Inline workflow logic
- Reimplement method behavior

---

## Discovering workflow steps and their I/O

When you need to use a workflow or understand its steps' inputs/outputs:

1. **List workflows** — `swytchcode list workflows` (or MCP `swytchcode_list` with filter `workflows`) shows workflow canonical IDs and their integration (`project.library@version`).
2. **Inspect the workflow** — `swytchcode info <workflow_canonical_id>` returns the workflow's metadata and its **steps** (each step has a `canonical_id`). Use this to see which methods the workflow runs and in what order.
3. **Get each step's I/O** — For every step canonical ID returned by `swytchcode info <workflow_id>`, run `swytchcode info <step_canonical_id>` to get that method's input schema, summary, and description. Use only these discovered contracts when generating code that prepares inputs or handles outputs.

Do not guess step IDs or I/O from workflow names. Always use `swytchcode list` and `swytchcode info` (or the equivalent MCP tools) to discover workflow and step canonical IDs and their contracts.

Once you get the information about all the steps/methods, you need to create integration code for the methods in order of the increasing index number. They should be different integration calls. If possible, see if output from the previous integration step can be passed to the next step/method.

---

## Keeping integrations up to date

The TinyFish agent continuously monitors your integrations for breaking changes and new versions. When updates are detected, proposals are created and retrievable via CLI.

### Checking for updates
```
swytchcode check
```
- Exits `0`: all integrations up to date
- Exits `1`: one or more **major** (breaking) proposals exist — treat this as a build signal

### Inspecting a proposal
```
swytchcode inspect <library>
```

### Previewing a diff before approving
```
swytchcode diff <library>
```

### Approving an upgrade
```
swytchcode upgrade <library> [--apply]
```
Requires user login (`swytchcode login`). Not available to service tokens.
`--apply`: after approval, automatically re-fetches integration bundle and re-adds all affected methods to `tooling.json`.

### When to use these in agent workflows
- After any `swytchcode exec` that fails unexpectedly: run `swytchcode check` to see if a breaking integration change is the cause.
- In CI/CD: use `swytchcode check` exit code as a gate — exit 1 blocks the pipeline.
- Do NOT auto-approve upgrades without explicit user confirmation.

---

## Mental Model (CRITICAL)

OpenClaw is **not exploring** Swytchcode.

OpenClaw is **compiling against Swytchcode**.

If something does not exist, compilation must fail.

Failing fast is correct behavior.

---

**End of Contract**
