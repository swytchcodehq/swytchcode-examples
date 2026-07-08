import express, { type Request, type Response } from "express";
import {
  createActivationService,
  type ActivationRecord,
  type StripeEvent,
} from "../../../services/activation-service/activationService.js";
import { verifyStripeSignature } from "./verifyStripeSignature.js";

function required(name: string): string {
  const v = process.env[name];
  if (!v) {
    console.error(`missing required env var: ${name}`);
    process.exit(1);
  }
  return v;
}

const PORT = Number(process.env.PORT ?? 3000);
const STRIPE_SECRET_KEY = required("STRIPE_SECRET_KEY");
const STRIPE_WEBHOOK_SECRET = required("STRIPE_WEBHOOK_SECRET");

const activation = createActivationService({ stripeSecretKey: STRIPE_SECRET_KEY });

// Tiny in-memory store. Real apps replace this with their DB.
const records = new Map<string, ActivationRecord>();
function findBySession(sessionId: string): ActivationRecord | undefined {
  for (const r of records.values()) if (r.sessionId === sessionId) return r;
  return undefined;
}
function findBySubscription(subscriptionId: string): ActivationRecord | undefined {
  for (const r of records.values()) if (r.subscriptionId === subscriptionId) return r;
  return undefined;
}

const app = express();

// Webhook route MUST be mounted before express.json() so we keep the raw body
// for signature verification.
app.post(
  "/webhooks/stripe",
  express.raw({ type: "application/json" }),
  async (req: Request, res: Response) => {
    const sig = req.header("stripe-signature");
    if (!sig) {
      res.status(400).send("missing stripe-signature");
      return;
    }

    let event: StripeEvent;
    try {
      event = verifyStripeSignature(
        (req.body as Buffer).toString("utf8"),
        sig,
        STRIPE_WEBHOOK_SECRET,
      ) as StripeEvent;
    } catch (err) {
      console.warn("webhook signature verification failed:", (err as Error).message);
      res.status(400).send("invalid signature");
      return;
    }

    try {
      let next: ActivationRecord | null = null;
      if (event.type === "checkout.session.completed") {
        const sessionId = (event.data?.object as { id?: string } | undefined)?.id;
        const prior = sessionId ? findBySession(sessionId) : undefined;
        next = await activation.handleCheckoutSessionCompleted(event, prior);
      } else if (event.type === "invoice.paid") {
        const inv = event.data?.object as
          | {
              parent?: { subscription_details?: { subscription?: string | { id: string } } };
              subscription?: string | { id: string };
            }
          | undefined;
        const subRef =
          inv?.parent?.subscription_details?.subscription ?? inv?.subscription ?? undefined;
        const subscriptionId =
          typeof subRef === "string" ? subRef : subRef?.id;
        const prior = subscriptionId ? findBySubscription(subscriptionId) : undefined;
        next = await activation.handleInvoicePaid(event, prior);
      }
      if (next) records.set(next.accountId, next);
      res.status(200).json({ received: true, type: event.type });
    } catch (err) {
      console.error("handler error", err);
      // 5xx → Stripe will retry the webhook
      res.status(500).send("handler failed");
    }
  },
);

app.use(express.json());

app.post("/checkout", async (req: Request, res: Response) => {
  const body = req.body as {
    accountId?: string;
    priceId?: string;
    successUrl?: string;
    cancelUrl?: string;
    workspaceId?: string;
    tenantId?: string;
    customerEmail?: string;
  };
  const { accountId, priceId, successUrl, cancelUrl } = body;
  if (!accountId || !priceId || !successUrl || !cancelUrl) {
    res.status(400).json({
      error: "accountId, priceId, successUrl, cancelUrl are required",
    });
    return;
  }
  try {
    const result = await activation.createCheckoutSession({
      accountId,
      successUrl,
      cancelUrl,
      lineItems: [{ price: priceId, quantity: 1 }],
      workspaceId: body.workspaceId,
      tenantId: body.tenantId,
      customerEmail: body.customerEmail,
    });
    records.set(result.record.accountId, result.record);
    res.json({
      sessionId: result.sessionId,
      url: result.url,
      expiresAt: result.expiresAt,
      state: result.record.state,
    });
  } catch (err) {
    console.error("createCheckoutSession failed", err);
    res.status(500).json({ error: (err as Error).message });
  }
});

app.get("/activation/:accountId", (req: Request, res: Response) => {
  const accountId = req.params.accountId;
  if (!accountId) {
    res.status(400).json({ error: "accountId is required" });
    return;
  }
  const record = records.get(accountId);
  if (!record) {
    res.json({ accountId, state: "pending", known: false });
    return;
  }
  const state = activation.getActivationState(record);
  res.json({ accountId, state, known: true, record });
});

app.get("/healthz", (_req: Request, res: Response) => {
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`activation example listening on http://localhost:${PORT}`);
});
