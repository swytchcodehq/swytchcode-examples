# Swytchcode Examples

Runnable LangGraph + Swytchcode example projects, served by the Swytchcode CLI.

## Installation & setup

Install the Swytchcode CLI (requires Node.js):

```bash
npm install -g swytchcode
```

Fetch an example project:

```bash
swytchcode examples          # choose a demo interactively
```

Set it up and run it (requires Python 3.9+):

```bash
cd 
pip install -r requirements.txt
cp .env.example .env          # then add your credentials
python main.py
```

Each demo's own README lists its exact prerequisites, environment variables, and the tools it uses.

## Projects

- **customer-onboarding-langgraph** — Creates a HubSpot contact and a Stripe customer, then sends a welcome email via Resend.
- **create-and-send-payment-langgraph** — Generates a Stripe payment link and emails it to the customer via Resend.
- **bug-escalation-langgraph** — Opens a GitHub issue, creates a linked Jira ticket, and notifies the team on Slack.
- **lead-qualification-langgraph** — Turns an inbound lead into a HubSpot contact and a HubSpot deal.
- **weekly-reporting-langgraph** — Pulls metrics from Google Sheets, publishes a Notion page, and emails a weekly report via Resend.
- **fintech-compliance-langgraph** — Bank linking (Plaid), identity verification (Persona KYC), and payments (Dwolla) with compliance policy enforcement.
