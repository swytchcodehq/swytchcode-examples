# Swytchcode Examples & Demos

Welcome to the official repository for **Swytchcode** example projects!

**Swytchcode** is the easiest way to give your AI agents the ability to interact with real-world APIs, databases, and tools. Our SDKs provide seamless tool-calling integration for frameworks like LangGraph, OpenAI Agents SDK, Vercel AI SDK, and more. 

This repository contains both our core CLI starter templates and our advanced reference implementations.

## 🚀 Quick Start (CLI Templates)

The fastest way to get started is by using the Swytchcode CLI. This will let you interactively download one of our ready-to-run starter templates.

### 1. Install Swytchcode CLI
*(Requires Node.js)*
```bash
npm install -g swytchcode
```

### 2. Fetch an Example Project
```bash
swytchcode examples
```
This will launch an interactive menu where you can choose a demo (e.g., Customer Onboarding, Bug Escalation) and a framework (e.g., LangGraph).

### 3. Run Your Agent
*(Requires Python 3.9+)*
```bash
cd <your-demo-folder>
pip install -r requirements.txt
cp .env.example .env          # Add your API keys here
python main.py
```

## 📁 Available Projects

### Core CLI Templates
These templates are available directly via the `swytchcode examples` command:
- **customer-onboarding-langgraph** — Creates a HubSpot contact and a Stripe customer, then sends a welcome email via Resend.
- **create-and-send-payment-langgraph** — Generates a Stripe payment link and emails it to the customer via Resend.
- **bug-escalation-langgraph** — Opens a GitHub issue, creates a linked Jira ticket, and notifies the team on Slack.
- **lead-qualification-langgraph** — Turns an inbound lead into a HubSpot contact and a HubSpot deal.
- **weekly-reporting-langgraph** — Pulls metrics from Google Sheets, publishes a Notion page, and emails a weekly report via Resend.
- **fintech-compliance-langgraph** — Bank linking (Plaid), identity verification (Persona KYC), and payments (Dwolla) with compliance policy enforcement.

### Advanced Reference Implementations
Explore our more advanced multi-agent and custom framework integrations:
- **Github-issue-integration-with-swytchcode** — Automate GitHub issue triaging and responses.
- **Fintech-Compliance-Multiuser-Langgraph-Demo** — Multi-user compliance workflows using Swytchcode.
- **Stripe-Subscriptions** — End-to-end Stripe subscription management.
- **langswytch** — LangGraph + Swytchcode deep integration examples.
- **openclaw-swytchcode-demo** — A multi-API customer onboarding workflow (HubSpot, Stripe, Resend) demonstrating Swytchcode's core agent guardrails.
