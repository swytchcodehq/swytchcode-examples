import crypto from "node:crypto";

export interface VerifyOptions {
  /** Max allowed age of the timestamp in seconds. Default 300 (5 min). */
  toleranceSeconds?: number;
  /** Override clock for tests. */
  now?: () => number;
}

/**
 * Verifies a Stripe webhook signature header (`Stripe-Signature`) and returns the
 * parsed event. Throws on any mismatch.
 *
 * Implementation follows https://docs.stripe.com/webhooks#verify-manually — no Stripe
 * SDK dependency.
 */
export function verifyStripeSignature(
  rawPayload: string,
  signatureHeader: string,
  webhookSecret: string,
  options: VerifyOptions = {},
): unknown {
  const tolerance = options.toleranceSeconds ?? 300;
  const now = options.now ?? (() => Math.floor(Date.now() / 1000));

  const parts = new Map<string, string[]>();
  for (const segment of signatureHeader.split(",")) {
    const eq = segment.indexOf("=");
    if (eq === -1) continue;
    const key = segment.slice(0, eq).trim();
    const value = segment.slice(eq + 1).trim();
    const list = parts.get(key) ?? [];
    list.push(value);
    parts.set(key, list);
  }

  const tsRaw = parts.get("t")?.[0];
  const v1List = parts.get("v1") ?? [];
  if (!tsRaw || v1List.length === 0) {
    throw new Error("invalid Stripe-Signature header");
  }
  const ts = Number(tsRaw);
  if (!Number.isFinite(ts)) {
    throw new Error("invalid timestamp in Stripe-Signature");
  }
  if (Math.abs(now() - ts) > tolerance) {
    throw new Error("Stripe-Signature timestamp outside tolerance window");
  }

  const signedPayload = `${ts}.${rawPayload}`;
  const expected = crypto
    .createHmac("sha256", webhookSecret)
    .update(signedPayload, "utf8")
    .digest("hex");
  const expectedBuf = Buffer.from(expected, "hex");

  const matched = v1List.some((candidate) => {
    const candidateBuf = Buffer.from(candidate, "hex");
    return (
      candidateBuf.length === expectedBuf.length &&
      crypto.timingSafeEqual(candidateBuf, expectedBuf)
    );
  });
  if (!matched) {
    throw new Error("Stripe-Signature mismatch");
  }

  return JSON.parse(rawPayload);
}
