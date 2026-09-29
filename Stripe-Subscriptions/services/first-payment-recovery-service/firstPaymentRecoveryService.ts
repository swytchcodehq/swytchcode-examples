/**
 * swytchcode-stripe-first-payment-recovery — single-file reusable service.
 *
 * Solves one problem: failed first subscription payments and SCA / 3DS recovery.
 * Stripe documents that the first invoice can remain `open`, the subscription
 * `incomplete`, and the PaymentIntent in `requires_payment_method`,
 * `requires_action`, or `processing`, with unresolved cases moving to
 * `incomplete_expired` after roughly 23 hours.
 *
 * All Stripe API calls are delegated to the Swytchcode runtime — no Stripe SDK.
 * Canonical IDs used (must be `swytchcode add`ed before use):
 *   - invoices.invoice.get
 *   - payment_intents.payment_intent.get
 *   - subscriptions.subscription.get
 *
 * Public API (see `createFirstPaymentRecoveryService` below):
 *   - handleInvoicePaymentFailed(event, prior?)
 *   - handleInvoicePaymentActionRequired(event, prior?)
 *   - handleInvoicePaid(event, prior?)
 *   - getRecoveryState(record)
 *   - buildRecoveryAction(record)
 */
import { exec as defaultExec } from "swytchcode-runtime";

// ─── Public types ────────────────────────────────────────────────────────────

/**
 * Outward, action-shaped state the application reacts to.
 *
 *   billing_action_required          fallback / unmapped
 *   payment_method_update_required   PI requires_payment_method (decline)
 *   pending_authentication           PI requires_action (SCA / 3DS)
 *   processing                       PI processing (async PM, e.g. ACH)
 *   recovered                        invoice paid
 *   expired                          subscription incomplete_expired
 */
export type RecoveryState =
  | "billing_action_required"
  | "payment_method_update_required"
  | "pending_authentication"
  | "processing"
  | "recovered"
  | "expired";

/** Underlying Stripe-side classification of the failure. */
export type FailureKind =
  | "requires_payment_method"
  | "requires_action"
  | "processing"
  | "expired";

/**
 * Persistable record. Caller stores it (DB, KV, memory — the service is
 * storage-agnostic). Handlers return an updated record; the caller persists.
 *
 * `getRecoveryState` derives `state` purely from the raw signal fields below,
 * so this record round-trips through any store without losing meaning.
 */
export interface RecoveryStateRecord {
  accountId?: string;
  state: RecoveryState;
  // IDs
  customerId?: string;
  subscriptionId?: string;
  invoiceId?: string;
  paymentIntentId?: string;
  // Raw signals — getRecoveryState/buildRecoveryAction read these.
  invoiceStatus?: string;
  invoiceBillingReason?: string;
  invoiceAttemptCount?: number;
  hostedInvoiceUrl?: string;
  paymentIntentStatus?: string;
  paymentIntentNextActionType?: string;
  paymentIntentClientSecret?: string;
  paymentIntentLastErrorCode?: string;
  paymentIntentLastErrorMessage?: string;
  subscriptionStatus?: string;
  failureKind?: FailureKind;
  metadata?: Record<string, string>;
  updatedAt?: number;
}

export type RecoveryAction =
  | { type: "confirm_payment"; clientSecret: string; returnUrl?: string }
  | { type: "redirect_to_hosted_invoice"; url: string }
  | { type: "wait"; retryAfterMs: number }
  | { type: "restart_signup" }
  | { type: "none"; reason: "recovered" | "no_state" };

export interface StripeEvent<T = unknown> {
  id: string;
  type: string;
  data: { object: T };
  livemode?: boolean;
  created?: number;
}

/** A Swytchcode exec callable. Default uses `swytchcode-runtime`. Override for tests. */
export type ExecFn = (canonicalId: string, input?: unknown) => Promise<unknown>;

export interface FirstPaymentRecoveryConfig {
  stripeSecretKey: string;
  exec?: ExecFn;
  /** When true (default), webhook handlers re-fetch via Swytchcode for verification. */
  verify?: { invoice?: boolean; paymentIntent?: boolean; subscription?: boolean };
  /** Optional `return_url` surfaced in `confirm_payment` actions. */
  defaultReturnUrl?: string;
  /** Hint surfaced in `wait` actions. Default: 30_000. */
  processingPollIntervalMs?: number;
  /** Override clock (epoch ms). Default `Date.now`. */
  now?: () => number;
}

export interface FirstPaymentRecoveryService {
  handleInvoicePaymentFailed(
    event: StripeEvent,
    prior?: Partial<RecoveryStateRecord>,
  ): Promise<RecoveryStateRecord | null>;
  handleInvoicePaymentActionRequired(
    event: StripeEvent,
    prior?: Partial<RecoveryStateRecord>,
  ): Promise<RecoveryStateRecord | null>;
  handleInvoicePaid(
    event: StripeEvent,
    prior?: Partial<RecoveryStateRecord>,
  ): Promise<RecoveryStateRecord | null>;
  getRecoveryState(record: Partial<RecoveryStateRecord>): RecoveryState;
  buildRecoveryAction(record: Partial<RecoveryStateRecord>): RecoveryAction;
}

