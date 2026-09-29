from langgraph.types import interrupt
from state import TriageState

def approval_node(state: TriageState) -> TriageState:
    decision = interrupt({
        "issue_number": state["issue_number"],
        "labels": state["suggested_labels"],
        "duplicate_of": state.get("duplicate_of"),
        "draft_reply": state["draft_reply"],
        "preview": state["preview"],
    })
    state["human_decision"] = decision["action"]
    if decision["action"] == "edited":
        state["draft_reply"] = decision.get("edited_reply", state["draft_reply"])
        state["suggested_labels"] = decision.get("edited_labels", state["suggested_labels"])
    return state
    