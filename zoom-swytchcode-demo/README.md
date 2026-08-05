# Zoom via swytchcode (MCP demo)

Zoom, driven entirely through swytchcode as an MCP server in Claude/Cursor/Codex/Copilot/Windsurf

## Connect it as an MCP server (do this first)

1. Run this in the project folder and log in when prompted:
   ```bash
   swytchcode init
   ```
   Pick `claude` when asked "Which editor do you use?" — this logs you in (if not
   already) and wires swytchcode up as an MCP server for Claude Code in this project.
2. Restart/reload Claude Code so it picks up the new MCP connection.
3. That's it. Just prompt Claude with what you want — e.g. *"schedule a Zoom meeting
   tomorrow at 2pm"* — and it will discover the Zoom tools, fetch the integration, enable
   the right methods, and run them for you. No manual commands required.

**Alternatively**, everything below is the same demo built by hand, command by command,
if you want to drive it yourself instead of prompting.

## Requirements

- swytchcode CLI (install the cli)[https://docs.swytchcode.com/docs/]
- A Zoom **Server-to-Server OAuth** app (https://marketplace.zoom.us/)
- Free Zoom plan is fine for Meetings. Webinars need the paid Webinar add-on.

## Setup

```bash
swytchcode get zoom
swytchcode add method zoom.user.meetings.create
swytchcode add method zoom.user.meetings.get
swytchcode add method zoom.meeting.update
swytchcode add method zoom.meeting.delete
swytchcode add method zoom.meeting.recordings.delete
```

## Auth

To obtain your ZOOM_AUTH_TOKEN, follow these steps:

1) Sign in to https://marketplace.zoom.us/.
2) Create or select your Zoom app.
3) Add different scopes
4) Activate your app


```bash
clientId="<Client ID>"
clientSecret="<Client Secret>"
accountId="<Account ID>"

basicAuth=$(printf '%s:%s' "$clientId" "$clientSecret" | base64 | tr -d '\n')

curl -s -X POST "https://zoom.us/oauth/token?grant_type=account_credentials&account_id=$accountId" \
  -H "Authorization: Basic $basicAuth"
```

Put the `access_token` in `.env`:
```
ZOOM_ACCESS_TOKEN=<access_token>
```

Tokens expire after 1 hour — repeat this when calls start 401ing.

## Usage

### Create a meeting

```bash
set -a && source .env && set +a

swytchcode exec zoom.user.meetings.create \
  --input userId=me \
  --body '{"topic":"Meeting","type":2,"start_time":"2026-08-06T14:00:00","duration":30,"timezone":"Asia/Kolkata"}' \
  --header "Authorization=Bearer $ZOOM_ACCESS_TOKEN" \
  --json 2>/dev/null
```

Always redirect stderr (`2>/dev/null`) when passing `--header` — swytchcode's request
log prints it unredacted otherwise.

### List meetings

```bash
swytchcode exec zoom.user.meetings.get --input userId=me \
  --header "Authorization=Bearer $ZOOM_ACCESS_TOKEN" --json 2>/dev/null
```

### Other methods

| Method | Needs scope |
|---|---|
| `zoom.user.get` | `user:read:user` |
| `zoom.user.settings.get` | `user:read:user` |
| `zoom.user.webinars.get` | `webinar:read:list_webinars` |
| `zoom.user.list` | `user:read:list_users` |
| `zoom.group.list` / `zoom.group.create` | `group:read:list_groups` / `group:write:master_group` |
| `zoom.webhook.list` | `webhook:read:admin` |
| `zoom.tracking_field.list` / `.create` | `tracking_field:read` / `write` |

## Policy: deletes require approval

```json
{
  "defaults": { "on_violation": "fail", "evaluation": "pre_execution" },
  "policies": [
    {
      "id": "zoom-meeting-delete-approval",
      "target": ["zoom.meeting.delete"],
      "when": { "field": "meetingId", "operator": "exists" },
      "action": { "type": "POLICY_BLOCKED", "message": "Deleting a Zoom meeting requires approval." }
    },
    {
      "id": "zoom-meeting-recording-delete-approval",
      "target": ["zoom.meeting.recordings.delete"],
      "when": { "field": "meetingId", "operator": "exists" },
      "action": { "type": "POLICY_BLOCKED", "message": "Deleting a recording requires approval." }
    }
  ]
}
```

## Adding your own policies

```bash
swytchcode policy add        # interactive wizard — name, target tool(s), condition, action
swytchcode policy list       # show every configured policy
swytchcode policy validate   # check policies.json against the schema
swytchcode policy remove <policy-id>
```