/**
 * swytchcode-stripe-entitlement-sync — single-file reusable service.
 *
 * Solves one problem: application access drifting from Stripe billing state.
 * Stripe recommends provisioning access via Entitlements (the Features +
 * Active Entitlements API) or by tracking subscription status through
 * webhooks, and warns that Subscription, Invoice, and PaymentIntent states
 * can diverge — especially for asynchronous payment methods where the
 * subscription can flip to `active` while the underlying PaymentIntent is
 * still `processing`, and where invoice outcomes can later change the
 * access interpretation (e.g. `paid` → `voided`/`uncollectible`).
 *
 * This service maintains a normalized entitlement snapshot per record and
 * gives the caller two tools to keep the snapshot honest:
 *   - `applyBillingEvent(event, prior?)` — fold a Stripe webhook into the snapshot
 *   - `recomputeEntitlements(record)`     — out-of-band reconcile by re-fetching
 *
 * All Stripe API calls are delegated to the Swytchcode runtime — no Stripe SDK.
 * Canonical IDs used (must be `swytchcode add`ed before use):
 *   - subscriptions.subscription.get
 *   - invoices.invoice.get
 *   - payment_intents.payment_intent.get
 *   - entitlements.active_entitlement.list
 *
 * Public API (see `createEntitlementSyncService` below):
 *   - applyBillingEvent(event, prior?)
 *   - recomputeEntitlements(record)
 *   - getEntitlements(record)
 *   - evaluateAccess(record)
 */
import { exec as defaultExec } from "swytchcode-runtime";

// ─── Public types ────────────────────────────────────────────────────────────

/**
 * Normalized billing status. This is the SINGLE source of truth for access
 * decisions; it mirrors Stripe's `subscription.status` vocabulary so the
 * mapping is auditable end-to-end.
 *
 *   trialing    in a trial; grant access
 *   active      paid and current; grant access (see `paymentPending` for async edge)
 *   incomplete  first invoice not yet paid; do not grant access
 *   past_due    renewal failed, Stripe still retrying; access at app's discretion
 *   unpaid      renewal failed, Stripe gave up; revoke access
 *   canceled    subscription ended; revoke access
 *   paused      intentionally paused; revoke access
 *   unknown     no signal yet (fresh record before first event/recompute)
 */
export type BillingStatus =
  | "trialing"
  | "active"
  | "incomplete"
  | "past_due"
  | "unpaid"
  | "canceled"
  | "paused"
  | "unknown";

/** Coarse access decision derived from `BillingStatus` + async signals. */
export type AccessDecision = "grant" | "grace" | "deny";

/**
 * Normalized snapshot the application reads. Stable across webhook deliveries
 * and out-of-band recomputes — `recomputeEntitlements` is idempotent and
 * always rebuilds this from authoritative Stripe state.
 */
export interface EntitlementsSnapshot {
  /** Mapped from `subscription.status`; `unknown` until first signal. */
  status: BillingStatus;
  /**
   * `true` when the subscription is `active`/`trialing` BUT the latest invoice
   * still has an open or processing PaymentIntent — the classic async-payment
   * edge case (e.g. SEPA, ACH, OXXO). Callers can choose to gate sensitive
   * features even though `status === "active"`.
   */
  paymentPending: boolean;
  /**
   * Feature lookup keys currently granted by Stripe Entitlements
   * (`active_entitlement.lookup_key`). Empty when entitlements are unused or
   * the snapshot has never been recomputed.
   */
  features: string[];
  /** When the snapshot was last reconciled (epoch ms). */
  asOf: number;
}

/**
 * Persistable record. Caller stores it (DB, KV, memory — the service is
 * storage-agnostic). All handlers return an updated record; the caller persists.
 *
 * `evaluateAccess`/`getEntitlements` are pure derivations from the raw
 * signal fields below, so the record round-trips through any store.
 */
