# GitHub Operations Agent - CrewAI (Python)

An agentic example where a **CrewAI** agent performs real GitHub actions -
listing repositories and pull requests, creating issues, commenting on issues,
and opening pull requests - **through the Swytchcode CLI**. You never write the
GitHub API call, the tool schema, or the auth: Swytchcode provides the tools and
WorkOS OAuth handles authorization.

The agent code is only **two Swytchcode lines**; everything else is CrewAI's own
`Agent` / `Task` / `Crew` boilerplate.

```python
swx   = Swytchcode(provider=CrewAIProvider())
tools = swx.tools.get(toolkits=["github"])
```

Switching language or framework never changes how you use Swytchcode - only the
wiring around these two lines.

> **Why Python?** CrewAI is a Python-native framework with first-class tool
> calling. There is no working CrewAI TypeScript SDK today (the `crewai` npm
> package is an empty placeholder, and `crewai-ts` has no tool-calling yet), so a
> CrewAI agent that actually executes tools must run in Python.

## How it works

```
your prompt
   -> CrewAI agent (OpenAI LLM) decides which GitHub tool to call
   -> swytchcode-runtime wraps each tool as a crewai BaseTool and forwards the call
   -> Swytchcode CLI executes the GitHub REST request using WorkOS-brokered OAuth
   -> action performed (issue created / PR opened / list returned)
```

Two credentials, two jobs: the **OpenAI key** pays for the *thinking*; **WorkOS
OAuth** authorizes the *GitHub action* - there is no GitHub token for you to
manage.

## What the agent can do

Each action below has been verified end-to-end against a live repository.

| Prompt | Swytchcode method (canonical ID) | Action |
| :--- | :--- | :--- |
| "List my repositories" | `github.user.repos.list` | Read repos |
| "Create an issue in owner/repo titled ..." | `github.repo.issues.create` | Create issue |
| "Comment on issue #1 in owner/repo ..." | `github.repo.comments.create.1` | Add issue comment |
| "Open a PR from feature-x into develop" | `github.repo.pulls.create` | Create pull request |
| "List the open PRs in owner/repo" | `github.repo.pulls.get.1` | Read pull requests |

## Prerequisites

- [Swytchcode CLI](https://swytchcode.com) installed and `swytchcode login` done
- Python **3.10+**
- An `OPENAI_API_KEY` in `.env`

## Quick start

```bash
# 1. environment
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env          # add your OPENAI_API_KEY  (cp on macOS/Linux)

# 2. one-time Swytchcode setup (run in this folder)
swytchcode init                 # editor: none | mode: PRODUCTION  (see note below)
swytchcode get github
swytchcode add method github.user.repos.list
swytchcode add method github.repo.issues.create
swytchcode add method github.repo.comments.create.1
swytchcode add method github.repo.pulls.create
swytchcode add method github.repo.pulls.get.1
swytchcode auth connect github  # WorkOS OAuth opens in your browser
swytchcode auth status          # confirm "connected"

# 3. run
python main.py                  # type a prompt, or press Enter for the default

# 4. verify
swytchcode audit                # the method you triggered should show success
```

> **Choose PRODUCTION mode at `swytchcode init`.** In sandbox/demo mode the
> provider is routed to `http://localhost`, so the real GitHub action will **not**
> happen and responses are simulated. If you ever see a `demo_mode` /
> `"_simulated": true` warning, the CLI could not resolve this project - re-run
> `swytchcode init`/`get`/`add` in this folder, or set `SWYTCHCODE_BIN` to the
> correct CLI binary.

## Policies

Swytchcode can enforce guardrails on each tool call. The five sample policies
often shown with this demo split by what the engine can enforce, because **the
policy engine evaluates each call in isolation - it keeps no memory of earlier
calls** (`policies.example.json` documents both groups).

**Enforceable (stateless - decided from the single request):**

- **Read-only** on `github.user.repos.list` and `github.repo.pulls.get.1` -
  these calls have no side effects, so they are simply allowed.
- **"PRs may only target `develop`, never `main`"** on `github.repo.pulls.create`
  - the target branch (`base`) is present on every create request, so the engine
  can allow/deny per call.

**Not enforceable as written (needs persistent state):**

- **"Max 50 issues/day"** (`github.repo.issues.create`) and **"Max 100
  comments/day"** (`github.repo.comments.create.1`) require a running per-day
  counter, which a stateless engine has no memory for. Enforcing them needs an
  external counter (e.g. a datastore the agent checks) or a Swytchcode feature
  that persists per-window counts. They are kept in `policies.example.json` under
  `illustrative_requires_state` so the intent is documented, not silently dropped.

## Files

```
github-agent-crewai-python/
  main.py                 # agent code (2 Swytchcode lines + CrewAI wiring)
  requirements.txt        # swytchcode-runtime, crewai, python-dotenv
  .env.example            # OPENAI_API_KEY placeholder
  .gitignore              # .env, .venv/, __pycache__/, .swytchcode/
  policies.example.json   # sample guardrails (see Policies above)
```

## License

MIT - see [LICENSE](./LICENSE).
