from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from state import TriageState
from nodes.classify import classify_node
from nodes.duplicates import duplicate_search_node
from nodes.draft_reply import draft_reply_node
from nodes.preview import preview_node
from nodes.approval import approval_node
from nodes.executor import executor_node
import sqlite3

graph = StateGraph(TriageState)
graph.add_node("classify", classify_node)
graph.add_node("find_duplicates", duplicate_search_node)
graph.add_node("draft_reply", draft_reply_node)
graph.add_node("preview", preview_node)
graph.add_node("approval", approval_node)
graph.add_node("execute", executor_node)

graph.set_entry_point("classify")
graph.add_edge("classify", "find_duplicates")
graph.add_edge("find_duplicates", "draft_reply")
graph.add_edge("preview", "approval")
graph.add_edge("draft_reply", "preview")
graph.add_conditional_edges(
    "approval",
    lambda s: "execute" if s["human_decision"] in ("approved", "edited") else END,
    {"execute": "execute", END: END},
)
graph.add_edge("execute", END)

conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
app = graph.compile(checkpointer=checkpointer)