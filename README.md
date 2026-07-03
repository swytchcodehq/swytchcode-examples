# Swytchcode Examples

A collection of runnable [LangGraph](https://github.com/langchain-ai/langgraph) + [Swytchcode](https://swytchcode.com) example projects. Each folder is a **self-contained, pre-bootstrapped demo** — it ships with its `.swytchcode/` integration bootstrap already generated, so you only need to add credentials and run.

These are the same examples served by the Swytchcode CLI (`swytchcode examples`). Each folder is published as a `<name>.zip` asset on this repo's rolling [`latest`](https://github.com/swytchcodehq/swytchcode-examples/releases/latest) release.

---

## The demos

| Demo | What it does | Integrations |
|------|--------------|--------------|
| [`customer-onboarding-langgraph`](customer-onboarding-langgraph) | Create a HubSpot contact → create a Stripe customer → send a welcome email via Resend | HubSpot, Stripe, Resend |
| [`create-and-send-payment-langgraph`](create-and-send-payment-langgraph) | Generate a Stripe payment link → email it to the customer via Resend | Stripe, Resend |
| [`bug-escalation-langgraph`](bug-escalation-langgraph) | Create a GitHub issue → create a linked Jira ticket → notify the team on Slack | GitHub, Jira, Slack |
| [`lead-qualification-langgraph`](lead-qualification-langgraph) | Create a HubSpot contact → create a HubSpot deal (sales opportunity) | HubSpot |
| [`weekly-reporting-langgraph`](weekly-reporting-langgraph) | Pull metrics from Google Sheets → publish a Notion page → email a weekly report via Resend | Google Sheets, Notion, Resend |
| [`fintech-compliance-langgraph`](fintech-compliance-langgraph) | Plaid bank linking → Persona KYC → Dwolla customer/funding source → policy enforcement | Plaid, Persona, Dwolla |

---

## Quick start

Each demo is independent. Pick one, then:

```bash
# 1. Get a demo (clone the whole collection, or download one via the CLI)
git clone https://github.com/swytchcodehq/swytchcode-examples.git
cd swytchcode-examples/customer-onboarding-langgraph

# 2. Install dependencies (Python 3.9+)
pip install -r requirements.txt

# 3. Add your credentials
cp .env.example .env      # then fill in the keys

# 4. Run
python main.py
```

Or fetch a single demo through the Swytchcode CLI:

```bash
npm install -g swytchcode
swytchcode examples          # pick a demo interactively
```

Every folder has its own `README.md` with the exact prerequisites, required environment variables, and the canonical IDs it uses.

---

## Demo details

### `customer-onboarding-langgraph`
Automates the full customer onboarding flow: creates a HubSpot contact, creates a Stripe customer, and sends a welcome email via Resend.
- **Tools:** `hubspot.crm.contacts.create`, `customers.customer.create`, `resend.email.create`

### `create-and-send-payment-langgraph`
Creates a Stripe payment link (e.g. $99) and emails it to the customer via Resend.
- **Tools:** `prices.price.create`, `stripe.payment_link.create`, `resend.email.create`

### `bug-escalation-langgraph`
Cross-platform bug escalation: opens a GitHub issue with a severity label, creates a linked Jira ticket, and posts a notification to a Slack channel.
- **Tools:** `repos.issue.create`, `rest.api.issue.create`, `chat.postmessage.chat.postmessage.create`

### `lead-qualification-langgraph`
Lead capture into the sales pipeline: creates a HubSpot contact and a HubSpot deal (sales opportunity).
- **Tools:** `hubspot.crm.contacts.create`, `hubspot.crm.deals.create`

### `weekly-reporting-langgraph`
Turns a Google Sheet of metrics into a published Notion page and an emailed weekly report.
- **Tools:** `spreadsheets.values:batchget.get`, `pages.page.create`, `emails.email.create`

### `fintech-compliance-langgraph`
A 4-step fintech onboarding compliance workflow:
1. **Plaid (sandbox)** — simulate bank account linking and retrieve account context
2. **Persona KYC** — create an inquiry, approve it in sandbox, verify status
3. **Dwolla** — create a customer + funding source (only if Persona KYC passes)
4. **Policy enforcement** — block transfers when KYC isn't approved, reject unsupported account types, hold transactions above a threshold
- **Tools:** `plaid.*` (public token / exchange / accounts), `persona.inquiry.*`, `dwolla.customer.*`

---

## Repository layout

```
swytchcode-examples/
├── <demo>/
│   ├── main.py                          # the LangGraph agent entrypoint
│   ├── requirements.txt                 # swytchcode-runtime, langgraph, python-dotenv, ...
│   ├── .env.example                     # required credentials (copy to .env)
│   ├── README.md                        # per-demo instructions
│   └── .swytchcode/                     # pre-generated integration bootstrap
│       ├── tooling.json
│       └── integrations/manifest.json
└── .github/workflows/release.yml        # zips each demo → uploads to the `latest` release
```

## Releases

On every push to `main`, a GitHub Action zips each demo folder and publishes it to the rolling `latest` release. Download any demo directly:

```
https://github.com/swytchcodehq/swytchcode-examples/releases/latest/download/<demo>.zip
```

## License

Most demos carry their own MIT `LICENSE` file; see each demo folder for details.
