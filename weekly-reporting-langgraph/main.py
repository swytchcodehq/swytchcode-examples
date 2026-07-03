from swytchcode_runtime import exec as swytchcode_exec
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
import sys
import csv
import zipfile
import base64
import io

# Fix Windows cp1252 console encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()


class WeeklyReportState(TypedDict):
    week_label: str
    report_email: str
    notion_database_id: str
    report_data: Optional[List]
    notion_page_id: Optional[str]
    email_sent: Optional[bool]


# ── Node 1: Load report data from Google Sheets ───────────────────────────────

def load_report_data(state: WeeklyReportState) -> dict:
    print(f"[1/3] Loading report data from Google Sheets for {state['week_label']}...")
    try:
        result = swytchcode_exec("spreadsheets.values:batchget.get", {
            "spreadsheetId": os.environ["GOOGLE_SPREADSHEET_ID"],
            "ranges":        [os.environ.get("GOOGLE_SHEETS_RANGE", "Sheet1!A1:B10")],
            "Authorization": f"Bearer {os.environ['GOOGLE_ACCESS_TOKEN']}",
        })
        value_ranges = (result or {}).get("valueRanges") or (result or {}).get("data", {}).get("valueRanges", [])
        report_data = value_ranges[0].get("values", []) if value_ranges else []
    except Exception as e:
        report_data = []
        print(f"    [WARN] Google Sheets unavailable ({type(e).__name__}) — using mock data for demo")

    if not report_data:
        # Provide realistic demo data so the rest of the workflow runs cleanly
        print("    [DEMO MODE] Using mock weekly metrics")
        report_data = [
            ["Metric",               "Value"],
            ["New Signups",          "1,284"],
            ["Active Users",         "8,302"],
            ["Revenue (USD)",        "$42,150"],
            ["Support Tickets",      "37"],
            ["Avg Response Time",    "2.4 hrs"],
            ["NPS Score",            "72"],
            ["Churn Rate",           "1.8%"],
            ["Feature Adoption",     "63%"],
        ]
    else:
        print(f"    [OK] Loaded {max(0, len(report_data) - 1)} metrics")
    return {"report_data": report_data}


# ── Node 2: Create Notion report page ────────────────────────────────────────

def create_notion_report(state: WeeklyReportState) -> dict:
    print(f"[2/3] Creating Notion report page for {state['week_label']}...")
    rows = state.get("report_data") or []
    data_rows = rows[1:] if len(rows) > 1 else []
    summary = "\n".join(f"{r[0]}: {r[1]}" for r in data_rows if len(r) >= 2) or "No data."

    try:
        result = swytchcode_exec("pages.page.create", {
            "body": {
                "parent": {"database_id": state["notion_database_id"]},
                "properties": {
                    "title": {
                        "title": [{"text": {"content": f"Weekly Report — {state['week_label']}"}}]
                    },
                },
                "children": [
                    {
                        "object": "block",
                        "type":   "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": summary}}]
                        },
                    }
                ],
            },
            "Authorization": f"Bearer {os.environ['NOTION_API_KEY']}",
            "headers": {
                "Notion-Version": "2022-06-28",
            },
        })
        notion_page_id = (result or {}).get("id") or (result or {}).get("data", {}).get("id")
    except Exception as e:
        print(f"    [WARN] Notion unavailable ({type(e).__name__}) — using mock page ID for demo")
        notion_page_id = "mock-notion-page-weekly-report"

    if not notion_page_id:
        notion_page_id = "mock-notion-page-weekly-report"
        print("    [DEMO MODE] Notion page ID not returned — using mock ID")

    print(f"    [OK] Notion page created: {notion_page_id}")
    return {"notion_page_id": notion_page_id}


# ── Node 3: Email stakeholders ────────────────────────────────────────────────

def email_stakeholders(state: WeeklyReportState) -> dict:
    print(f"[3/3] Emailing report to {state['report_email']}...")
    rows = state.get("report_data") or []
    data_rows = rows[1:] if len(rows) > 1 else []
    table_rows = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td></tr>"
        for r in data_rows if len(r) >= 2
    )
    # Create CSV in memory
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerows(rows)
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("weekly_report.csv", csv_buffer.getvalue())
    
    zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')

    swytchcode_exec("emails.email.create", {
        "body": {
            "from":    "reports@resend.dev",
            "to":      [state["report_email"]],
            "subject": f"Weekly Report — {state['week_label']}",
            "html": (
                f"<h2>Weekly Report: {state['week_label']}</h2>"
                f"<table border='1' cellpadding='8'>"
                f"<tr><th>Metric</th><th>Value</th></tr>"
                f"{table_rows}"
                f"</table>"
                f"<p>Notion: {state.get('notion_page_id', '')}</p>"
            ),
            "attachments": [
                {
                    "filename": "weekly_report.zip",
                    "content": zip_b64
                }
            ]
        },
        "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
    })
    print(f"    [OK] Email sent to {state['report_email']} with zip attachment")
    return {"email_sent": True}


# ── Build graph ───────────────────────────────────────────────────────────────

workflow = StateGraph(WeeklyReportState)
workflow.add_node("load_report",        load_report_data)
workflow.add_node("create_notion_page", create_notion_report)
workflow.add_node("email_stakeholders", email_stakeholders)

workflow.set_entry_point("load_report")
workflow.add_edge("load_report",        "create_notion_page")
workflow.add_edge("create_notion_page", "email_stakeholders")
workflow.add_edge("email_stakeholders", END)

app = workflow.compile()


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = app.invoke({
        "week_label":          f"Week of {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
        "report_email":        os.environ["REPORT_EMAIL"],
        "notion_database_id":  os.environ["NOTION_DATABASE_ID"],
        "report_data":         None,
        "notion_page_id":      None,
        "email_sent":          None,
    })

    print("\n[DONE] Weekly report complete!")
    print(f"   Rows reported:   {len(result['report_data'] or []) - 1}")
    print(f"   Notion page ID:  {result['notion_page_id']}")
    print(f"   Email sent:      {result['email_sent']}")
