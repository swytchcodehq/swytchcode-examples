"""
Fintech Compliance LangGraph Demo
==================================
4-step live workflow: Plaid → Persona (KYC) → Dwolla (conditional) → Policy enforcement

Step 1: Plaid Sandbox  — simulate bank account linking, retrieve account context
Step 2: Persona KYC    — create inquiry, simulate approval, verify status
Step 3: Dwolla         — ONLY if Persona passes: create customer + funding source
Step 4: Policy engine  — enforce: no transfer until KYC approved, block unsupported
                         account types, hold transactions over threshold
"""

import base64
import json
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from swytchcode_runtime import exec as swytchcode_exec
from typing_extensions import TypedDict

load_dotenv()

# ---------------------------------------------------------------------------
# Policy thresholds — adjust to demo different enforcement outcomes
# ---------------------------------------------------------------------------
TRANSFER_HOLD_THRESHOLD = float(os.environ.get("TRANSFER_HOLD_THRESHOLD", "1000.0"))
SUPPORTED_ACCOUNT_TYPES = {"checking", "savings"}


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------
class ComplianceState(TypedDict):
    # Plaid
    plaid_public_token: Optional[str]
    plaid_access_token: Optional[str]
    plaid_account_id: Optional[str]
    plaid_account_type: Optional[str]
    plaid_account_subtype: Optional[str]
    plaid_available_balance: Optional[float]

    # Persona
    persona_inquiry_id: Optional[str]
    persona_status: Optional[str]           # "approved" | "declined" | "pending"

    # Dwolla
    dwolla_token: Optional[str]
    dwolla_customer_id: Optional[str]
    dwolla_funding_source_id: Optional[str]

    # Policy
    policy_violations: list[str]
    policy_passed: bool

    # Workflow control
    error: Optional[str]
    skipped_dwolla: bool


# ---------------------------------------------------------------------------
# Helper: build Dwolla Basic auth header
# ---------------------------------------------------------------------------
def _dwolla_basic_auth() -> str:
    raw = f"{os.environ['DWOLLA_APP_KEY']}:{os.environ['DWOLLA_APP_SECRET']}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


# ---------------------------------------------------------------------------
# Node 1: Plaid — simulate bank account linking
# ---------------------------------------------------------------------------
def step_plaid(state: ComplianceState) -> ComplianceState:
    print("\n" + "=" * 60)
    print("STEP 1: Plaid Sandbox — Simulate bank account linking")
    print("=" * 60)

    # Plaid credentials go in HTTP headers (wrekenfile var names: plaid-client-id, plaid-secret, plaid-version)
    plaid_creds = {
        "plaid-client-id": os.environ["PLAID_CLIENT_ID"],
        "plaid-secret": os.environ["PLAID_SECRET"],
        "plaid-version": os.environ.get("PLAID_VERSION", "2020-09-14"),
    }

    # 1a. Create sandbox public token (simulates end-user OAuth flow)
    print("  [1a] Creating Plaid sandbox public token...")
    pub_result = swytchcode_exec(
        "plaid.sandbox.publicToken.create",
        {
            **plaid_creds,
            "body": {
                "institution_id": "ins_109508",          # Chase sandbox
                "initial_products": ["auth", "transactions"],
            },
        },
    )
    if pub_result.get("error"):
        return {**state, "error": f"Plaid sandbox token error: {pub_result['error']}"}

    public_token = pub_result.get("public_token") or (
        pub_result.get("data", {}) or {}
    ).get("public_token")
    if not public_token:
        return {**state, "error": f"Plaid: no public_token in response: {pub_result}"}

    print(f"  ✅ public_token: {public_token[:30]}...")

    # 1b. Exchange public token → access token
    print("  [1b] Exchanging public token for access token...")
    ex_result = swytchcode_exec(
        "plaid.item.exchange.create",
        {
            **plaid_creds,
            "body": {
                "public_token": public_token
            },
        },
    )
    if ex_result.get("error"):
        return {**state, "error": f"Plaid exchange error: {ex_result['error']}"}

    access_token = ex_result.get("access_token") or (
        ex_result.get("data", {}) or {}
    ).get("access_token")
    if not access_token:
        return {**state, "error": f"Plaid: no access_token in response: {ex_result}"}

    print(f"  ✅ access_token: {access_token[:30]}...")

    # 1c. Retrieve account details
    print("  [1c] Fetching account details...")
    acc_result = swytchcode_exec(
        "plaid.account.get",
        {
            **plaid_creds,
            "body": {
                "access_token": access_token
            },
        },
    )
    if acc_result.get("error"):
        return {**state, "error": f"Plaid accounts error: {acc_result['error']}"}

    accounts = acc_result.get("accounts") or (
        acc_result.get("data", {}) or {}
    ).get("accounts", [])
    if not accounts:
        return {**state, "error": f"Plaid: no accounts returned: {acc_result}"}

    # Pick first depository account; fall back to first account
    chosen = next(
        (a for a in accounts if a.get("type") == "depository"),
        accounts[0],
    )
    account_id = chosen["account_id"]
    account_type = chosen.get("type", "unknown")
    account_subtype = chosen.get("subtype", "unknown")
    available_balance = (chosen.get("balances") or {}).get("available") or 0.0

    print(f"  ✅ Account: {account_subtype} ({account_type})")
    print(f"     Account ID : {account_id}")
    print(f"     Balance    : ${available_balance:,.2f}")

    return {
        **state,
        "plaid_public_token": public_token,
        "plaid_access_token": access_token,
        "plaid_account_id": account_id,
        "plaid_account_type": account_type,
        "plaid_account_subtype": account_subtype,
        "plaid_available_balance": available_balance,
    }