// ─── Internal Stripe shapes (only fields we read) ────────────────────────────

interface StripeInvoice {
  id: string;
  object: "invoice";
  status?: string | null;
  billing_reason?: string | null;
  attempt_count?: number;
  hosted_invoice_url?: string | null;
  customer: string | { id: string };
  payment_intent?: string | { id: string } | null;
  parent?: {
    subscription_details?: {
      subscription?: string | { id: string };
      metadata?: Record<string, string>;
    } | null;
  } | null;
  subscription?: string | { id: string } | null;
  payments?: { data?: Array<{ payment?: { payment_intent?: string | { id: string } } }> } | null;
}

interface StripePaymentIntent {
  id: string;
  status: string;
  client_secret?: string | null;
  next_action?: { type?: string } | null;
  last_payment_error?: { code?: string; message?: string } | null;
}

interface StripeSubscription {
  id: string;
  status: string;
  customer: string | { id: string };
}

// ─── Stripe canonical IDs ────────────────────────────────────────────────────

const STRIPE = {
  INVOICE_GET: "invoices.invoice.get",
  PAYMENT_INTENT_GET: "payment_intents.payment_intent.get",
  SUBSCRIPTION_GET: "subscriptions.subscription.get",
} as const;

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

function readPaymentIntentId(invoice: StripeInvoice): string | undefined {
  if (invoice.payment_intent) return refId(invoice.payment_intent);
  const first = invoice.payments?.data?.[0]?.payment?.payment_intent;
  return refId(first ?? null);
}

