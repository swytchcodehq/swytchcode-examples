/**
 * swytchcode-stripe-plan-change — single-file reusable service.
 *
 * Solves one problem: safe upgrades, downgrades, and proration-aware
 * subscription changes. Stripe says subscriptions can be modified in place,
 * and notes that Checkout-created subscriptions cannot be updated while
 * the session subscription is `incomplete`.
 *
 * All Stripe API calls are delegated to the Swytchcode runtime — no Stripe SDK.
 * Canonical IDs used (must be `swytchcode add`ed before use):
 *   - subscriptions.subscription.get
 *   - subscriptions.subscription.create_2926          // "Update a subscription"
 *   - invoices.create_preview.create                  // "Create a preview invoice"
 *   - invoices.invoice.get                            // (re)used for handleInvoicePaid verify
 *
 * Public API (see `createPlanChangeService` below):
 *   - previewPlanChange(input)
 *   - changePlan(input)
 *   - handleSubscriptionUpdated(event, prior?)
 *   - handleInvoicePaid(event, prior?)
 *   - getPlanChangeState(record)
 */
import { exec as defaultExec } from "swytchcode-runtime";

// ─── Public types ────────────────────────────────────────────────────────────

export type PlanChangeMode = "upgrade_now" | "immediate_no_proration" | "scheduled";

export type PlanChangeState =
  | "preview_ready"
  | "change_pending"
  | "changed"
  | "scheduled"
  | "blocked_incomplete";

/**
 * Persistable record. Caller stores it (DB, KV, memory — the service is
 * storage-agnostic). Handlers return an updated record; the caller persists.
 */
export interface PlanChangeRecord {
  accountId: string;
  state: PlanChangeState;
  subscriptionId: string;
  customerId?: string;
  /** Currently-active Stripe price IDs on the subscription. */
  currentPriceIds?: string[];
  /** Target price IDs the change is moving toward. */
  targetPriceIds?: string[];
  /** Plan-change correlation id stored on Stripe metadata for replay safety. */
  planChangeId?: string;
  /** Mode requested by the caller. */
  mode?: PlanChangeMode;
  /** Stripe proration_date (epoch seconds) snapshotted at preview time. */
  prorationDate?: number;
  /** Invoice produced by an `always_invoice` proration, if any. */
  prorationInvoiceId?: string;
  prorationInvoiceStatus?: string;
  prorationInvoiceAmountDue?: number;
  /** Raw subscription signals — getPlanChangeState derives `state` from these. */
  subscriptionStatus?: string;
  workspaceId?: string;
  tenantId?: string;
  metadata?: Record<string, string>;
  updatedAt?: number;
}

export interface StripeEvent<T = unknown> {
  id: string;
  type: string;
  data: { object: T };
  livemode?: boolean;
  created?: number;
}

/** Item-level change request: which price to land on, and how many seats. */
export interface PlanChangeItemTarget {
  /** Stripe price ID to land on. */
  price: string;
  /** Quantity for the new item. Defaults to 1. */
  quantity?: number;
  /** Optional: id of the existing subscription_item being replaced. If omitted, the service
   * replaces ALL current items with `targets` (the common single-item case). */
  replacesSubscriptionItemId?: string;
}

export interface PreviewPlanChangeInput {
  accountId: string;
  subscriptionId: string;
  /** Target items the subscription should land on after the change. */
  targets: PlanChangeItemTarget[];
  mode?: PlanChangeMode; // default "upgrade_now"
  workspaceId?: string;
  tenantId?: string;
  metadata?: Record<string, string>;
}

export interface PreviewPlanChangeResult {
  state: PlanChangeState; // "preview_ready" or "blocked_incomplete"
  /** Net amount that would be billed in cents on the next invoice. */
  amountDue: number;
  /** Sum of proration line items only (positive=charge, negative=credit). */
  prorationAmount: number;
  currency: string;
  periodStart: number;
  periodEnd: number;
  /** Stripe `proration_date` snapshot — pass back into changePlan to lock math. */
  prorationDate: number;
  lines: Array<{
    description?: string;
    amount: number;
    proration: boolean;
    period?: { start: number; end: number };
    priceId?: string;
  }>;
  record: PlanChangeRecord;
}

