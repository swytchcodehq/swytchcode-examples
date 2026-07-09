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

Every entry below lives in this repository. **CLI** entries are also scaffoldable via the `swytchcode examples` interactive CLI; **Repo** entries are browsed and cloned directly.

| Name | Description | Integrations / Focus |
| :--- | :--- | :--- |
| [**`customer-onboarding`**](./customer-onboarding-langgraph) · CLI | End-to-end B2B onboarding. Creates contacts, provisions billing, and sends welcome sequences. | HubSpot, Stripe, Resend |
| [**`create-and-send-payment`**](./create-and-send-payment-langgraph) · CLI | Revenue operations workflow. Generates secure payment links and dispatches them to clients. | Stripe, Resend |
| [**`bug-escalation`**](./bug-escalation-langgraph) · CLI | Engineering triaging. Opens GitHub issues, synchronizes Jira tickets, and alerts Slack channels. | GitHub, Jira, Slack |
| [**`lead-qualification`**](./lead-qualification-langgraph) · CLI | Sales pipeline automation. Enriches inbound leads and transitions them into CRM deal stages. | HubSpot |
| [**`weekly-reporting`**](./weekly-reporting-langgraph) · CLI | Automated analytics distribution. Extracts data, generates documentation, and emails stakeholders. | Sheets, Notion, Resend |
| [**`fintech-compliance`**](./fintech-compliance-langgraph) · CLI | **(High-Security)** Identity verification, bank linking, and secure payments with policy enforcement. | Plaid, Persona, Dwolla |
| [**`openclaw-swytchcode`**](./openclaw-swytchcode) · Repo | Multi-API customer onboarding workflow demonstrating core agent guardrails and state recovery. | Reliability & Idempotency |
| [**`github-issue-integration`**](./github-issue-integration) · Repo | Autonomous repository maintenance, automated issue triaging, and PR commentary. | Developer Productivity |
| [**`fintech-compliance-multiuser`**](./fintech-compliance-multiuser-langgraph) · Repo | Scalable multi-user compliance workflows tailored for financial institutions. | Compliance Security |
| [**`stripe-subscriptions`**](./stripe-subscriptions) · Repo | Complete subscription lifecycle management, dunning, and entitlement synchronization. | Revenue Automation |
| [**`langswytch`**](./langswytch) · Repo | Deep integration examples showcasing advanced LangGraph cognitive architectures with Swytchcode. | Cognitive Architecture |
| [**`swytchcode-refund-agent-openclaw`**](./swytchcode-refund-agent-openclaw) · Repo | Automated refund agent processing workflows leveraging Swytchcode tool calling and OpenClaw. | Customer Support |

---

## License

This repository is licensed under the [MIT License](LICENSE).