export interface EntitlementRecord {
  accountId?: string;
  // IDs
  customerId?: string;
  subscriptionId?: string;
  invoiceId?: string;
  paymentIntentId?: string;
  // Raw Stripe signals — recompute/event handlers update these in place
  subscriptionStatus?: string;
  cancelAtPeriodEnd?: boolean;
  pauseCollectionBehavior?: string;
  trialEnd?: number;
  currentPeriodEnd?: number;
  invoiceStatus?: string;
  invoiceBillingReason?: string;
  invoiceAmountPaid?: number;
  invoiceAmountRemaining?: number;
  paymentIntentStatus?: string;
  paymentIntentLastErrorCode?: string;
  // Stripe Entitlements (lookup_keys of the customer's active features)
  entitlementFeatures?: string[];
  // Bookkeeping
  metadata?: Record<string, string>;
  updatedAt?: number;
  /** Last event id applied. Used to short-circuit replays. */
  lastEventId?: string;
  /** Last event `created` (epoch s). Used to drop out-of-order deliveries. */
  lastEventAt?: number;
}

export interface StripeEvent<T = unknown> {
  id: string;
  type: string;
  data: { object: T };
  livemode?: boolean;
  /** Epoch SECONDS, per Stripe. */
  created?: number;
}

/** A Swytchcode exec callable. Default uses `swytchcode-runtime`. Override for tests. */
export type ExecFn = (canonicalId: string, input?: unknown) => Promise<unknown>;

export interface EntitlementSyncConfig {
  stripeSecretKey: string;
  exec?: ExecFn;
  /**
   * When true (default), `applyBillingEvent` re-fetches the affected entity
   * via Swytchcode before mutating the record. Disable per-entity for cost
   * or for tests that pre-stub the inbound payload.
   */
  verify?: { subscription?: boolean; invoice?: boolean; paymentIntent?: boolean };
  /**
   * When true (default), `recomputeEntitlements` also calls
   * `entitlements.active_entitlement.list` and refreshes
   * `entitlementFeatures`. Disable if you don't use Stripe Entitlements —
   * the rest of the snapshot still works.
   */
  syncEntitlementsApi?: boolean;
  /** Override clock (epoch ms). Default `Date.now`. */
  now?: () => number;
}

export interface EntitlementSyncService {
  applyBillingEvent(
    event: StripeEvent,
    prior?: Partial<EntitlementRecord>,
  ): Promise<EntitlementRecord | null>;
  recomputeEntitlements(
    record: Partial<EntitlementRecord>,
  ): Promise<EntitlementRecord>;
  getEntitlements(record: Partial<EntitlementRecord>): EntitlementsSnapshot;
  evaluateAccess(record: Partial<EntitlementRecord>): AccessDecision;
}

// ─── Internal Stripe shapes (only fields we read) ────────────────────────────

interface StripeSubscription {
  id: string;
  status: string;
  customer: string | { id: string };
  cancel_at_period_end?: boolean;
  trial_end?: number | null;
  current_period_end?: number | null;
  pause_collection?: { behavior?: string } | null;
  latest_invoice?: string | { id: string } | null;
  metadata?: Record<string, string>;
}

interface StripeInvoice {
  id: string;
  object: "invoice";
  status?: string | null;
  billing_reason?: string | null;
  amount_paid: number;
  amount_remaining?: number;
  customer: string | { id: string };
  payment_intent?: string | { id: string } | null;
  parent?: {
    subscription_details?: {
      subscription?: string | { id: string };
      metadata?: Record<string, string>;
    } | null;
  } | null;
  subscription?: string | { id: string } | null;
}

interface StripePaymentIntent {
  id: string;
  status: string;
  last_payment_error?: { code?: string | null } | null;
  invoice?: string | { id: string } | null;
  customer?: string | { id: string } | null;
}

interface StripeActiveEntitlementListResponse {
  data: Array<{ id: string; lookup_key: string; livemode: boolean; object: string }>;
  has_more: boolean;
}

// ─── Stripe canonical IDs ────────────────────────────────────────────────────

const STRIPE = {
  SUBSCRIPTION_GET: "subscriptions.subscription.get",
  INVOICE_GET: "invoices.invoice.get",
  PAYMENT_INTENT_GET: "payment_intents.payment_intent.get",
  ACTIVE_ENTITLEMENT_LIST: "entitlements.active_entitlement.list",
} as const;

