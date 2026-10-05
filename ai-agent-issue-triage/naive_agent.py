import os
import json
import requests
from openai import OpenAI

client = OpenAI()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# sitting right here, next to untrusted text
REPO = "velourcodes/agent-test-repo"
# <-- your disposable test repo
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

# --- Tool schemas: what the model is allowed to ask for ---

close_issue_tool = {
    "type": "function",
    "function": {
        "name": "close_issue",
        "description": "Close a GitHub issue by its number",
        "parameters": {
            "type": "object",
            "properties": {"number": {"type": "integer"}},
            "required": ["number"],
        },
    },
}

comment_tool = {
    "type": "function",
    "function": {
        "name": "post_comment",
        "description": "Post a comment on a GitHub issue",
        "parameters": {
            "type": "object",
            "properties": {
                "number": {"type": "integer"},
                "body": {"type": "string"},
            },
            "required": ["number", "body"],
        },
    },
}

label_tool = {
    "type": "function",
    "function": {
        "name": "add_labels",
        "description": "Add labels to a GitHub issue",
        "parameters": {
            "type": "object",
            "properties": {
                "number": {"type": "integer"},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["number", "labels"],
        },
    },
}

# --- Real functions: what actually happens when a tool is "called" ---

def close_issue(number: int) -> str:
    resp = requests.patch(
        f"https://api.github.com/repos/{REPO}/issues/{number}",
        headers=HEADERS,
        json={"state": "closed"},
    )
    return f"close_issue({number}) -> HTTP {resp.status_code}"

def post_comment(number: int, body: str) -> str:
    resp = requests.post(
        f"https://api.github.com/repos/{REPO}/issues/{number}/comments",
        headers=HEADERS,
        json={"body": body},
    )
    return f"post_comment({number}) -> HTTP {resp.status_code}"

def add_labels(number: int, labels: list) -> str:
    resp = requests.post(
        f"https://api.github.com/repos/{REPO}/issues/{number}/labels",
        headers=HEADERS,
        json={"labels": labels},
    )
    return f"add_labels({number}) -> HTTP {resp.status_code}"

AVAILABLE_FUNCTIONS = {
    "close_issue": close_issue,
    "post_comment": post_comment,
    "add_labels": add_labels,
}

def execute_immediately(tool_call) -> None:
    """Decided and executed in the same breath — no review step exists."""
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    result = AVAILABLE_FUNCTIONS[name](**args)
    print(result)   # <-- this is the ACTUAL return value of a real HTTP call

def handle_issue(issue_body: str) -> None:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"Triage this issue and take whatever action it needs:\n\n{issue_body}",
        }],
        tools=[close_issue_tool, comment_tool, label_tool],
    )
    for call in response.choices[0].message.tool_calls or []:
        execute_immediately(call)

if __name__ == "__main__":
    with open("issue_501.txt") as f:
        handle_issue(f.read())