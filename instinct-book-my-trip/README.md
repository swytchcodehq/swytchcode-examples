# Book My Trip with Instinct

Book real flights from your AI assistant, with spending rules it can't get around.

- **Search** flights freely.
- **Bookings over $100 wait for your approval** in Slack or Telegram, outside the assistant's chat.
- **No ticket over $300, no more than $500 a day, no more than 2 bookings a day.**
- **Only flights a search actually returned** can be booked. A made-up flight is refused.
- **The assistant never sees a key:** not the airline's, not Google's, not the email service's.
- **A confirmation email** goes out for every booking, through Resend.

Flights come from [Duffel](https://duffel.com), a real airline API. Test mode has a fake airline (Duffel Airways), so this runs for free and nothing is really booked.

The rules are in [`.swytchcode/integrations/policies.json`](.swytchcode/integrations/policies.json). [Swytchcode](https://swytchcode.com) checks every call against them before it reaches Duffel. Run `swytchcode policy validate` to see them tested.

> **Test mode only.** Use a `duffel_test_` token. Switching to live is your call, and the rules apply there too, but start with test.

## Which assistant?

| Assistant | How it connects | Guide |
|---|---|---|
| **Instinct**, or any assistant that can write to a Google Sheet | Through a Google Sheet: the assistant writes a request, and a small bridge script runs it | [instinct-bridge/](instinct-bridge/) |
| OpenClaw, Hermes and other MCP agents | Directly, over MCP | Coming soon |

## Setup

```bash
git clone https://github.com/swytchcodehq/swytchcode-examples
cd swytchcode-examples/instinct-book-my-trip/instinct-bridge
./setup.sh
```

The script needs only Docker. It signs you in to Swytchcode, connects Duffel (a free test key), Google Sheets and Resend, asks where approvals go, and starts everything. Keys go into Swytchcode, never into a chat or a file in this folder. Details are in the [Instinct bridge guide](instinct-bridge/).

## Change the rules

Edit `policies.json`, run `swytchcode policy validate` (10 rules, each with tests), then restart the bridge with `docker compose up -d --build`. For example, change `300` in `trip-cap-ticket` to raise the per-ticket limit. If your test offers come in GBP or EUR rather than USD, change `trip-usd-only` and the amounts to match.

## Not just flights

Duffel is only the example. Any API with an OpenAPI spec works the same way: add it, and write the rules once for every assistant you use.

---

*Made by the Swytchcode team. MIT license.*
