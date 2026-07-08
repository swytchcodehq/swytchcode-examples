# Stripe Subscriptions

> Subscription lifecycle services that turn Stripe's webhook-driven edge cases into ready-to-use modules, with every Stripe call delegated to the [Swytchcode](https://cli.swytchcode.com) runtime.

[![Node 20+](https://img.shields.io/badge/node-20%2B-339933)](https://nodejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178c6)](https://www.typescriptlang.org/)
[![Runtime: Swytchcode](https://img.shields.io/badge/runtime-Swytchcode-5b2bd6)](https://cli.swytchcode.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

Each service owns one subscription problem (activation, payment recovery, plan changes, entitlements, webhook reliability) and resolves it against verified Stripe events rather than the browser redirect. No Stripe SDK: the services call canonical Stripe methods through the Swytchcode runtime, which handles auth, validation, and idempotency.

## Use cases

| Use case                    | What it solves                                                                                                                                                                                                                                                                                                          |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Subscription activation     | Prevents developers from granting access too early, such as on Checkout redirect success instead of waiting for verified billing events like invoice.paid. Stripe explicitly recommends provisioning access when the invoice is successfully paid and the subscription is active. stripe+1                              |
| First payment recovery      | Handles failed first subscription payments, including cases where the subscription is incomplete and the invoice requires authentication or a new payment method. This removes the need for developers to manually reason through requires_action, requires_payment_method, and incomplete_expired edge cases. stripe+1 |
| Renewal recovery            | Handles recurring payment failures after activation by helping developers model states like past_due, retry/recovery behavior, and unpaid, where Stripe recommends revoking access. This solves the common problem of inconsistent grace-period and lockout logic. stripe+2                                             |
| Plan changes and prorations | Helps developers safely handle upgrades, downgrades, scheduling, and proration behavior without corrupting subscription state or user entitlements. Stripe’s docs show that plan changes have nuanced proration and scheduling rules, especially in the customer portal and subscription updates. stripe+1              |
| Customer portal sync        | Lets developers rely on Stripe’s hosted customer portal for subscription and billing changes, while correctly syncing those changes back into the app through webhooks instead of trusting the return redirect. Stripe recommends using the customer portal for self-serve billing management. stripe+1                 |
| Entitlement sync            | Maps raw Stripe states like trialing, active, past_due, unpaid, canceled, and paused into product-safe access decisions such as active, grace, or locked. Stripe’s entitlements docs specifically position entitlements and entitlement webhooks as a way to drive access control in your own system. stripe+1          |
| Webhook reliability         | Solves one of the most common Stripe integration problems: missed events, duplicate delivery, idempotency, replay, and out-of-order processing. Stripe’s subscription docs and webhook docs make clear that subscriptions are fundamentally webhook-driven. stripe+1                                                    |
## Setup

```bash
# 1. Install dependencies
npm install

# 2. Copy and fill environment variables (see table above)
cp .env.example examples/express/.env

# 3. Install the Swytchcode CLI
npm install -g swytchcode

# 4. Bootstrap the integrations declared in .swytchcode/tooling.json
swytchcode bootstrap
```



## Run the demo

```bash
cd examples/express
npm run dev
```

Server starts at `http://localhost:3000`.

## Architecture

Stripe subscriptions are webhook-driven, so each service is built around the events that actually move state. The Express example verifies the webhook signature once, then routes each event type to the service that owns it.

```
Stripe event ──► /webhooks/stripe (signature verified) ──► service handler ──► Swytchcode runtime
```

| Stripe event | Handled by | What it drives |
|---|---|---|
| `checkout.session.completed` | activation-service | Records the pending sign-up; does not grant access yet |
| `invoice.paid` | activation-service | Grants access only after billing is verified |
| `invoice.payment_failed` (first cycle) | first-payment-recovery-service | Classifies the failure (`requires_payment_method`, SCA/3DS, async, expired) and emits a next-action hint |
| `invoice.payment_action_required` | first-payment-recovery-service | Surfaces the authentication step to the app |
| `invoice.payment_failed` (renewals) | renewal-recovery-service | Dunning: `past_due` grace, `unpaid` lockout, `restored` on recovery |
| `customer.subscription.updated` | plan-change-service | Applies upgrades, downgrades, and proration outcomes |
| subscription state projection | entitlement-sync-service | Maps Stripe states to app entitlements (`active`, `grace`, `locked`) |
| any event | webhook-reliability-service | Idempotent ingestion, dedupe, replay, out-of-order handling |

## Services

Each service is a single-file, storage-agnostic module. You provide persistence; the service returns updated records to store.

| Service | Status | Purpose |
|---|---|---|
| [`activation-service`](services/activation-service) | implemented + wired in the example | Convert sign-ups to active subscriptions — access granted only after verified `invoice.paid` |
| [`first-payment-recovery-service`](services/first-payment-recovery-service) | implemented | Recover failed initial charges — declines, SCA/3DS, async payment methods |
| [`renewal-recovery-service`](services/renewal-recovery-service) | implemented; standalone example included | Dunning for renewals — `past_due` grace, `unpaid` lockout, `restored` on recovery |
| [`plan-change-service`](services/plan-change-service) | implemented; example routes drafted, not yet mounted | Upgrades, downgrades, proration |
| [`entitlement-sync-service`](services/entitlement-sync-service) | implemented; no example wiring yet | Keep app entitlements in sync with Stripe |
| [`webhook-reliability-service`](services/webhook-reliability-service) | implemented; no example wiring yet | Idempotent, replayable webhook handling |

> **Status note:** all six service modules are implemented as standalone TypeScript files with public APIs you can import today. They differ in how far the runnable Express example exercises them: `activation-service` is mounted end to end in [`examples/express/src/server.ts`](examples/express/src/server.ts); `renewal-recovery-service` ships a standalone runnable example in [`services/renewal-recovery-service/example.ts`](services/renewal-recovery-service/example.ts); `plan-change-service` has route handlers written in [`examples/express/src/planChangeRoutes.ts`](examples/express/src/planChangeRoutes.ts) that are not yet imported into the server; `first-payment-recovery-service`, `entitlement-sync-service`, and `webhook-reliability-service` have no example wiring yet. The docs elsewhere label the last three as "scaffold"; that refers to example coverage, not the modules, which are written. See [docs/service-index.md](docs/service-index.md).

## Prerequisites

- Node.js ≥ 20
- npm ≥ 10
- [Stripe CLI](https://docs.stripe.com/stripe-cli) — for local webhook forwarding
- [Swytchcode CLI](https://swytchcode.com) — for runtime integration setup

## Environment variables

Copy the template and fill in your credentials before starting the server.

```bash
cp .env.example examples/express/.env
```

| Variable | Required | Where to get it |
|---|---|---|
| `STRIPE_SECRET_KEY` | Yes | [Stripe Dashboard → Developers → API keys](https://dashboard.stripe.com/test/apikeys) — use the `sk_test_...` key for local dev |
| `STRIPE_WEBHOOK_SECRET` | Yes | Run `stripe listen --forward-to localhost:3000/webhooks/stripe` — the CLI prints a `whsec_...` value; paste it here |
| `SWYTCHCODE_TOKEN` | Yes | [Swytchcode Dashboard](https://swytchcode.com) → Settings → API keys |
| `PORT` | No | Defaults to `3000` |



### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Health check |
| `POST` | `/checkout` | Create a Stripe Checkout session |
| `GET` | `/activation/:accountId` | Get current activation state for an account |
| `POST` | `/webhooks/stripe` | Stripe webhook receiver |
| `POST` | `/plan-change/preview` | Preview a plan change with proration |
| `POST` | `/plan-change/apply` | Apply a plan change |

## Test with Stripe CLI

**1. Forward webhooks to your local server:**

```bash
stripe listen --forward-to localhost:3000/webhooks/stripe
```

Copy the printed `whsec_...` value into `.env` as `STRIPE_WEBHOOK_SECRET`, then restart the server.

**2. Trigger test events:**

```bash
# Subscription activation flow
stripe trigger checkout.session.completed
stripe trigger invoice.paid

# Renewal recovery flow
stripe trigger invoice.payment_failed

# Plan change flow
stripe trigger customer.subscription.updated
```

**3. Check activation state:**

```bash
curl http://localhost:3000/activation/<accountId>
```

## Repo layout

```
services/   — subscription service modules (one problem per file)
examples/   — reference integrations (Express)
docs/       — architecture, service index, local testing guide
```
