/**
 * swytchcode-stripe-renewal-recovery — single-file reusable service.
 *
 * Solves one problem: recurring subscription payment failures after activation.
 * Stripe recommends monitoring `invoice.paid` and `invoice.payment_failed` and
 * mirroring the resulting subscription status:
 *   - `past_due`  → recoverable; smart retries are still in flight
 *   - `unpaid`    → revoke access; Stripe has stopped retrying
 *
 * All Stripe API calls are delegated to the Swytchcode runtime — no Stripe SDK.
 * Canonical IDs used (must be `swytchcode add`ed before use):
 *   - invoices.invoice.get
 *   - subscriptions.subscription.get
 *
 * Public API (see `createRenewalRecoveryService` below):
 *   - handleRecurringInvoicePaid(event, prior?)
 *   - handleRecurringInvoicePaymentFailed(event, prior?)
 *   - handleSubscriptionUpdated(event, prior?)
 *   - getRenewalState(record)
 */
import { exec as defaultExec } from "swytchcode-runtime";

// ─── Public types ────────────────────────────────────────────────────────────

/**
 * Outward, access-shaped state the application reacts to.
 *
 *   healthy         renewal billing OK; grant paid access
 *   grace           renewal payment failed but Stripe is still retrying
 *   unpaid_locked   Stripe stopped retrying (or app-side grace exhausted) — revoke access
 *   restored        one-shot transition: was degraded, now healthy again
 */
export type RenewalState = "healthy" | "grace" | "unpaid_locked" | "restored";

/**
 * Persistable record. Caller stores it (DB, KV, memory — the service is
 * storage-agnostic). Handlers return an updated record; the caller persists.
 *
 * `getRenewalState` derives `state` purely from the raw signal fields below
 * plus `priorState`, so the record round-trips through any store.
 */
