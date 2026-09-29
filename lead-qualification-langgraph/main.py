from swytchcode_runtime import exec as swytchcode_exec
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()


class LeadQualificationState(TypedDict):
    lead_name: str
    lead_email: str
    company: str
    phone: Optional[str]
    deal_value: int
    hubspot_contact_id: Optional[str]
    hubspot_deal_id: Optional[str]


# ── Node 1: Create HubSpot contact ───────────────────────────────────────────

def create_hubspot_contact(state: LeadQualificationState) -> dict:
    print(f"[1/2] Creating HubSpot contact for {state['lead_email']}...")
    name_parts = state["lead_name"].split()
    result = swytchcode_exec("hubspot.crm.contacts.create", {
        "body": {
            "properties": {
                "email":          state["lead_email"],
                "firstname":      name_parts[0],
                "lastname":       name_parts[-1] if len(name_parts) > 1 else "",
                "company":        state["company"],
                "phone":          state.get("phone", ""),
                "hs_lead_status": "NEW",
            }
        },
        "Authorization": f"Bearer {os.environ['HUBSPOT_API_KEY']}",
    })
    result = result or {"error": "HubSpot contact create: no response from swytchcode_exec"}
    if result.get("status_code") == 409 and "Existing ID:" in (result.get("data", {}) or {}).get("message", ""):
        msg = result["data"]["message"]
        contact_id = msg.split("Existing ID: ")[1].split()[0]
    elif result.get("status_code") not in (200, 201):
        raise RuntimeError(f"HubSpot contact create failed: {result}")
    else:
        contact_id = (result or {}).get("id") or (result or {}).get("data", {}).get("id")
        
    print(f"    ✔ HubSpot contact created: {contact_id}")
    return {"hubspot_contact_id": contact_id}


# 🛠️ Node 2: Create HubSpot Deal 🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️🛠️

def create_hubspot_deal(state: LeadQualificationState) -> dict:
    print(f"[2/2] Creating HubSpot sales opportunity for {state['company']}...")
    close_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    result = swytchcode_exec("hubspot.crm.deals.create", {
        "body": {
            "properties": {
                "dealname":  f"{state['company']} — Inbound Lead",
                "amount":    str(state["deal_value"]),
                "closedate": close_date,
            },
            "associations": [
                {
                    "to":    {"id": state["hubspot_contact_id"]},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
                }
            ],
        },
        "Authorization": f"Bearer {os.environ['HUBSPOT_API_KEY']}",
    })
    result = result or {"error": "HubSpot deal create: no response from swytchcode_exec"}
    if result.get("status_code") == 409 and "Existing ID:" in (result.get("data", {}) or {}).get("message", ""):
        msg = result["data"]["message"]
        deal_id = msg.split("Existing ID: ")[1].split()[0]
    elif result.get("status_code") not in (200, 201):
        raise RuntimeError(f"HubSpot deal create failed: {result}")
    else:
        deal_id = (result or {}).get("id") or (result or {}).get("data", {}).get("id")
        
    print(f"    ✔ HubSpot deal created: {deal_id}")
    return {"hubspot_deal_id": deal_id}


# ── Build graph ───────────────────────────────────────────────────────────────

workflow = StateGraph(LeadQualificationState)
workflow.add_node("create_contact", create_hubspot_contact)
workflow.add_node("create_deal",    create_hubspot_deal)

workflow.set_entry_point("create_contact")
workflow.add_edge("create_contact", "create_deal")
workflow.add_edge("create_deal",    END)

app = workflow.compile()


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Validate required environment variables before doing any work
    required = ["HUBSPOT_API_KEY", "SWYTCHCODE_TOKEN"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"\n❌ Missing required environment variables: {missing}")
        print("   Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    result = app.invoke({
        "lead_name":          "Alex Johnson",
        "lead_email":         "alex@techcorp.io",
        "company":            "TechCorp",
        "phone":              "+1-415-555-0192",
        "deal_value":         5000,
        "hubspot_contact_id": None,
        "hubspot_deal_id":    None,
    })

    print("\n✅ Lead qualified!")
    print(f"   HubSpot Contact ID: {result['hubspot_contact_id']}")
    print(f"   HubSpot Deal ID:    {result['hubspot_deal_id']}")