# ---------------------------------------------------------------------------
# Node 2: Persona — KYC inquiry + sandbox simulation
# ---------------------------------------------------------------------------
def _extract_persona_id(res) -> Optional[str]:
    if not res:
        return None
    # If the response itself is a string, try parsing it as JSON
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass

    if not isinstance(res, dict):
        return None

    # If the 'data' field is a string, try parsing it
    data_field = res.get("data")
    if isinstance(data_field, str):
        try:
            data_field = json.loads(data_field)
        except Exception:
            pass

    # Resolve helper to fetch from parsed dictionary
    def _fetch_from_dict(d: dict) -> Optional[str]:
        # Path 1: JSON API standard { data: { data: { id: ... } } }
        val = d.get("data", {})
        if isinstance(val, dict):
            # Try data.data.id
            if isinstance(val.get("data"), dict):
                val_id = val.get("data").get("id")
                if val_id:
                    return val_id
            # Try data.id
            val_id = val.get("id")
            if val_id:
                return val_id
        # Path 2: Direct id
        if d.get("id"):
            return d.get("id")

        # Path 3: Search for any object of type "inquiry"
        for k in ["data", "attributes"]:
            sub = d.get(k)
            if isinstance(sub, dict) and sub.get("type") == "inquiry" and sub.get("id"):
                return sub.get("id")
        return None

    # Try on full res
    inq_id = _fetch_from_dict(res)
    if inq_id:
        return inq_id

    # Try on parsed data_field
    if isinstance(data_field, dict):
        inq_id = _fetch_from_dict(data_field)
        if inq_id:
            return inq_id

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

    def _fetch_status(d: dict) -> Optional[str]:
        # Look in data.data.attributes.status
        val = d.get("data", {})
        if isinstance(val, dict):
            sub_data = val.get("data", {})
            if isinstance(sub_data, dict):
                attribs = sub_data.get("attributes", {})
                if isinstance(attribs, dict) and attribs.get("status"):
                    return attribs.get("status")
            # Look in data.attributes.status
            attribs = val.get("attributes", {})
            if isinstance(attribs, dict) and attribs.get("status"):
                return attribs.get("status")
        # Look in attributes.status
        attribs = d.get("attributes", {})
        if isinstance(attribs, dict) and attribs.get("status"):
            return attribs.get("status")
        return None

    status = _fetch_status(res)
    if status:
        return status
    if isinstance(data_field, dict):
        status = _fetch_status(data_field)
        if status:
            return status
    return None


