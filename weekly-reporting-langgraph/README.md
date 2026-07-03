# Weekly Reporting (LangGraph + Swytchcode)

A LangGraph agent that turns a Google Sheet of metrics into a published Notion page and an emailed weekly report.

> Run one command to pull your weekly numbers, publish them to Notion, and email stakeholders, without writing API glue code or managing credentials and retries.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/swytchcodehq/Weekly-Reporting-Langgraph?style=flat-square)](https://github.com/swytchcodehq/Weekly-Reporting-Langgraph/commits)

## What this does

This demo automates a recurring weekly report. It reads a range of metrics from a Google Sheet, creates a Notion page summarizing them, and emails an HTML table of the same numbers to a stakeholder address through Resend. The three steps run as a LangGraph state machine, so each node passes its result to the next.

Every external call goes through [Swytchcode](https://www.swytchcode.com/), a deterministic API execution layer for AI agents. The agent code never calls Google, Notion, or Resend directly. Instead it asks the Swytchcode runtime to run a named method, and the runtime validates the request against a schema registry of 2,000+ integrations, handles auth and retries, and records an audit trail of what ran.

## How it works

The graph has three nodes and runs them in order:

```
load_report -> create_notion_page -> email_stakeholders
```

- **load_report** reads the configured range from your Google Sheet via `spreadsheets.values:batchget.get` and stores the rows in state.
- **create_notion_page** writes a new page into your Notion database via `pages.page.create`, with the metrics rendered as a paragraph block.
- **email_stakeholders** sends an HTML table of the metrics to the report address via `emails.email.create` (Resend), including a reference to the Notion page that was created.

## Prerequisites

- **Python 3.9+**
- **Swytchcode CLI:** install with the verified script for your platform:
  
  npm install -g swytchcode

- A **Google Sheets** access token, a **Notion** integration token, and a **Resend** API key (see the table below).

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/swytchcodehq/Weekly-Reporting-Langgraph.git
   cd Weekly-Reporting-Langgraph
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example env file and fill in your keys:
   ```bash
   cp .env.example .env
   ```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_ACCESS_TOKEN` | Yes | OAuth bearer token the Sheets read is authenticated with. |
| `GOOGLE_SPREADSHEET_ID` | Yes | Spreadsheet ID, taken from the sheet URL. |
| `GOOGLE_SHEETS_RANGE` | No | A1 range to read. Defaults to `Sheet1!A1:B10`. |
| `NOTION_API_KEY` | Yes | Notion integration token (`secret_...`). |
| `NOTION_DATABASE_ID` | Yes | ID of the Notion database the report page is created in. |
| `RESEND_API_KEY` | Yes | Resend API key (`re_...`). |
| `REPORT_EMAIL` | Yes | Address that receives the emailed report. |
| `SWYTCHCODE_TOKEN` | Yes | Swytchcode auth token, from the [Swytchcode dashboard](https://swytchcode.com) under Settings, API keys. |

The first row of the sheet range is treated as a header and skipped; remaining rows are read as `metric, value` pairs.

## Run

```bash
python main.py
```

## Expected output

The script prints each node as it runs and a summary at the end:

```
[1/3] Loading report data from Google Sheets for Week of June 10, 2026...
    Loaded 5 metrics
[2/3] Creating Notion report page for Week of June 10, 2026...
    Notion page created: 1a2b3c4d-...
[3/3] Emailing report to you@example.com...
    Email sent to you@example.com

Weekly report complete!
   Rows reported:   5
   Notion page ID:  1a2b3c4d-...
   Email sent:      True
```

After a run you should see a new page in your Notion database, titled for the week you ran it, and a report email in the `REPORT_EMAIL` inbox.

## Canonical IDs used

| Service | Canonical ID |
|---------|--------------|
| Google Sheets | `spreadsheets.values:batchget.get` |
| Notion | `pages.page.create` |
| Resend | `emails.email.create` |

## Part of the Swytchcode demo collection

Runnable LangGraph + Swytchcode examples:

- [Bug-Escalation-Langgraph](https://github.com/swytchcodehq/Bug-Escalation-Langgraph)
- [Create-And-Send-Payment-Langgraph](https://github.com/swytchcodehq/Create-And-Send-Payment-Langgraph)
- [Customer-Onboarding-Langgraph](https://github.com/swytchcodehq/Customer-Onboarding-Langgraph)
- [Fintech-Compliance-Langgraph-Demo](https://github.com/swytchcodehq/Fintech-Compliance-Langgraph-Demo)
- [Lead-Qualification-Langgraph](https://github.com/swytchcodehq/Lead-Qualification-Langgraph)
- [Weekly-Reporting-Langgraph](https://github.com/swytchcodehq/Weekly-Reporting-Langgraph)

## License

MIT. See [LICENSE](LICENSE).
