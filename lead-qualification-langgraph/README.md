# Lead Qualification — LangGraph + Swytchcode

Automates lead capture and sales pipeline creation:
1. Creates a HubSpot contact
2. Creates a HubSpot sales opportunity (deal)

Built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Swytchcode](https://swytchcode.com).

---

## Prerequisites

- **Python 3.9+**
- **Swytchcode CLI:** install with the verified script for your platform:
  
  npm install -g swytchcode

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/swytchcodehq/Lead-Qualification-Langgraph.git
   cd Lead-Qualification-Langgraph
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
| Hubspot | `hubspot.crm.contacts.create` |
| Hubspot | `hubspot.crm.deals.create` |

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
