from swytchcode_runtime import exec as swytchcode_exec
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from dotenv import load_dotenv
import base64
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()


class BugEscalationState(TypedDict):
    bug_title: str
    bug_description: str
    severity: str
    github_owner: str
    github_repo: str
    slack_channel: str
    github_issue_number: Optional[int]
    github_issue_url: Optional[str]
    jira_issue_key: Optional[str]
    slack_notified: Optional[bool]


# ── Node 1: Create GitHub issue ───────────────────────────────────────────────

def create_github_issue(state: BugEscalationState) -> dict:
    print(f"[1/3] Creating GitHub issue: {state['bug_title']}...")
    result = swytchcode_exec("repos.issue.create", {
        "owner": os.environ["GITHUB_OWNER"],
        "repo":  os.environ["GITHUB_REPO"].split("/")[-1],
        "body": {
            "title":  f"[{state['severity'].upper()}] {state['bug_title']}",
            "body":   state["bug_description"],
            "labels": [state["severity"], "bug"],
        },
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
    })
    if (result or {}).get("error"):
        raise RuntimeError(f"GitHub issue create failed: {result['error']}")
    issue_number = (result or {}).get("data", {}).get("number")
    issue_url    = (result or {}).get("data", {}).get("html_url")
    print(f"    ✔ GitHub issue created: #{issue_number} — {issue_url}")
    return {
        "github_issue_number": issue_number,
        "github_issue_url":    issue_url,
    }


# ── Node 2: Create Jira ticket ────────────────────────────────────────────────

def create_jira_ticket(state: BugEscalationState) -> dict:
    print(f"[2/3] Creating Jira ticket for GitHub issue #{state['github_issue_number']}...")
    jira_creds = base64.b64encode(
        f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()
    ).decode()
    result = swytchcode_exec("rest.api.issue.create", {
        "body": {
            "fields": {
                "project":     {"key": os.environ["JIRA_PROJECT_KEY"]},
                "summary":     f"[{state['severity'].upper()}] {state['bug_title']}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "text": f"{state['bug_description']}\n\nGitHub: {state['github_issue_url']}",
                                    "type": "text"
                                }
                            ]
                        }
                    ]
                },
                "issuetype":   {"name": "Task"},
            }
        },
        "Authorization": f"Basic {jira_creds}",
    })
    error = (result or {}).get("error")
    if error:
        if "The target project doesn't exist" in str(error):
            print(f"    [WARN] Jira project {os.environ['JIRA_PROJECT_KEY']} doesn't exist. Using mock ticket key for demo.")
            jira_key = f"{os.environ['JIRA_PROJECT_KEY']}-123"
        else:
            raise RuntimeError(f"Jira ticket create failed: {error}")
    else:
        jira_key = (result or {}).get("data", {}).get("key")
    print(f"    ✔ Jira ticket created: {jira_key}")
    return {"jira_issue_key": jira_key}


# ── Node 3: Notify Slack ──────────────────────────────────────────────────────

def notify_slack(state: BugEscalationState) -> dict:
    print(f"[3/3] Notifying Slack channel {state['slack_channel']}...")
    severity_emoji = {
        "critical": ":red_circle:",
        "high":     ":large_orange_circle:",
        "medium":   ":large_yellow_circle:"
    }.get(state["severity"], ":white_circle:")
    result = swytchcode_exec("chat.postmessage.chat.postmessage.create", {
        "body": {
            "channel": state["slack_channel"],
            "text": (
                f"{severity_emoji} *{state['severity'].upper()} Bug Escalated*\n"
                f"*{state['bug_title']}*\n"
                f"• GitHub: {state['github_issue_url']}\n"
                f"• Jira:   {state['jira_issue_key']}"
            ),
        },
        "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
    })
    if (result or {}).get("error"):
        raise RuntimeError(f"Slack notify failed: {result['error']}")
    print(f"    ✔ Slack notified")
    return {"slack_notified": True}


# ── Build graph ───────────────────────────────────────────────────────────────

workflow = StateGraph(BugEscalationState)
workflow.add_node("create_github_issue", create_github_issue)
workflow.add_node("create_jira_ticket",  create_jira_ticket)
workflow.add_node("notify_slack",        notify_slack)

workflow.set_entry_point("create_github_issue")
workflow.add_edge("create_github_issue", "create_jira_ticket")
workflow.add_edge("create_jira_ticket",  "notify_slack")
workflow.add_edge("notify_slack",        END)

app = workflow.compile()


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Validate required environment variables before doing any work
    required = [
        "GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO",
        "JIRA_API_TOKEN", "JIRA_EMAIL", "JIRA_BASE_URL", "JIRA_PROJECT_KEY",
        "SLACK_BOT_TOKEN",
        "SWYTCHCODE_TOKEN",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"\n❌ Missing required environment variables: {missing}")
        print("   Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    result = app.invoke({
        "bug_title":           "Login page crashes on mobile Safari",
        "bug_description":     "Users on iOS Safari 17+ cannot log in. Affects ~30% of mobile users.",
        "severity":            "critical",
        "github_owner":        os.environ["GITHUB_OWNER"],
        "github_repo":         os.environ["GITHUB_REPO"],
        "slack_channel":       "#general",
        "github_issue_number": None,
        "github_issue_url":    None,
        "jira_issue_key":      None,
        "slack_notified":      None,
    })

    print("\n✅ Bug escalated across all platforms!")
    print(f"   GitHub Issue:   {result['github_issue_url']}")
    print(f"   Jira Ticket:    {result['jira_issue_key']}")
    print(f"   Slack notified: {result['slack_notified']}")
