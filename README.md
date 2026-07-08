<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://via.placeholder.com/600x150/000000/FFFFFF?text=Swytchcode+Examples">
    <img src="https://via.placeholder.com/600x150/FFFFFF/000000?text=Swytchcode+Examples" alt="Swytchcode" width="400">
  </picture>
</div>

<h1 align="center">Swytchcode Enterprise Examples & Reference Architectures</h1>

<div align="center">
  <strong>Production-ready AI agent workflows, integration templates, and compliance guardrails.</strong>
  <br />
  <br />

  <a href="https://swytchcode.com/docs">Documentation</a>
  ·
  <a href="https://github.com/swytchcodehq/swytchcode-cli/issues">Report Bug</a>
  ·
  <a href="https://github.com/swytchcodehq/swytchcode-cli/issues">Request Feature</a>
</div>

<br />

## 📖 Overview

**Swytchcode** is the enterprise standard for connecting autonomous AI agents to real-world APIs, databases, and tooling. By providing a unified interface and native SDKs for frameworks like **LangGraph**, **OpenAI Agents SDK**, and the **Vercel AI SDK**, Swytchcode enables developers to build agentic workflows with built-in idempotency, audit trails, and strict policy enforcement.

This centralized repository houses our official starter templates, enterprise reference architectures, and multi-API orchestration demos.

---

## 🚀 Quick Start (CLI Templates)

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

## 📂 Project Directory

### 🛠️ Core CLI Templates
These foundational templates are accessible directly via the `swytchcode examples` interactive CLI.

| Template | Description | Integrations |
| :--- | :--- | :--- |
| **`customer-onboarding`** | End-to-end B2B onboarding. Creates contacts, provisions billing, and sends welcome sequences. | HubSpot, Stripe, Resend |
| **`create-and-send-payment`** | Revenue operations workflow. Generates secure payment links and dispatches them to clients. | Stripe, Resend |
| **`bug-escalation`** | Engineering triaging. Opens GitHub issues, synchronizes Jira tickets, and alerts Slack channels. | GitHub, Jira, Slack |
| **`lead-qualification`** | Sales pipeline automation. Enriches inbound leads and transitions them into CRM deal stages. | HubSpot |
| **`weekly-reporting`** | Automated analytics distribution. Extracts data, generates documentation, and emails stakeholders. | Sheets, Notion, Resend |
| **`fintech-compliance`** | **(High-Security)** Identity verification, bank linking, and secure payments with policy enforcement. | Plaid, Persona, Dwolla |

<br/>

### 🏛️ Advanced Reference Architectures
Complex, multi-agent enterprise deployments and deep framework integrations.

| Repository | Description | Focus Area |
| :--- | :--- | :--- |
| [**`openclaw-swytchcode-demo`**](./openclaw-swytchcode-demo) | Multi-API customer onboarding workflow demonstrating core agent guardrails and state recovery. | Reliability & Idempotency |
| [**`Github-issue-integration`**](./Github-issue-integration-with-swytchcode) | Autonomous repository maintenance, automated issue triaging, and PR commentary. | Developer Productivity |
| [**`Fintech-Compliance-Multiuser`**](./Fintech-Compliance-Multiuser-Langgraph-Demo) | Scalable multi-user compliance workflows tailored for financial institutions. | Enterprise Security |
| [**`Stripe-Subscriptions`**](./Stripe-Subscriptions) | Complete subscription lifecycle management, dunning, and entitlement synchronization. | Revenue Automation |
| [**`langswytch`**](./langswytch) | Deep integration examples showcasing advanced LangGraph cognitive architectures with Swytchcode. | Cognitive Architecture |

---

## 🔒 Enterprise Guardrails

Every example in this repository is built to demonstrate Swytchcode's core enterprise promises:
- **Idempotency:** Agents can safely retry tool calls without double-charging customers or duplicating records.
- **Policy Enforcement:** Strict, declarative constraints on what actions agents are permitted to take.
- **Audit Trails:** Complete visibility into the execution lifecycle of every API invocation.

---

## 🤝 Contributing

We welcome contributions from the community! Whether you are submitting a new reference implementation or improving an existing template, please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting a Pull Request.

## 📄 License

This repository is licensed under the [MIT License](LICENSE).
