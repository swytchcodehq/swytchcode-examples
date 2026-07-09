<h1 align="center">Swytchcode Examples & Reference Architectures</h1>

<div align="center">
  <strong>Production-ready AI agent workflows, integration templates, and compliance guardrails.</strong>
</div>

<br />

## Overview

**Swytchcode** is the standard for connecting autonomous AI agents to real-world APIs, databases, and tooling. By providing a unified interface and native SDKs for frameworks like **LangGraph**, **OpenAI Agents SDK**, and the **Vercel AI SDK**, Swytchcode enables developers to build agentic workflows with built-in idempotency, audit trails, and strict policy enforcement.

This centralized repository houses our official starter templates, reference architectures, and multi-API orchestration demos.

---

## Quick Start (CLI Templates)

The fastest way to scaffold a production-ready agent is via the **Swytchcode CLI**. The CLI provides instant access to our core templates, pre-wired with environment configurations and dependency management.

### 1. Install the CLI
Ensure you have [Node.js](https://nodejs.org/) installed, then run:
```bash
npm install -g swytchcode
```

### 2. Scaffold a Project
Launch the interactive project generator:
```bash
swytchcode examples
```
*Select your desired use case (e.g., Customer Onboarding, Bug Escalation) and framework (e.g., LangGraph).*

### 3. Run the Agent
*(Requires Python 3.9+)*
```bash
cd <your-scaffolded-demo>
pip install -r requirements.txt

# Configure your environment variables
cp .env.example .env

# Execute the agent workflow
python main.py
```

---

## Project Directory

The first six examples can be scaffolded fresh via the `swytchcode examples` interactive CLI; the rest are reference architectures meant to be explored and cloned directly.

| Example | Description | Framework | Tags |
| :--- | :--- | :--- | :--- |
| [**`customer-onboarding`**](./customer-onboarding-langgraph) | B2B onboarding + billing setup | LangGraph | CRM • Onboarding • HubSpot • Stripe • Resend |
| [**`create-and-send-payment`**](./create-and-send-payment-langgraph) | Generate and send payment links | LangGraph | Payments • Stripe • Resend |
| [**`bug-escalation`**](./bug-escalation-langgraph) | GitHub + Jira + Slack triage | LangGraph | Engineering • GitHub • Jira • Slack |
| [**`lead-qualification`**](./lead-qualification-langgraph) | Lead enrichment and CRM routing | LangGraph | CRM • Sales • HubSpot |
| [**`weekly-reporting`**](./weekly-reporting-langgraph) | Automated analytics report distribution | LangGraph | Analytics • Sheets • Notion • Resend |
| [**`fintech-compliance`**](./fintech-compliance-langgraph) | KYC, bank linking, secure payments | LangGraph | Finance • Compliance • Plaid • Persona • Dwolla |
| [**`openclaw-swytchcode`**](./openclaw-swytchcode) | GitHub issue triage bot | OpenClaw (Go) | GitHub • Automation • Reliability |
| [**`github-issue-integration`**](./github-issue-integration) | Automated GitHub issue creation | Swytchcode SDK | GitHub • Automation |
| [**`fintech-compliance-multiuser`**](./fintech-compliance-multiuser-langgraph) | Multi-user compliance workflows | LangGraph | Finance • Compliance • Multi-user |
| [**`stripe-subscriptions`**](./stripe-subscriptions) | Subscription lifecycle + dunning | Swytchcode SDK | Billing • Stripe • Webhooks |
| [**`langswytch`**](./langswytch) | Advanced LangGraph cognitive patterns | LangGraph | Multi-Agent • Orchestration • Memory |
| [**`swytchcode-refund-agent-openclaw`**](./swytchcode-refund-agent-openclaw) | Automated refund processing agent | OpenClaw | Support • Refunds |

---

## License

This repository is licensed under the [MIT License](LICENSE).