// Stripe event types this service folds into the snapshot. Anything else is
// returned as `null` so the caller can keep dispatching to other services.
const SUBSCRIPTION_EVENTS = new Set([
  "customer.subscription.created",
  "customer.subscription.updated",
  "customer.subscription.deleted",
  "customer.subscription.paused",
  "customer.subscription.resumed",
  "customer.subscription.trial_will_end",
]);
const INVOICE_EVENTS = new Set([
  "invoice.paid",
  "invoice.payment_failed",
  "invoice.payment_action_required",
  "invoice.finalized",
  "invoice.voided",
  "invoice.marked_uncollectible",
]);
const PAYMENT_INTENT_EVENTS = new Set([
  "payment_intent.succeeded",
  "payment_intent.payment_failed",
  "payment_intent.processing",
  "payment_intent.canceled",
  "payment_intent.requires_action",
]);

// Subscription statuses that imply paid (or trial-paid) access.
const ACCESS_STATUSES = new Set<BillingStatus>(["active", "trialing"]);

// ─── Helpers ─────────────────────────────────────────────────────────────────

function refId(v: string | { id: string } | null | undefined): string | undefined {
  if (!v) return undefined;
  return typeof v === "string" ? v : v.id;
}

function readSubscriptionId(invoice: StripeInvoice): string | undefined {
  return refId(invoice.parent?.subscription_details?.subscription) ?? refId(invoice.subscription);
}