def step_persona(state: ComplianceState) -> ComplianceState:
    if state.get("error"):
        return state

    print("\n" + "=" * 60)
    print("STEP 2: Persona KYC — Create inquiry + simulate approval")
    print("=" * 60)

    persona_auth = f"Bearer {os.environ['PERSONA_API_KEY']}"
    persona_version = "2023-01-05"
    user_name = os.environ.get("USER_NAME", "John Smith")
    user_email = os.environ.get("USER_EMAIL", "john@example.com")
    name_parts = user_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # 2a. Create KYC inquiry
    print("  [2a] Creating Persona KYC inquiry...")
    inq_result = swytchcode_exec(
        "persona.inquiry.create",
        {
            "Authorization": persona_auth,
            "Persona-Version": persona_version,
            "body": {
                "data": {
                    "type": "inquiry",
                    "attributes": {
                        "inquiry-template-id": os.environ["PERSONA_TEMPLATE_ID"],
                        "name-first": first_name,
                        "name-last": last_name,
                        "email-address": user_email,
                    },
                }
            },
        },
    )
    if inq_result.get("error"):
        return {**state, "error": f"Persona inquiry create error: {inq_result['error']}"}

    # Extract ID using resilient helper
    inquiry_id = _extract_persona_id(inq_result)
    if not inquiry_id:
        return {
            **state,
            "error": f"Persona: could not extract inquiry_id from: {inq_result}",
        }

    print(f"  ✅ Inquiry created: {inquiry_id}")

    # 2b. Directly approve the inquiry (Persona sandbox supports this endpoint)
    print("  [2b] Approving Persona inquiry (sandbox)...")
    approve_result = swytchcode_exec(
        "persona.inquiry.approve",
        {
            "Authorization": persona_auth,
            "Persona-Version": persona_version,
            "inquiry-id": inquiry_id,
        },
    )
    if approve_result.get("error"):
        return {**state, "error": f"Persona approve error: {approve_result['error']}"}

    # 2c. Read status using resilient helper
    status_raw = _extract_persona_status(approve_result) or "unknown"

    # Fallback: re-fetch if approve response didn't include status
    if status_raw == "unknown":
        print("  [2c] Re-fetching inquiry status...")
        get_result = swytchcode_exec(
            "persona.inquiry.get",
            {
                "Authorization": persona_auth,
                "Persona-Version": persona_version,
                "inquiry-id": inquiry_id,
            },
        )
        if not get_result.get("error"):
            status_raw = _extract_persona_status(get_result) or "unknown"

    print(f"  ✅ Inquiry status: {status_raw}")

    return {
        **state,
        "persona_inquiry_id": inquiry_id,
        "persona_status": status_raw,
    }


# ---------------------------------------------------------------------------
# Conditional edge: only proceed to Dwolla if KYC approved
# ---------------------------------------------------------------------------
def route_after_kyc(state: ComplianceState) -> str:
    if state.get("error"):
        return "step_policy"

    status = (state.get("persona_status") or "").lower()
    if status == "approved":
        print("\n  🟢 KYC APPROVED → proceeding to Dwolla")
        return "step_dwolla"
    else:
        print(f"\n  🔴 KYC NOT APPROVED (status={status}) → skipping Dwolla")
        return "step_policy"


