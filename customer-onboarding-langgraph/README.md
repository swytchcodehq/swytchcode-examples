# Customer Onboarding — LangGraph + Swytchcode

Automates the full customer onboarding flow:
1. Creates a HubSpot contact
2. Creates a Stripe customer
3. Sends a welcome email via Resend

Built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Swytchcode](https://swytchcode.com).

---

## Prerequisites

- **Python 3.9+**
- **Swytchcode CLI:** install with the verified script for your platform:
  
  npm install -g swytchcode

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/swytchcodehq/Customer-Onboarding-Langgraph.git
   cd Customer-Onboarding-Langgraph
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example env file and fill in your keys:
   ```bash
   cp .env.example .env
   ```
## Run

```bash
python main.py
```

## Canonical IDs Used

| Service | Canonical ID |
|---------|--------------|
| Stripe | `customers.customer.create` |
| Hubspot | `hubspot.crm.contacts.create` |
| Resend | `resend.email.create` |

## Part of the Swytchcode demo collection

Runnable LangGraph + Swytchcode examples:

- [Bug-Escalation-Langgraph](https://github.com/swytchcodehq/Bug-Escalation-Langgraph)
- [Create-And-Send-Payment-Langgraph](https://github.com/swytchcodehq/Create-And-Send-Payment-Langgraph)
- [Customer-Onboarding-Langgraph](https://github.com/swytchcodehq/Customer-Onboarding-Langgraph)
- [Fintech-Compliance-Langgraph-Demo](https://github.com/swytchcodehq/Fintech-Compliance-Langgraph-Demo)
- [Lead-Qualification-Langgraph](https://github.com/swytchcodehq/Lead-Qualification-Langgraph)
- [Weekly-Reporting-Langgraph](https://github.com/swytchcodehq/Weekly-Reporting-Langgraph)

## License

MIT. See [LICENSE](LICENSE).
