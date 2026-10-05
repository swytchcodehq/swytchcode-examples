from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from state import TriageState

client = OpenAI()

def draft_reply_node(state: TriageState) -> TriageState:
    dup_info = (
        f"#{state['duplicate_of']} ({state['duplicate_confidence']:.0%} match)"
        if state.get("duplicate_of") else "not a duplicate"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": (
                f"Draft a short first-reply comment for a GitHub issue. "
                f"Type: {state['issue_type']}. Duplicate status: {dup_info}. "
                f"Under 4 sentences. Do not promise timelines."
            ),
        }],
    )
    state["draft_reply"] = response.choices[0].message.content
    return state