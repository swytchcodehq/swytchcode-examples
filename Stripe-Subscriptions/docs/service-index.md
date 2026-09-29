# Service index

| Service | Path | Status | Responsibility |
|---|---|---|---|
| Activation | [services/activation-service](../services/activation-service) | implemented | Convert successful sign-ups into active Stripe subscriptions. Never grants access from the browser redirect alone — activation only follows verified `invoice.paid`. Single file: [`activationService.ts`](../services/activation-service/activationService.ts). |
| First payment recovery | [services/first-payment-recovery-service](../services/first-payment-recovery-service) | implemented | Detect and recover from failed initial subscription charges. Classifies each failure into `requires_payment_method`, `requires_action` (SCA / 3DS), `processing` (async PMs), or `expired` (`incomplete_expired`); reacts to `invoice.payment_failed`, `invoice.payment_action_required`, and `invoice.paid`; emits a normalized state and a next-action hint for the application. Single file: [`firstPaymentRecoveryService.ts`](../services/first-payment-recovery-service/firstPaymentRecoveryService.ts). |
| Renewal recovery | [services/renewal-recovery-service](../services/renewal-recovery-service) | implemented | Dunning + recovery for renewals — `past_due` grace, `unpaid` lockout, `restored` on recovery. Single file: [`renewalRecoveryService.ts`](../services/renewal-recovery-service/renewalRecoveryService.ts). |
| Plan change | [services/plan-change-service](../services/plan-change-service) | scaffold | Upgrades, downgrades, proration, schedule transitions. |
| Entitlement sync | [services/entitlement-sync-service](../services/entitlement-sync-service) | scaffold | Project Stripe subscription state into application-side entitlements. |
| Webhook reliability | [services/webhook-reliability-service](../services/webhook-reliability-service) | scaffold | Idempotent ingestion, dedupe, replay, and DLQ for Stripe webhooks. |

## Examples

| Example | Path |
|---|---|
| Express | [examples/express](../examples/express) |
