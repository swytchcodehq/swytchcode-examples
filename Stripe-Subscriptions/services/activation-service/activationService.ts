/**
 * swytchcode-stripe-subscription-activation — single-file reusable service.
 *
 * Solves one problem: developers grant access too early when starting a Stripe
 * subscription. Stripe recommends creating subscriptions through Checkout
 * (mode=subscription), persisting Customer + Subscription IDs on
 * `checkout.session.completed`, and continuing provisioning only after
 * `invoice.paid`. The browser success redirect must NEVER grant paid access.
 *
 * All Stripe API calls are delegated to the Swytchcode runtime — no Stripe SDK.
 * Canonical IDs used (must be `swytchcode add`ed before use):
 *   - checkout.session.create
 *   - checkout.session.get
 *   - invoices.invoice.get
 *   - subscriptions.subscription.get
 *
 * Public API (see `createActivationService` below):
 *   - createCheckoutSession(input)
 *   - handleCheckoutSessionCompleted(event, prior?)
 *   - handleInvoicePaid(event, prior?)
 *   - getActivationState(record)
 */
import { exec as defaultExec } from "swytchcode-runtime";

// ─── Public types ────────────────────────────────────────────────────────────

export type ActivationState =
  | "pending"
  | "active"
  | "failed_initial_payment"
  | "expired";

/**
 * Persistable record. Caller stores it (DB, KV, memory — the service is
 * storage-agnostic). Handlers return an updated record; the caller persists.
 */
export interface ActivationRecord {
  accountId: string;
  state: ActivationState;
  sessionId?: string;
  customerId?: string;
  subscriptionId?: string;
  invoiceId?: string;
  workspaceId?: string;
  tenantId?: string;
  metadata?: Record<string, string>;
  // Raw signals — getActivationState derives `state` from these
  sessionStatus?: string;
  invoiceStatus?: string;
  invoiceAmountPaid?: number;
  invoiceBillingReason?: string;
  subscriptionStatus?: string;
  failureReason?: string;
  updatedAt?: number;
}

export interface StripeEvent<T = unknown> {
  id: string;
  type: string;
  data: { object: T };
  livemode?: boolean;
  created?: number;
}

export interface CreateCheckoutSessionInput {
  accountId: string;
  successUrl: string;
  cancelUrl: string;
  lineItems: Array<{ price: string; quantity?: number }>;
  customerEmail?: string;
  customerId?: string;
  workspaceId?: string;
  tenantId?: string;
  trialPeriodDays?: number;
  allowPromotionCodes?: boolean;
  clientReferenceId?: string;
  metadata?: Record<string, string>;
}

export interface CreateCheckoutSessionResult {
  sessionId: string;
  url: string;
  expiresAt: number;
  record: ActivationRecord;
}

/** A Swytchcode exec callable. Default uses `swytchcode-runtime`. Override for tests. */
export type ExecFn = (canonicalId: string, input?: unknown) => Promise<unknown>;

export interface ActivationServiceConfig {
  stripeSecretKey: string;
  exec?: ExecFn;
  /** When true (default), webhook handlers re-fetch via Swytchcode for verification. */
  verify?: { session?: boolean; invoice?: boolean };
  /** Override clock (epoch ms). Default `Date.now`. */
  now?: () => number;
}

export interface ActivationService {
  createCheckoutSession(input: CreateCheckoutSessionInput): Promise<CreateCheckoutSessionResult>;
  handleCheckoutSessionCompleted(
    event: StripeEvent,
    prior?: Partial<ActivationRecord>,
  ): Promise<ActivationRecord | null>;
  handleInvoicePaid(
    event: StripeEvent,
    prior?: Partial<ActivationRecord>,
  ): Promise<ActivationRecord | null>;
  getActivationState(record: Partial<ActivationRecord>): ActivationState;
}

// ─── Internal Stripe shapes (only fields we read) ────────────────────────────

interface StripeCheckoutSession {
  id: string;
  object: "checkout.session";
  mode: string;
  status?: string | null;
  customer?: string | { id: string } | null;
  subscription?: string | { id: string } | null;
  invoice?: string | { id: string } | null;
  client_reference_id?: string | null;
  metadata?: Record<string, string> | null;
  expires_at?: number;
  url?: string | null;
}

