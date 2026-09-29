# Stripe Webhook Reliability

A single reusable TypeScript file — [`webhookReliabilityService.ts`](webhookReliabilityService.ts) — that solves one problem: **making Stripe webhook delivery safe and idempotent for subscription flows.**

Stripe recommends monitoring at minimum `checkout.session.completed`, `invoice.paid`, and `invoice.payment_failed` for subscription lifecycles, and warns that webhooks may be **duplicated, delivered out of order, or arrive after the underlying object has already advanced**. This service handles all three.

All Stripe API calls (replay, reconciliation) are delegated to the [Swytchcode](https://swytchcode.com) runtime — no Stripe SDK. Signature verification uses Node's built-in `crypto`.

## Setup

```bash
# Once per machine
swytchcode login
swytchcode get stripe

# Once per repo
swytchcode add events.event.get                       # replay-by-id
swytchcode add invoices.invoice.get                   # already added by activation-service
swytchcode add subscriptions.subscription.get         # already added by plan-change-service
swytchcode add checkout.session.get                   # already added by activation-service

# In your project
npm install swytchcode-runtime
```

Then drop [`webhookReliabilityService.ts`](webhookReliabilityService.ts) into your codebase and import it.

## Public API

| Function | Purpose |
|---|---|
| `createWebhookReliabilityService({ webhookSecret, stripeSecretKey, store, handlers })` | Factory. |
| `verifyAndParseWebhook(rawBody, signature)` | Verifies the `Stripe-Signature` header against the raw request body using HMAC-SHA256, enforces the replay-tolerance window (default 300s), and returns the parsed `StripeEvent`. Throws `WebhookVerificationError` on any failure. |
| `storeEvent(event)` | Persists the raw event through the caller-supplied `EventStore`. Returns `verified` for new events and `duplicate_ignored` for repeats. |
| `processEvent(event, context?)` | The full pipeline: persist → idempotency check → out-of-order suppression → optional reconciliation → caller's handler. Returns one of `processed`, `duplicate_ignored`, `failed_retryable`, `failed_terminal`. |
| `replayEvent(eventId, context?)` | Re-fetches the canonical event from Stripe via `events.event.get` and re-runs the handler. Returns `replayed` on success. |
| `getEventStatus(eventId)` | Reads the stored record. |

## Normalized states

```
"verified" | "duplicate_ignored" | "processed" | "replayed" | "failed_retryable" | "failed_terminal"
```

- `verified` — signature OK, event persisted, handler not yet invoked.
- `duplicate_ignored` — the same `event.id` was already seen, OR the event is strictly older than the newest one processed for the same resource (out-of-order safe drop).
- `processed` — handler ran successfully on first delivery.
- `replayed` — handler ran successfully via `replayEvent`.
- `failed_retryable` — handler threw `RetryableError` (or a transient I/O code). Stripe will redeliver, or the caller can schedule a retry. Not terminal.
- `failed_terminal` — handler threw any other error. Terminal; will not auto-retry.

## Behavior

- **Pass the raw body, not parsed JSON.** Stripe signs the exact bytes; `JSON.stringify(req.body)` will not match. In Express use `express.raw({ type: "application/json" })` for the webhook route only.
- **Constant-time signature compare.** Uses `crypto.timingSafeEqual` over the hex digests; supports header rotation by accepting any `v1=` candidate.
- **Replay tolerance.** Rejects timestamps older — or further in the future — than `toleranceSeconds` (default 300, matching Stripe's recommendation).
- **Idempotency by `event.id`.** `storeEvent` calls `EventStore.putIfAbsent`; implementations should use a conditional insert (e.g. `INSERT ... ON CONFLICT DO NOTHING`) so concurrent webhook deliveries cannot both run the handler.
- **Out-of-order safety.** If your store implements `getResourceCursor` / `advanceResourceCursor`, an event whose `created` is strictly less than the resource's high-water mark is dropped as `duplicate_ignored`. This is the documented mitigation for Stripe's out-of-order delivery.
- **Reconciliation on by default.** Before invoking the handler, `processEvent` re-fetches the underlying Stripe object (subscription / invoice / checkout session) via Swytchcode so the handler sees the *current* state, not the snapshot Stripe encoded in the event payload. Disable with `reconcile: false` when latency matters more than freshness.
- **Replay sources from Stripe.** `replayEvent(eventId)` always calls `events.event.get` instead of trusting the local copy — Stripe retains events for 30 days.
- **Storage-agnostic.** Bring your own DB. The `EventStore` interface is six small methods; two of them are optional.

## EventStore contract (summary)

| Method | Required | Notes |
|---|---|---|
| `putIfAbsent(record)` | yes | Must be atomic; return `{ inserted: false, existing }` for repeats. |
| `get(eventId)` | yes | — |
| `update(eventId, patch)` | yes | Patch-merge update. |
| `getResourceCursor(resourceId)` | optional | Returns max `event.created` seen for the resource. |
| `advanceResourceCursor(resourceId, createdAt)` | optional | Atomically `max(existing, createdAt)`. |

## Usage

```ts
import express from "express";
import {
  createWebhookReliabilityService,
  RetryableError,
  type StripeEvent,
} from "./webhookReliabilityService.js";

const webhooks = createWebhookReliabilityService({
  webhookSecret: process.env.STRIPE_WEBHOOK_SECRET!,
  stripeSecretKey: process.env.STRIPE_SECRET_KEY!,
  store: myEventStore,                           // your DB-backed implementation
  handlers: {
    "checkout.session.completed": async (event) => {
      const session = event.data.object as { id: string; subscription?: string };
      await db.activation.markCompleted(session.id, session.subscription);
    },
    "invoice.paid": async (event) => {
      await db.invoices.markPaid((event.data.object as { id: string }).id);
    },
    "invoice.payment_failed": async (event) => {
      const ok = await dunning.scheduleRetry(event.data.object);
      if (!ok) throw new RetryableError("dunning queue temporarily unavailable");
    },
  },
});

const app = express();

// IMPORTANT: raw body for the webhook route only — do NOT use express.json() here.
app.post(
  "/stripe/webhook",
  express.raw({ type: "application/json" }),
  async (req, res) => {
    let parsed;
    try {
      parsed = webhooks.verifyAndParseWebhook(req.body, req.header("stripe-signature") ?? "");
    } catch (err) {
      return res.status(400).send(`verification failed: ${(err as Error).message}`);
    }

    const result = await webhooks.processEvent(parsed.event, { reqId: req.id });
    if (result.state === "failed_retryable") return res.status(500).end();   // Stripe will redeliver
    return res.status(200).end();
  },
);

// Operator endpoint — replay a dropped event by id.
app.post("/admin/replay/:eventId", async (req, res) => {
  const result = await webhooks.replayEvent(req.params.eventId);
  res.json({ state: result.state, eventId: result.record.eventId });
});
```

## Stripe canonical IDs (via Swytchcode)

| Canonical ID | Used by |
|---|---|
| `events.event.get` | `replayEvent` (re-fetch canonical event) |
| `subscriptions.subscription.get` | reconciliation for `customer.subscription.*` |
| `invoices.invoice.get` | reconciliation for `invoice.*` |
| `checkout.session.get` | reconciliation for `checkout.session.*` |

All four resolve to the locally installed Stripe integration `stripe.stripe@2026-02-25.clover`.