export interface RenewalStateRecord {
  accountId?: string;
  state: RenewalState;
  /** Previous `state` before the most recent handler call. Drives `restored`. */
  priorState?: RenewalState;
  // IDs
  customerId?: string;
  subscriptionId?: string;
  invoiceId?: string;
  // Raw signals
  subscriptionStatus?: string;
  invoiceStatus?: string;
  invoiceBillingReason?: string;
  invoiceAttemptCount?: number;
  invoiceNextPaymentAttempt?: number;
  hostedInvoiceUrl?: string;
  /** Epoch ms when we first observed the subscription enter `past_due`. */
  firstPastDueAt?: number;
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

/** A Swytchcode exec callable. Default uses `swytchcode-runtime`. Override for tests. */
export type ExecFn = (canonicalId: string, input?: unknown) => Promise<unknown>;

/**
 * Configurable grace logic. Both bounds are evaluated; if either trips while
 * the subscription is still `past_due`, state is forced to `unpaid_locked` —
 * even before Stripe itself flips the subscription to `unpaid`.
 *
 *   - `maxAttempts`   — lock once `invoice.attempt_count` reaches this value
 *   - `maxDurationMs` — lock once (now - firstPastDueAt) reaches this value
 *
 * Leave both undefined to defer entirely to Stripe (subscription `unpaid` is
 * still always treated as locked).
 */
export interface GraceConfig {
  maxAttempts?: number;
  maxDurationMs?: number;
}

export interface RenewalRecoveryConfig {
  stripeSecretKey: string;
  exec?: ExecFn;
  /** When true (default), webhook handlers re-fetch via Swytchcode for verification. */
  verify?: { invoice?: boolean; subscription?: boolean };
  grace?: GraceConfig;
  /** Override clock (epoch ms). Default `Date.now`. */
  now?: () => number;
}

export interface RenewalRecoveryService {
  handleRecurringInvoicePaid(
    event: StripeEvent,
    prior?: Partial<RenewalStateRecord>,
  ): Promise<RenewalStateRecord | null>;
  handleRecurringInvoicePaymentFailed(
    event: StripeEvent,
    prior?: Partial<RenewalStateRecord>,
  ): Promise<RenewalStateRecord | null>;
  handleSubscriptionUpdated(
    event: StripeEvent,
    prior?: Partial<RenewalStateRecord>,
  ): Promise<RenewalStateRecord | null>;
  getRenewalState(record: Partial<RenewalStateRecord>): RenewalState;
}

// ─── Internal Stripe shapes (only fields we read) ────────────────────────────

interface StripeInvoice {
  id: string;
  object: "invoice";
  status?: string | null;
  billing_reason?: string | null;
  attempt_count?: number;
  next_payment_attempt?: number | null;
  hosted_invoice_url?: string | null;
  customer: string | { id: string };
  parent?: {
    subscription_details?: {
      subscription?: string | { id: string };
      metadata?: Record<string, string>;
    } | null;
  } | null;
  subscription?: string | { id: string } | null;
}

interface StripeSubscription {
  id: string;
  status: string;
  customer: string | { id: string };
  metadata?: Record<string, string>;
  latest_invoice?: string | { id: string } | null;
}

// ─── Stripe canonical IDs ────────────────────────────────────────────────────

const STRIPE = {
  INVOICE_GET: "invoices.invoice.get",
  SUBSCRIPTION_GET: "subscriptions.subscription.get",
} as const;

// Renewal billing reasons. `subscription_create` is owned by the
// first-payment-recovery-service and is intentionally excluded here.
const RENEWAL_BILLING_REASONS = new Set([
  "subscription_cycle",
  "subscription_update",
  "subscription_threshold",
]);

// ─── Helpers ─────────────────────────────────────────────────────────────────

function refId(v: string | { id: string } | null | undefined): string | undefined {
  if (!v) return undefined;
  return typeof v === "string" ? v : v.id;
}

function readSubscriptionId(invoice: StripeInvoice): string | undefined {
  return (
    refId(invoice.parent?.subscription_details?.subscription) ?? refId(invoice.subscription)
  );
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createRenewalRecoveryService(
  config: RenewalRecoveryConfig,
): RenewalRecoveryService {
  if (!config.stripeSecretKey) throw new Error("stripeSecretKey is required");

  const exec: ExecFn = config.exec ?? (defaultExec as ExecFn);
  const verify = { invoice: true, subscription: true, ...(config.verify ?? {}) };
  const now = config.now ?? (() => Date.now());
  const grace: GraceConfig = config.grace ?? {};
  const auth = `Bearer ${config.stripeSecretKey}`;

  async function callStripe<T>(canonicalId: string, args: Record<string, unknown>): Promise<T> {
    const res = await exec(canonicalId, { Authorization: auth, ...args });
    return res as T;
  }

  function isGraceExhausted(record: Partial<RenewalStateRecord>): boolean {
    if (typeof grace.maxAttempts === "number" && grace.maxAttempts > 0) {
      if ((record.invoiceAttemptCount ?? 0) >= grace.maxAttempts) return true;
    }
    if (typeof grace.maxDurationMs === "number" && grace.maxDurationMs > 0) {
      if (record.firstPastDueAt && now() - record.firstPastDueAt >= grace.maxDurationMs) {
        return true;
      }
    }
    return false;
  }

  function getRenewalState(record: Partial<RenewalStateRecord>): RenewalState {
    const sub = record.subscriptionStatus;

    // Stripe-terminal lock: revoke access immediately.
    if (sub === "unpaid" || sub === "canceled" || sub === "incomplete_expired") {
      return "unpaid_locked";
    }

    if (sub === "past_due") {
      return isGraceExhausted(record) ? "unpaid_locked" : "grace";
    }

    if (sub === "active" || sub === "trialing") {
      const wasDegraded = record.priorState === "grace" || record.priorState === "unpaid_locked";
      if (wasDegraded && record.invoiceStatus === "paid") return "restored";
      return "healthy";
    }

    // Out-of-scope statuses (incomplete / paused) — first-payment / pause flows
    // own those. Default to healthy so we don't spuriously lock.
    return "healthy";
  }

  /**
   * Reconcile state from a Stripe invoice event. Re-fetches invoice and
   * subscription through Swytchcode (toggleable via `verify`), then derives
   * the normalized state. Returns null when the invoice is not a renewal
   * invoice (first-payment lifecycle is handled elsewhere).
   */
  async function reconcileFromInvoice(
    inbound: StripeInvoice | undefined,
    prior: Partial<RenewalStateRecord> | undefined,
    { paid }: { paid: boolean },
  ): Promise<RenewalStateRecord | null> {
    if (!inbound?.id) return null;

    const invoice: StripeInvoice = verify.invoice
      ? await callStripe<StripeInvoice>(STRIPE.INVOICE_GET, { params: { invoice: inbound.id } })
      : inbound;

    // Renewal scope guard. The first-payment-recovery-service owns
    // `subscription_create`. If billing_reason is missing, fall through to the
    // subscription-status check so we don't drop renewals on sparse payloads.
    const billingReason = invoice.billing_reason ?? prior?.invoiceBillingReason;
    if (billingReason === "subscription_create") return null;

    const subscriptionId = readSubscriptionId(invoice) ?? prior?.subscriptionId;
    let subscription: StripeSubscription | undefined;
    if (verify.subscription && subscriptionId) {
      subscription = await callStripe<StripeSubscription>(STRIPE.SUBSCRIPTION_GET, {
        params: { subscription_exposed_id: subscriptionId },
      });
    }

    const subStatus = subscription?.status ?? prior?.subscriptionStatus;
    if (
      billingReason === undefined &&
      (subStatus === "incomplete" || subStatus === "incomplete_expired")
    ) {
      return null;
    }
    if (billingReason !== undefined && !RENEWAL_BILLING_REASONS.has(billingReason)) {
      return null;
    }

    return mergeRecord({
      prior,
      invoice,
      subscription,
      paid,
    });
  }

  async function reconcileFromSubscription(
    inbound: StripeSubscription | undefined,
    prior: Partial<RenewalStateRecord> | undefined,
  ): Promise<RenewalStateRecord | null> {
    if (!inbound?.id) return null;

    const subscription: StripeSubscription = verify.subscription
      ? await callStripe<StripeSubscription>(STRIPE.SUBSCRIPTION_GET, {
          params: { subscription_exposed_id: inbound.id },
        })
      : inbound;

    // Out of renewal scope: first-payment lifecycle.
    if (subscription.status === "incomplete" || subscription.status === "incomplete_expired") {
      return null;
    }

    return mergeRecord({ prior, invoice: undefined, subscription, paid: false });
  }

  function mergeRecord(args: {
    prior: Partial<RenewalStateRecord> | undefined;
    invoice: StripeInvoice | undefined;
    subscription: StripeSubscription | undefined;
    paid: boolean;
  }): RenewalStateRecord {
    const { prior, invoice, subscription, paid } = args;
    const ts = now();

    const subStatus = subscription?.status ?? prior?.subscriptionStatus;
    const priorState = prior?.state;

    // Track when the subscription first entered `past_due` so duration-based
    // grace windows can be evaluated without an external clock store.
    let firstPastDueAt = prior?.firstPastDueAt;
    if (subStatus === "past_due" && !firstPastDueAt) firstPastDueAt = ts;
    if (subStatus !== "past_due" && subStatus !== undefined) firstPastDueAt = undefined;

    const accountId =
      prior?.accountId ??
      invoice?.parent?.subscription_details?.metadata?.account_id ??
      subscription?.metadata?.account_id;

    const merged: Partial<RenewalStateRecord> = {
      ...(prior ?? {}),
      accountId,
      priorState,
      customerId:
        refId(invoice?.customer) ?? refId(subscription?.customer) ?? prior?.customerId,
      subscriptionId:
        (invoice ? readSubscriptionId(invoice) : undefined) ??
        subscription?.id ??
        prior?.subscriptionId,
      invoiceId: invoice?.id ?? prior?.invoiceId,
      invoiceStatus: paid ? "paid" : invoice?.status ?? prior?.invoiceStatus,
      invoiceBillingReason: invoice?.billing_reason ?? prior?.invoiceBillingReason,
      invoiceAttemptCount: paid
        ? 0
        : invoice?.attempt_count ?? prior?.invoiceAttemptCount,
      invoiceNextPaymentAttempt: paid
        ? undefined
        : invoice?.next_payment_attempt ?? prior?.invoiceNextPaymentAttempt,
      hostedInvoiceUrl: invoice?.hosted_invoice_url ?? prior?.hostedInvoiceUrl,
      subscriptionStatus: subStatus,
      firstPastDueAt,
      metadata: {
        ...(prior?.metadata ?? {}),
        ...(invoice?.parent?.subscription_details?.metadata ?? {}),
        ...(subscription?.metadata ?? {}),
      },
      updatedAt: ts,
    };
    merged.state = getRenewalState(merged);
    return merged as RenewalStateRecord;
  }

  async function handleRecurringInvoicePaid(
    event: StripeEvent,
    prior?: Partial<RenewalStateRecord>,
  ): Promise<RenewalStateRecord | null> {
    if (event?.type !== "invoice.paid") return null;
    return reconcileFromInvoice(event.data?.object as StripeInvoice | undefined, prior, {
      paid: true,
    });
  }

  async function handleRecurringInvoicePaymentFailed(
    event: StripeEvent,
    prior?: Partial<RenewalStateRecord>,
  ): Promise<RenewalStateRecord | null> {
    if (event?.type !== "invoice.payment_failed") return null;
    return reconcileFromInvoice(event.data?.object as StripeInvoice | undefined, prior, {
      paid: false,
    });
  }

  async function handleSubscriptionUpdated(
    event: StripeEvent,
    prior?: Partial<RenewalStateRecord>,
  ): Promise<RenewalStateRecord | null> {
    if (event?.type !== "customer.subscription.updated") return null;
    return reconcileFromSubscription(
      event.data?.object as StripeSubscription | undefined,
      prior,
    );
  }

  return {
    handleRecurringInvoicePaid,
    handleRecurringInvoicePaymentFailed,
    handleSubscriptionUpdated,
    getRenewalState,
  };
}