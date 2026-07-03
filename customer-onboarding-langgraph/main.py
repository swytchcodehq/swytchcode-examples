from swytchcode_runtime import exec as swytchcode_exec
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from dotenv import load_dotenv
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()


class OnboardingState(TypedDict):
    customer_name: str
    customer_email: str
    stripe_customer_id: Optional[str]
    hubspot_contact_id: Optional[str]
    email_sent: Optional[bool]


# ── Node 1: Create HubSpot contact ───────────────────────────────────────────

def create_hubspot_contact(state: OnboardingState) -> dict:
    print(f"[1/3] Creating HubSpot contact for {state['customer_email']}...")
    name_parts = state["customer_name"].split()
    result = swytchcode_exec("hubspot.crm.contacts.create", {
        "body": {
            "properties": {
                "email":          state["customer_email"],
                "firstname":      name_parts[0],
                "lastname":       name_parts[-1] if len(name_parts) > 1 else "",
                "hs_lead_status": "NEW",
            }
        },
        "Authorization": f"Bearer {os.environ['HUBSPOT_API_KEY']}",
    })
    if result.get("status_code") == 409 and "Existing ID:" in result.get("data", {}).get("message", ""):
        msg = result["data"]["message"]
        contact_id = msg.split("Existing ID: ")[1].split()[0]
    elif result.get("status_code") not in (200, 201):
        raise RuntimeError(f"HubSpot contact create failed: {result}")
    else:
        contact_id = (result or {}).get("id") or (result or {}).get("data", {}).get("id")
        
    print(f"    ✔ HubSpot contact created: {contact_id}")
    return {"hubspot_contact_id": contact_id}


# ── Node 2: Create Stripe customer ───────────────────────────────────────────

def create_stripe_customer(state: OnboardingState) -> dict:
    print(f"[2/3] Creating Stripe customer for {state['customer_email']}...")
    result = swytchcode_exec("customers.customer.create", {
        "body": {
            "email": state["customer_email"],
            "name":  state["customer_name"],
            "metadata[hubspot_contact_id]": state["hubspot_contact_id"],
        },
        "Authorization": f"Bearer {os.environ['STRIPE_SECRET_KEY']}",
    })
    if (result or {}).get("error"):
        raise RuntimeError(f"Stripe customer create failed: {result['error']}")
    stripe_customer_id = (result or {}).get("data", {}).get("id")
    print(f"    ✔ Stripe customer created: {stripe_customer_id}")
    return {"stripe_customer_id": stripe_customer_id}


# ── Node 3: Send welcome email via Resend ────────────────────────────────────

def send_welcome_email(state: OnboardingState) -> dict:
    print(f"[3/3] Sending welcome email to {state['customer_email']}...")
    result = swytchcode_exec("resend.email.create", {
        "body": {
            "from":    "onboarding@resend.dev",
            "to":      [state["customer_email"]],
            "subject": "Welcome to Swytchcode!",
            "html":    f"<h2>Welcome, {state['customer_name']}!</h2><p>Your account is ready.</p>",
        },
        "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
    })
    if (result or {}).get("error"):
        raise RuntimeError(f"Resend email send failed: {result['error']}")
    print(f"    ✔ Welcome email sent")
    return {"email_sent": True}


# ── Build graph ───────────────────────────────────────────────────────────────

workflow = StateGraph(OnboardingState)
workflow.add_node("create_hubspot_contact", create_hubspot_contact)
workflow.add_node("create_stripe_customer", create_stripe_customer)
workflow.add_node("send_welcome_email",     send_welcome_email)

workflow.set_entry_point("create_hubspot_contact")
workflow.add_edge("create_hubspot_contact", "create_stripe_customer")
workflow.add_edge("create_stripe_customer", "send_welcome_email")
workflow.add_edge("send_welcome_email",     END)

app = workflow.compile()


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = app.invoke({
        "customer_name":      os.environ.get("CUSTOMER_NAME", "Jane Doe"),
        "customer_email":     os.environ["CUSTOMER_EMAIL"],
        "stripe_customer_id": None,
        "hubspot_contact_id": None,
        "email_sent":         None,
    })

    print("\n✅ Customer onboarding complete!")
    print(f"   HubSpot Contact ID:  {result['hubspot_contact_id']}")
    print(f"   Stripe Customer ID:  {result['stripe_customer_id']}")
    print(f"   Welcome email sent:  {result['email_sent']}")
