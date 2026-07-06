# Fintech Compliance — LangGraph + Swytchcode

4-step compliance workflow for fintech onboarding:

1. **Plaid Sandbox** — simulate bank account linking and retrieve account context
2. **Persona KYC** — create an inquiry, approve it in sandbox, verify status
3. **Dwolla** — create customer + funding source (only runs if Persona KYC passes)
4. **Policy enforcement** — blocks transfers if KYC is not approved, rejects unsupported account types, holds transactions above threshold

Built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Swytchcode](https://swytchcode.com).

---

## Prerequisites

- **Python 3.9+**
- **Swytchcode CLI:** install with the verified script for your platform:
  
  npm install -g swytchcode

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/swytchcodehq/swytchcode-examples.git
   cd swytchcode-examples/fintech-compliance-langgraph
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
| Dwolla | `dwolla.customer.create` |
| Dwolla | `dwolla.customer.fundingSources.create` |
| Dwolla | `dwolla.customer.list` |
| Dwolla | `dwolla.token.create` |
| Persona | `persona.inquiry.approve` |
| Persona | `persona.inquiry.create` |
| Persona | `persona.inquiry.get` |
| Persona | `persona.inquiry.performSimulateActions.create` |
| Plaid | `plaid.account.get` |
| Plaid | `plaid.item.exchange.create` |
| Plaid | `plaid.sandbox.publicToken.create` |

## Part of the Swytchcode demo collection

Runnable LangGraph + Swytchcode examples:

- [bug-escalation-langgraph](../bug-escalation-langgraph)
- [create-and-send-payment-langgraph](../create-and-send-payment-langgraph)
- [customer-onboarding-langgraph](../customer-onboarding-langgraph)
- [fintech-compliance-langgraph](../fintech-compliance-langgraph)
- [lead-qualification-langgraph](../lead-qualification-langgraph)
- [weekly-reporting-langgraph](../weekly-reporting-langgraph)

## License

MIT. See [LICENSE](LICENSE).
