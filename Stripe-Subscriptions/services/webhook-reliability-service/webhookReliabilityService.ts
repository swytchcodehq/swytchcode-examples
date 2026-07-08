/**
 * swytchcode-stripe-webhook-reliability — single-file reusable service.
 *
 * Solves one problem: making Stripe webhook delivery safe and idempotent for
 * subscription flows. Stripe recommends monitoring at minimum
 * `checkout.session.completed`, `invoice.paid`, and `invoice.payment_failed`
 * for subscription lifecycles, and warns that webhooks may be duplicated,
 * delivered out of order, or arrive after the corresponding Stripe object
 * has already advanced.
 *
 * What this service does:
 *   1. Verifies Stripe-Signature using the standard `t=...,v1=...` scheme
 *      (HMAC-SHA256 over `${t}.${rawBody}`) with constant-time comparison
 *      and a configurable replay-tolerance window.
 *   2. Persists raw events through a caller-provided EventStore so the
 *      original payload survives crashes and retries.
 *   3. Enforces idempotency by Stripe `event.id`.
 *   4. Tolerates out-of-order delivery via per-resource cursors derived from
 *      `event.created`.
 *   5. Supports replay-by-id, re-fetching the canonical event via Swytchcode
 *      `events.event.get` so the replay is sourced from Stripe, not from a
 *      possibly-tampered local copy.
 *   6. Optionally reconciles the event's underlying Stripe object via
 *      Swytchcode (subscription / invoice / checkout session) before the
 *      caller's handler runs.
 *
 * Stripe API calls are delegated to the Swytchcode runtime — no Stripe SDK.
 * Canonical IDs used (must be `swytchcode add`ed before use):
 *   - events.event.get
 *   - invoices.invoice.get               (already added by activation-service)
 *   - subscriptions.subscription.get     (already added by plan-change-service)
 *   - checkout.session.get               (already added by activation-service)
 *
 * Public API (see `createWebhookReliabilityService` below):
 *   - verifyAndParseWebhook(rawBody, signature)
 *   - storeEvent(event)
 *   - processEvent(event, context)
 *   - replayEvent(eventId)
 *   - getEventStatus(eventId)
 */
import { createHmac, timingSafeEqual } from "node:crypto";
import { exec as defaultExec } from "swytchcode-runtime";

// ─── Public types ────────────────────────────────────────────────────────────

/**
 * Normalized processing state for a Stripe event lifecycle.
 *
 *  - `verified`         signature OK and event persisted, handler not yet run
 *  - `duplicate_ignored` event.id already processed, or strictly older than
 *                       the per-resource cursor (out-of-order safe drop)
 *  - `processed`        handler ran successfully on first delivery
 *  - `replayed`         handler ran successfully via `replayEvent`
 *  - `failed_retryable` handler threw a transient error; safe for Stripe to
 *                       redeliver or for the caller to schedule a retry
 *  - `failed_terminal`  handler threw a non-recoverable error; do not retry
 */
export type WebhookProcessingState =
  | "verified"
  | "duplicate_ignored"
  | "processed"
  | "replayed"
  | "failed_retryable"
  | "failed_terminal";

/** Stripe event shape (only fields we read; permissive on `data.object`). */
export interface StripeEvent<T = unknown> {
  id: string;
  object: "event";
  type: string;
  api_version?: string | null;
  created: number;
  livemode: boolean;
  pending_webhooks?: number;
  request?: { id?: string | null; idempotency_key?: string | null } | null;
  account?: string | null;
  data: { object: T; previous_attributes?: Record<string, unknown> | null };
}

/**
 * Persistable record for one Stripe event. Caller stores it in DB / KV; the
 * service never holds long-lived state.
 */
