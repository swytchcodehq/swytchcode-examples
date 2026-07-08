# Local testing with the Stripe CLI

The Stripe CLI lets you forward live webhook events to your local services and trigger synthetic events for replay/regression testing.

## Install

- macOS: `brew install stripe/stripe-cli/stripe`
- Windows: `scoop install stripe`
- Linux: see https://docs.stripe.com/stripe-cli

## Authenticate

```bash
stripe login
```

## Forward webhooks to a local service

```bash
stripe listen --forward-to localhost:3000/webhooks/stripe
```

Copy the printed `whsec_...` value into your `.env` as `STRIPE_WEBHOOK_SECRET`.

## Trigger events

```bash
stripe trigger customer.subscription.created
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.updated
```

## Service-specific scenarios

| Service | Useful triggers |
|---|---|
| `activation-service` | `checkout.session.completed`, `invoice.paid` |
| `first-payment-recovery-service` | `invoice.payment_failed`, `invoice.payment_action_required`, `invoice.paid` (with `billing_reason=subscription_create`) |
| `renewal-recovery-service` | `invoice.payment_failed` (with `billing_reason=subscription_cycle`) |
| `plan-change-service` | `customer.subscription.updated` |
| `entitlement-sync-service` | `customer.subscription.updated`, `customer.subscription.deleted` |
| `webhook-reliability-service` | any — used to test idempotency and replay |

## Replaying past events

```bash
stripe events resend evt_XXXXXXXX
```
