"""
GitHub Operations Agent - CrewAI (Python), agentic mode.

The Swytchcode part is only two lines:

    swx   = Swytchcode(provider=CrewAIProvider())
    tools = swx.tools.get(toolkits=["github"])

Everything else is CrewAI's own Agent / Task / Crew boilerplate. You never
write the GitHub API call, the tool schema, or the auth - the Swytchcode CLI
provides the tools and WorkOS OAuth handles authorization.

One-time setup (run once in THIS folder - see README.md):
    swytchcode init                              # editor: none | mode: PRODUCTION
    swytchcode get github
    swytchcode add method github.user.repos.list         # list repositories
    swytchcode add method github.repo.issues.create      # create issue
    swytchcode add method github.repo.comments.create.1  # comment on an issue
    swytchcode add method github.repo.pulls.create       # open pull request
    swytchcode add method github.repo.pulls.get.1        # list pull requests
    swytchcode auth connect github               # WorkOS OAuth in your browser
"""
import os

from dotenv import load_dotenv

from swytchcode_runtime import Swytchcode, TOOL_USE_INSTRUCTIONS
from swytchcode_runtime.providers.crewai import CrewAIProvider
from crewai import Agent, Task, Crew, Process  # pip install crewai

load_dotenv()

# --- Swytchcode: two lines to retrieve the GitHub tools -----------------------
swx = Swytchcode(provider=CrewAIProvider())
tools = swx.tools.get(toolkits=["github"])
# -----------------------------------------------------------------------------

# A single CrewAI agent that owns the GitHub toolset.
# TOOL_USE_INSTRUCTIONS makes the model actually CALL a tool instead of just
# describing the action in prose.
github_agent = Agent(
    role="GitHub Operations Agent",
    goal=(
        "Fulfil GitHub requests - list repositories and pull requests, create "
        "issues, comment on issues, and open pull requests - by CALLING the "
        "provided Swytchcode tools rather than describing what should happen."
    ),
    backstory=(
        "You act on a GitHub account that has been connected through Swytchcode. "
        "You always prefer calling a tool over guessing.\n\n" + TOOL_USE_INSTRUCTIONS
    ),
    tools=tools,
    llm=os.environ.get("OPENAI_MODEL_NAME", "gpt-4o"),
    verbose=True,
    allow_delegation=False,
)

DEFAULT_PROMPT = "List the open pull requests in swytchcodehq/swytchcode-examples."

user_input = input(f"Prompt [{DEFAULT_PROMPT}]: ").strip()
prompt = user_input or DEFAULT_PROMPT

task = Task(
    description=prompt,
    expected_output=(
        "A short confirmation of the action taken, including any URL, number, or "
        "list that GitHub returned."
    ),
    agent=github_agent,
)

crew = Crew(
    agents=[github_agent],
    tasks=[task],
    process=Process.sequential,
    verbose=True,
)

result = crew.kickoff()
print("\n--- Result ---")
print(result)