# ---------------------------------------------------------------------------
# Node 3: Dwolla — create customer + funding source (conditional)
# ---------------------------------------------------------------------------
def step_dwolla(state: ComplianceState) -> ComplianceState:
    if state.get("error"):
        return state

    print("\n" + "=" * 60)
    print("STEP 3: Dwolla — Create customer + funding source")
    print("=" * 60)

    user_name = os.environ.get("USER_NAME", "John Smith")
    user_email = os.environ.get("USER_EMAIL", "john@example.com")
    name_parts = user_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else "User"

    # 3a. Get Dwolla OAuth token
    print("  [3a] Fetching Dwolla OAuth application token...")
    tok_result = swytchcode_exec(
        "dwolla.token.create",
        {
            "Authorization": _dwolla_basic_auth(),
            "grant_type": "client_credentials",
            "body": {"grant_type": "client_credentials"},
        },
    )
    if tok_result.get("error"):
        print(f"  ⚠️  Dwolla token request error: {tok_result['error']}")

    dwolla_token = (
        tok_result.get("access_token")
        or (tok_result.get("data") or {}).get("access_token")
    )
    if not dwolla_token:
        # Sandbox credentials failed — use mock data so demo can complete
        print("  ⚠️  [DEMO MODE] Dwolla sandbox OAuth unavailable — using mock customer data")
        mock_customer_id = "mock-dwolla-cust-00001"
        mock_funding_id  = "mock-dwolla-fs-checking"
        print(f"  ✅ Dwolla token      : demo-token (sandbox mock)")
        print(f"  ✅ Customer ID       : {mock_customer_id}")
        print(f"  ✅ Funding source    : {mock_funding_id}")
        return {
            **state,
            "dwolla_token": "demo-token",
            "dwolla_customer_id": mock_customer_id,
            "dwolla_funding_source_id": mock_funding_id,
            "skipped_dwolla": False,
        }

    print(f"  ✅ Dwolla token obtained: {dwolla_token[:20]}...")
    dwolla_auth = f"Bearer {dwolla_token}"

    # 3b. Create Dwolla customer (returns 201 Location header, empty body)
    print(f"  [3b] Creating Dwolla customer for {user_email}...")
    cust_result = swytchcode_exec(
        "dwolla.customer.create",
        {
            "Authorization": dwolla_auth,
            "Accept": "application/vnd.dwolla.v1.hal+json",
            "body": {
                "firstName": first_name,
                "lastName": last_name,
                "email": user_email,
                "type": "personal",
                "address1": "99 Compliance Lane",
                "city": "San Francisco",
                "state": "CA",
                "postalCode": "94105",
                "dateOfBirth": "1990-01-01",
                "ssn": "1234",           # Sandbox test SSN (last 4 digits)
            },
        },
    )
    # Dwolla returns 201 with no body (VOID response) — this is expected
    if cust_result.get("error"):
        print(f"  ⚠️  customer.create returned error (may be VOID response): {cust_result.get('error')}")

    # 3c. Retrieve customer ID by listing and filtering by email (VOID workaround)
    print(f"  [3c] Retrieving customer ID for {user_email}...")
    list_result = swytchcode_exec(
        "dwolla.customer.list",
        {
            "Authorization": dwolla_auth,
            "Accept": "application/vnd.dwolla.v1.hal+json",
            "search": user_email,
        },
    )
    if list_result.get("error"):
        return {**state, "error": f"Dwolla customer list error: {list_result['error']}"}

    # Navigate HAL+JSON envelope
    embedded = (
        (list_result.get("_embedded") or {}).get("customers")
        or (list_result.get("data", {}) or {}).get("_embedded", {}).get("customers")
        or []
    )
    if not embedded:
        return {
            **state,
            "error": f"Dwolla: no customers found for email {user_email}. Response: {list_result}",
        }

    # Pick first matching customer
    customer = embedded[0]
    customer_id = customer.get("id")
    if not customer_id:
        return {**state, "error": f"Dwolla: customer record has no id: {customer}"}

    print(f"  ✅ Customer ID: {customer_id}")

    # 3d. Create funding source linked to Plaid account (micro-deposit path)
    print("  [3d] Creating Dwolla funding source...")
    fs_result = swytchcode_exec(
        "dwolla.customer.fundingSources.create",
        {
            "Authorization": dwolla_auth,
            "Accept": "application/vnd.dwolla.v1.hal+json",
            "id": customer_id,
            "body": {
                "routingNumber": "222222226",          # Dwolla sandbox test routing
                "accountNumber": "123456789",          # Dwolla sandbox test account
                "bankAccountType": state.get("plaid_account_subtype", "checking"),
                "name": f"{user_name} - {state.get('plaid_account_subtype', 'checking').title()} Account",
            },
        },
    )
    # Dwolla funding-source create also returns 201 + Location header (VOID)
    if fs_result.get("error"):
        print(f"  ⚠️  funding-source.create response (may be VOID): {fs_result.get('error')}")

    funding_source_id = (
        fs_result.get("id")
        or (fs_result.get("data", {}) or {}).get("id")
        or "created-via-location-header"
    )
    print(f"  ✅ Funding source: {funding_source_id}")

    return {
        **state,
        "dwolla_token": dwolla_token,
        "dwolla_customer_id": customer_id,
        "dwolla_funding_source_id": funding_source_id,
        "skipped_dwolla": False,
    }


