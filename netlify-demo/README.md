# Netlify Ops Agent (Swytchcode + OpenAI Agents SDK)

A tiny demo agent that manages a Netlify site over chat. Given one prompt, it
decides on its own which Netlify operations to call, in what order, and
chains the results together:

1. **Create a site** (`netlify.site.create`)
2. **Trigger a deploy** for it (`netlify.site.deploys.create`)
3. **Check the account's build status**, using the account ID returned by
   step 1 (`netlify.build.status.get`)

## Prerequisites

- Node.js 22 or later
- The [Swytchcode CLI](https://cli.swytchcode.com) installed (`swytchcode` /
  `swy`)
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Netlify Personal Access Token](https://app.netlify.com/user/applications#personal-access-tokens)

## Setup

**1. Log in to Swytchcode**

```bash
swytchcode login
```

**2. Install dependencies**

```bash
npm install
```

**3. Fetch the integrations this project needs**

The methods this demo uses are already declared in `tooling.json` (checked
into this repo) - you just need to pull down the integration bundles:

```bash
swytchcode bootstrap
```

**4. Connect your Netlify account**

Netlify auth is handled by Swytchcode itself, not by a `.env` variable. This
opens an inline prompt for your Netlify token:

```bash
swytchcode auth connect netlify --type api_key
```

Paste the Personal Access Token you generated above when prompted. Verify it
worked:

```bash
swytchcode auth status
```

You should see a `netlify` row with `type: api_key`.

**5. Add your OpenAI key**

Copy `.env.example` to `.env` (or create `.env` directly) and set:

```
OPENAI_API_KEY=sk-...
```

## Run it

```bash
node main.ts
```

You should see output like:

```
Done.

- Site: `swytchcode-demo-2`
- Deploy triggered on branch: `main`
- Account build status: active: 0, enqueued: 0, pending_concurrency: 0
```

Heads up: every run creates a **real** site in your Netlify account. Delete
the test sites from your Netlify dashboard once you're done poking around.

## How it works

`main.ts` wires up three pieces:

- **`@swytchcode/runtime`** - fetches the enabled Netlify tools and executes
  them (`swytchcode exec` under the hood) when the model calls them.
- **`@openai/agents`** - the OpenAI Agents SDK; runs the actual tool-calling
  loop.
- **`OpenAIAgentsProvider`** - adapts Swytchcode's tools into the shape the
  Agents SDK expects.

```ts
const swx = new Swytchcode(new OpenAIAgentsProvider());
const tools = await swx.tools.get({ tools: [ /* canonical IDs */ ] });
const agent = new Agent({ name: '...', instructions: '...', tools });
const result = await run(agent, 'your prompt here');
```

To change what the demo does, edit the prompt passed to `run(...)` in
`main.ts` - the agent will pick different tools based on what you ask for.

## Policies

Swytchcode can guard specific tool calls with policies - rules that are
checked before a call executes, and block it if the condition matches.

This demo ships with one:

| Policy                        | Target                        | Condition          | Action  |
| ------------------------------ | ------------------------------ | ------------------- | ------- |
| No Production Deploys via Agent | `netlify.site.deploys.create` | `production == true` | Blocked |

This means the agent can trigger preview/branch deploys on its own, but can
never push straight to production - that always has to go through your
normal deploy pipeline.

### Add a policy

```bash
swytchcode policy add
```

This walks you through it interactively: policy name, which tool(s) to
guard, which field on that tool to check, the operator and value to compare
it against, and what should happen when it matches.

### List policies

```bash
swytchcode policy list
```

### Remove a policy

```bash
swytchcode policy remove <policy-id>
```

### Validate policies

```bash
swytchcode policy validate
```

## Troubleshooting

- **`401 Access Denied` from Netlify** - your token isn't connected or is
  invalid. Re-run `swytchcode auth connect netlify --type api_key` and
  double check the token works by generating a fresh one if needed.
- **Multiple `netlify` rows in `swytchcode auth status`** - connect a new,
  distinctly labeled account instead of fighting with duplicates:
  `swytchcode auth connect netlify --type api_key --label netlify-fresh --set-default`
