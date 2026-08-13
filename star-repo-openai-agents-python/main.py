"""
Star-repo agent - OpenAI Agents SDK (Python).

Uses the swytchcode-runtime agentic API (Swytchcode + OpenAIAgentsProvider).
The Swytchcode part is two lines; the OpenAI Agents SDK runs the tool loop.

Prereq (run once in this folder, see setup commands):
    swytchcode init            # editor: none | mode: PRODUCTION
    swytchcode get github
    swytchcode add method github.starred.update
    swytchcode auth connect github
"""
from dotenv import load_dotenv

from swytchcode_runtime import Swytchcode, TOOL_USE_INSTRUCTIONS
from swytchcode_runtime.providers.openai_agents import OpenAIAgentsProvider
from agents import Agent, Runner  # pip install openai-agents

load_dotenv()

# --- Swytchcode: identical in every framework example ---
swx = Swytchcode(provider=OpenAIAgentsProvider())
tools = swx.tools.get(toolkits=["github"])      # simplified, required-fields-only tools

# --- OpenAI Agents SDK specifics (the SDK runs the tool loop) ---
# TOOL_USE_INSTRUCTIONS nudges the model to actually CALL the tool
# instead of just describing how to star a repo.
agent = Agent(
    name="Star Repo Agent",
    instructions=TOOL_USE_INSTRUCTIONS,
    tools=tools,
)

DEFAULT_PROMPT = "Star the swytchcodehq/swytchcode-examples repo on GitHub for me."

# Type your instruction at runtime; press Enter to use the default.
user_input = input(f"Prompt [{DEFAULT_PROMPT}]: ").strip()
prompt = user_input or DEFAULT_PROMPT

result = Runner.run_sync(agent, prompt)
print(result.final_output)
