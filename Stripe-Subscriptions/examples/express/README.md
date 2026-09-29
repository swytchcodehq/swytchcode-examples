# Express example — single-file activation service

End-to-end wiring for `services/activation-service/activationService.ts`:

- `POST /checkout` — creates a Stripe Checkout Session (mode=subscription) and returns the redirect URL.
- `POST /webhooks/stripe` — verifies the `Stripe-Signature` header (no Stripe SDK), then routes `checkout.session.completed` and `invoice.paid` into the service.
- `GET /activation/:accountId` — returns the normalized state used to authorize requests.

## Setup

```bash
cd "Stripe/Stripe Subscriptions/examples/express"
npm install
cp .env.example .env
# fill in STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, SWYTCHCODE_TOKEN
```

## Run

```bash
npm run dev
```

Server listens on `http://localhost:3000`.

## End-to-end with the Stripe CLI

In one terminal — forward live test webhooks:

```bash
stripe listen --forward-to localhost:3000/webhooks/stripe
# copy the printed whsec_... into .env as STRIPE_WEBHOOK_SECRET, then restart the server
```

In another terminal — drive the flow:

```bash
# 1. Create a Checkout Session
curl -s http://localhost:3000/checkout \
  -H 'content-type: application/json' \
  -d '{
    "accountId": "acct_42",
    "priceId": "price_test_xxx",
    "successUrl": "https://example.com/return?session_id={CHECKOUT_SESSION_ID}",
    "cancelUrl": "https://example.com/cancel"
  }' | jq .
# → returns { sessionId, url, state: "pending", ... }

# 2. Open the returned `url` in a browser and complete with a test card (4242 4242 4242 4242).
#    Stripe fires checkout.session.completed → invoice.paid; the listener forwards them.

# 3. Check normalized state
curl -s http://localhost:3000/activation/acct_42 | jq .
# → { accountId: "acct_42", state: "active" }
```

You can also drive it without a real browser using `stripe trigger`, but that fires synthetic events whose `metadata.account_id` will not match an account you created — useful for sniff-testing the signature path, not the full state machine.

## Notes

- Webhook signature verification uses the documented HMAC-SHA256 scheme directly; no `stripe` npm package is pulled in.
- The webhook route uses `express.raw()` and is mounted **before** `express.json()` — order matters; signature verification needs the exact bytes Stripe signed.
- Storage is a tiny in-memory `Map` (resets on restart). Replace it with your DB in `server.ts`.
