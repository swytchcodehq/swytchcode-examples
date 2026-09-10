# Gmail + Calendar agent

A chat app for your own Gmail and Google Calendar. You type in plain language; an
[OpenAI Agents SDK](https://openai.github.io/openai-agents-js/) agent picks the
action and [Swytchcode](https://swytchcode.com) runs every API call and enforces a
policy file. No hand-written HTTP, OAuth, or tool schemas anywhere.

## Run it

```bash
npm install
cp .env.example .env.local            # add your OPENAI_API_KEY

swytchcode login
swytchcode auth connect Gmail         # opens a browser
swytchcode auth connect "Google Calendar"
swytchcode bootstrap                  # fetch the enabled method bundles

npm run dev                           # http://localhost:3000
```

The two dots in the header go green once each Google account is connected.

## How it uses Swytchcode

**Methods.** `.swytchcode/tooling.json` is the agent's allowlist. `lib/agent.ts`
asks Swytchcode for one tool per enabled method and hands them to the agent:

```ts
const swx = new Swytchcode();
const methods = await swx.tools.get({ toolkits: ["gmail", "calendar"] });
```

| method | used for |
| --- | --- |
| `gmail.user.messages.get` / `.get1` | list / read mail |
| `gmail.user.profile.get` | header identity |
| `calendar.event.get` / `.get1` | read events |
| `calendar.event.quickAdd.create` / `calendar.event.create` | create events |
| `calendar.me.calendarList.list` | list calendars |

`app/api/health/route.ts` is the same thing without an agent:
`exec("gmail.user.profile.get", { params: { userId: "me" } })`.

**Policies.** `.swytchcode/integrations/policies.json` is checked by the Swytchcode
kernel before every call, on any code path. `on_violation: fail` turns a match
into an error.

| policy | blocks |
| --- | --- |
| `no-calendar-deletes` | `calendar.event.delete`, `calendar.clear.create`, `calendar.calendar.delete`, `calendar.me.calendarList.delete` |
| `no-destructive-event-titles` | `calendar.event.quickAdd.create` when `text` matches `delete\|cancel\|remove\|clear` |
| `no-destructive-event-summary` | same, for `calendar.event.create` / `summary` |

```bash
swytchcode policy list
swytchcode policy validate
swytchcode policy add --target <id> --field <param> --operator matches \
  --value "<regex>" --action POLICY_BLOCKED --message "..."
```

## Build the Swytchcode project from scratch

```bash
swytchcode init
swytchcode get Gmail
swytchcode get "Google Calendar"

swytchcode add method gmail.user.messages.get
swytchcode add method gmail.user.messages.get1
swytchcode add method gmail.user.profile.get
swytchcode add method calendar.event.get
swytchcode add method calendar.event.get1
swytchcode add method calendar.event.quickAdd.create
swytchcode add method calendar.event.create
swytchcode add method calendar.me.calendarList.list
```

Then add the policies with `swytchcode policy add` (above) and wire the tools into
an agent as in `lib/agent.ts`.

## Project layout

```
app/
  api/chat/route.ts     POST { message, sessionId } -> { reply, calls }
  api/health/route.ts   two exec() probes for the header dots
  page.tsx  layout.tsx  globals.css
components/Chat.tsx      transcript + composer
lib/
  agent.ts              Swytchcode tools + OpenAI agent + guardrails
  session.ts            in-memory conversation history, per browser
.swytchcode/
  tooling.json                  the 8 enabled methods
  integrations/policies.json    the 3 guard policies
```

## Links

- [Swytchcode docs](https://docs.swytchcode.com)
- [CLI reference](https://docs.swytchcode.com/cli)
- [Discord](https://discord.com/invite/zuSXSv5GWs)
- [OpenAI Agents SDK quickstart](https://openai.github.io/openai-agents-js/)
