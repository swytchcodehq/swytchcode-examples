# Stripe First Payment Recovery

A single reusable TypeScript file — [`firstPaymentRecoveryService.ts`](firstPaymentRecoveryService.ts) — that solves one problem: **failed first subscription payments and SCA / 3DS recovery.**

Stripe documents that the first invoice can stay `open`, the subscription `incomplete`, and the PaymentIntent in `requires_payment_method`, `requires_action`, or `processing`. Unresolved cases move to `incomplete_expired` after roughly 23 hours.

All Stripe calls are delegated to the [Swytchcode](https://swytchcode.com) runtime (no Stripe SDK).

## Setup

```bash
# Once per machine
swytchcode login
swytchcode get stripe

# Once per repo (these are the only Stripe canonical IDs the file needs)
swytchcode add invoices.invoice.get
swytchcode add payment_intents.payment_intent.get
swytchcode add subscriptions.subscription.get

# In your project
npm install swytchcode-runtime
```

Then drop [`firstPaymentRecoveryService.ts`](firstPaymentRecoveryService.ts) into your codebase and import it.

## Public API

| Function | Purpose |
|---|---|
| `createFirstPaymentRecoveryService({ stripeSecretKey })` | Factory. |
| `handleInvoicePaymentFailed(event, prior?)` | Reconciles `invoice.payment_failed`. Re-fetches invoice + subscription + PaymentIntent for verification. Returns an updated record. |
| `handleInvoicePaymentActionRequired(event, prior?)` | Reconciles `invoice.payment_action_required` (3DS / SCA). |
| `handleInvoicePaid(event, prior?)` | Reconciles `invoice.paid` for the **first** invoice; promotes state to `recovered`. |
| `getRecoveryState(record)` | Pure derivation of the normalized state from a record's signal fields. |
| `buildRecoveryAction(record)` | Pure derivation of the next action the app should take. |

## Normalized states

```
"billing_action_required"
| "payment_method_update_required"
| "pending_authentication"
| "processing"
| "recovered"
| "expired"
```

## Failure classification

| `failureKind` | Triggered by |
|---|---|
| `requires_payment_method` | declined / expired card, fraud rules |
| `requires_action` | SCA / 3DS challenge |
| `processing` | async PM (ACH, SEPA debit) settling |
| `expired` | subscription `incomplete_expired` (~23h elapsed) |

## Recovery actions

| Action | When | App should |
|---|---|---|
| `confirm_payment` | `pending_authentication` and `clientSecret` is present | call `stripe.confirmCardPayment(clientSecret)` on the client |
| `redirect_to_hosted_invoice` | declined PM, or 3DS without a `clientSecret` | redirect customer to `hostedInvoiceUrl` |
| `wait` | async PM still processing | poll again after `retryAfterMs` |
| `restart_signup` | subscription expired | re-run sign-up flow |
| `none` | recovered, or unknown record | nothing |

## Behavior

- Renewal invoices (`billing_reason !== "subscription_create"`) are ignored — the renewal-recovery service handles those. The first-payment scope is also matched via `subscription.status === "incomplete" / "incomplete_expired"`, so renewal-vs-first-payment classification doesn't depend on `billing_reason` alone.
- Verification is on by default. Each handler re-fetches the invoice (and subscription, and PaymentIntent for non-`paid` events) from Stripe through Swytchcode before deriving state. Disable per-handler with `verify: { invoice: false, paymentIntent: false, subscription: false }` (not recommended).
- Storage-agnostic: the caller persists the returned `RecoveryStateRecord` and passes the prior record back into the next handler so IDs and signals can be merged.
- `getRecoveryState` and `buildRecoveryAction` are pure — they read only the signal fields on the record, so they round-trip through any store.

## Usage

```ts
import {
  createFirstPaymentRecoveryService,
  type RecoveryStateRecord,
  type StripeEvent,
} from "./firstPaymentRecoveryService.js";

const recovery = createFirstPaymentRecoveryService({
  stripeSecretKey: process.env.STRIPE_SECRET_KEY!,
  defaultReturnUrl: "https://app.example.com/billing/return",
});

// Stripe webhook (signature already verified upstream)
async function onStripeEvent(event: StripeEvent) {
  const prior = await db.recovery.findByInvoiceOrSubscription(event);
  let next: RecoveryStateRecord | null = null;

  if (event.type === "invoice.payment_failed") {
    next = await recovery.handleInvoicePaymentFailed(event, prior ?? undefined);
  } else if (event.type === "invoice.payment_action_required") {
    next = await recovery.handleInvoicePaymentActionRequired(event, prior ?? undefined);
  } else if (event.type === "invoice.paid") {
    next = await recovery.handleInvoicePaid(event, prior ?? undefined);
  }
  if (next) await db.recovery.upsert(next);
}

// Surface the next action to the customer's billing UI
const record = await db.recovery.get(accountId);
const action = recovery.buildRecoveryAction(record ?? {});
// → { type: "confirm_payment", clientSecret } | { type: "redirect_to_hosted_invoice", url } | …
```

## Stripe canonical IDs (via Swytchcode)

| Canonical ID | Used by |
|---|---|
| `invoices.invoice.get` | every handler (re-verify) |
| `payment_intents.payment_intent.get` | `handleInvoicePaymentFailed`, `handleInvoicePaymentActionRequired` |
| `subscriptions.subscription.get` | every handler (detects `incomplete_expired`) |

All three resolve to the locally installed Stripe integration `stripe.stripe@2026-02-25.clover`.

## Local testing

Use the [Stripe CLI](../../docs/local-testing-with-stripe-cli.md) with the test cards documented at <https://docs.stripe.com/testing>:

| Scenario | Test card | Expected `state` |
|---|---|---|
| 3DS authentication required | `4000 0027 6000 3184` | `pending_authentication` |
| 3DS — auth fails | `4000 0084 0000 0029` | `payment_method_update_required` |
| Generic decline | `4000 0000 0000 0002` | `payment_method_update_required` |
| Insufficient funds | `4000 0000 0000 9995` | `payment_method_update_required` |
| Async PM (processing) | `4000 0000 0000 0077` | `processing` |
| Successful first payment | `4242 4242 4242 4242` | `recovered` |