function classifyFailureKind(
  paymentIntentStatus: string | undefined,
  subscriptionStatus: string | undefined,
): FailureKind | undefined {
  if (subscriptionStatus === "incomplete_expired") return "expired";
  switch (paymentIntentStatus) {
    case "requires_payment_method":
      return "requires_payment_method";
    case "requires_action":
    case "requires_confirmation":
      return "requires_action";
    case "processing":
      return "processing";
    default:
      return undefined;
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createFirstPaymentRecoveryService(
  config: FirstPaymentRecoveryConfig,
): FirstPaymentRecoveryService {
  if (!config.stripeSecretKey) throw new Error("stripeSecretKey is required");

  const exec: ExecFn = config.exec ?? (defaultExec as ExecFn);
  const verify = {
    invoice: true,
    paymentIntent: true,
    subscription: true,
    ...(config.verify ?? {}),
  };
  const now = config.now ?? (() => Date.now());
  const processingPollIntervalMs = config.processingPollIntervalMs ?? 30_000;
  const defaultReturnUrl = config.defaultReturnUrl;
  const auth = `Bearer ${config.stripeSecretKey}`;

  async function callStripe<T>(canonicalId: string, args: Record<string, unknown>): Promise<T> {
    const res = await exec(canonicalId, { Authorization: auth, ...args });
    return res as T;
  }

  function getRecoveryState(record: Partial<RecoveryStateRecord>): RecoveryState {
    if (record.subscriptionStatus === "incomplete_expired") return "expired";
    if (record.invoiceStatus === "paid") return "recovered";
    switch (record.paymentIntentStatus) {
      case "requires_payment_method":
        return "payment_method_update_required";
      case "requires_action":
      case "requires_confirmation":
        return "pending_authentication";
      case "processing":
        return "processing";
      default:
        return "billing_action_required";
    }
  }

  function buildRecoveryAction(record: Partial<RecoveryStateRecord>): RecoveryAction {
    const state = getRecoveryState(record);
    switch (state) {
      case "recovered":
        return { type: "none", reason: "recovered" };
      case "expired":
        return { type: "restart_signup" };
      case "pending_authentication":
        if (record.paymentIntentClientSecret) {
          return defaultReturnUrl
            ? {
                type: "confirm_payment",
                clientSecret: record.paymentIntentClientSecret,
                returnUrl: defaultReturnUrl,
              }
            : { type: "confirm_payment", clientSecret: record.paymentIntentClientSecret };
        }
        if (record.hostedInvoiceUrl) {
          return { type: "redirect_to_hosted_invoice", url: record.hostedInvoiceUrl };
        }
        return { type: "none", reason: "no_state" };
      case "payment_method_update_required":
      case "billing_action_required":
        if (record.hostedInvoiceUrl) {
          return { type: "redirect_to_hosted_invoice", url: record.hostedInvoiceUrl };
        }
        return { type: "none", reason: "no_state" };
      case "processing":
        return { type: "wait", retryAfterMs: processingPollIntervalMs };
    }
  }

  /**
   * Reconcile state from a Stripe invoice event. Re-fetches invoice +
   * subscription + PaymentIntent through Swytchcode (toggleable via `verify`),
   * then derives the normalized state. Returns null when the invoice is not
   * a first-payment invoice (renewal recovery is handled elsewhere).
   */
  async function reconcile(
    inbound: StripeInvoice | undefined,
    prior: Partial<RecoveryStateRecord> | undefined,
    { paid }: { paid: boolean },
  ): Promise<RecoveryStateRecord | null> {
    if (!inbound?.id) return null;

    const invoice: StripeInvoice = verify.invoice
      ? await callStripe<StripeInvoice>(STRIPE.INVOICE_GET, { params: { invoice: inbound.id } })
      : inbound;

    const subscriptionId = readSubscriptionId(invoice) ?? prior?.subscriptionId;
    let subscription: StripeSubscription | undefined;
    if (verify.subscription && subscriptionId) {
      subscription = await callStripe<StripeSubscription>(STRIPE.SUBSCRIPTION_GET, {
        params: { subscription_exposed_id: subscriptionId },
      });
    }

    // First-payment scope guard. Renewals (`subscription_cycle` /
    // `subscription_update`) belong to the renewal-recovery service.
    const billingReason = invoice.billing_reason ?? prior?.invoiceBillingReason;
    const subStatus = subscription?.status ?? prior?.subscriptionStatus;
    const inFirstPaymentLifecycle =
      billingReason === "subscription_create" ||
      subStatus === "incomplete" ||
      subStatus === "incomplete_expired" ||
      (paid && (subStatus === "active" || subStatus === "trialing"));
    if (!inFirstPaymentLifecycle) return null;

    const paymentIntentId = readPaymentIntentId(invoice) ?? prior?.paymentIntentId;
    let paymentIntent: StripePaymentIntent | undefined;
    if (verify.paymentIntent && paymentIntentId && !paid) {
      paymentIntent = await callStripe<StripePaymentIntent>(STRIPE.PAYMENT_INTENT_GET, {
        params: { intent: paymentIntentId },
      });
    }

    const accountId =
      prior?.accountId ?? invoice.parent?.subscription_details?.metadata?.account_id;

    const merged: Partial<RecoveryStateRecord> = {
      ...(prior ?? {}),
      accountId,
      customerId: refId(invoice.customer) ?? prior?.customerId,
      subscriptionId,
      invoiceId: invoice.id,
      paymentIntentId,
      invoiceStatus: invoice.status ?? prior?.invoiceStatus,
      invoiceBillingReason: billingReason,
      invoiceAttemptCount: invoice.attempt_count ?? prior?.invoiceAttemptCount,
      hostedInvoiceUrl: invoice.hosted_invoice_url ?? prior?.hostedInvoiceUrl,
      paymentIntentStatus: paymentIntent?.status ?? (paid ? undefined : prior?.paymentIntentStatus),
      paymentIntentNextActionType:
        paymentIntent?.next_action?.type ?? (paid ? undefined : prior?.paymentIntentNextActionType),
      paymentIntentClientSecret:
        paymentIntent?.client_secret ?? (paid ? undefined : prior?.paymentIntentClientSecret),
      paymentIntentLastErrorCode:
        paymentIntent?.last_payment_error?.code ??
        (paid ? undefined : prior?.paymentIntentLastErrorCode),
      paymentIntentLastErrorMessage:
        paymentIntent?.last_payment_error?.message ??
        (paid ? undefined : prior?.paymentIntentLastErrorMessage),
      subscriptionStatus: subStatus,
      metadata: {
        ...(prior?.metadata ?? {}),
        ...(invoice.parent?.subscription_details?.metadata ?? {}),
      },
      updatedAt: now(),
    };
    merged.failureKind = classifyFailureKind(merged.paymentIntentStatus, merged.subscriptionStatus);
    merged.state = getRecoveryState(merged);
    return merged as RecoveryStateRecord;
  }

  async function handleInvoicePaymentFailed(
    event: StripeEvent,
    prior?: Partial<RecoveryStateRecord>,
  ): Promise<RecoveryStateRecord | null> {
    if (event?.type !== "invoice.payment_failed") return null;
    return reconcile(event.data?.object as StripeInvoice | undefined, prior, { paid: false });
  }

  async function handleInvoicePaymentActionRequired(
    event: StripeEvent,
    prior?: Partial<RecoveryStateRecord>,
  ): Promise<RecoveryStateRecord | null> {
    if (event?.type !== "invoice.payment_action_required") return null;
    return reconcile(event.data?.object as StripeInvoice | undefined, prior, { paid: false });
  }

  async function handleInvoicePaid(
    event: StripeEvent,
    prior?: Partial<RecoveryStateRecord>,
  ): Promise<RecoveryStateRecord | null> {
    if (event?.type !== "invoice.paid") return null;
    return reconcile(event.data?.object as StripeInvoice | undefined, prior, { paid: true });
  }

  return {
    handleInvoicePaymentFailed,
    handleInvoicePaymentActionRequired,
    handleInvoicePaid,
    getRecoveryState,
    buildRecoveryAction,
  };
}
