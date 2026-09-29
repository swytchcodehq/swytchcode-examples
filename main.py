from dotenv import load_dotenv
load_dotenv()
from graph import app

config = {"configurable": {"thread_id": "issue-3"}}

result = app.invoke({
    "issue_number": 3,
    "issue_title": "Add dark mode",
    "issue_body": "The dark mode button exists but it doesnt yet support on iOS devices.",
}, config)

print(result["__interrupt__"])