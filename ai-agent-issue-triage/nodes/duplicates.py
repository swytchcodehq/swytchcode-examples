import os
import requests
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from state import TriageState

load_dotenv()

client = OpenAI()

def get_embedding(text: str) -> list:
    response = client.embeddings.create(model="text-embedding-3-large", input=text)
    return response.data[0].embedding

def cosine_similarity(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def fetch_recent_open_issues(limit: int = 30):
    """Yield (number, title, body, embedding) for each open non-PR issue."""
    resp = requests.get(
        f"https://api.github.com/repos/{os.getenv('REPO_OWNER')}/{os.getenv('REPO_NAME')}/issues",
        headers={
            "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
        },
        params={"state": "open", "per_page": limit},
    )
    resp.raise_for_status()

    for issue in resp.json():
        if "pull_request" in issue:      # the issues endpoint also returns PRs; skip them
            continue
        title = issue["title"]
        body = issue.get("body") or ""
        text = f"{title}\n{body}"
        yield issue["number"], title, body, get_embedding(text)

def duplicate_search_node(state: TriageState) -> TriageState:
    new_embedding = get_embedding(f"{state['issue_title']}\n{state['issue_body']}")
    best_match, best_score = None, 0.0

    for number, title, body, embedding in fetch_recent_open_issues():
        score = cosine_similarity(new_embedding, embedding)
        if score > best_score:
            best_match, best_score = number, score

    if best_score > 0.85:
        state["duplicate_of"] = best_match
        state["duplicate_confidence"] = best_score
        state["issue_type"] = "duplicate"

    return state