const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const p = path.join(__dirname, ".env");
for (const line of fs.readFileSync(p, "utf8").split("\n")) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
}

const email = process.env.DEMO_LEAD_EMAIL || "test@example.com";

console.log(`\n========================================`);
console.log(`TESTING IDEMPOTENCY FOR: ${email}`);
console.log(`========================================`);

const req = {
  tool: "emails.email.create",
  args: { 
    headers: { "Idempotency-Key": "idempotency-demo-" + email },
    body: { 
      from: "onboarding@resend.dev", 
      to: [email], 
      subject: "Idempotency Test",
      html: "<p>If idempotency works, you will only receive ONE of these emails no matter how many times you run this script!</p>" 
    } 
  }
};

const r = spawnSync("npx", ["swytchcode", "exec", "--verbose"], { 
  input: JSON.stringify(req),
  encoding: "utf8", 
  shell: process.platform === "win32" 
});

if (r.stdout) console.log(r.stdout.trim());
if (r.stderr) console.log(r.stderr.trim());

console.log(`\n>>> Done! Run me again. You'll get a success response, but no duplicate email will arrive. <<<`);
