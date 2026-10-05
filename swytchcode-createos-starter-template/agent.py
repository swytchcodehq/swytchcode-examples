"""Sample starter. Change the instructions and PROMPT, then build on this."""

from dotenv import load_dotenv
from agents import Agent, Runner
from swytchcode_runtime import Swytchcode, TOOL_USE_INSTRUCTIONS
from swytchcode_runtime.providers.openai_agents import OpenAIAgentsProvider

load_dotenv()

swx = Swytchcode(provider=OpenAIAgentsProvider())
tools = swx.tools.get(toolkits=["CreateOS"])

agent = Agent(
    name="CreateOS Starter",
    instructions=(
        "Use the CreateOS tools to do what the user asks.\n\n"
        + TOOL_USE_INSTRUCTIONS
    ),
    tools=tools,
)

# Replace this with your task.
PROMPT = "Create a sandbox and run echo hello."

if __name__ == "__main__":
    result = Runner.run_sync(agent, PROMPT, max_turns=40)
    print(result.final_output)
