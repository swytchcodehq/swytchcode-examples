"""
A tiny Gemini-powered agent that can star a GitHub repo when you ask it to
in plain English.

Big picture:
  - Gemini decides *what* to do (which tool, which repo).
  - Swytchcode actually *does* it (makes the real, authenticated GitHub call).
  Gemini never sees your GitHub token; Swytchcode holds the credentials and
  runs the call for you. That separation is the whole point.
"""

import os
import sys

from google import genai
from google.genai import types
from dotenv import load_dotenv

from swytchcode_runtime import Swytchcode
from swytchcode_runtime.prompts import TOOL_USE_INSTRUCTIONS


load_dotenv()


instruction = " ".join(sys.argv[1:]) or "Star the octocat/Hello-World repo for me"


gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

swy = Swytchcode()

neutral_tools = swy.tools.get(toolkits=["github"])
if not neutral_tools:
    sys.exit("No github tools found. Run: swy add github.starred.update")


tools_by_name = {t.name: t for t in neutral_tools}

gemini_tool = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name=t.name,
        description=t.description,
        parameters=t.input_schema,
    )
    for t in neutral_tools
])

chat = gemini.chats.create(
    model="gemini-3.6-flash",
    config=types.GenerateContentConfig(
        tools=[gemini_tool],
        system_instruction=TOOL_USE_INSTRUCTIONS,
    ),
)

print(f"\nYou said: {instruction}\n")


message = instruction
while True:
    response = chat.send_message(message)


    calls = response.function_calls or []
    if not calls:

        print("Gemini:", (response.text or "").strip(), "\n")
        break


    replies = []
    for fc in calls:
        args = dict(fc.args or {})
        print(f"[Gemini wants to run: {fc.name}  input={args}]")
        tool = tools_by_name[fc.name]
        try:
            result = tool.execute(args)         
            print(f"[executor ran it -> ok: {str(result)[:400]}]")
        except Exception as e:
            result = f"Error: {e}"
            print(f"[executor ran it -> ERROR: {e}]")

        replies.append(types.Part.from_function_response(
            name=fc.name,
            response={"result": str(result)},
        ))


    message = replies
