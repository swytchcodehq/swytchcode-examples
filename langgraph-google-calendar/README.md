# Google Calendar Agent (LangGraph + Swytchcode)

An agentic Python demo that uses [LangGraph](https://github.com/langchain-ai/langgraph) and [Swytchcode](https://swytchcode.com) to manage Google Calendar through natural-language prompts. The LLM decides which calendar API calls to make; Swytchcode handles execution.

## What it does

Running `main.py` executes five tasks in order:

1. **Schedule** a meeting titled "Team Sync" for tomorrow at 3:00 PM IST
2. **List** all meetings on tomorrow's calendar
3. **Move** the Team Sync meeting to 4:00 PM IST
4. **Delete** the Team Sync meeting
5. **Find free time** on the coming Friday (9 AM–6 PM IST)

Each step prints the agent conversation and final response to the console.

## Architecture

```
main.py
  └── LangGraph ReAct agent (OpenAI)
        └── Swytchcode runtime (LangGraphProvider)
              └── swytchcode exec → Google Calendar API v3
```

Enabled Swytchcode methods (see `.swytchcode/tooling.json`):

| Method | Purpose |
|--------|---------|
| `calendar.calendar.events.create` | Create events |
| `calendar.calendar.events.get` | List events |
| `calendar.calendar.events.update` | Reschedule events |
| `calendar.calendar.events.delete` | Delete events |
| `calendar.freebusy.create` | Check availability |

## Prerequisites

- **Python 3.10+**
- **[Swytchcode CLI](https://cli.swytchcode.com)** installed and on your `PATH`
- **OpenAI API key** (the agent uses `gpt-4o-mini`)
- **Google Calendar access** configured for Swytchcode (OAuth / bearer token via the CLI)

## Install

### 1. Clone and enter the project

```bash
cd langgraph-google-calendar
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install the Swytchcode CLI (if not already installed)

```bash
curl -fsSL https://cli.swytchcode.com/install.sh | sh
```

Verify:

```bash
swytchcode version
```

### 5. Bootstrap Swytchcode integrations

Integration bundles are **not** committed to this repo. The project ships with `.swytchcode/tooling.json`, which declares the Google Calendar integration and the five enabled methods. Fetch the integration locally with:

```bash
swytchcode bootstrap
```

This reads `tooling.json` and runs `swytchcode get` for any integration that is not already installed (e.g. `Google Calendar.calendar@v3`).

Verify the enabled tools:

```bash
swytchcode list tooling
```

You should see all five `calendar.*` methods listed in the table above.

Ensure Google Calendar authentication is available to the CLI (e.g. via `swytchcode login` or your project's auth setup).

## Configure

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-...
```

Do not commit `.env` to version control.

## Run

```bash
source .venv/bin/activate
python main.py
```

You will see labeled console output for each of the five tasks, including tool calls and the agent's final summary.

## Customization

Edit constants at the top of `main.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `MEETING_TITLE` | `Team Sync` | Event title used for create/update/delete |
| `TIMEZONE` | `Asia/Kolkata` | Time zone for all calendar operations |
| `CALENDAR_ID` | `primary` | Target calendar |

To run individual tasks, call the functions from `main.py` in a Python shell or comment out steps in `main()`.

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `Set OPENAI_API_KEY...` | Add `OPENAI_API_KEY` to `.env` |
| `Failed to spawn swytchcode` | Install the CLI or set `SWYTCHCODE_BIN` to its path |
| Auth / 401 errors from Calendar | Re-authenticate with Swytchcode; confirm Calendar access |
| Tool not found | Run `swytchcode bootstrap` then `swytchcode list tooling` |
| Agent skips tool calls | Re-run; the system prompt includes Swytchcode tool-use guidance |

Dry-run a single API call without hitting Google:

```bash
swytchcode exec calendar.calendar.events.create --dry-run --json <<'EOF'
{
  "params": {"calendarId": "primary"},
  "body": {
    "summary": "Test",
    "start": {"dateTime": "2026-08-06T15:00:00", "timeZone": "Asia/Kolkata"},
    "end": {"dateTime": "2026-08-06T16:00:00", "timeZone": "Asia/Kolkata"}
  }
}
EOF
```

## Project layout

```
langgraph-google-calendar/
├── main.py              # LangGraph agent and calendar task functions
├── requirements.txt     # Python dependencies
├── .env                 # API keys (local only, gitignored)
├── .gitignore
├── .swytchcode/
│   ├── tooling.json     # Declared integration + enabled methods (committed)
│   └── integrations/    # Fetched locally via `swytchcode bootstrap` (gitignored)
└── README.md
```
