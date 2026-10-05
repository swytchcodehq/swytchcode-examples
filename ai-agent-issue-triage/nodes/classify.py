from dotenv import load_dotenv
load_dotenv()
import json
from openai import OpenAI
from state import TriageState

client = OpenAI()

classify_tool = {
    "type": "function",
    "function": {
        "name": "classify_issue",
        "description": "Classify a GitHub issue by type and priority",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_type": {"type": "string", "enum": ["bug", "feature", "question", "duplicate"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "suggested_labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["issue_type", "priority", "suggested_labels"],
        },
    },
}

def classify_node(state: TriageState) -> TriageState:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"{state['issue_title']}\n\n{state['issue_body']}"}],
        tools=[classify_tool],
        tool_choice={"type": "function", "function": {"name": "classify_issue"}},
    )
    result = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
    state["issue_type"] = result["issue_type"]
    state["priority"] = result["priority"]
    state["suggested_labels"] = result["suggested_labels"]
    return state