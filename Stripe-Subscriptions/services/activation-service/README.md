# Stripe Subscription Activation

A single reusable TypeScript file — [`activationService.ts`](activationService.ts) — that solves one problem: **developers grant access too early when starting a Stripe subscription.**

It follows Stripe's recommended flow:

1. Create the subscription through **Checkout** with `mode=subscription`.
2. Persist `customer`, `subscription`, and `invoice` IDs on `checkout.session.completed`.
3. **Activate only after a verified `invoice.paid`** — never from the browser success redirect.

All Stripe calls are delegated to the [Swytchcode](https://swytchcode.com) runtime (no Stripe SDK).

## Setup

```bash
# Once per machine
swytchcode login
swytchcode get stripe

# Once per repo (these are the only Stripe canonical IDs the file needs)
swytchcode add checkout.session.create
swytchcode add checkout.session.get
swytchcode add invoices.invoice.get
swytchcode add subscriptions.subscription.get

# In your project
npm install swytchcode-runtime
```

Then drop [`activationService.ts`](activationService.ts) into your codebase and import it.

## Public API

| Function | Purpose |
|---|---|
| `createActivationService({ stripeSecretKey })` | Factory. |
| `createCheckoutSession(input)` | Creates a Stripe Checkout Session in `mode=subscription`; returns `{ sessionId, url, expiresAt, record }`. |
| `handleCheckoutSessionCompleted(event, prior?)` | Reconciles `checkout.session.completed`. Re-fetches via `checkout.session.get` for verification. Returns an updated record (still `pending`). |
| `handleInvoicePaid(event, prior?)` | Reconciles `invoice.paid`. Re-fetches the invoice **and** subscription for verification. Promotes state to `active` only when invoice is paid AND subscription is `active`/`trialing`. |
| `getActivationState(record)` | Pure derivation of the normalized state from a record's signal fields. |

## Normalized states

```
"pending" | "active" | "failed_initial_payment" | "expired"
```

Treat anything other than `"active"` as **no paid access**.

## Behavior

- The browser redirect alone never activates — `createCheckoutSession` returns `state: "pending"` and only `invoice.paid` flips it to `"active"`.
- Renewal invoices (`billing_reason !== "subscription_create"`) are ignored — the renewal-recovery service handles those.
- Non-`subscription` Checkout sessions are ignored.
- Verification is on by default. Both webhook handlers re-fetch the entity from Stripe through Swytchcode before deriving state. Disable per-call with `verify: { session: false, invoice: false }` (not recommended).
- Idempotent: replaying `checkout.session.completed` for an already-`active` account does not regress.
- Storage-agnostic: the caller persists the returned `ActivationRecord`. Pass the prior record back into the next handler so subscription/invoice IDs can be merged.

## Usage

```ts
import { createActivationService, type ActivationRecord, type StripeEvent }
  from "./activationService.js";

const activation = createActivationService({
  stripeSecretKey: process.env.STRIPE_SECRET_KEY!,
});

// 1. Create the Checkout Session
const { url, record } = await activation.createCheckoutSession({
  accountId: "acct_42",
  successUrl: "https://app.example.com/billing/return?session_id={CHECKOUT_SESSION_ID}",
  cancelUrl:  "https://app.example.com/billing/cancel",
  lineItems:  [{ price: "price_pro_monthly", quantity: 1 }],
  workspaceId: "ws_99",
});
await db.activation.upsert(record);   // state === "pending"
return res.redirect(url);

// 2. Stripe webhook (signature already verified upstream)
async function onStripeEvent(event: StripeEvent) {
  const prior = await db.activation.findBySessionOrSubscription(event);
  let next: ActivationRecord | null = null;

  if (event.type === "checkout.session.completed") {
    next = await activation.handleCheckoutSessionCompleted(event, prior ?? undefined);
  } else if (event.type === "invoice.paid") {
    next = await activation.handleInvoicePaid(event, prior ?? undefined);
  }
  if (next) await db.activation.upsert(next);
}

// 3. Authorize requests
const record = await db.activation.get("acct_42");
if (activation.getActivationState(record) !== "active") {
  throw new Error("paid features locked");
}
```

## Stripe canonical IDs (via Swytchcode)

| Canonical ID | Used by |
|---|---|
| `checkout.session.create` | `createCheckoutSession` |
| `checkout.session.get` | `handleCheckoutSessionCompleted` (re-verify) |
| `invoices.invoice.get` | `handleInvoicePaid` (re-verify) |
| `subscriptions.subscription.get` | `handleInvoicePaid` (re-verify) |

All four resolve to the locally installed Stripe integration `stripe.stripe@2026-02-25.clover`.
