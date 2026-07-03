# Create and Send Payment — LangGraph + Swytchcode

Automates payment link creation and customer notification:
1. Generates a Stripe payment link for $99
2. Emails the link to the customer via Resend

Built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Swytchcode](https://swytchcode.com).

---

## Prerequisites

- **Python 3.9+**
- **Swytchcode CLI:** install with the verified script for your platform:
  
  npm install -g swytchcode

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/swytchcodehq/Create-And-Send-Payment-Langgraph.git
   cd Create-And-Send-Payment-Langgraph
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
| Stripe | `prices.price.create` |
| Resend | `resend.email.create` |
| Stripe | `stripe.payment_link.create` |

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