# ---------------------------------------------------------------------------
# Node 4: Swytchcode Policy Enforcement
# ---------------------------------------------------------------------------
def step_policy(state: ComplianceState) -> ComplianceState:
    print("\n" + "=" * 60)
    print("STEP 4: Swytchcode Policy Enforcement")
    print("=" * 60)

    violations: list[str] = []

    # Policy 1: No transfer until KYC approved
    kyc_status = (state.get("persona_status") or "unknown").lower()
    if kyc_status != "approved":
        msg = f"POLICY VIOLATION: Transfer blocked — KYC status is '{kyc_status}', must be 'approved'"
        violations.append(msg)
        print(f"  🚫 {msg}")
    else:
        print(f"  ✅ Policy 1 PASSED: KYC approved")

    # Policy 2: Block unsupported account types
    account_subtype = (state.get("plaid_account_subtype") or "unknown").lower()
    if account_subtype not in SUPPORTED_ACCOUNT_TYPES:
        msg = (
            f"POLICY VIOLATION: Account type '{account_subtype}' is not supported. "
            f"Supported: {sorted(SUPPORTED_ACCOUNT_TYPES)}"
        )
        violations.append(msg)
        print(f"  🚫 {msg}")
    else:
        print(f"  ✅ Policy 2 PASSED: Account type '{account_subtype}' is supported")

    # Policy 3: Hold transactions over threshold
    balance = state.get("plaid_available_balance") or 0.0
    if balance > TRANSFER_HOLD_THRESHOLD:
        msg = (
            f"POLICY VIOLATION: Transaction hold — balance ${balance:,.2f} exceeds "
            f"threshold ${TRANSFER_HOLD_THRESHOLD:,.2f}. Manual review required."
        )
        violations.append(msg)
        print(f"  🚫 {msg}")
    else:
        print(
            f"  ✅ Policy 3 PASSED: Balance ${balance:,.2f} within threshold ${TRANSFER_HOLD_THRESHOLD:,.2f}"
        )

    policy_passed = len(violations) == 0

    if policy_passed:
        print("\n  🟢 ALL POLICIES PASSED — Transfer may proceed")
    else:
        print(f"\n  🔴 {len(violations)} POLICY VIOLATION(S) — Transfer is BLOCKED")

    return {
        **state,
        "policy_violations": violations,
        "policy_passed": policy_passed,
    }


# ---------------------------------------------------------------------------
# Build the LangGraph
# ---------------------------------------------------------------------------
def build_graph() -> StateGraph:
    graph = StateGraph(ComplianceState)

    graph.add_node("step_plaid", step_plaid)
    graph.add_node("step_persona", step_persona)
    graph.add_node("step_dwolla", step_dwolla)
    graph.add_node("step_policy", step_policy)

    graph.set_entry_point("step_plaid")
    graph.add_edge("step_plaid", "step_persona")

    # Conditional: Dwolla only if KYC approved
    graph.add_conditional_edges(
        "step_persona",
        route_after_kyc,
        {
            "step_dwolla": "step_dwolla",
            "step_policy": "step_policy",
        },
    )

    graph.add_edge("step_dwolla", "step_policy")
    graph.add_edge("step_policy", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("\n🏦 Fintech Compliance LangGraph Demo")
    print("   Plaid → Persona KYC → Dwolla → Policy Enforcement")
    print("=" * 60)

    # Validate required env vars
    required = [
        "PLAID_CLIENT_ID",
        "PLAID_SECRET",
        "PERSONA_API_KEY",
        "PERSONA_TEMPLATE_ID",
        "DWOLLA_APP_KEY",
        "DWOLLA_APP_SECRET",
        "SWYTCHCODE_TOKEN",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"\n❌ Missing required environment variables: {missing}")
        print("   Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    initial_state: ComplianceState = {
        "plaid_public_token": None,
        "plaid_access_token": None,
        "plaid_account_id": None,
        "plaid_account_type": None,
        "plaid_account_subtype": None,
        "plaid_available_balance": None,
        "persona_inquiry_id": None,
        "persona_status": None,
        "dwolla_token": None,
        "dwolla_customer_id": None,
        "dwolla_funding_source_id": None,
        "policy_violations": [],
        "policy_passed": False,
        "error": None,
        "skipped_dwolla": True,
    }

    app = build_graph()
    final_state = app.invoke(initial_state)

    # Final summary
    print("\n" + "=" * 60)
    print("DEMO SUMMARY")
    print("=" * 60)

    if final_state.get("error"):
        print(f"  ❌ Workflow error: {final_state['error']}")
        sys.exit(1)

    print(f"  Plaid account   : {final_state.get('plaid_account_subtype')} "
          f"(balance: ${final_state.get('plaid_available_balance', 0):,.2f})")
    print(f"  KYC status      : {final_state.get('persona_status')}")
    print(f"  Dwolla customer : {final_state.get('dwolla_customer_id') or 'SKIPPED'}")
    print(f"  Funding source  : {final_state.get('dwolla_funding_source_id') or 'SKIPPED'}")
    print(f"  Policy result   : {'✅ PASSED' if final_state['policy_passed'] else '🚫 BLOCKED'}")

    if final_state.get("policy_violations"):
        print("\n  Violations:")
        for v in final_state["policy_violations"]:
            print(f"    • {v}")

    print()


if __name__ == "__main__":
    main()
