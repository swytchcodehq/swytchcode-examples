# Stripe Renewal Recovery

A single reusable TypeScript file — [`renewalRecoveryService.ts`](renewalRecoveryService.ts) — that solves one problem: **recurring subscription payment failures after activation.**

Stripe recommends mirroring renewal billing health off two webhooks — `invoice.paid` and `invoice.payment_failed` — and treating subscription status `past_due` as recoverable while `unpaid` should revoke product access.

All Stripe calls are delegated to the [Swytchcode](https://swytchcode.com) runtime (no Stripe SDK).

## Setup

```bash
# Once per machine
swytchcode login
swytchcode get stripe

# Once per repo (these are the only Stripe canonical IDs the file needs)
swytchcode add invoices.invoice.get
swytchcode add subscriptions.subscription.get

# In your project
npm install swytchcode-runtime
```

Then drop [`renewalRecoveryService.ts`](renewalRecoveryService.ts) into your codebase and import it. A copy-pasteable Express webhook wiring lives in [`example.ts`](example.ts).

## Public API

| Function | Purpose |
|---|---|
| `createRenewalRecoveryService({ stripeSecretKey, grace? })` | Factory. |
| `handleRecurringInvoicePaid(event, prior?)` | Reconciles `invoice.paid` for renewal invoices only. Re-fetches invoice + subscription. |
| `handleRecurringInvoicePaymentFailed(event, prior?)` | Reconciles `invoice.payment_failed` for renewal invoices only. |
| `handleSubscriptionUpdated(event, prior?)` | Reconciles `customer.subscription.updated` (catches Stripe's `past_due → unpaid` flip). |
| `getRenewalState(record)` | Pure derivation of the normalized state from a record's signal fields. |

## Normalized states

```
"healthy" | "grace" | "unpaid_locked" | "restored"
```

Treat `unpaid_locked` as **revoke paid access**. `restored` is a one-shot transition emitted on the first healthy event after a degraded record; it returns to `healthy` on the next reconcile.

## Behavior

- First-payment invoices (`billing_reason === "subscription_create"`) are ignored — the [`first-payment-recovery-service`](../first-payment-recovery-service) owns that lifecycle.
- `unpaid_locked` is set whenever Stripe reports subscription status `unpaid`, `canceled`, or `incomplete_expired`. Stripe makes this decision based on your dunning settings (smart retries, max retries) — mirror it; don't second-guess it.
- `past_due` maps to `grace` until either Stripe flips the subscription to `unpaid` or your configured grace bound trips:
  - `grace.maxAttempts` — locks once `invoice.attempt_count` reaches this value.
  - `grace.maxDurationMs` — locks once `(now - firstPastDueAt)` reaches this value.
  - Leave both undefined to defer entirely to Stripe.
- Verification is on by default. Each handler re-fetches the invoice and subscription from Stripe through Swytchcode before deriving state. Disable per-handler with `verify: { invoice: false, subscription: false }` (not recommended).
- Storage-agnostic: the caller persists the returned `RenewalStateRecord` and passes the prior record back into the next handler so `priorState` and `firstPastDueAt` carry through.

## Usage

```ts
import {
  createRenewalRecoveryService,
  type RenewalStateRecord,
  type StripeEvent,
} from "./renewalRecoveryService.js";

const renewal = createRenewalRecoveryService({
  stripeSecretKey: process.env.STRIPE_SECRET_KEY!,
  grace: { maxAttempts: 4, maxDurationMs: 7 * 24 * 60 * 60 * 1000 },
});

// Stripe webhook (signature already verified upstream)
async function onStripeEvent(event: StripeEvent) {
  const prior = await db.renewal.findBySubscription(event);
  let next: RenewalStateRecord | null = null;

  if (event.type === "invoice.paid") {
    next = await renewal.handleRecurringInvoicePaid(event, prior ?? undefined);
  } else if (event.type === "invoice.payment_failed") {
    next = await renewal.handleRecurringInvoicePaymentFailed(event, prior ?? undefined);
  } else if (event.type === "customer.subscription.updated") {
    next = await renewal.handleSubscriptionUpdated(event, prior ?? undefined);
  }
  if (next) await db.renewal.upsert(next);
}

// Authorize requests
const record = await db.renewal.get(accountId);
const state = renewal.getRenewalState(record ?? {});
if (state === "unpaid_locked") throw new Error("paid features locked");
```

## Stripe canonical IDs (via Swytchcode)

| Canonical ID | Used by |
|---|---|
| `invoices.invoice.get` | `handleRecurringInvoicePaid`, `handleRecurringInvoicePaymentFailed` (re-verify) |
| `subscriptions.subscription.get` | every handler (detects `past_due → unpaid` flip) |

Both resolve to the locally installed Stripe integration `stripe.stripe@2026-02-25.clover`.

## Local testing

Use the [Stripe CLI](../../docs/local-testing-with-stripe-cli.md) with [test clocks](https://docs.stripe.com/billing/testing/test-clocks) to simulate renewal cycles, and the test cards documented at <https://docs.stripe.com/testing>:

| Scenario | Test card | Expected `state` |
|---|---|---|
| Renewal succeeds | `4242 4242 4242 4242` | `healthy` (or `restored` if previously degraded) |
| Renewal declined, retries pending | `4000 0000 0000 0341` | `grace` |
| Stripe exhausts retries → `unpaid` | (after smart retries) | `unpaid_locked` |