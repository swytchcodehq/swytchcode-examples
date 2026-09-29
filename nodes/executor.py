import os
from dotenv import load_dotenv
load_dotenv()
from swytchcode_runtime import exec
from state import TriageState

OWNER = os.getenv("REPO_OWNER")
REPO = os.getenv("REPO_NAME")

def executor_node(state: TriageState) -> TriageState:
    log = state.get("execution_log", [])

    if state["suggested_labels"]:
        result = exec(
            "github.issue.labels.create",
            {
                "body": {"labels": state["suggested_labels"]},
                "params": {
                    "owner": OWNER,
                    "repo": REPO,
                    "issue_number": state["issue_number"],
                },
            },
        )
        log.append(f"labels: {result}")

    if state.get("draft_reply"):
        result = exec(
            "github.issue.comments.create",
            {
                "body": {"body": state["draft_reply"]},
                "params": {
                    "owner": OWNER,
                    "repo": REPO,
                    "issue_number": state["issue_number"],
                },
            },
        )
        log.append(f"comment: {result}")

    if state.get("duplicate_of"):
        result = exec(
            "github.issue.update",
            {
                "body": {"state": "closed", "state_reason": "duplicate"},
                "params": {
                    "owner": OWNER,
                    "repo": REPO,
                    "issue_number": state["issue_number"],
                },
            },
        )
        log.append(f"closed as duplicate of #{state['duplicate_of']}: {result}")

    state["execution_log"] = log
    return state