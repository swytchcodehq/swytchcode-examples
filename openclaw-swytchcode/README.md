# OpenClaw × Swytchcode — GitHub Issue Triage Bot

> An AI-powered GitHub issue triage bot demonstrating [OpenClaw](https://openclaw.ai) using [Swytchcode](https://cli.swytchcode.com) as its deterministic API execution layer.

[![Go 1.26](https://img.shields.io/badge/go-1.26-00ADD8)](https://go.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/swytchcodehq/openclaw-swytchcode-demo)](https://github.com/swytchcodehq/openclaw-swytchcode-demo/commits)

---

## What Is This?

This repo is a working demo of the **OpenClaw + Swytchcode** integration pattern.

**The problem:** AI agents that call APIs directly are unpredictable — they hallucinate endpoints, bypass auth policies, and are impossible to audit.

**The solution:** OpenClaw (the AI agent) reasons and plans. Swytchcode (the execution kernel) runs every API call deterministically, with schema validation, policy enforcement, and a full audit trail.

This bot watches a GitHub repository for open issues related to Stripe integration problems. It classifies each issue, posts a helpful templated comment, and logs every action to a CSV file for team follow-up — all without the AI ever touching the GitHub API directly.

---

## Running the Bot

Set your environment variables and run:

**Linux / macOS**
```bash
export GITHUB_TOKEN="ghp_your_token_here"
export GITHUB_OWNER="your-org-or-username"
export GITHUB_REPO="your-repo-name"
go run .
```

**Windows (PowerShell)**
```powershell
$env:GITHUB_TOKEN="ghp_your_token_here"
$env:GITHUB_OWNER="your-org-or-username"
$env:GITHUB_REPO="your-repo-name"
go run .
```

### Sample output

```
2026/04/19 12:00:01 Starting triage bot for myorg/myrepo
2026/04/19 12:00:02 Found 8 open issues
2026/04/19 12:00:02 Processing issue #42: Stripe payment failing with 401
2026/04/19 12:00:03 Issue #42 classified as: error
2026/04/19 12:00:04 ✅ Commented on issue #42
2026/04/19 12:00:06 Processing issue #43: How do I set up Stripe webhooks?
2026/04/19 12:00:07 Issue #43 classified as: webhook
2026/04/19 12:00:08 ✅ Commented on issue #43
2026/04/19 12:00:08 Done. Commented on 2 issues. Log saved to issues_log.csv
```

---

## How It Works

### Step 1 — Fetch Issues
`main.go` calls `FetchIssues()` which uses `swytchcode exec repos.issue.get` to pull open GitHub issues from the target repo.

### Step 2 — Classify
`classifier.go` sends each issue title + body to `swytchcode_discover` with a classification prompt. It categorises issues into:

| Type | Trigger keywords |
|------|-----------------|
| `setup` | how, install, configure, getting started |
| `error` | error, fail, 401, 500, crash, bug, broken |
| `webhook` | webhook, event, listener, endpoint |
| `unknown` | anything else — skipped |

If the MCP call fails, it falls back to local keyword matching — the bot never crashes.

### Step 3 — Comment
`commenter.go` calls `swytchcode exec repos.issue.comments.create` to post the matching template. Max **5 comments per run**, with a **2-second delay** between posts.

### Step 4 — Log
Every action is appended to `issues_log.csv` with issue URL, title, type, comment body, and timestamp — for manual team review.

---

## Architecture

```
OpenClaw (AI Agent)
      │
      │  decides what to do
      ▼
Swytchcode CLI (Execution Kernel)
      │
      │  swytchcode exec repos.issue.comments.create
      ▼
GitHub API  ──►  Issue Comment Posted
      │
      ▼
issues_log.csv  (audit trail)
```

**Key principle:** The AI classifies and decides. Swytchcode executes. The two are never mixed.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | [OpenClaw](https://openclaw.ai) |
| Execution Kernel | [Swytchcode CLI](https://cli.swytchcode.com) v2.2.7 |
| GitHub Integration | `github.github@1.1.4` (via Swytchcode registry) |
| Language | Go 1.21+ (stdlib only — zero external dependencies) |
| Logging | CSV via `encoding/csv` |

---

## Prerequisites

- **Go 1.21+**
- **Swytchcode CLI v2+** — install via:
```bash
  npm install -g swytchcode
```
- A **GitHub Personal Access Token** with `repo` scope

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/swytchcodehq/openclaw-swytchcode-demo.git
cd openclaw-swytchcode-demo
```

### 2. Initialise Swytchcode

```bash
swytchcode init --editor=none --mode=sandbox --non-interactive
```

### 3. Fetch the GitHub integration

```bash
swytchcode get github
```

### 4. Add the tools used by this bot

```bash
swytchcode add repos.issue.get
swytchcode add repos.issue.comments.create
```

### 5. Verify

```bash
swytchcode list methods
# Should show repos.issue.get and repos.issue.comments.create
```

---

## Configuration

| Environment Variable | Required | Description |
|---------------------|----------|-------------|
| `GITHUB_TOKEN` | ✅ | GitHub PAT with `repo` scope |
| `GITHUB_OWNER` | ✅ | GitHub org or username that owns the target repo |
| `GITHUB_REPO` | ✅ | Repository name to triage |

To change the max comments per run, edit `maxComments` in `main.go` (default: `5`).

---

## Rate Limiting

This bot is deliberately conservative:

- **Max 5 comments per run** (hardcoded default)
- **2-second sleep** between comments
- Recommended: run via cron **once per day max**

This is intentional — posting too aggressively via automation risks GitHub flagging the account as spam.

---

## Testing Safely

**Always test on a private repo with seeded fake issues before pointing at any public repo.**

Create a private test repo, open a few issues with titles like:
- `"Getting 401 error when calling Stripe API"`
- `"How do I install the Stripe SDK?"`
- `"Webhook endpoint not receiving events"`

Then point the bot at that repo first.

---

## Comment Templates

The bot uses three hardcoded templates in `templates.go`:

**Setup** — guides the user to `npx swytchcode stripe.create_payment` for quick Stripe setup.

**Error** — asks the user for their error message and suggests checking API key configuration via Swytchcode.

**Webhook** — explains how to wire up Stripe webhooks using the Swytchcode execution layer.

---

## Why Swytchcode?

Without Swytchcode, an AI agent calling the GitHub API directly would:
- Need credentials embedded in its context (security risk)
- Have no schema validation on API inputs
- Produce no audit log
- Be impossible to reproduce deterministically

With Swytchcode, the agent only decides *what* to call — the kernel handles *how*, validates the inputs against the Wrekenfile schema, and records every execution.

---

## Part of the Swytchcode demo collection

This bot is one of several runnable examples showing Swytchcode as the execution layer for AI agents and integration-heavy apps:

- [langswytch](https://github.com/swytchcodehq/langswytch): a LangGraph agent that turns natural language into validated API calls across 2,000+ integrations (Python)
- [Stripe-Subscriptions](https://github.com/swytchcodehq/Stripe-Subscriptions): subscription lifecycle services on the Swytchcode runtime (TypeScript)
- [swytchcode-google-analytics](https://github.com/swytchcodehq/swytchcode-google-analytics): Google Analytics reporting built on the Swytchcode CLI (TypeScript)
- [Weekly-Reporting-Langgraph](https://github.com/swytchcodehq/Weekly-Reporting-Langgraph), [Customer-Onboarding-Langgraph](https://github.com/swytchcodehq/Customer-Onboarding-Langgraph), [Lead-Qualification-Langgraph](https://github.com/swytchcodehq/Lead-Qualification-Langgraph), [Bug-Escalation-Langgraph](https://github.com/swytchcodehq/Bug-Escalation-Langgraph), [Create-And-Send-Payment-Langgraph](https://github.com/swytchcodehq/Create-And-Send-Payment-Langgraph): single-purpose LangGraph agents

---

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md)

---

## License

MIT — see [LICENSE](./LICENSE)

---

## Links

- [Swytchcode CLI docs](https://cli.swytchcode.com)
- [OpenClaw](https://openclaw.ai)
- [Swytchcode registry](https://api-v2.swytchcode.com)