function normalizeStatus(raw: string | undefined | null): BillingStatus {
  switch (raw) {
    case "trialing":
    case "active":
    case "incomplete":
    case "past_due":
    case "unpaid":
    case "canceled":
    case "paused":
      return raw;
    case "incomplete_expired":
      return "canceled";
    default:
      return "unknown";
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createEntitlementSyncService(
  config: EntitlementSyncConfig,
): EntitlementSyncService {
  if (!config.stripeSecretKey) throw new Error("stripeSecretKey is required");

  const exec: ExecFn = config.exec ?? (defaultExec as ExecFn);
  const verify = {
    subscription: true,
    invoice: true,
    paymentIntent: true,
    ...(config.verify ?? {}),
  };
  const syncEntitlementsApi = config.syncEntitlementsApi ?? true;
  const now = config.now ?? (() => Date.now());
  const auth = `Bearer ${config.stripeSecretKey}`;

  async function callStripe<T>(canonicalId: string, args: Record<string, unknown>): Promise<T> {
    const res = await exec(canonicalId, { Authorization: auth, ...args });
    return res as T;
  }

  // ── Pure derivations ─────────────────────────────────────────────────────

  function getEntitlements(record: Partial<EntitlementRecord>): EntitlementsSnapshot {
    const status = normalizeStatus(record.subscriptionStatus);
    // Async-payment edge case: Stripe flips the subscription to `active` as soon
    // as the invoice is finalized, but for delayed payment methods the
    // PaymentIntent can stay `processing` (or worse, fail) for hours/days.
    const piPending =
      record.paymentIntentStatus === "processing" ||
      record.paymentIntentStatus === "requires_action" ||
      record.paymentIntentStatus === "requires_confirmation" ||
      record.paymentIntentStatus === "requires_payment_method";
    const invoiceUnsettled =
      record.invoiceStatus === "open" ||
      (record.invoiceStatus === undefined && (record.invoiceAmountRemaining ?? 0) > 0);
    const paymentPending = ACCESS_STATUSES.has(status) && (piPending || invoiceUnsettled);
    return {
      status,
      paymentPending,
      features: record.entitlementFeatures ?? [],
      asOf: record.updatedAt ?? 0,
    };
  }

  function evaluateAccess(record: Partial<EntitlementRecord>): AccessDecision {
    const snap = getEntitlements(record);
    if (snap.status === "active" || snap.status === "trialing") {
      // For async payment methods, surface a `grace` decision so the caller
      // can soft-gate sensitive features without revoking the account.
      return snap.paymentPending ? "grace" : "grant";
    }
    if (snap.status === "past_due") return "grace";
    // unpaid / canceled / paused / incomplete / unknown → no access.
    return "deny";
  }

  // ── Re-fetch primitives ──────────────────────────────────────────────────

  async function fetchSubscription(id: string): Promise<StripeSubscription> {
    return callStripe<StripeSubscription>(STRIPE.SUBSCRIPTION_GET, {
      params: { subscription_exposed_id: id },
    });
  }

  async function fetchInvoice(id: string): Promise<StripeInvoice> {
    return callStripe<StripeInvoice>(STRIPE.INVOICE_GET, { params: { invoice: id } });
  }

  async function fetchPaymentIntent(id: string): Promise<StripePaymentIntent> {
    return callStripe<StripePaymentIntent>(STRIPE.PAYMENT_INTENT_GET, {
      params: { intent: id },
    });
  }

  async function fetchActiveEntitlementLookupKeys(customerId: string): Promise<string[]> {
    const keys: string[] = [];
    let startingAfter: string | undefined;
    // Page through — Stripe caps `limit` at 100. Bounded loop guards against
    // bad servers that always set has_more=true.
    for (let page = 0; page < 50; page++) {
      const params: Record<string, string> = { customer: customerId, limit: "100" };
      if (startingAfter) params.starting_after = startingAfter;
      const res = await callStripe<StripeActiveEntitlementListResponse>(
        STRIPE.ACTIVE_ENTITLEMENT_LIST,
        { params },
      );
      for (const e of res.data ?? []) keys.push(e.lookup_key);
      const last = res.data?.at(-1);
      if (!res.has_more || !last) break;
      startingAfter = last.id;
    }
    return keys;
  }

  // ── Merge core ───────────────────────────────────────────────────────────

  function mergeFromSubscription(
    prior: Partial<EntitlementRecord> | undefined,
    sub: StripeSubscription,
  ): Partial<EntitlementRecord> {
    return {
      ...(prior ?? {}),
      accountId: prior?.accountId ?? sub.metadata?.account_id,
      customerId: refId(sub.customer) ?? prior?.customerId,
      subscriptionId: sub.id,
      subscriptionStatus: sub.status,
      cancelAtPeriodEnd: sub.cancel_at_period_end,
      trialEnd: sub.trial_end ?? undefined,
      currentPeriodEnd: sub.current_period_end ?? undefined,
      pauseCollectionBehavior: sub.pause_collection?.behavior,
      invoiceId: refId(sub.latest_invoice) ?? prior?.invoiceId,
      metadata: { ...(prior?.metadata ?? {}), ...(sub.metadata ?? {}) },
    };
  }

  function mergeFromInvoice(
    prior: Partial<EntitlementRecord> | undefined,
    inv: StripeInvoice,
  ): Partial<EntitlementRecord> {
    const meta = inv.parent?.subscription_details?.metadata ?? {};
    return {
      ...(prior ?? {}),
      accountId: prior?.accountId ?? meta.account_id,
      customerId: refId(inv.customer) ?? prior?.customerId,
      subscriptionId: readSubscriptionId(inv) ?? prior?.subscriptionId,
      invoiceId: inv.id,
      invoiceStatus: inv.status ?? undefined,
      invoiceBillingReason: inv.billing_reason ?? undefined,
      invoiceAmountPaid: inv.amount_paid,
      invoiceAmountRemaining: inv.amount_remaining,
      paymentIntentId: refId(inv.payment_intent) ?? prior?.paymentIntentId,
      metadata: { ...(prior?.metadata ?? {}), ...meta },
    };
  }

  function mergeFromPaymentIntent(
    prior: Partial<EntitlementRecord> | undefined,
    pi: StripePaymentIntent,
  ): Partial<EntitlementRecord> {
    return {
      ...(prior ?? {}),
      customerId: refId(pi.customer) ?? prior?.customerId,
      invoiceId: refId(pi.invoice) ?? prior?.invoiceId,
      paymentIntentId: pi.id,
      paymentIntentStatus: pi.status,
      paymentIntentLastErrorCode: pi.last_payment_error?.code ?? undefined,
    };
  }

  function stamp(record: Partial<EntitlementRecord>, event?: StripeEvent): EntitlementRecord {
    return {
      ...record,
      updatedAt: now(),
      lastEventId: event?.id ?? record.lastEventId,
      lastEventAt: event?.created ?? record.lastEventAt,
    } as EntitlementRecord;
  }

  // ── Public: applyBillingEvent ────────────────────────────────────────────

  async function applyBillingEvent(
    event: StripeEvent,
    prior?: Partial<EntitlementRecord>,
  ): Promise<EntitlementRecord | null> {
    if (!event?.type || !event.id) return null;

    // Drop replays and out-of-order deliveries. Stripe guarantees `created`
    // monotonicity per object only weakly, but it's strictly correct to ignore
    // an older event after a newer one — the snapshot would otherwise regress.
    if (prior?.lastEventId === event.id) return null;
    if (
      typeof prior?.lastEventAt === "number" &&
      typeof event.created === "number" &&
      event.created < prior.lastEventAt
    ) {
      return null;
    }

    if (SUBSCRIPTION_EVENTS.has(event.type)) {
      const inbound = event.data?.object as StripeSubscription | undefined;
      if (!inbound?.id) return null;
      const sub: StripeSubscription = verify.subscription
        ? await fetchSubscription(inbound.id)
        : inbound;
      // `customer.subscription.deleted` arrives with status="canceled"; honor it.
      const merged = mergeFromSubscription(prior, sub);
      return stamp(merged, event);
    }

    if (INVOICE_EVENTS.has(event.type)) {
      const inbound = event.data?.object as StripeInvoice | undefined;
      if (!inbound?.id) return null;
      const inv: StripeInvoice = verify.invoice ? await fetchInvoice(inbound.id) : inbound;
      let merged = mergeFromInvoice(prior, inv);
      // Async edge case: invoice.finalized fires before the PaymentIntent
      // settles. Pull the PaymentIntent so `paymentPending` is accurate when
      // the caller next reads `evaluateAccess(record)`.
      const piId = refId(inv.payment_intent);
      if (piId && verify.paymentIntent) {
        const pi = await fetchPaymentIntent(piId);
        merged = mergeFromPaymentIntent(merged, pi);
      }
      // Invoice changing to `void`/`uncollectible` after a previous `paid`
      // outcome is an interpretation flip — re-pull the subscription so
      // `subscriptionStatus` is consistent with what the user is paying for.
      if (
        (inv.status === "void" || inv.status === "uncollectible") &&
        merged.subscriptionId &&
        verify.subscription
      ) {
        const sub = await fetchSubscription(merged.subscriptionId);
        merged = { ...merged, ...mergeFromSubscription(merged, sub) };
      }
      return stamp(merged, event);
    }

    if (PAYMENT_INTENT_EVENTS.has(event.type)) {
      const inbound = event.data?.object as StripePaymentIntent | undefined;
      if (!inbound?.id) return null;
      const pi: StripePaymentIntent = verify.paymentIntent
        ? await fetchPaymentIntent(inbound.id)
        : inbound;
      return stamp(mergeFromPaymentIntent(prior, pi), event);
    }

    // Stripe Entitlements summary changed — nothing to do per-event; the
    // caller should call `recomputeEntitlements(record)` to pull fresh keys.
    if (event.type === "entitlements.active_entitlement_summary.updated") {
      return stamp({ ...(prior ?? {}) }, event);
    }

    return null;
  }

  // ── Public: recomputeEntitlements ────────────────────────────────────────

  /**
   * Out-of-band reconcile. Pulls subscription → latest invoice → that
   * invoice's PaymentIntent → active entitlements (in that order, because
   * each lookup informs the next). Use this when:
   *   - A record looks stale (e.g. snapshot.asOf older than your SLO)
   *   - A webhook was missed (replayed from Stripe Dashboard or skipped)
   *   - `evaluateAccess` returned `grace` and you want a definitive answer
   */
  async function recomputeEntitlements(
    record: Partial<EntitlementRecord>,
  ): Promise<EntitlementRecord> {
    let next: Partial<EntitlementRecord> = { ...record };

    if (next.subscriptionId) {
      const sub = await fetchSubscription(next.subscriptionId);
      next = { ...next, ...mergeFromSubscription(next, sub) };
    }

    const invoiceId = next.invoiceId;
    if (invoiceId) {
      const inv = await fetchInvoice(invoiceId);
      next = { ...next, ...mergeFromInvoice(next, inv) };
    }

    if (next.paymentIntentId) {
      const pi = await fetchPaymentIntent(next.paymentIntentId);
      next = { ...next, ...mergeFromPaymentIntent(next, pi) };
    }

    if (syncEntitlementsApi && next.customerId) {
      next.entitlementFeatures = await fetchActiveEntitlementLookupKeys(next.customerId);
    }

    return stamp(next);
  }

  return {
    applyBillingEvent,
    recomputeEntitlements,
    getEntitlements,
    evaluateAccess,
  };
}