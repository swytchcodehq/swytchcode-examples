/**
 * Tiny end-to-end example: wire `renewalRecoveryService` into an Express
 * webhook handler with an in-memory store. Replace the store with your DB.
 */
import express, { type Request, type Response } from "express";
import {
  createRenewalRecoveryService,
  type RenewalStateRecord,
  type StripeEvent,
} from "./renewalRecoveryService.js";

const renewal = createRenewalRecoveryService({
  stripeSecretKey: process.env.STRIPE_SECRET_KEY!,
  grace: { maxAttempts: 4, maxDurationMs: 7 * 24 * 60 * 60 * 1000 },
});

const records = new Map<string, RenewalStateRecord>();

const app = express();
app.post(
  "/webhooks/stripe",
  express.raw({ type: "application/json" }),
  async (req: Request, res: Response) => {
    // Signature verification omitted — see examples/express/src/server.ts.
    const event = JSON.parse((req.body as Buffer).toString("utf8")) as StripeEvent;
    const subId = (event.data?.object as { id?: string; subscription?: string })?.subscription
      ?? (event.data?.object as { id?: string })?.id;
    const prior = subId ? records.get(subId) : undefined;

    let next: RenewalStateRecord | null = null;
    if (event.type === "invoice.paid") {
      next = await renewal.handleRecurringInvoicePaid(event, prior);
    } else if (event.type === "invoice.payment_failed") {
      next = await renewal.handleRecurringInvoicePaymentFailed(event, prior);
    } else if (event.type === "customer.subscription.updated") {
      next = await renewal.handleSubscriptionUpdated(event, prior);
    }

    if (next?.subscriptionId) records.set(next.subscriptionId, next);

    if (next?.state === "unpaid_locked") {
      // → revoke entitlements for this customer
    } else if (next?.state === "restored") {
      // → re-grant entitlements (one-shot signal)
    }
    res.json({ received: true, state: next?.state });
  },
);

app.listen(3000);
