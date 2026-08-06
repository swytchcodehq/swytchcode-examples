# Gmail Assistant - Anthropic SDK (TypeScript)

An AI agent that searches, reads, marks as read, drafts, and sends Gmail messages through the Swytchcode CLI. You never write custom API integration code, JSON tool schemas, or OAuth token refresh logic. Swytchcode provides ready-to-use tool definitions and handles Gmail authorization securely via WorkOS OAuth.

The agent integration requires only two Swytchcode lines; everything else is standard Anthropic tool-use loop boilerplate in `src/index.ts`.

```typescript
const swx = new Swytchcode(new AnthropicProvider());
const tools = await swx.tools.get({ toolkits: ["gmail"] });
```

---

## Architecture & Data Flow

```
+-------------------------------------------------------------------------------+
| 1. User Prompt (e.g. "Find unread emails from Amazon")                       |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 2. Anthropic Claude (via @anthropic-ai/sdk)                                   |
|    - Evaluates user prompt against tools loaded from swx.tools.get()          |
|    - Selects tool and parameter: `gmail_gmail_messages_get(q: "...")`        |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 3. Swytchcode Runtime (`swx.handleToolCalls(response)`)                        |
|    - Intercepts tool call from Claude                                         |
|    - Evaluates active guard policies (.swytchcode/integrations/policies.json)  |
|    - Executes `swytchcode exec` CLI command in production mode                |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 4. Swytchcode CLI & WorkOS Gateway                                            |
|    - Attaches stored WorkOS OAuth token                                     |
|    - Dispatches HTTP request to Google Gmail API                              |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 5. Output returned back to Claude -> Final response printed in user terminal   |
+-------------------------------------------------------------------------------+
```

Two credentials, two roles:
- **Anthropic API Key**: Pays for model inference and tool decision-making.
- **WorkOS OAuth Token**: Authorizes the Gmail API actions securely out-of-band.

---

## Canonical Methods & Action Matrix

| Example Prompt | Expected Action | Canonical Method ID | Parameters Used | Notes |
|---|---|---|---|---|
| *"Find unread emails from Amazon"* | Search Inbox | `gmail.gmail.messages.get` | `q: "is:unread from:Amazon"` | Gmail search query syntax |
| *"List the last 10 emails in my inbox"* | Read Inbox | `gmail.gmail.messages.get` | `maxResults: 10` | Omits `q` parameter to list recent mail |
| *"Mark the latest email as read"* | Modify Email | `gmail.gmail.modify.create` | `id: "<msg_id>", body: { removeLabelIds: ["UNREAD"] }` | Removes UNREAD label |
| *"Draft a thank-you email to..."* | Create Draft | `gmail.gmail.drafts.create` | `userId: "me", body: { message: { raw: "..." } }` | Drafts message in inbox |
| *"Send a test email to..."* | Send Email | `gmail.gmail.send.create.1` | `userId: "me", body: { raw: "..." }` | **Blocked by policy** in this demo |

---

## Guard Policy: Sends Require Approval

This project ships with `policies.example.json`, a method-level guard policy that intercepts and blocks `gmail.gmail.send.create.1` with `POLICY_BLOCKED`. When blocked, the agent informs the user and creates a draft instead so a human can inspect and send it.

```json
{
  "defaults": {
    "on_violation": "fail",
    "evaluation": "pre_execution"
  },
  "policies": [
    {
      "id": "gmail-send-requires-approval",
      "target": ["gmail.gmail.send.create.1"],
      "when": {
        "operator": "always"
      },
      "action": {
        "type": "block",
        "message": "Direct email sending is blocked by safety policy. Create a draft instead."
      }
    }
  ]
}
```

---

## Project Structure

```
gmail-assistant-anthropic-typescript/
├── src/
│   └── index.ts               # Anthropic SDK tool-use loop + Swytchcode wiring
├── .env.example               # ANTHROPIC_API_KEY placeholder
├── .gitignore                 # Ignores .env, node_modules/, dist/, wrekenfile.yaml & methods.json
├── package.json               # Dependencies: @anthropic-ai/sdk, @swytchcode/runtime, zod
├── tsconfig.json              # TypeScript ES2022 / NodeNext config
├── policies.example.json      # Sample guard policy blocking direct sends
├── LICENSE                    # MIT License
└── README.md                  # Detailed documentation and quick start guide
```

---

## Prerequisites

- [Swytchcode CLI](https://swytchcode.com) installed and logged in (`swytchcode login`)
- Node.js v22+
- An `ANTHROPIC_API_KEY` set in `.env`
- A Google/Gmail account to connect

---

## Step-by-Step Setup Guide

### 1. Install Dependencies & Set Environment
```bash
npm install
cp .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Initialize Swytchcode in Production Mode
```bash
swytchcode init
```
*(Select `editor: none` and `mode: PRODUCTION`. Production mode ensures real API requests reach Gmail rather than routing to a local sandbox mock).*

### 3. Fetch Integrations from tooling.json
```bash
swytchcode bootstrap
```

### 4. Authenticate via WorkOS OAuth
```bash
swytchcode auth connect gmail
```
*(Follow the browser prompt to log into your Google account. Confirm connection status by running `swytchcode auth status`).*

### 5. Activate Guard Policy
```bash
cp policies.example.json .swytchcode/integrations/policies.json
swytchcode policy validate
```

---

## Running the Agent

Start the interactive terminal agent:
```bash
npm start
```

1. Enter a custom prompt or press `Enter` to run the default prompt (*"List the last 10 emails in my inbox"*).
2. The agent executes tool calls against your connected Gmail account.
3. Run `swytchcode audit` to view recorded CLI executions and verified API responses.
