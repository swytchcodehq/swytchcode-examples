"""
Fintech Compliance — Multi-User LangGraph Demo
===============================================
Runs the 4-step compliance workflow for 10 demo users with:
  - Retry logic: 3 attempts with delay on every API call
  - Idempotency: unique email per user (no duplicate Dwolla customers)
  - Resumable workflow: run_state.json tracks completed users across runs
  - Per-user result tracking
  - Final compliance summary table

Workflow per user: Plaid -> Persona KYC -> Dwolla (conditional) -> Policy enforcement

Resumability:
  If the script is interrupted mid-run (Ctrl+C, crash, network failure),
  re-running it will skip already-completed users and resume from where it stopped.
  Delete run_state.json to start a completely fresh run.
"""

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from swytchcode_runtime import exec as swytchcode_exec
from typing_extensions import TypedDict

load_dotenv()

# ---------------------------------------------------------------------------
# Policy thresholds — adjust via .env to demo different enforcement outcomes
# ---------------------------------------------------------------------------
TRANSFER_HOLD_THRESHOLD = float(os.environ.get("TRANSFER_HOLD_THRESHOLD", "1000.0"))
SUPPORTED_ACCOUNT_TYPES = {"checking", "savings"}

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries

# ---------------------------------------------------------------------------
# 10 Demo users — unique emails guarantee idempotency across retries
# ---------------------------------------------------------------------------
DEMO_USERS = [
    {"name": "Alice Johnson",   "email": "alice.johnson@fintech-demo.com"},
    {"name": "Bob Martinez",    "email": "bob.martinez@fintech-demo.com"},
    {"name": "Carol Williams",  "email": "carol.williams@fintech-demo.com"},
    {"name": "David Chen",      "email": "david.chen@fintech-demo.com"},
    {"name": "Emma Davis",      "email": "emma.davis@fintech-demo.com"},
    {"name": "Frank Thompson",  "email": "frank.thompson@fintech-demo.com"},
    {"name": "Grace Lee",       "email": "grace.lee@fintech-demo.com"},
    {"name": "Henry Wilson",    "email": "henry.wilson@fintech-demo.com"},
    {"name": "Isabella Moore",  "email": "isabella.moore@fintech-demo.com"},
    {"name": "James Taylor",    "email": "james.taylor@fintech-demo.com"},
]


# ---------------------------------------------------------------------------
# Run state — persists completed users to disk for resumability
# ---------------------------------------------------------------------------
STATE_FILE = "run_state.json"


