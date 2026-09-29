import os
from dotenv import load_dotenv
load_dotenv()
from swytchcode_runtime import exec
from state import TriageState

def preview_node(state: TriageState) -> TriageState:
    state["preview"] = exec(
        "github.issue.labels.create",
        {
            "body": {"labels": state["suggested_labels"]},
            "owner": os.getenv("REPO_OWNER"),
            "repo": os.getenv("REPO_NAME"),
            "issue_number": state["issue_number"],
        },
        dry_run=True,
    )
    return state


if __name__ == "__main__":
    state = {
        "issue_number": 3,
        "suggested_labels": ["bug", "safari"],
    }
    result = preview_node(state)
    print(result["preview"])