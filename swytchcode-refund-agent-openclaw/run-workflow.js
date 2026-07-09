#!/usr/bin/env node
/*
 * Onboarding workflow runner — HubSpot -> Stripe (customer + charge) -> Resend.
 * Runs each step through `swytchcode exec` so the calls (and credentials from .env)
 * are handled for you. Clean output for recording.
 *
 * Usage:
 *   node run-workflow.js            # real run (creates contact, customer, charge, sends email)
 *   node run-workflow.js --dry-run  # preview only, nothing is created
 */
"use strict";
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

function loadEnv() {
  const p = path.join(__dirname, ".env");
  if (!fs.existsSync(p)) { console.error("Missing .env"); process.exit(1); }
  for (const line of fs.readFileSync(p, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
  }
}

function run(label, canonicalId, input, dryRun) {
  const req = {
    tool: canonicalId,
    args: input
  };
  
  const args = ["exec", "--verbose"];
  if (dryRun) args.push("--dry-run");

  console.log("\n========================================");
  console.log("STEP: " + label + "   (" + canonicalId + ")");
  console.log("========================================");
  
  const r = spawnSync("npx", ["swytchcode", ...args], { 
    input: JSON.stringify(req),
    encoding: "utf8", 
    shell: process.platform === "win32" 
  });
  
  if (r.stdout) console.log(r.stdout.trim());
  if (r.stderr) console.log(r.stderr.trim());
  if (r.status !== 0) {
    console.log("\n>>> Step failed (exit " + r.status + "). Stopping. <<<");
    process.exit(r.status || 1);
  }
  
  return r.stdout || "";
}

function main() {
  loadEnv();
  
  // Map .env keys to the env vars expected by Swytchcode CLI (PROVIDER_API_KEY)
  if (process.env.HUBSPOT_PRIVATE_APP_TOKEN) {
    process.env.HUBSPOT_CRM_CONTACTS_API_KEY = process.env.HUBSPOT_PRIVATE_APP_TOKEN;
  }
  if (process.env.STRIPE_SECRET_KEY) {
    process.env.STRIPE_API_KEY = process.env.STRIPE_SECRET_KEY;
  }

  const dryRun = process.argv.includes("--dry-run");
  const email = process.env.DEMO_LEAD_EMAIL || "test@example.com";
  const name  = process.env.DEMO_LEAD_NAME || "Test Lead";
  const amount = Number(process.env.DEMO_PLAN_AMOUNT || 2000);

  console.log(dryRun ? "DRY RUN — previewing only, nothing is created.\n" : "LIVE RUN — creating real test records.\n");

  // 1) HubSpot: create the contact (JSON body wrapper)
  run("Create CRM contact in HubSpot", process.env.SWX_HUBSPOT_CREATE_CONTACT,
    { body: { properties: { email, firstname: name.split(" ")[0] || "Test", lastname: name.split(" ").slice(1).join(" ") || "Lead" } } },
    dryRun);

  // 2) Stripe: create the customer (Stripe handles x-www-form-urlencoded automatically via body wrapper)
  const custRes = run("Create customer in Stripe", process.env.SWX_STRIPE_CREATE_CUSTOMER,
    { body: { email, name, description: "New onboarding customer", source: "tok_visa" } },
    dryRun);

  let customerId = "cus_DRY_RUN_ID";
  if (!dryRun) {
    try {
      const parsed = JSON.parse(custRes);
      if (parsed.data && parsed.data.id) customerId = parsed.data.id;
    } catch(e) {}
  }

  // 3) Stripe: charge the customer. Use Idempotency-Key header to prevent double charges.
  run("Charge the customer in Stripe", process.env.SWX_CREATE_CHARGE_ID,
    { 
      headers: { "Idempotency-Key": "charge-" + email },
      body: { amount, currency: "usd", customer: customerId, description: "Onboarding charge" }
    },
    dryRun);

  // 4) Resend: send the welcome email (JSON body wrapper).
  // onboarding@resend.dev is Resend's shared test sender (no domain verification needed;
  // it can only deliver to YOUR Resend account email — set DEMO_LEAD_EMAIL to that).
  run("Send welcome email via Resend", process.env.SWX_RESEND_SEND_EMAIL,
    { 
      headers: { "Idempotency-Key": "onboarding-" + email },
      body: { from: "onboarding@resend.dev", to: [email], subject: "Welcome aboard!",
              html: "<p>Hi " + name + ", welcome! Your account is ready.</p>" } 
    },
    dryRun);

  console.log("\n========================================");
  console.log("WORKFLOW COMPLETE — 4 API calls across 3 services.");
  console.log("========================================");
}
main();
