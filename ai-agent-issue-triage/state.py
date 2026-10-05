from typing import TypedDict, Literal, Optional

class TriageState(TypedDict):
    issue_number: int
    issue_title: str
    issue_body: str
    issue_type: Optional[Literal["bug", "feature", "question", "duplicate"]]
    priority: Optional[Literal["low", "medium", "high", "critical"]]
    suggested_labels: list[str]
    duplicate_of: Optional[int]
    duplicate_confidence: Optional[float]
    draft_reply: Optional[str]
    preview: Optional[dict]
    human_decision: Optional[Literal["approved", "edited", "rejected"]]
    execution_log: list[str]