interface StripeInvoice {
  id: string;
  object: "invoice";
  status?: string | null;
  billing_reason?: string | null;
  amount_paid: number;
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
}

// ─── Stripe canonical IDs ────────────────────────────────────────────────────

const STRIPE = {
  CHECKOUT_SESSION_CREATE: "checkout.session.create",
  CHECKOUT_SESSION_GET: "checkout.session.get",
  INVOICE_GET: "invoices.invoice.get",
  SUBSCRIPTION_GET: "subscriptions.subscription.get",
} as const;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function refId(v: string | { id: string } | null | undefined): string | undefined {
  if (!v) return undefined;
  return typeof v === "string" ? v : v.id;
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createActivationService(config: ActivationServiceConfig): ActivationService {
  if (!config.stripeSecretKey) throw new Error("stripeSecretKey is required");

  const exec: ExecFn = config.exec ?? (defaultExec as ExecFn);
  const verify = { session: true, invoice: true, ...(config.verify ?? {}) };
  const now = config.now ?? (() => Date.now());
  const auth = `Bearer ${config.stripeSecretKey}`;

  async function callStripe<T>(canonicalId: string, args: Record<string, unknown>): Promise<T> {
    const res = await exec(canonicalId, { Authorization: auth, ...args });
    return res as T;
  }

  function getActivationState(record: Partial<ActivationRecord>): ActivationState {
    if (record.sessionStatus === "expired") return "expired";
    if (
      record.invoiceStatus === "paid" &&
      (record.invoiceAmountPaid ?? 0) > 0 &&
      (record.subscriptionStatus === undefined ||
        record.subscriptionStatus === "active" ||
        record.subscriptionStatus === "trialing")
    ) {
      return "active";
    }
    if (
      record.invoiceBillingReason === "subscription_create" &&
      (record.invoiceStatus === "open" ||
        record.invoiceStatus === "uncollectible" ||
        record.invoiceStatus === "void" ||
        !!record.failureReason)
    ) {
      return "failed_initial_payment";
    }
    return "pending";
  }

  async function createCheckoutSession(
    input: CreateCheckoutSessionInput,
  ): Promise<CreateCheckoutSessionResult> {
    if (!input.accountId) throw new Error("accountId is required");
    if (!input.successUrl) throw new Error("successUrl is required");
    if (!input.cancelUrl) throw new Error("cancelUrl is required");
    if (!input.lineItems?.length) throw new Error("lineItems must contain at least one item");

    const metadata: Record<string, string> = {
      account_id: input.accountId,
      ...(input.workspaceId ? { workspace_id: input.workspaceId } : {}),
      ...(input.tenantId ? { tenant_id: input.tenantId } : {}),
      ...(input.metadata ?? {}),
    };

    const body: Record<string, unknown> = {
      mode: "subscription",
      success_url: input.successUrl,
      cancel_url: input.cancelUrl,
      line_items: input.lineItems.map((li) => ({ price: li.price, quantity: li.quantity ?? 1 })),
      client_reference_id: input.clientReferenceId ?? input.accountId,
      metadata,
    };
    if (input.customerEmail) body.customer_email = input.customerEmail;
    if (input.customerId) body.customer = input.customerId;
    if (input.allowPromotionCodes) body.allow_promotion_codes = true;
    if (input.trialPeriodDays != null) {
      body.subscription_data = { trial_period_days: input.trialPeriodDays };
    }

    const session = await callStripe<StripeCheckoutSession>(STRIPE.CHECKOUT_SESSION_CREATE, {
      body,
    });
    if (!session?.id || !session.url) {
      throw new Error(
        `Stripe did not return a usable Checkout Session (id=${String(session?.id)})`,
      );
    }

    const record: ActivationRecord = {
      accountId: input.accountId,
      state: "pending",
      sessionId: session.id,
      customerId: refId(session.customer),
      workspaceId: input.workspaceId,
      tenantId: input.tenantId,
      metadata,
      updatedAt: now(),
    };

    return {
      sessionId: session.id,
      url: session.url,
      expiresAt: session.expires_at ?? 0,
      record,
    };
  }

  async function handleCheckoutSessionCompleted(
    event: StripeEvent,
    prior?: Partial<ActivationRecord>,
  ): Promise<ActivationRecord | null> {
    if (event?.type !== "checkout.session.completed") return null;
    const inbound = event.data?.object as StripeCheckoutSession | undefined;
    if (!inbound?.id) return null;

    const session: StripeCheckoutSession = verify.session
      ? await callStripe<StripeCheckoutSession>(STRIPE.CHECKOUT_SESSION_GET, {
          params: { session: inbound.id },
        })
      : inbound;

    if (session.mode !== "subscription") return null;

    const accountId =
      session.metadata?.account_id ?? session.client_reference_id ?? prior?.accountId;
    if (!accountId) return null;

    // Never regress an already-active account on a replayed event.
    if (prior?.state === "active") {
      return { ...prior, accountId } as ActivationRecord;
    }

    const merged: Partial<ActivationRecord> = {
      ...(prior ?? {}),
      accountId,
      sessionId: session.id,
      customerId: refId(session.customer) ?? prior?.customerId,
      subscriptionId: refId(session.subscription) ?? prior?.subscriptionId,
      invoiceId: refId(session.invoice) ?? prior?.invoiceId,
      workspaceId: session.metadata?.workspace_id ?? prior?.workspaceId,
      tenantId: session.metadata?.tenant_id ?? prior?.tenantId,
      metadata: { ...(prior?.metadata ?? {}), ...(session.metadata ?? {}) },
      sessionStatus: session.status ?? undefined,
      updatedAt: now(),
    };
    merged.state = getActivationState(merged);
    return merged as ActivationRecord;
  }

  async function handleInvoicePaid(
    event: StripeEvent,
    prior?: Partial<ActivationRecord>,
  ): Promise<ActivationRecord | null> {
    if (event?.type !== "invoice.paid") return null;
    const inbound = event.data?.object as StripeInvoice | undefined;
    if (!inbound?.id) return null;

    // Renewal recovery is handled elsewhere; activation only acts on the first invoice.
    if (inbound.billing_reason && inbound.billing_reason !== "subscription_create") {
      return null;
    }

    const invoice: StripeInvoice = verify.invoice
      ? await callStripe<StripeInvoice>(STRIPE.INVOICE_GET, { params: { invoice: inbound.id } })
      : inbound;

    const subscriptionId =
      refId(invoice.parent?.subscription_details?.subscription) ?? refId(invoice.subscription);

    let subscription: StripeSubscription | undefined;
    if (verify.invoice && subscriptionId) {
      subscription = await callStripe<StripeSubscription>(STRIPE.SUBSCRIPTION_GET, {
        params: { subscription_exposed_id: subscriptionId },
      });
    }

    const accountId =
      prior?.accountId ?? invoice.parent?.subscription_details?.metadata?.account_id;
    if (!accountId) return null;

    const paid = invoice.status === "paid" && invoice.amount_paid > 0;
    const subOk =
      !subscription || subscription.status === "active" || subscription.status === "trialing";
    const failureReason =
      paid && subOk
        ? undefined
        : `invoice ${invoice.id} status=${String(invoice.status)} amount_paid=${invoice.amount_paid} subscription.status=${String(subscription?.status ?? "n/a")}`;

    const merged: Partial<ActivationRecord> = {
      ...(prior ?? {}),
      accountId,
      invoiceId: invoice.id,
      subscriptionId: subscriptionId ?? prior?.subscriptionId,
      customerId: refId(invoice.customer) ?? prior?.customerId,
      invoiceStatus: invoice.status ?? undefined,
      invoiceAmountPaid: invoice.amount_paid,
      invoiceBillingReason: invoice.billing_reason ?? undefined,
      subscriptionStatus: subscription?.status,
      failureReason,
      updatedAt: now(),
    };
    merged.state = getActivationState(merged);
    return merged as ActivationRecord;
  }

  return {
    createCheckoutSession,
    handleCheckoutSessionCompleted,
    handleInvoicePaid,
    getActivationState,
  };
}
