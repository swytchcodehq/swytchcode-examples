# Gmail Assistant - Anthropic SDK (TypeScript)

An agent that searches, reads, marks as read, drafts, and sends Gmail messages
by calling the Gmail API through the Swytchcode CLI. You never write the
Gmail API call, the tool schema, or the OAuth flow. Swytchcode provides the
tools and handles Gmail authorization via WorkOS OAuth.

The agent code is only two Swytchcode lines. Everything else is the Anthropic
SDK's own tool-use loop in src/index.ts.

## How it works

```
your prompt
   -> Claude (via the Anthropic SDK) decides which Gmail tool(s) to call
   -> swytchcode-runtime forwards the call
   -> Swytchcode CLI executes the Gmail API request
      using WorkOS-brokered OAuth
   -> mailbox searched / message marked read / draft created / email sent
```

Two credentials, two jobs: the Anthropic API key pays for model inference,
while WorkOS OAuth authorizes the Gmail action.

## Example prompts

| Prompt | Tool called | Notes |
|---|---|---|
| "Find unread emails from Amazon" | `gmail.gmail.messages.get` (search, `q=from:amazon is:unread`) | |
| "List the last 10 emails in my inbox" | `gmail.gmail.messages.get` (list, no `q`) | |
| "Mark the latest email as read" | `gmail.gmail.modify.create` | removes the `UNREAD` label |
| "Draft a thank-you email to ..." | `gmail.gmail.drafts.create` | creates a draft only, never sends |
| "Send a test email to ..." | `gmail.gmail.send.create.1` | blocked by guard policy |

## Guard policy: sends require approval

This example includes `policies.example.json`, a guard policy that blocks
`gmail.gmail.send.create.1` with `POLICY_BLOCKED` and directs the agent to create
drafts instead.

## Prerequisites

- Swytchcode CLI installed and `swytchcode login` completed
- Node.js v22+
- An `ANTHROPIC_API_KEY` in `.env`
- A Google/Gmail account to connect

## Quick start

```bash
# 1. environment
npm install
cp .env.example .env                                        # add your ANTHROPIC_API_KEY

# 2. one-time Swytchcode setup
swytchcode init                                              # editor: none | mode: production
swytchcode get gmail
swytchcode add method gmail.gmail.messages.get
swytchcode add method gmail.gmail.send.create.1
swytchcode add method gmail.gmail.modify.create
swytchcode add method gmail.gmail.drafts.create
swytchcode auth connect gmail                                # WorkOS OAuth in your browser
cp policies.example.json .swytchcode/integrations/policies.json
swytchcode policy validate                                   # confirm the guard is active

# 3. run
npm start
```

Type a prompt (or press Enter for default) and the agent acts on your inbox.
Run `swytchcode audit` to view recorded CLI executions.
