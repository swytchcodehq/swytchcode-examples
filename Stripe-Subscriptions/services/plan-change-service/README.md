# Stripe Subscription Plan Change

A single reusable TypeScript file — [`planChangeService.ts`](planChangeService.ts) — that solves one problem: **safe upgrades, downgrades, and proration-aware subscription changes.**

Stripe says subscriptions can be modified in place, and notes that **Checkout-created subscriptions cannot be updated while the session subscription is `incomplete`**. This service preflights that condition and surfaces it as a normalized state instead of letting Stripe fail mid-flow.

All Stripe calls are delegated to the [Swytchcode](https://swytchcode.com) runtime (no Stripe SDK).

## Setup

```bash
# Once per machine
swytchcode login
swytchcode get stripe

# Once per repo
swytchcode add subscriptions.subscription.get
swytchcode add subscriptions.subscription.create_2926   # "Update a subscription"
swytchcode add invoices.create_preview.create
swytchcode add invoices.invoice.get                     # already added by activation-service

# In your project
npm install swytchcode-runtime
```

Then drop [`planChangeService.ts`](planChangeService.ts) into your codebase and import it.

## Public API

| Function | Purpose |
|---|---|
| `createPlanChangeService({ stripeSecretKey })` | Factory. |
| `previewPlanChange(input)` | Calls Stripe's `create_preview` invoice with the target items. Returns the net `amountDue`, the proration line subtotal, and a `prorationDate` snapshot to feed back into `changePlan` so the actual proration matches the preview exactly. |
| `changePlan(input)` | Updates the subscription in place. `mode=upgrade_now` uses `proration_behavior=always_invoice` + `payment_behavior=default_incomplete` and yields `change_pending` until `invoice.paid`. `mode=immediate_no_proration` uses `proration_behavior=none` and yields `changed` immediately. `mode=scheduled` is rejected (see below). |
| `handleSubscriptionUpdated(event, prior?)` | Reconciles `customer.subscription.updated`. Only reacts to subscriptions tagged with our `plan_change_id` metadata, so unrelated updates are ignored. |
| `handleInvoicePaid(event, prior?)` | Reconciles `invoice.paid` for `billing_reason=subscription_update` only. Promotes state to `changed`. (Initial-payment invoices are handled by `activation-service`, renewals by `renewal-recovery-service`.) |
| `getPlanChangeState(record)` | Pure derivation of the normalized state from a record's signal fields. |

## Modes

| Mode | Stripe params | Outcome |
|---|---|---|
| `upgrade_now` *(default)* | `proration_behavior=always_invoice`, `payment_behavior=default_incomplete` | A proration invoice is created and charged. State is `change_pending` until `invoice.paid` flips it to `changed`. |
| `immediate_no_proration` | `proration_behavior=none` | Items swap immediately; customer is billed the new price at the next renewal. State goes straight to `changed`. |
| `scheduled` | — | **Not supported in this build.** Requires `subscription_schedules.*` canonical IDs, which currently fail to register with `swytchcode add` due to a registry struct resolution error (`subscription_schedule_Union not found in STRUCTS`). `changePlan` throws with `code=unsupported_scheduled_mode`. |

## Normalized states

```
"preview_ready" | "change_pending" | "changed" | "scheduled" | "blocked_incomplete"
```

- `preview_ready` — preview returned; nothing applied yet.
- `change_pending` — subscription updated; waiting on `invoice.paid` for the proration charge.
- `changed` — change is fully applied (invoice paid, or no invoice was needed).
- `scheduled` — reserved for the schedule-backed flow once the registry bug is fixed.
- `blocked_incomplete` — the subscription is `incomplete` (typical for Checkout-created subs whose first payment hasn't cleared). Stripe will reject updates; do not retry until activation completes.

## Behavior

- **Incomplete subscriptions are blocked, not retried.** `previewPlanChange` and `changePlan` both call `subscriptions.subscription.get` first; if `status ∈ {incomplete, incomplete_expired}`, preview returns `state=blocked_incomplete` and `changePlan` throws with `code=blocked_incomplete`.
- **Proration math is locked.** `previewPlanChange` snapshots `proration_date` and returns it; pass it back into `changePlan` so the invoice Stripe issues exactly matches what you previewed.
- **Idempotent webhooks.** Each plan change is tagged on Stripe `metadata.plan_change_id`. `handleSubscriptionUpdated` and `handleInvoicePaid` ignore events whose `plan_change_id` doesn't match the one on the prior record.
- **Item swap defaults.** If `targets` don't specify `replacesSubscriptionItemId`, the service replaces *all* current subscription items with the targets (the common single-item plan-swap case). Pass explicit `replacesSubscriptionItemId` for per-item swaps on multi-item subscriptions.
- **Verification on by default.** Both webhook handlers re-fetch via Swytchcode before deriving state. Disable per-call with `verify: { invoice: false, subscription: false }` (not recommended).
- **Storage-agnostic.** The caller persists the returned `PlanChangeRecord` and passes the prior record back into the next handler.

## Usage

```ts
import { createPlanChangeService, type PlanChangeRecord, type StripeEvent }
  from "./planChangeService.js";

const planChange = createPlanChangeService({
  stripeSecretKey: process.env.STRIPE_SECRET_KEY!,
});

// 1. Preview
const preview = await planChange.previewPlanChange({
  accountId: "acct_42",
  subscriptionId: "sub_123",
  targets: [{ price: "price_pro_yearly", quantity: 1 }],
  mode: "upgrade_now",
});
if (preview.state === "blocked_incomplete") return res.status(409).send("activation pending");
res.json({ amountDue: preview.amountDue, prorationAmount: preview.prorationAmount });

// 2. Apply
const applied = await planChange.changePlan({
  accountId: "acct_42",
  subscriptionId: "sub_123",
  targets: [{ price: "price_pro_yearly", quantity: 1 }],
  mode: "upgrade_now",
  prorationDate: preview.prorationDate, // lock the math
});
await db.planChange.upsert(applied.record);   // state === "change_pending"

// 3. Stripe webhook (signature already verified upstream)
async function onStripeEvent(event: StripeEvent) {
  const prior = await db.planChange.findBySubscription(event);
  let next: PlanChangeRecord | null = null;

  if (event.type === "customer.subscription.updated") {
    next = await planChange.handleSubscriptionUpdated(event, prior ?? undefined);
  } else if (event.type === "invoice.paid") {
    next = await planChange.handleInvoicePaid(event, prior ?? undefined);
  }
  if (next) await db.planChange.upsert(next);   // state === "changed" once invoice.paid
}
```

## Stripe canonical IDs (via Swytchcode)

| Canonical ID | Used by |
|---|---|
| `subscriptions.subscription.get` | preflight + verify |
| `subscriptions.subscription.create_2926` | `changePlan` (Update a subscription) |
| `invoices.create_preview.create` | `previewPlanChange` |
| `invoices.invoice.get` | `handleInvoicePaid` (re-verify) |

All four resolve to the locally installed Stripe integration `stripe.stripe@2026-02-25.clover`.
