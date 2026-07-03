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
   git clone https://github.com/swytchcodehq/Fintech-Compliance-Langgraph-Demo.git
   cd Fintech-Compliance-Langgraph-Demo
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

- [Bug-Escalation-Langgraph](https://github.com/swytchcodehq/Bug-Escalation-Langgraph)
- [Create-And-Send-Payment-Langgraph](https://github.com/swytchcodehq/Create-And-Send-Payment-Langgraph)
- [Customer-Onboarding-Langgraph](https://github.com/swytchcodehq/Customer-Onboarding-Langgraph)
- [Fintech-Compliance-Langgraph-Demo](https://github.com/swytchcodehq/Fintech-Compliance-Langgraph-Demo)
- [Lead-Qualification-Langgraph](https://github.com/swytchcodehq/Lead-Qualification-Langgraph)
- [Weekly-Reporting-Langgraph](https://github.com/swytchcodehq/Weekly-Reporting-Langgraph)

## License

MIT. See [LICENSE](LICENSE).
