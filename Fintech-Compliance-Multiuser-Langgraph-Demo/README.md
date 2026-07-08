# Fintech Compliance — Multi-User LangGraph Demo

A production-style showcase of the [swytchcode](https://swytchcode.com) platform running a full fintech compliance workflow across **10 dummy users** — with automatic retries, resumable execution, policy enforcement, and a built-in audit trail.

Built on [LangGraph](https://github.com/langchain-ai/langgraph) with three real financial APIs: **Plaid**, **Persona**, and **Dwolla** — all orchestrated through swytchcode.

---

## Table of Contents

- [What This Demo Shows](#what-this-demo-shows)
- [How It Works](#how-it-works)
- [Workflow Diagram](#workflow-diagram)
- [The 3 Compliance Policies](#the-3-compliance-policies)
- [Retry Logic](#retry-logic)
- [Resumable Execution (Idempotency)](#resumable-execution-idempotency)
- [Audit Trail](#audit-trail)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Demo](#running-the-demo)
- [Demo Scenarios](#demo-scenarios)
- [Expected Output](#expected-output)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Related](#related)

---

## What This Demo Shows

| Capability | How It's Demonstrated |
|---|---|
| **Multi-user orchestration** | 10 users processed sequentially, each through a 4-step compliance workflow |
| **Swytchcode execution** | Every API call (Plaid, Persona, Dwolla) goes through `swytchcode_exec` |
| **Retry logic** | Every API call retried up to 3 times with a 2-second delay before failing |
| **Resumable workflow** | If the script crashes, re-running it skips completed users and resumes from where it stopped |
| **Conditional routing** | Dwolla only runs if Persona KYC is approved — blocked users skip straight to policy |
| **Policy enforcement** | 3 compliance rules checked per user — violations block the transfer |
| **Audit trail** | `swytchcode audit` shows every API call made across all users after the run |

---

## How It Works

The demo simulates a fintech company onboarding customers for bank transfers. Before any transfer is allowed, every customer must pass a 4-step compliance check:

1. **Plaid** — Link the customer's bank account. Fetch account type (checking/savings) and available balance.
2. **Persona KYC** — Create a KYC identity verification inquiry and approve it. If this fails, the customer never reaches Dwolla.
3. **Dwolla** — Register the customer on the payment network and attach a funding source. Only runs if KYC is approved.
4. **Policy Engine** — Run 3 compliance rules against the data collected in steps 1–3. Any violation blocks the transfer.

This runs for all 10 demo users back to back. Every API call goes through swytchcode, which handles routing, authentication, and logging.

---

## Workflow Diagram

```
For each of 10 users:

  ┌─────────────────────────────────────┐
  │  STEP 1: Plaid                      │
  │  - Create sandbox public token      │
  │  - Exchange for access token        │
  │  - Fetch account type + balance     │
  └────────────────┬────────────────────┘
                   │
  ┌────────────────▼────────────────────┐
  │  STEP 2: Persona KYC                │
  │  - Create KYC inquiry               │
  │  - Approve in sandbox               │
  │  - Read KYC status                  │
  └────────────────┬────────────────────┘
                   │
         ┌─────────▼──────────┐
         │  KYC approved?     │
         └──────┬─────────────┘
       YES              NO
        │                │
  ┌─────▼───┐       ┌────▼────────────────┐
  │ STEP 3  │       │  Skip Dwolla        │
  │ Dwolla  │       │  Go to policy check │
  │ customer│       └─────────────────────┘
  │ + fund  │
  └─────┬───┘
        │
  ┌─────▼───────────────────────────────┐
  │  STEP 4: Policy Enforcement         │
  │  Rule 1: KYC must be approved       │
  │  Rule 2: Account type must be       │
  │          checking or savings        │
  │  Rule 3: Balance <= threshold       │
  └─────────────────────────────────────┘
```

---

## The 3 Compliance Policies

All 3 rules are checked for every user. The engine does **not** stop at the first failure — it collects all violations so you can see everything that's wrong at once.

### Policy 1 — KYC Must Be Approved

```
persona_status == "approved"
```

If the customer's identity verification did not pass, no transfer is allowed. Dwolla is also skipped entirely for these users.

### Policy 2 — Supported Account Type

```
plaid_account_subtype in {"checking", "savings"}
```

Only standard bank accounts are accepted. Investment accounts, credit lines, and other account types are rejected.

### Policy 3 — Balance Under Threshold

```
plaid_available_balance <= TRANSFER_HOLD_THRESHOLD
```

If the account balance exceeds the configured threshold, the transaction is placed on hold. The threshold is controlled by the `TRANSFER_HOLD_THRESHOLD` environment variable — no code change needed.

**Default threshold:** `$1,000`
**To trigger violations:** set `TRANSFER_HOLD_THRESHOLD=50` (sandbox accounts return ~$100 balance)

---

## Retry Logic

Every `swytchcode_exec` call is wrapped in `exec_with_retry`:

```python
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def exec_with_retry(canonical_id, params, label):
    for attempt in range(1, MAX_RETRIES + 1):
        result = swytchcode_exec(canonical_id, params)
        if not result.get("error"):
            return result   # success — return immediately
        if attempt < MAX_RETRIES:
            print(f"  [{label}] Attempt {attempt}/3 failed — retrying in 2s...")
            time.sleep(2)
    return result           # all 3 failed — return last error
```

This applies to every API call: Plaid (3 calls), Persona (3 calls), Dwolla (3 calls) — 9 calls per user, all protected by retry logic.

The Dwolla OAuth token fetch uses `requests.post` directly (outside swytchcode) and has its own identical retry loop.

**What you see when a retry fires:**

```
  [plaid:exchange] Attempt 1/3 failed — retrying in 2s...
  [plaid:exchange] Attempt 2/3 failed — retrying in 2s...
  [plaid:exchange] All 3 attempts failed
```

---

## Resumable Execution (Idempotency)

### How it works

After every user completes, their result is immediately written to `run_state.json`:

```json
{
  "run_id": "2026-06-12T10:30:00Z",
  "completed": {
    "alice.johnson@fintech-demo.com": {
      "name": "Alice Johnson",
      "kyc": "approved",
      "dwolla": "abc12345",
      "policy_passed": true,
      "violations": [],
      "completed_at": "2026-06-12T10:30:15Z"
    }
  }
}
```

On the next run, the script reads this file and skips any user already listed in `completed`. It re-hydrates their results into the final summary so the totals are always accurate.

### Why this matters

If the script crashes on user 6 — network failure, Ctrl+C, power cut — users 1–5 are safe. Re-running picks up from user 6. No duplicate API calls, no duplicate Dwolla customers, no wasted time.

This is **workflow-level idempotency** — the same guarantee you'd build into a production job queue or distributed system, applied here to a local script.

### Resetting a run

To start completely fresh:

```bash
# Mac/Linux
rm run_state.json

# Windows
del run_state.json
```

`run_state.json` is in `.gitignore` — it will never be accidentally committed.

### Email uniqueness

Each of the 10 demo users has a unique, hardcoded email address. This also protects against Dwolla creating duplicate customer records if a user is re-processed — `customer.list` filtered by email always resolves to the same existing record.

---

## Audit Trail

After any run:

```bash
swytchcode audit
```

This prints every `swytchcode_exec` call made during the run — canonical ID, timestamp, request inputs, and response outputs — across all 10 users and all retry attempts.

**What it shows:**

```
[2026-06-12T10:30:01Z] sandbox.public_token.create
  -> { institution_id: "ins_109508", ... }
  <- { public_token: "public-sandbox-..." }

[2026-06-12T10:30:02Z] item.public_token.exchange.create
  -> { public_token: "public-sandbox-..." }
  <- { access_token: "access-sandbox-..." }

... (9 calls x 10 users = 90 total entries)
```

This is built into swytchcode — no extra configuration needed.

---

## Prerequisites

- Python 3.10 or higher
- `swytchcode` CLI — install via: `npm install -g swytchcode`
- Sandbox accounts for:
  - [Plaid](https://dashboard.plaid.com) — free sandbox
  - [Persona](https://withpersona.com) — free sandbox
  - [Dwolla](https://accounts-sandbox.dwolla.com) — free sandbox

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/swytchcodehq/Fintech-Compliance-Multiuser-Demo.git
cd Fintech-Compliance-Multiuser-Demo
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials (see [Environment Variables](#environment-variables) below).

### 4. Install swytchcode integrations

```bash
swytchcode bootstrap
```

This installs the 3 integrations — Plaid, Persona, Dwolla — from `.swytchcode/tooling.json` into your local swytchcode environment.

### 5. Run

```bash
python main.py
```

---

## Running the Demo

### First run

```bash
python main.py
```

All 10 users are processed. A `run_state.json` file is created and updated after each user completes.

### Resuming after a crash

If the script was interrupted, just run it again:

```bash
python main.py
```

Output will show:

```
Resuming from previous run (run_id: 2026-06-12T10:30:00Z)
   4 user(s) already completed — skipping them.
```

### Starting fresh

```bash
del run_state.json   # Windows
rm run_state.json    # Mac/Linux

python main.py
```

---

## Demo Scenarios

These are the scenarios designed for live showcasing. All require only a `.env` change — no code modifications.

### Scenario A — Happy Path (all users pass)

```env
TRANSFER_HOLD_THRESHOLD=1000
```

Sandbox Plaid accounts return ~$100 available balance. $100 < $1,000 so Policy 3 passes for all users. All 10 users complete the full workflow and pass compliance.

**Final summary:**
```
Total: 10 users | 10 passed | 0 blocked | 0 errors
```

---

### Scenario B — Policy Enforcement (all users blocked)

```env
TRANSFER_HOLD_THRESHOLD=50
```

$100 balance > $50 threshold triggers a Policy 3 violation for every user. All 10 are blocked at the compliance step.

**Final summary:**
```
Total: 10 users | 0 passed | 10 blocked | 0 errors
```

> Delete `run_state.json` between scenario switches to ensure a clean run.

---

### Scenario C — Resilience Demo (crash and resume)

1. Run `python main.py` with Scenario A settings
2. Press `Ctrl+C` after 4–5 users complete
3. Open `run_state.json` — the completed users are already saved with timestamps
4. Run `python main.py` again — it resumes from where it stopped
5. After completion, run `swytchcode audit` to show the full execution trace

---

## Expected Output

```
Fintech Compliance — Multi-User LangGraph Demo
   Plaid -> Persona KYC -> Dwolla -> Policy Enforcement
   10 users | 3 retries per API call | Threshold: $1,000
============================================================

============================================================
USER 1/10: Alice Johnson (alice.johnson@fintech-demo.com)
============================================================

  --------------------------------------------------------
  STEP 1: Plaid — bank account linking
  --------------------------------------------------------
    [1a] Creating Plaid sandbox public token...
    public_token obtained
    [1b] Exchanging public token for access token...
    access_token obtained
    [1c] Fetching account details...
    Account: checking | Balance: $100.00

  STEP 2: Persona KYC — identity verification
  --------------------------------------------------------
    [2a] Creating Persona KYC inquiry...
    Inquiry created: inq_abc123
    [2b] Approving Persona inquiry (sandbox)...
    KYC status: approved

    KYC APPROVED -> proceeding to Dwolla

  STEP 3: Dwolla — customer + funding source
  --------------------------------------------------------
    [3a] Fetching Dwolla OAuth token...
    Dwolla token obtained
    [3b] Creating Dwolla customer...
    [3c] Retrieving customer ID...
    Customer ID: cus_xyz789
    [3d] Creating Dwolla funding source...
    Funding source: created

  STEP 4: Policy enforcement
  --------------------------------------------------------
    Policy 1 PASSED: KYC approved
    Policy 2 PASSED: Account type 'checking' is supported
    Policy 3 PASSED: Balance $100.00 within threshold

    ALL POLICIES PASSED — Transfer may proceed

... (repeated for users 2-10)

============================================================
COMPLIANCE RUN SUMMARY
============================================================
  USER                   KYC          DWOLLA     POLICY
  --------------------------------------------------------
  Alice Johnson          approved     cus_xy...  PASSED
  Bob Martinez           approved     cus_ab...  PASSED
  Carol Williams         approved     cus_cd...  PASSED
  David Chen             approved     cus_ef...  PASSED
  Emma Davis             approved     cus_gh...  PASSED
  Frank Thompson         approved     cus_ij...  PASSED
  Grace Lee              approved     cus_kl...  PASSED
  Henry Wilson           approved     cus_mn...  PASSED
  Isabella Moore         approved     cus_op...  PASSED
  James Taylor           approved     cus_qr...  PASSED
  --------------------------------------------------------
  Total: 10 users | 10 passed | 0 blocked | 0 errors
============================================================

  Run `swytchcode audit` to see the full execution log.
  Delete run_state.json to reset and start a fresh run.
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SWYTCHCODE_TOKEN` | Yes | Your swytchcode API token |
| `PLAID_CLIENT_ID` | Yes | Plaid sandbox client ID |
| `PLAID_SECRET` | Yes | Plaid sandbox secret key |
| `PLAID_VERSION` | optional | Plaid API version (default: `2020-09-14`) |
| `PERSONA_API_KEY` | Yes | Persona sandbox API key |
| `PERSONA_TEMPLATE_ID` | Yes | Persona KYC inquiry template ID |
| `DWOLLA_APP_KEY` | Yes | Dwolla sandbox application key |
| `DWOLLA_APP_SECRET` | Yes | Dwolla sandbox application secret |
| `TRANSFER_HOLD_THRESHOLD` | optional | Balance threshold in USD (default: `1000.0`) |

---

## Project Structure

```
fintech-compliance-multiuser-demo/
|
|-- main.py                          # Main demo script
|-- requirements.txt                 # Python dependencies
|-- .env.example                     # Environment variable template
|-- .gitignore                       # Excludes .env, run_state.json, __pycache__
|-- README.md                        # This file
|
|-- run_state.json                   # Auto-generated — tracks completed users
|                                    # (git-ignored, delete to reset)
|
+-- .swytchcode/
    |-- tooling.json                 # Declares 3 integrations for swytchcode bootstrap
    +-- integrations/
        |-- plaid/plaid/             # Plaid API integration (wrekenfile + methods)
        |-- persona/persona/         # Persona API integration
        +-- dwolla/dwolla_api/       # Dwolla API integration
```

---

## Swytchcode Canonical IDs Used

Every `swytchcode_exec` call maps to a canonical ID — a stable, versioned identifier for an API operation.

| Service | Canonical ID | Operation |
|---|---|---|
| Plaid | `sandbox.public_token.create` | Create sandbox bank token |
| Plaid | `item.public_token.exchange.create` | Exchange for access token |
| Plaid | `accounts.get.create` | Fetch account details |
| Persona | `inquiries.inquiry.create` | Create KYC inquiry |
| Persona | `inquiries.approve.create` | Approve inquiry (sandbox) |
| Persona | `inquiries.inquiry.get` | Fetch inquiry status |
| Dwolla | `customers.customer.create` | Register customer |
| Dwolla | `customers.customer.list` | Look up customer by email |
| Dwolla | `customers.funding-source.create` | Attach bank account |

9 canonical IDs x 10 users = **90 swytchcode executions per full run.**

---

## Related

- [Fintech Compliance — Single User Demo](https://github.com/swytchcodehq/Fintech-Compliance-Langgraph-Demo) — the original single-user version this demo is built on
- [swytchcode documentation](https://docs.swytchcode.com)
- [LangGraph documentation](https://langchain-ai.github.io/langgraph/)