export interface ChangePlanInput {
  accountId: string;
  subscriptionId: string;
  targets: PlanChangeItemTarget[];
  mode?: PlanChangeMode; // default "upgrade_now"
  /** Pass the value returned by previewPlanChange to keep proration math identical. */
  prorationDate?: number;
  /** Plan-change correlation id; auto-generated if absent. */
  planChangeId?: string;
  workspaceId?: string;
  tenantId?: string;
  metadata?: Record<string, string>;
}

export interface ChangePlanResult {
  state: PlanChangeState;
  /** Stripe subscription id (unchanged across plan changes). */
  subscriptionId: string;
  /** Latest invoice id, if Stripe created/touched one (e.g. `always_invoice`). */
  latestInvoiceId?: string;
  record: PlanChangeRecord;
}

/** A Swytchcode exec callable. Default uses `swytchcode-runtime`. Override for tests. */
export type ExecFn = (canonicalId: string, input?: unknown) => Promise<unknown>;

export interface PlanChangeServiceConfig {
  stripeSecretKey: string;
  exec?: ExecFn;
  /** When true (default), webhook handlers re-fetch via Swytchcode for verification. */
  verify?: { invoice?: boolean; subscription?: boolean };
  /** Override clock (epoch ms). Default `Date.now`. */
  now?: () => number;
  /** Override id generator for `planChangeId`. */
  newId?: () => string;
}

export interface PlanChangeService {
  previewPlanChange(input: PreviewPlanChangeInput): Promise<PreviewPlanChangeResult>;
  changePlan(input: ChangePlanInput): Promise<ChangePlanResult>;
  handleSubscriptionUpdated(
    event: StripeEvent,
    prior?: Partial<PlanChangeRecord>,
  ): Promise<PlanChangeRecord | null>;
  handleInvoicePaid(
    event: StripeEvent,
    prior?: Partial<PlanChangeRecord>,
  ): Promise<PlanChangeRecord | null>;
  getPlanChangeState(record: Partial<PlanChangeRecord>): PlanChangeState;
}

// ─── Internal Stripe shapes (only fields we read) ────────────────────────────

interface StripeSubscriptionItem {
  id: string;
  price?: { id: string } | null;
  quantity?: number;
  metadata?: Record<string, string> | null;
}

interface StripeSubscription {
  id: string;
  object: "subscription";
  status: string;
  customer: string | { id: string };
  cancel_at_period_end?: boolean;
  schedule?: string | { id: string } | null;
  latest_invoice?: string | { id: string } | null;
  metadata?: Record<string, string> | null;
  pending_update?: unknown | null;
  items: { object: "list"; data: StripeSubscriptionItem[] };
}

interface StripeInvoiceLine {
  id?: string;
  amount: number;
  description?: string | null;
  period?: { start: number; end: number } | null;
  price?: { id: string } | null;
  parent?: {
    subscription_item_details?: { proration?: boolean; subscription?: string } | null;
  } | null;
  proration?: boolean;
}

interface StripeInvoice {
  id: string;
  object: "invoice";
  status?: string | null;
  billing_reason?: string | null;
  amount_due: number;
  amount_paid: number;
  currency: string;
  customer: string | { id: string };
  period_start: number;
  period_end: number;
  lines: { object: "list"; data: StripeInvoiceLine[] };
  parent?: {
    subscription_details?: {
      subscription?: string | { id: string };
      metadata?: Record<string, string>;
    } | null;
  } | null;
  subscription?: string | { id: string } | null;
}

// ─── Stripe canonical IDs ────────────────────────────────────────────────────

const STRIPE = {
  SUBSCRIPTION_GET: "subscriptions.subscription.get",
  SUBSCRIPTION_UPDATE: "subscriptions.subscription.create_2926",
  INVOICE_PREVIEW: "invoices.create_preview.create",
  INVOICE_GET: "invoices.invoice.get",
} as const;

const PLAN_CHANGE_META_KEY = "plan_change_id";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function refId(v: string | { id: string } | null | undefined): string | undefined {
  if (!v) return undefined;
  return typeof v === "string" ? v : v.id;
}

