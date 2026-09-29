import { type Request, type Response, Router } from "express";
import {
  createPlanChangeService,
  type PlanChangeRecord,
  type StripeEvent,
} from "../../../services/plan-change-service/planChangeService.js";

const planChange = createPlanChangeService({
  stripeSecretKey: process.env.STRIPE_SECRET_KEY!,
});

const records = new Map<string, PlanChangeRecord>();
const findBySubscription = (id: string) => {
  for (const r of records.values()) if (r.subscriptionId === id) return r;
  return undefined;
};

export const planChangeRoutes = Router();

planChangeRoutes.post("/preview", async (req: Request, res: Response) => {
  const { accountId, subscriptionId, priceId, mode } = req.body as {
    accountId: string;
    subscriptionId: string;
    priceId: string;
    mode?: "upgrade_now" | "immediate_no_proration";
  };
  try {
    const preview = await planChange.previewPlanChange({
      accountId,
      subscriptionId,
      targets: [{ price: priceId, quantity: 1 }],
      mode,
    });
    res.json(preview);
  } catch (err) {
    const code = (err as Error & { code?: string }).code;
    res.status(400).json({ error: (err as Error).message, code });
  }
});

planChangeRoutes.post("/apply", async (req: Request, res: Response) => {
  const { accountId, subscriptionId, priceId, mode, prorationDate } = req.body as {
    accountId: string;
    subscriptionId: string;
    priceId: string;
    mode?: "upgrade_now" | "immediate_no_proration";
    prorationDate?: number;
  };
  try {
    const result = await planChange.changePlan({
      accountId,
      subscriptionId,
      targets: [{ price: priceId, quantity: 1 }],
      mode,
      prorationDate,
    });
    records.set(result.record.accountId, result.record);
    res.json(result);
  } catch (err) {
    const code = (err as Error & { code?: string }).code;
    res.status(code === "blocked_incomplete" ? 409 : 400).json({
      error: (err as Error).message,
      code,
    });
  }
});

// Mount this under the same /webhooks/stripe handler as activation —
// it dispatches `customer.subscription.updated` and `invoice.paid` events.
export async function dispatchPlanChangeEvent(event: StripeEvent): Promise<void> {
  let next: PlanChangeRecord | null = null;
  if (event.type === "customer.subscription.updated") {
    const sub = event.data?.object as { id?: string } | undefined;
    const prior = sub?.id ? findBySubscription(sub.id) : undefined;
    next = await planChange.handleSubscriptionUpdated(event, prior);
  } else if (event.type === "invoice.paid") {
    const inv = event.data?.object as
      | { parent?: { subscription_details?: { subscription?: string | { id: string } } }; subscription?: string | { id: string } }
      | undefined;
    const subRef = inv?.parent?.subscription_details?.subscription ?? inv?.subscription;
    const subscriptionId = typeof subRef === "string" ? subRef : subRef?.id;
    const prior = subscriptionId ? findBySubscription(subscriptionId) : undefined;
    next = await planChange.handleInvoicePaid(event, prior);
  }
  if (next) records.set(next.accountId, next);
}