export interface WebhookEventRecord {
  eventId: string;
  type: string;
  state: WebhookProcessingState;
  /** Unix seconds (Stripe `event.created`). Used for out-of-order detection. */
  createdAt: number;
  /** Raw event JSON exactly as Stripe sent it. Source of truth on replay. */
  rawEvent: StripeEvent;
  /** Resource id this event mutated (sub_..., in_..., cs_...) when known. */
  resourceId?: string;
  /** Stripe API version at the time of delivery. */
  apiVersion?: string;
  livemode?: boolean;
  /** Set when handler failed; surfaced for observability. */
  lastError?: string;
  /** Number of times processEvent has been invoked for this id. */
  attemptCount: number;
  /** True once the event has reached a terminal state (`processed`/`replayed`/`failed_terminal`). */
  terminal: boolean;
  receivedAt: number;
  updatedAt: number;
}

/**
 * Storage interface the service depends on. Implement against your DB/KV.
 * All methods must be safe under concurrent webhook deliveries — use
 * conditional writes (e.g. `INSERT ... ON CONFLICT DO NOTHING`) inside
 * `putIfAbsent` to make idempotency race-proof.
 */
export interface EventStore {
  /** Insert if eventId is new; return whether the insert happened. */
  putIfAbsent(record: WebhookEventRecord): Promise<{ inserted: boolean; existing?: WebhookEventRecord }>;
  get(eventId: string): Promise<WebhookEventRecord | null>;
  update(eventId: string, patch: Partial<WebhookEventRecord>): Promise<WebhookEventRecord>;
  /**
   * Returns the highest `event.created` seen so far for a given resource id
   * (e.g. a subscription id). Used to drop strictly-older deliveries that
   * arrive after a newer event has already been processed. Implementations
   * may return `null` to disable out-of-order suppression.
   */
  getResourceCursor?(resourceId: string): Promise<number | null>;
  /** Atomically advance the per-resource cursor to `max(existing, createdAt)`. */
  advanceResourceCursor?(resourceId: string, createdAt: number): Promise<void>;
}

/** Caller-supplied per-event handler. Throw `RetryableError` for retryables. */
export type EventHandler = (
  event: StripeEvent,
  context: ProcessContext,
) => Promise<void> | void;

export interface ProcessContext {
  /** Caller-supplied request-scoped object (db handle, logger, tenant id...). */
  [key: string]: unknown;
}

/** A Swytchcode exec callable. Default uses `swytchcode-runtime`. Override for tests. */
export type ExecFn = (canonicalId: string, input?: unknown) => Promise<unknown>;

/** Throw this from a handler to mark the failure as retryable. */
export class RetryableError extends Error {
  readonly retryable = true as const;
  constructor(message: string, public override cause?: unknown) {
    super(message);
    this.name = "RetryableError";
  }
}

/** Thrown by `verifyAndParseWebhook` for any signature/parse failure. */
export class WebhookVerificationError extends Error {
  constructor(public reason: string) {
    super(`webhook verification failed: ${reason}`);
    this.name = "WebhookVerificationError";
  }
}

export interface VerifyResult {
  state: "verified";
  event: StripeEvent;
  /** Timestamp the signature was issued at (Unix seconds). */
  signatureTimestamp: number;
}

export interface StoreResult {
  state: "verified" | "duplicate_ignored";
  record: WebhookEventRecord;
}

export interface ProcessResult {
  state: WebhookProcessingState;
  record: WebhookEventRecord;
}

export interface ReplayResult {
  state: WebhookProcessingState;
  record: WebhookEventRecord;
}

export interface WebhookReliabilityServiceConfig {
  /** Stripe Webhook signing secret (`whsec_...`) for signature verification. */
  webhookSecret: string;
  /**
   * Stripe secret key used by reconciliation calls and replay-by-id.
   * Required for `replayEvent` and any reconciliation; can be omitted if you
   * only use this service for verification + storage + caller-provided handlers.
   */
  stripeSecretKey?: string;
  /** Persistence layer. */
  store: EventStore;
  /**
   * Map of Stripe event type → handler. The service routes verified events
   * to these. Unhandled types are short-circuited to `processed` (no-op).
   */
  handlers?: Record<string, EventHandler>;
  /** Replay tolerance for the Stripe-Signature timestamp. Default 300 sec. */
  toleranceSeconds?: number;
  /**
   * If true (default), `processEvent` calls Swytchcode to refetch the
   * underlying Stripe object (subscription/invoice/session) before invoking
   * the handler — protects against stale event payloads when out-of-order
   * deliveries cross paths.
   */
  reconcile?: boolean;
  exec?: ExecFn;
  now?: () => number;
}