function defaultId(): string {
  return `pc_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function isLineProration(line: StripeInvoiceLine): boolean {
  return Boolean(line.proration ?? line.parent?.subscription_item_details?.proration);
}

function buildItemsForUpdate(
  current: StripeSubscriptionItem[],
  targets: PlanChangeItemTarget[],
): Array<Record<string, unknown>> {
  // If callers point each target at a specific existing item id, do per-item swaps.
  const explicit = targets.every((t) => !!t.replacesSubscriptionItemId);
  if (explicit && targets.length > 0) {
    return targets.map((t) => ({
      id: t.replacesSubscriptionItemId!,
      price: t.price,
      quantity: t.quantity ?? 1,
    }));
  }
  // Otherwise, replace ALL current items with the targets (single-item plan-swap case).
  const removed = current.map((it) => ({ id: it.id, deleted: true }));
  const added = targets.map((t) => ({ price: t.price, quantity: t.quantity ?? 1 }));
  return [...removed, ...added];
}

function buildItemsForPreview(
  current: StripeSubscriptionItem[],
  targets: PlanChangeItemTarget[],
): Array<Record<string, unknown>> {
  return buildItemsForUpdate(current, targets);
}

function modeToProrationBehavior(mode: PlanChangeMode): "always_invoice" | "none" | "create_prorations" {
  switch (mode) {
    case "upgrade_now":
      return "always_invoice";
    case "immediate_no_proration":
      return "none";
    case "scheduled":
      // Caller is rejected before this is consulted, but keep the mapping honest.
      return "create_prorations";
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createPlanChangeService(config: PlanChangeServiceConfig): PlanChangeService {
  if (!config.stripeSecretKey) throw new Error("stripeSecretKey is required");

  const exec: ExecFn = config.exec ?? (defaultExec as ExecFn);
  const verify = { invoice: true, subscription: true, ...(config.verify ?? {}) };
  const now = config.now ?? (() => Date.now());
  const newId = config.newId ?? defaultId;
  const auth = `Bearer ${config.stripeSecretKey}`;

  async function callStripe<T>(canonicalId: string, args: Record<string, unknown>): Promise<T> {
    const res = await exec(canonicalId, { Authorization: auth, ...args });
    return res as T;
  }

  function getPlanChangeState(record: Partial<PlanChangeRecord>): PlanChangeState {
    if (record.subscriptionStatus === "incomplete") return "blocked_incomplete";
    if (record.mode === "scheduled") return "scheduled";
    if (
      record.prorationInvoiceStatus === "paid" ||
      (record.prorationInvoiceStatus === undefined && record.state === "changed")
    ) {
      return "changed";
    }
    if (record.prorationInvoiceId || record.state === "change_pending") return "change_pending";
    if (record.state === "preview_ready") return "preview_ready";
    return record.state ?? "preview_ready";
  }

  async function getSubscription(subscriptionId: string): Promise<StripeSubscription> {
    return callStripe<StripeSubscription>(STRIPE.SUBSCRIPTION_GET, {
      params: { subscription_exposed_id: subscriptionId },
    });
  }

  function rejectIfIncomplete(sub: StripeSubscription): void {
    if (sub.status === "incomplete" || sub.status === "incomplete_expired") {
      const err = new Error(
        `subscription ${sub.id} is ${sub.status}; Stripe blocks updates to Checkout-created subscriptions until the initial payment completes`,
      );
      (err as Error & { code?: string }).code = "blocked_incomplete";
      throw err;
    }
  }

  async function previewPlanChange(
    input: PreviewPlanChangeInput,
  ): Promise<PreviewPlanChangeResult> {
    if (!input.accountId) throw new Error("accountId is required");
    if (!input.subscriptionId) throw new Error("subscriptionId is required");
    if (!input.targets?.length) throw new Error("targets must contain at least one item");

    const sub = await getSubscription(input.subscriptionId);

    // Block previews on incomplete subs — Stripe will reject the actual change anyway.
    if (sub.status === "incomplete" || sub.status === "incomplete_expired") {
      const baseRecord: PlanChangeRecord = {
        accountId: input.accountId,
        state: "blocked_incomplete",
        subscriptionId: sub.id,
        customerId: refId(sub.customer),
        currentPriceIds: sub.items.data.map((it) => it.price?.id).filter((v): v is string => !!v),
        targetPriceIds: input.targets.map((t) => t.price),
        mode: input.mode ?? "upgrade_now",
        subscriptionStatus: sub.status,
        workspaceId: input.workspaceId,
        tenantId: input.tenantId,
        metadata: input.metadata,
        updatedAt: now(),
      };
      return {
        state: "blocked_incomplete",
        amountDue: 0,
        prorationAmount: 0,
        currency: "usd",
        periodStart: 0,
        periodEnd: 0,
        prorationDate: 0,
        lines: [],
        record: baseRecord,
      };
    }

    const mode = input.mode ?? "upgrade_now";
    const prorationDate = Math.floor(now() / 1000);
    const items = buildItemsForPreview(sub.items.data, input.targets);

    const previewBody: Record<string, unknown> = {
      subscription: sub.id,
      subscription_details: {
        items,
        proration_behavior: modeToProrationBehavior(mode),
        proration_date: prorationDate,
      },
    };

    const invoice = await callStripe<StripeInvoice>(STRIPE.INVOICE_PREVIEW, { body: previewBody });

    const lines = (invoice.lines?.data ?? []).map((l) => ({
      description: l.description ?? undefined,
      amount: l.amount,
      proration: isLineProration(l),
      period: l.period ?? undefined,
      priceId: l.price?.id,
    }));
    const prorationAmount = lines.filter((l) => l.proration).reduce((sum, l) => sum + l.amount, 0);

    const record: PlanChangeRecord = {
      accountId: input.accountId,
      state: "preview_ready",
      subscriptionId: sub.id,
      customerId: refId(sub.customer),
      currentPriceIds: sub.items.data.map((it) => it.price?.id).filter((v): v is string => !!v),
      targetPriceIds: input.targets.map((t) => t.price),
      mode,
      prorationDate,
      subscriptionStatus: sub.status,
      workspaceId: input.workspaceId,
      tenantId: input.tenantId,
      metadata: input.metadata,
      updatedAt: now(),
    };

    return {
      state: "preview_ready",
      amountDue: invoice.amount_due,
      prorationAmount,
      currency: invoice.currency,
      periodStart: invoice.period_start,
      periodEnd: invoice.period_end,
      prorationDate,
      lines,
      record,
    };
  }

  async function changePlan(input: ChangePlanInput): Promise<ChangePlanResult> {
    if (!input.accountId) throw new Error("accountId is required");
    if (!input.subscriptionId) throw new Error("subscriptionId is required");
    if (!input.targets?.length) throw new Error("targets must contain at least one item");

    const mode = input.mode ?? "upgrade_now";
    if (mode === "scheduled") {
      const err = new Error(
        "scheduled plan changes require subscription_schedules; this build cannot add subscription_schedule canonical IDs to swytchcode tooling.json (registry struct resolution error). Use mode=upgrade_now or mode=immediate_no_proration.",
      );
      (err as Error & { code?: string }).code = "unsupported_scheduled_mode";
      throw err;
    }

    const sub = await getSubscription(input.subscriptionId);
    rejectIfIncomplete(sub);

    const planChangeId = input.planChangeId ?? newId();
    const items = buildItemsForUpdate(sub.items.data, input.targets);

    const metadata: Record<string, string> = {
      ...(sub.metadata ?? {}),
      ...(input.metadata ?? {}),
      [PLAN_CHANGE_META_KEY]: planChangeId,
      account_id: input.accountId,
      ...(input.workspaceId ? { workspace_id: input.workspaceId } : {}),
      ...(input.tenantId ? { tenant_id: input.tenantId } : {}),
    };

    const body: Record<string, unknown> = {
      items,
      metadata,
      proration_behavior: modeToProrationBehavior(mode),
      payment_behavior: mode === "upgrade_now" ? "default_incomplete" : "allow_incomplete",
      expand: ["latest_invoice"],
    };
    if (input.prorationDate != null) body.proration_date = input.prorationDate;

    const updated = await callStripe<StripeSubscription>(STRIPE.SUBSCRIPTION_UPDATE, {
      params: { subscription_exposed_id: sub.id },
      body,
    });

    const latestInvoiceId = refId(updated.latest_invoice);

    const record: PlanChangeRecord = {
      accountId: input.accountId,
      state: "preview_ready",
      subscriptionId: updated.id,
      customerId: refId(updated.customer),
      currentPriceIds: updated.items.data.map((it) => it.price?.id).filter((v): v is string => !!v),
      targetPriceIds: input.targets.map((t) => t.price),
      planChangeId,
      mode,
      prorationDate: input.prorationDate,
      prorationInvoiceId: mode === "upgrade_now" ? latestInvoiceId : undefined,
      subscriptionStatus: updated.status,
      workspaceId: input.workspaceId,
      tenantId: input.tenantId,
      metadata,
      updatedAt: now(),
    };

    if (mode === "upgrade_now") {
      // Wait for invoice.paid before flipping to "changed".
      record.state = "change_pending";
    } else {
      // immediate_no_proration: Stripe applied the change without an invoice.
      record.state = "changed";
    }
    record.state = getPlanChangeState(record);

    return {
      state: record.state,
      subscriptionId: updated.id,
      latestInvoiceId,
      record,
    };
  }

  async function handleSubscriptionUpdated(
    event: StripeEvent,
    prior?: Partial<PlanChangeRecord>,
  ): Promise<PlanChangeRecord | null> {
    if (event?.type !== "customer.subscription.updated") return null;
    const inbound = event.data?.object as StripeSubscription | undefined;
    if (!inbound?.id) return null;

    // Only act on subscriptions we initiated a plan change for.
    const inboundPlanChangeId = inbound.metadata?.[PLAN_CHANGE_META_KEY];
    if (!inboundPlanChangeId && !prior?.planChangeId) return null;
    if (
      inboundPlanChangeId &&
      prior?.planChangeId &&
      inboundPlanChangeId !== prior.planChangeId
    ) {
      return null;
    }

    const sub: StripeSubscription = verify.subscription
      ? await getSubscription(inbound.id)
      : inbound;

    const accountId = sub.metadata?.account_id ?? prior?.accountId;
    if (!accountId) return null;

    const merged: Partial<PlanChangeRecord> = {
      ...(prior ?? {}),
      accountId,
      subscriptionId: sub.id,
      customerId: refId(sub.customer) ?? prior?.customerId,
      currentPriceIds: sub.items.data.map((it) => it.price?.id).filter((v): v is string => !!v),
      planChangeId: sub.metadata?.[PLAN_CHANGE_META_KEY] ?? prior?.planChangeId,
      subscriptionStatus: sub.status,
      metadata: { ...(prior?.metadata ?? {}), ...(sub.metadata ?? {}) },
      updatedAt: now(),
    };
    merged.state = getPlanChangeState(merged);
    return merged as PlanChangeRecord;
  }

  async function handleInvoicePaid(
    event: StripeEvent,
    prior?: Partial<PlanChangeRecord>,
  ): Promise<PlanChangeRecord | null> {
    if (event?.type !== "invoice.paid") return null;
    const inbound = event.data?.object as StripeInvoice | undefined;
    if (!inbound?.id) return null;

    // Activation handles the first-invoice case; we only react to update-driven invoices.
    if (inbound.billing_reason && inbound.billing_reason !== "subscription_update") {
      return null;
    }

    const invoice: StripeInvoice = verify.invoice
      ? await callStripe<StripeInvoice>(STRIPE.INVOICE_GET, { params: { invoice: inbound.id } })
      : inbound;

    const subscriptionId =
      refId(invoice.parent?.subscription_details?.subscription) ?? refId(invoice.subscription);
    if (!subscriptionId) return null;

    const inboundPlanChangeId = invoice.parent?.subscription_details?.metadata?.[PLAN_CHANGE_META_KEY];
    if (prior?.planChangeId && inboundPlanChangeId && inboundPlanChangeId !== prior.planChangeId) {
      return null;
    }

    const accountId =
      prior?.accountId ?? invoice.parent?.subscription_details?.metadata?.account_id;
    if (!accountId) return null;

    const merged: Partial<PlanChangeRecord> = {
      ...(prior ?? {}),
      accountId,
      subscriptionId,
      customerId: refId(invoice.customer) ?? prior?.customerId,
      planChangeId: inboundPlanChangeId ?? prior?.planChangeId,
      prorationInvoiceId: invoice.id,
      prorationInvoiceStatus: invoice.status ?? undefined,
      prorationInvoiceAmountDue: invoice.amount_due,
      updatedAt: now(),
    };
    merged.state = getPlanChangeState(merged);
    return merged as PlanChangeRecord;
  }

  return {
    previewPlanChange,
    changePlan,
    handleSubscriptionUpdated,
    handleInvoicePaid,
    getPlanChangeState,
  };
}