"""LangGraph agent that manages Google Calendar meetings via Swytchcode."""

import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from swytchcode_runtime import Swytchcode, TOOL_USE_INSTRUCTIONS
from swytchcode_runtime.providers.langgraph import LangGraphProvider

load_dotenv()

TIMEZONE = "Asia/Kolkata"
CALENDAR_ID = "primary"
MEETING_TITLE = "Team Sync"

CALENDAR_TOOLS = [
    "calendar.calendar.events.create",
    "calendar.calendar.events.get",
    "calendar.calendar.events.update",
    "calendar.calendar.events.delete",
    "calendar.freebusy.create",
]

SYSTEM_PROMPT = f"""You are a calendar scheduling assistant with access to Google Calendar tools.

General rules:
- Use calendarId "{CALENDAR_ID}" unless the user specifies another calendar.
- Use timeZone "{TIMEZONE}" (IST) for all date/time fields unless told otherwise.
- Default meeting length: 1 hour when only a start time is given.
- When listing events, use timeMin/timeMax for the requested day and set singleEvents=true.
- When updating an event, first list events if you need the eventId, then call update with the new start/end times.
- When deleting, find the event by title/date if eventId is not provided, then delete it.
- For free/busy queries, use calendar.freebusy.create with items=[{{"id": "{CALENDAR_ID}"}}]
  and timeMin/timeMax covering the requested day in RFC3339 format.

{TOOL_USE_INSTRUCTIONS}"""


def log_output(label: str, result: dict[str, Any]) -> None:
    print(f"\n{'=' * 60}")
    print(label)
    print("=" * 60)
    for message in result["messages"]:
        message.pretty_print()
    last = result["messages"][-1]
    if hasattr(last, "content") and last.content:
        print("\n--- Final response ---")
        print(last.content)


def build_agent():
    swx = Swytchcode(provider=LangGraphProvider())
    tools = swx.tools.get(tools=CALENDAR_TOOLS)
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return create_react_agent(model, tools=tools, prompt=SYSTEM_PROMPT)


def run_task(agent, prompt: str, label: str) -> dict[str, Any]:
    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    log_output(label, result)
    return result


def schedule_meeting(agent) -> dict[str, Any]:
    return run_task(
        agent,
        f"Schedule a meeting titled '{MEETING_TITLE}' tomorrow at 3:00 PM IST "
        f"on my primary Google Calendar.",
        "1. Schedule meeting (tomorrow 3 PM IST)",
    )


def list_tomorrows_meetings(agent) -> dict[str, Any]:
    return run_task(
        agent,
        "List all meetings on my primary calendar for tomorrow (full day, IST). "
        "Show each event's summary, start, end, and event id.",
        "2. List tomorrow's meetings",
    )


def move_meeting_to_4pm(agent) -> dict[str, Any]:
    return run_task(
        agent,
        f"Move the '{MEETING_TITLE}' meeting scheduled for tomorrow from 3:00 PM IST "
        f"to 4:00 PM IST on my primary calendar. Keep the same 1-hour duration.",
        "3. Move meeting to 4 PM",
    )


def delete_meeting(agent) -> dict[str, Any]:
    return run_task(
        agent,
        f"Delete the '{MEETING_TITLE}' meeting on my primary calendar for tomorrow.",
        "4. Delete meeting",
    )


def find_free_time_friday(agent) -> dict[str, Any]:
    return run_task(
        agent,
        "Find free time slots on this coming Friday (9 AM to 6 PM IST) on my primary "
        "calendar. Use the free/busy API, then summarize which hours are free.",
        "5. Find free time on Friday",
    )


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY in your environment or .env file.")

    agent = build_agent()

    schedule_meeting(agent)
    list_tomorrows_meetings(agent)
    move_meeting_to_4pm(agent)
    delete_meeting(agent)
    find_free_time_friday(agent)


if __name__ == "__main__":
    main()