export interface WebhookReliabilityService {
  verifyAndParseWebhook(rawBody: string | Buffer, signature: string): VerifyResult;
  storeEvent(event: StripeEvent): Promise<StoreResult>;
  processEvent(event: StripeEvent, context?: ProcessContext): Promise<ProcessResult>;
  replayEvent(eventId: string, context?: ProcessContext): Promise<ReplayResult>;
  getEventStatus(eventId: string): Promise<WebhookEventRecord | null>;
}

// ─── Stripe canonical IDs ────────────────────────────────────────────────────

const STRIPE = {
  EVENT_GET: "events.event.get",
  INVOICE_GET: "invoices.invoice.get",
  SUBSCRIPTION_GET: "subscriptions.subscription.get",
  CHECKOUT_SESSION_GET: "checkout.session.get",
} as const;

// Subset of Stripe-recommended subscription-flow event types this service
// understands well enough to extract a `resourceId` from. Other types still
// flow through; resourceId just stays undefined.
const SUBSCRIPTION_FLOW_TYPES = new Set([
  "checkout.session.completed",
  "checkout.session.async_payment_succeeded",
  "checkout.session.async_payment_failed",
  "invoice.paid",
  "invoice.payment_failed",
  "invoice.payment_action_required",
  "invoice.finalized",
  "customer.subscription.created",
  "customer.subscription.updated",
  "customer.subscription.deleted",
]);

// ─── Helpers ─────────────────────────────────────────────────────────────────

function parseStripeSignatureHeader(
  header: string,
): { t: number; v1: string[] } {
  // Stripe-Signature: t=1492774577,v1=5257a..,v1=...,v0=...
  const parts = header.split(",").map((p) => p.trim()).filter(Boolean);
  let t: number | null = null;
  const v1: string[] = [];
  for (const part of parts) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    const k = part.slice(0, eq);
    const v = part.slice(eq + 1);
    if (k === "t") t = Number(v);
    else if (k === "v1") v1.push(v);
  }
  if (t === null || Number.isNaN(t)) {
    throw new WebhookVerificationError("missing or malformed `t` in Stripe-Signature");
  }
  if (v1.length === 0) {
    throw new WebhookVerificationError("no v1 signatures present in Stripe-Signature");
  }
  return { t, v1 };
}

function constantTimeEqualHex(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  try {
    return timingSafeEqual(Buffer.from(a, "hex"), Buffer.from(b, "hex"));
  } catch {
    return false;
  }
}

function bodyToString(rawBody: string | Buffer): string {
  // Stripe verification REQUIRES the exact bytes Stripe sent. Callers must
  // pass the raw, unparsed request body — never `JSON.stringify(req.body)`.
  return Buffer.isBuffer(rawBody) ? rawBody.toString("utf8") : rawBody;
}

function extractResourceId(event: StripeEvent): string | undefined {
  const obj = event.data?.object as Record<string, unknown> | undefined;
  if (!obj) return undefined;
  const id = obj.id;
  return typeof id === "string" ? id : undefined;
}