def load_run_state() -> dict:
    """Load existing run state from disk, or return a fresh state."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            completed_count = len(state.get("completed", {}))
            if completed_count > 0:
                print(f"\n⚡ Resuming from previous run (run_id: {state.get('run_id')})")
                print(f"   {completed_count} user(s) already completed — skipping them.")
            return state
        except Exception:
            pass
    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completed": {},
    }


def save_user_result(run_state: dict, email: str, result: dict) -> None:
    """Persist a single user's result to run_state.json immediately after completion."""
    run_state["completed"][email] = {
        "name":          result["name"],
        "kyc":           result["kyc"],
        "dwolla":        result["dwolla"],
        "policy_passed": result["policy"],
        "violations":    result["violations"],
        "error":         result["error"],
        "completed_at":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(STATE_FILE, "w") as f:
        json.dump(run_state, f, indent=2)


# ---------------------------------------------------------------------------
# Retry wrapper — wraps every swytchcode_exec call
# ---------------------------------------------------------------------------
def exec_with_retry(canonical_id: str, params: dict, label: str) -> dict:
    """
    Execute a swytchcode_exec call with up to MAX_RETRIES attempts.
    If all attempts fail, returns the last error result.
    """
    last_result: dict = {}
    for attempt in range(1, MAX_RETRIES + 1):
        result = swytchcode_exec(canonical_id, params) or {"error": f"{label}: no response from swytchcode_exec"}
        if not result.get("error"):
            return result
        if attempt < MAX_RETRIES:
            print(f"    ⚠️  [{label}] Attempt {attempt}/{MAX_RETRIES} failed — retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
        else:
            print(f"    ❌ [{label}] All {MAX_RETRIES} attempts failed")
        last_result = result
    return last_result


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------
class ComplianceState(TypedDict):
    # User
    user_name: str
    user_email: str

    # Plaid
    plaid_public_token: Optional[str]
    plaid_access_token: Optional[str]
    plaid_account_id: Optional[str]
    plaid_account_type: Optional[str]
    plaid_account_subtype: Optional[str]
    plaid_available_balance: Optional[float]

    # Persona
    persona_inquiry_id: Optional[str]
    persona_status: Optional[str]

    # Dwolla
    dwolla_token: Optional[str]
    dwolla_customer_id: Optional[str]
    dwolla_funding_source_id: Optional[str]
    skipped_dwolla: bool

    # Policy
    policy_violations: list
    policy_passed: bool

    # Workflow control
    error: Optional[str]


# ---------------------------------------------------------------------------
# Helper: Dwolla Basic auth header
# ---------------------------------------------------------------------------
def _dwolla_basic_auth() -> str:
    raw = f"{os.environ['DWOLLA_APP_KEY']}:{os.environ['DWOLLA_APP_SECRET']}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


# ---------------------------------------------------------------------------
# Persona helpers — resilient ID and status extraction
# ---------------------------------------------------------------------------
def _extract_persona_id(res) -> Optional[str]:
    if not res:
        return None
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass
    if not isinstance(res, dict):
        return None
    data_field = res.get("data")
    if isinstance(data_field, str):
        try:
            data_field = json.loads(data_field)
        except Exception:
            pass

    def _fetch(d: dict) -> Optional[str]:
        val = d.get("data", {})
        if isinstance(val, dict):
            if isinstance(val.get("data"), dict):
                val_id = val["data"].get("id")
                if val_id:
                    return val_id
            val_id = val.get("id")
            if val_id:
                return val_id
        if d.get("id"):
            return d["id"]
        for k in ["data", "attributes"]:
            sub = d.get(k)
            if isinstance(sub, dict) and sub.get("type") == "inquiry" and sub.get("id"):
                return sub["id"]
        return None

    inq_id = _fetch(res)
    if inq_id:
        return inq_id
    if isinstance(data_field, dict):
        return _fetch(data_field)
    return None


def _extract_persona_status(res) -> Optional[str]:
    if not res:
        return None
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass
    if not isinstance(res, dict):
        return None
    data_field = res.get("data")
    if isinstance(data_field, str):
        try:
            data_field = json.loads(data_field)
        except Exception:
            pass

    def _fetch(d: dict) -> Optional[str]:
        val = d.get("data", {})
        if isinstance(val, dict):
            sub_data = val.get("data", {})
            if isinstance(sub_data, dict):
                attribs = sub_data.get("attributes", {})
                if isinstance(attribs, dict) and attribs.get("status"):
                    return attribs["status"]
            attribs = val.get("attributes", {})
            if isinstance(attribs, dict) and attribs.get("status"):
                return attribs["status"]
        attribs = d.get("attributes", {})
        if isinstance(attribs, dict) and attribs.get("status"):
            return attribs["status"]
        return None

    status = _fetch(res)
    if status:
        return status
    if isinstance(data_field, dict):
        return _fetch(data_field)
    return None


# ---------------------------------------------------------------------------
# Node 1: Plaid — bank account linking (with retry)
# ---------------------------------------------------------------------------
def step_plaid(state: ComplianceState) -> ComplianceState:
    print("\n  " + "-" * 56)
    print("  STEP 1: Plaid — bank account linking")
    print("  " + "-" * 56)

    plaid_creds = {
        "plaid-client-id": os.environ["PLAID_CLIENT_ID"],
        "plaid-secret":    os.environ["PLAID_SECRET"],
        "plaid-version":   os.environ.get("PLAID_VERSION", "2020-09-14"),
    }

    # 1a. Create sandbox public token
    print("    [1a] Creating Plaid sandbox public token...")
    pub_result = exec_with_retry(
        "sandbox.public_token.create",
        {**plaid_creds, "body": {"institution_id": "ins_109508", "initial_products": ["auth", "transactions"]}},
        "plaid:public_token",
    )
    if pub_result.get("error"):
        return {**state, "error": f"Plaid sandbox token error: {pub_result['error']}"}

    public_token = pub_result.get("public_token") or (pub_result.get("data") or {}).get("public_token")
    if not public_token:
        return {**state, "error": "Plaid: no public_token in response"}
    print("    ✅ public_token obtained")

    # 1b. Exchange public token for access token
    print("    [1b] Exchanging public token for access token...")
    ex_result = exec_with_retry(
        "item.public_token.exchange.create",
        {**plaid_creds, "body": {"public_token": public_token}},
        "plaid:exchange",
    )
    if ex_result.get("error"):
        return {**state, "error": f"Plaid exchange error: {ex_result['error']}"}

    access_token = ex_result.get("access_token") or (ex_result.get("data") or {}).get("access_token")
    if not access_token:
        return {**state, "error": "Plaid: no access_token in response"}
    print("    ✅ access_token obtained")

    # 1c. Fetch account details
    print("    [1c] Fetching account details...")
    acc_result = exec_with_retry(
        "accounts.get.create",
        {**plaid_creds, "body": {"access_token": access_token}},
        "plaid:accounts",
    )
    if acc_result.get("error"):
        return {**state, "error": f"Plaid accounts error: {acc_result['error']}"}

    accounts = acc_result.get("accounts") or (acc_result.get("data") or {}).get("accounts", [])
    if not accounts:
        return {**state, "error": "Plaid: no accounts returned"}

    chosen = next((a for a in accounts if a.get("type") == "depository"), accounts[0])
    account_subtype = chosen.get("subtype", "unknown")
    available_balance = float((chosen.get("balances") or {}).get("available") or 0.0)
    print(f"    ✅ Account: {account_subtype} | Balance: ${available_balance:,.2f}")

    return {
        **state,
        "plaid_public_token":      public_token,
        "plaid_access_token":      access_token,
        "plaid_account_id":        chosen.get("account_id", ""),
        "plaid_account_type":      chosen.get("type", "unknown"),
        "plaid_account_subtype":   account_subtype,
        "plaid_available_balance": available_balance,
    }


# ---------------------------------------------------------------------------
# Node 2: Persona KYC (with retry)
# ---------------------------------------------------------------------------
def step_persona(state: ComplianceState) -> ComplianceState:
    if state.get("error"):
        return state

    print("\n  STEP 2: Persona KYC — identity verification")
    print("  " + "-" * 56)

    persona_auth    = f"Bearer {os.environ['PERSONA_API_KEY']}"
    persona_version = "2023-01-05"
    name_parts      = state["user_name"].split(" ", 1)
    first_name      = name_parts[0]
    last_name       = name_parts[1] if len(name_parts) > 1 else ""

    # 2a. Create KYC inquiry
    print("    [2a] Creating Persona KYC inquiry...")
    inq_result = exec_with_retry(
        "inquiries.inquiry.create",
        {
            "Authorization":   persona_auth,
            "Persona-Version": persona_version,
            "body": {
                "data": {
                    "type": "inquiry",
                    "attributes": {
                        "inquiry-template-id": os.environ["PERSONA_TEMPLATE_ID"],
                        "name-first":          first_name,
                        "name-last":           last_name,
                        "email-address":       state["user_email"],
                    },
                }
            },
        },
        "persona:create",
    )
    if inq_result.get("error"):
        return {**state, "error": f"Persona inquiry create error: {inq_result['error']}"}

    inquiry_id = _extract_persona_id(inq_result)
    if not inquiry_id:
        return {**state, "error": "Persona: could not extract inquiry_id"}
    print(f"    ✅ Inquiry created: {inquiry_id}")

    # 2b. Approve inquiry (sandbox)
    print("    [2b] Approving Persona inquiry (sandbox)...")
    approve_result = exec_with_retry(
        "inquiries.approve.create",
        {"Authorization": persona_auth, "Persona-Version": persona_version, "inquiry-id": inquiry_id},
        "persona:approve",
    )
    if approve_result.get("error"):
        return {**state, "error": f"Persona approve error: {approve_result['error']}"}

    # 2c. Extract status — re-fetch if not found in approve response
    status_raw = _extract_persona_status(approve_result) or "unknown"
    if status_raw == "unknown":
        print("    [2c] Re-fetching inquiry status...")
        get_result = exec_with_retry(
            "inquiries.inquiry.get",
            {"Authorization": persona_auth, "Persona-Version": persona_version, "inquiry-id": inquiry_id},
            "persona:get",
        )
        if not get_result.get("error"):
            status_raw = _extract_persona_status(get_result) or "unknown"

    print(f"    ✅ KYC status: {status_raw}")
    return {**state, "persona_inquiry_id": inquiry_id, "persona_status": status_raw}


# ---------------------------------------------------------------------------
# Conditional edge: route after KYC
# ---------------------------------------------------------------------------
def route_after_kyc(state: ComplianceState) -> str:
    if state.get("error"):
        return "step_policy"
    status = (state.get("persona_status") or "").lower()
    if status == "approved":
        print("\n    🟢 KYC APPROVED → proceeding to Dwolla")
        return "step_dwolla"
    else:
        print(f"\n    🔴 KYC NOT APPROVED (status={status}) → skipping Dwolla")
        return "step_policy"


# ---------------------------------------------------------------------------
# Node 3: Dwolla — customer + funding source (with retry)
# ---------------------------------------------------------------------------
def step_dwolla(state: ComplianceState) -> ComplianceState:
    if state.get("error"):
        return state

    print("\n  STEP 3: Dwolla — customer + funding source")
    print("  " + "-" * 56)

    name_parts = state["user_name"].split(" ", 1)
    first_name = name_parts[0]
    last_name  = name_parts[1] if len(name_parts) > 1 else "User"
    user_email = state["user_email"]

    # 3a. Dwolla OAuth token (direct requests.post — not via swytchcode_exec)
    print("    [3a] Fetching Dwolla OAuth token...")
    dwolla_token = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tok_resp = requests.post(
                "https://api-sandbox.dwolla.com/token",
                headers={
                    "Content-Type":  "application/x-www-form-urlencoded",
                    "Authorization": _dwolla_basic_auth(),
                },
                data={"grant_type": "client_credentials"},
                timeout=15,
            )
            tok_resp.raise_for_status()
            dwolla_token = tok_resp.json().get("access_token")
            if dwolla_token:
                break
            # Token missing in response — retry
            if attempt < MAX_RETRIES:
                print(f"    ⚠️  [dwolla:token] Attempt {attempt}/{MAX_RETRIES} — no token in response, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"    ⚠️  [dwolla:token] Attempt {attempt}/{MAX_RETRIES} failed — retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                return {**state, "error": f"Dwolla token request failed after {MAX_RETRIES} attempts: {e}"}

    if not dwolla_token:
        return {**state, "error": "Dwolla: could not obtain access_token after all retries"}

    print("    ✅ Dwolla token obtained")
    dwolla_auth = f"Bearer {dwolla_token}"

    # 3b. Create customer (201 VOID response is expected — errors may indicate duplicate)
    print(f"    [3b] Creating Dwolla customer for {user_email}...")
    cust_result = exec_with_retry(
        "customers.customer.create",
        {
            "Authorization": dwolla_auth,
            "Accept":        "application/vnd.dwolla.v1.hal+json",
            "body": {
                "firstName":   first_name,
                "lastName":    last_name,
                "email":       user_email,
                "type":        "personal",
                "address1":    "99 Compliance Lane",
                "city":        "San Francisco",
                "state":       "CA",
                "postalCode":  "94105",
                "dateOfBirth": "1990-01-01",
                "ssn":         "1234",
            },
        },
        "dwolla:customer.create",
    )
    if cust_result.get("error"):
        # VOID 201 response and duplicate customers both appear as errors here — non-fatal
        print(f"    ⚠️  customer.create note (may be VOID or duplicate): {cust_result.get('error')}")

    # 3c. Retrieve customer ID by email — always use list to handle VOID + duplicate cases
    print("    [3c] Retrieving customer ID...")
    list_result = exec_with_retry(
        "customers.customer.list",
        {"Authorization": dwolla_auth, "Accept": "application/vnd.dwolla.v1.hal+json", "search": user_email},
        "dwolla:customer.list",
    )
    if list_result.get("error"):
        return {**state, "error": f"Dwolla customer list error: {list_result['error']}"}

    embedded = (
        (list_result.get("_embedded") or {}).get("customers")
        or ((list_result.get("data") or {}).get("_embedded") or {}).get("customers")
        or []
    )
    if not embedded:
        return {**state, "error": f"Dwolla: no customers found for {user_email}"}

    customer_id = embedded[0].get("id")
    if not customer_id:
        return {**state, "error": "Dwolla: customer record has no id field"}
    print(f"    ✅ Customer ID: {customer_id}")

    # 3d. Create funding source
    print("    [3d] Creating Dwolla funding source...")
    account_subtype = (state.get("plaid_account_subtype") or "checking").lower()
    fs_result = exec_with_retry(
        "customers.funding-source.create",
        {
            "Authorization": dwolla_auth,
            "Accept":        "application/vnd.dwolla.v1.hal+json",
            "id":            customer_id,
            "body": {
                "routingNumber":  "222222226",
                "accountNumber":  "123456789",
                "bankAccountType": account_subtype,
                "name": f"{state['user_name']} - {account_subtype.title()} Account",
            },
        },
        "dwolla:funding-source.create",
    )
    if fs_result.get("error"):
        print(f"    ⚠️  funding-source.create note (may be VOID): {fs_result.get('error')}")

    funding_source_id = fs_result.get("id") or "created-via-location-header"
    print(f"    ✅ Funding source: {funding_source_id}")

    return {
        **state,
        "dwolla_token":             dwolla_token,
        "dwolla_customer_id":       customer_id,
        "dwolla_funding_source_id": funding_source_id,
        "skipped_dwolla":           False,
    }


# ---------------------------------------------------------------------------
# Node 4: Policy enforcement
# ---------------------------------------------------------------------------
def step_policy(state: ComplianceState) -> ComplianceState:
    print("\n  STEP 4: Policy enforcement")
    print("  " + "-" * 56)

    violations = []

    # Policy 1: KYC must be approved
    kyc_status = (state.get("persona_status") or "unknown").lower()
    if kyc_status != "approved":
        msg = f"Transfer blocked — KYC status is '{kyc_status}', must be 'approved'"
        violations.append(msg)
        print(f"    🚫 Policy 1 FAILED: {msg}")
    else:
        print("    ✅ Policy 1 PASSED: KYC approved")

    # Policy 2: Account type must be checking or savings
    account_subtype = (state.get("plaid_account_subtype") or "unknown").lower()
    if account_subtype not in SUPPORTED_ACCOUNT_TYPES:
        msg = f"Account type '{account_subtype}' not supported (allowed: {sorted(SUPPORTED_ACCOUNT_TYPES)})"
        violations.append(msg)
        print(f"    🚫 Policy 2 FAILED: {msg}")
    else:
        print(f"    ✅ Policy 2 PASSED: Account type '{account_subtype}' is supported")

    # Policy 3: Balance must not exceed threshold
    balance = float(state.get("plaid_available_balance") or 0.0)
    if balance > TRANSFER_HOLD_THRESHOLD:
        msg = f"Transaction hold — balance ${balance:,.2f} exceeds threshold ${TRANSFER_HOLD_THRESHOLD:,.2f}"
        violations.append(msg)
        print(f"    🚫 Policy 3 FAILED: {msg}")
    else:
        print(f"    ✅ Policy 3 PASSED: Balance ${balance:,.2f} within threshold")

    policy_passed = len(violations) == 0
    if policy_passed:
        print("\n    🟢 ALL POLICIES PASSED — Transfer may proceed")
    else:
        print(f"\n    🔴 {len(violations)} POLICY VIOLATION(S) — Transfer BLOCKED")

    return {**state, "policy_violations": violations, "policy_passed": policy_passed}


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------
def build_graph():
    graph = StateGraph(ComplianceState)
    graph.add_node("step_plaid",   step_plaid)
    graph.add_node("step_persona", step_persona)
    graph.add_node("step_dwolla",  step_dwolla)
    graph.add_node("step_policy",  step_policy)

    graph.set_entry_point("step_plaid")
    graph.add_edge("step_plaid", "step_persona")
    graph.add_conditional_edges(
        "step_persona",
        route_after_kyc,
        {"step_dwolla": "step_dwolla", "step_policy": "step_policy"},
    )
    graph.add_edge("step_dwolla", "step_policy")
    graph.add_edge("step_policy", END)
    return graph.compile()


# ---------------------------------------------------------------------------
# Run compliance workflow for a single user
# ---------------------------------------------------------------------------
def run_user_compliance(app, user: dict) -> dict:
    initial_state: ComplianceState = {
        "user_name":               user["name"],
        "user_email":              user["email"],
        "plaid_public_token":      None,
        "plaid_access_token":      None,
        "plaid_account_id":        None,
        "plaid_account_type":      None,
        "plaid_account_subtype":   None,
        "plaid_available_balance": None,
        "persona_inquiry_id":      None,
        "persona_status":          None,
        "dwolla_token":            None,
        "dwolla_customer_id":      None,
        "dwolla_funding_source_id": None,
        "skipped_dwolla":          True,
        "policy_violations":       [],
        "policy_passed":           False,
        "error":                   None,
    }
    return app.invoke(initial_state)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("\n🏦 Fintech Compliance — Multi-User LangGraph Demo")
    print("   Plaid → Persona KYC → Dwolla → Policy Enforcement")
    print(f"   {len(DEMO_USERS)} users | {MAX_RETRIES} retries per API call | Threshold: ${TRANSFER_HOLD_THRESHOLD:,.0f}")
    print("=" * 60)

    # Validate required environment variables before doing any work
    required = [
        "PLAID_CLIENT_ID", "PLAID_SECRET",
        "PERSONA_API_KEY", "PERSONA_TEMPLATE_ID",
        "DWOLLA_APP_KEY",  "DWOLLA_APP_SECRET",
        "SWYTCHCODE_TOKEN",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"\n❌ Missing required environment variables: {missing}")
        print("   Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    app = build_graph()
    run_state = load_run_state()

    # Process all users in DEMO_USERS order — completed ones are skipped, not reordered
    results = []
    for i, user in enumerate(DEMO_USERS, 1):
        print(f"\n{'=' * 60}")
        print(f"USER {i}/{len(DEMO_USERS)}: {user['name']} ({user['email']})")
        print("=" * 60)

        # Resume: skip users already completed in a previous run
        if user["email"] in run_state["completed"]:
            saved = run_state["completed"][user["email"]]
            print(f"   ⏭️  SKIPPED — completed at {saved.get('completed_at', 'unknown')}")
            results.append({
                "name":       saved["name"],
                "email":      user["email"],
                "kyc":        saved["kyc"],
                "dwolla":     saved["dwolla"],
                "policy":     saved["policy_passed"],
                "violations": saved["violations"],
                "error":      saved["error"],
            })
            continue

        # Run compliance workflow for this user
        final_state = run_user_compliance(app, user)
        result = {
            "name":       user["name"],
            "email":      user["email"],
            "kyc":        final_state.get("persona_status") or "error",
            "dwolla":     final_state.get("dwolla_customer_id") or "SKIPPED",
            "policy":     final_state.get("policy_passed", False),
            "violations": final_state.get("policy_violations", []),
            "error":      final_state.get("error"),
        }
        results.append(result)

        # Save immediately — protects this user's result if the next one crashes
        save_user_result(run_state, user["email"], result)

    # ---------------------------------------------------------------------------
    # Final compliance summary
    # ---------------------------------------------------------------------------
    print("\n\n" + "=" * 60)
    print("COMPLIANCE RUN SUMMARY")
    print("=" * 60)
    print(f"  {'USER':<22} {'KYC':<12} {'DWOLLA':<14} {'POLICY'}")
    print("  " + "-" * 60)

    passed  = 0
    blocked = 0
    errors  = 0

    for r in results:
        if r["error"]:
            outcome = "❌ ERROR"
            errors += 1
        elif r["policy"]:
            outcome  = "✅ PASSED"
            passed  += 1
        else:
            outcome  = "🚫 BLOCKED"
            blocked += 1

        # Dwolla UUIDs are 36 chars — truncate to 8+... = 11 chars, fits in 14-wide column
        dwolla_val = r["dwolla"]
        dwolla_short = (dwolla_val[:8] + "...") if len(dwolla_val) > 11 else dwolla_val
        print(f"  {r['name']:<22} {r['kyc']:<12} {dwolla_short:<14} {outcome}")

    print("  " + "-" * 60)
    print(f"  Total: {len(results)} users | ✅ {passed} passed | 🚫 {blocked} blocked | ❌ {errors} errors")
    print("=" * 60)
    print()
    print("  Run `swytchcode audit` to see the full execution log.")
    print("  Delete run_state.json to reset and start a fresh run.")
    print()


if __name__ == "__main__":
    main()