function isHandlerRetryable(err: unknown): boolean {
  if (err instanceof RetryableError) return true;
  // Conventional escape hatches without forcing a dependency on RetryableError.
  if (typeof err === "object" && err !== null) {
    const e = err as { retryable?: unknown; code?: unknown };
    if (e.retryable === true) return true;
    if (e.code === "ECONNRESET" || e.code === "ETIMEDOUT" || e.code === "EAI_AGAIN") {
      return true;
    }
  }
  return false;
}

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createWebhookReliabilityService(
  config: WebhookReliabilityServiceConfig,
): WebhookReliabilityService {
  if (!config.webhookSecret) throw new Error("webhookSecret is required");
  if (!config.store) throw new Error("store is required");

  const exec: ExecFn = config.exec ?? (defaultExec as ExecFn);
  const handlers = config.handlers ?? {};
  const tolerance = config.toleranceSeconds ?? 300;
  const reconcile = config.reconcile ?? true;
  const now = config.now ?? (() => Date.now());

  function callStripe<T>(canonicalId: string, args: Record<string, unknown>): Promise<T> {
    if (!config.stripeSecretKey) {
      throw new Error(
        `stripeSecretKey is required to call Swytchcode '${canonicalId}'; configure it on the service or skip reconciliation/replay`,
      );
    }
    return exec(canonicalId, {
      Authorization: `Bearer ${config.stripeSecretKey}`,
      ...args,
    }) as Promise<T>;
  }

  function verifyAndParseWebhook(
    rawBody: string | Buffer,
    signature: string,
  ): VerifyResult {
    if (!signature) throw new WebhookVerificationError("missing Stripe-Signature header");
    const body = bodyToString(rawBody);
    const { t, v1 } = parseStripeSignatureHeader(signature);

    const ageSeconds = Math.floor(now() / 1000) - t;
    if (ageSeconds > tolerance) {
      throw new WebhookVerificationError(
        `signature timestamp is ${ageSeconds}s old, exceeds tolerance of ${tolerance}s`,
      );
    }
    if (ageSeconds < -tolerance) {
      throw new WebhookVerificationError(
        `signature timestamp is ${-ageSeconds}s in the future, exceeds tolerance of ${tolerance}s`,
      );
    }

    const expected = createHmac("sha256", config.webhookSecret)
      .update(`${t}.${body}`, "utf8")
      .digest("hex");
    const matched = v1.some((candidate) => constantTimeEqualHex(candidate, expected));
    if (!matched) throw new WebhookVerificationError("no v1 signature matched expected HMAC");

    let event: StripeEvent;
    try {
      event = JSON.parse(body) as StripeEvent;
    } catch (err) {
      throw new WebhookVerificationError(`payload is not valid JSON: ${errorMessage(err)}`);
    }
    if (!event || event.object !== "event" || typeof event.id !== "string") {
      throw new WebhookVerificationError("payload is not a Stripe event object");
    }

    return { state: "verified", event, signatureTimestamp: t };
  }

  async function storeEvent(event: StripeEvent): Promise<StoreResult> {
    const ts = now();
    const record: WebhookEventRecord = {
      eventId: event.id,
      type: event.type,
      state: "verified",
      createdAt: event.created,
      rawEvent: event,
      resourceId: extractResourceId(event),
      apiVersion: event.api_version ?? undefined,
      livemode: event.livemode,
      attemptCount: 0,
      terminal: false,
      receivedAt: ts,
      updatedAt: ts,
    };
    const { inserted, existing } = await config.store.putIfAbsent(record);
    if (!inserted) {
      return { state: "duplicate_ignored", record: existing ?? record };
    }
    return { state: "verified", record };
  }

  async function reconcileObject(event: StripeEvent): Promise<StripeEvent> {
    if (!reconcile || !config.stripeSecretKey) return event;
    const obj = event.data?.object as { id?: string; object?: string } | undefined;
    const objectType = obj?.object;
    const id = obj?.id;
    if (!id || !objectType) return event;

    try {
      let fresh: unknown;
      if (objectType === "subscription") {
        fresh = await callStripe<unknown>(STRIPE.SUBSCRIPTION_GET, {
          params: { subscription_exposed_id: id },
        });
      } else if (objectType === "invoice") {
        fresh = await callStripe<unknown>(STRIPE.INVOICE_GET, { params: { invoice: id } });
      } else if (objectType === "checkout.session") {
        fresh = await callStripe<unknown>(STRIPE.CHECKOUT_SESSION_GET, {
          params: { session: id },
        });
      } else {
        return event;
      }
      return { ...event, data: { ...event.data, object: fresh } };
    } catch {
      // Reconciliation is best-effort; if it fails the handler still runs on the
      // signed payload Stripe sent. The handler can retry by throwing RetryableError.
      return event;
    }
  }

  async function runHandler(
    event: StripeEvent,
    context: ProcessContext,
    finalState: "processed" | "replayed",
  ): Promise<ProcessResult> {
    const handler = handlers[event.type];
    const ts = now();

    if (!handler) {
      // Unhandled type — record as terminal `processed` so duplicates short-circuit.
      const updated = await config.store.update(event.id, {
        state: finalState,
        terminal: true,
        attemptCount: 1,
        lastError: undefined,
        updatedAt: ts,
      });
      if (updated.resourceId && config.store.advanceResourceCursor) {
        await config.store.advanceResourceCursor(updated.resourceId, event.created);
      }
      return { state: finalState, record: updated };
    }

    const reconciled = await reconcileObject(event);
    try {
      await handler(reconciled, context);
      const updated = await config.store.update(event.id, {
        state: finalState,
        terminal: true,
        attemptCount: (await currentAttempts(event.id)) + 1,
        lastError: undefined,
        updatedAt: ts,
      });
      if (updated.resourceId && config.store.advanceResourceCursor) {
        await config.store.advanceResourceCursor(updated.resourceId, event.created);
      }
      return { state: finalState, record: updated };
    } catch (err) {
      const retryable = isHandlerRetryable(err);
      const next: WebhookProcessingState = retryable ? "failed_retryable" : "failed_terminal";
      const updated = await config.store.update(event.id, {
        state: next,
        terminal: !retryable,
        attemptCount: (await currentAttempts(event.id)) + 1,
        lastError: errorMessage(err),
        updatedAt: ts,
      });
      return { state: next, record: updated };
    }
  }

  async function currentAttempts(eventId: string): Promise<number> {
    const r = await config.store.get(eventId);
    return r?.attemptCount ?? 0;
  }

  async function processEvent(
    event: StripeEvent,
    context: ProcessContext = {},
  ): Promise<ProcessResult> {
    // Ensure persistence + idempotency.
    const stored = await storeEvent(event);

    // Out-of-order suppression: if this event is strictly older than the
    // newest event already processed for the same resource, drop it.
    if (
      stored.record.resourceId &&
      config.store.getResourceCursor &&
      !stored.record.terminal
    ) {
      const cursor = await config.store.getResourceCursor(stored.record.resourceId);
      if (cursor !== null && cursor !== undefined && event.created < cursor) {
        const ts = now();
        const updated = await config.store.update(event.id, {
          state: "duplicate_ignored",
          terminal: true,
          updatedAt: ts,
        });
        return { state: "duplicate_ignored", record: updated };
      }
    }

    // Idempotency: if storeEvent reported a duplicate AND the prior attempt
    // already reached a terminal state, short-circuit with `duplicate_ignored`.
    // If the prior attempt is `failed_retryable`, fall through and re-run.
    if (stored.state === "duplicate_ignored") {
      if (stored.record.terminal) {
        return { state: "duplicate_ignored", record: stored.record };
      }
      if (stored.record.state !== "failed_retryable") {
        // Another in-flight worker is processing it; do not double-run.
        return { state: "duplicate_ignored", record: stored.record };
      }
    }

    return runHandler(event, context, "processed");
  }

  async function replayEvent(
    eventId: string,
    context: ProcessContext = {},
  ): Promise<ReplayResult> {
    if (!eventId) throw new Error("eventId is required");

    // Always re-fetch the canonical event from Stripe — the local copy may be
    // stale or tampered with. Stripe retains events for 30 days.
    const fresh = await callStripe<StripeEvent>(STRIPE.EVENT_GET, {
      params: { id: eventId },
    });
    if (!fresh || fresh.object !== "event" || fresh.id !== eventId) {
      throw new Error(`events.event.get returned a non-event payload for id=${eventId}`);
    }

    // storeEvent is idempotent — re-running it on a known id is a no-op insert.
    await storeEvent(fresh);
    return runHandler(fresh, context, "replayed");
  }

  async function getEventStatus(eventId: string): Promise<WebhookEventRecord | null> {
    if (!eventId) throw new Error("eventId is required");
    return config.store.get(eventId);
  }

  return {
    verifyAndParseWebhook,
    storeEvent,
    processEvent,
    replayEvent,
    getEventStatus,
  };
}
