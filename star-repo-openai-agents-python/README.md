# Star Repo Agent — OpenAI Agents SDK (Python)

Minimal example showing an AI agent star a GitHub repository
(`github.com/swytchcodehq/swytchcode-examples`) by calling the GitHub API
**through the Swytchcode CLI**. You never write the GitHub API call, the tool
schema, or the auth — Swytchcode provides the tool and handles GitHub
authorization via WorkOS OAuth.

The agent code is only two Swytchcode lines; everything else is the agent
framework's own boilerplate.

## How it works

```
your prompt
   -> LLM (via the agent SDK) decides to call the GitHub tool
   -> swytchcode-runtime forwards the call
   -> Swytchcode CLI executes the GitHub API request
      using WorkOS-brokered OAuth
   -> repo starred
```

Two credentials, two jobs: the LLM API key pays for the *thinking*; WorkOS OAuth
authorizes the *GitHub action* (no GitHub token to manage yourself).

## Prerequisites

- [Swytchcode CLI](https://swytchcode.com) installed and `swytchcode login` done
- Python 3.10+
- An `OPENAI_API_KEY` in `.env`

## Quick start

```bash
# 1. environment
python -m venv .venv && .venv\Scripts\activate     # Windows (.venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
cp .env.example .env                                # add your OPENAI_API_KEY

# 2. one-time Swytchcode setup
swytchcode init                                     # editor: none | mode: production
swytchcode get github
swytchcode add method github.user.starred.update
swytchcode auth connect github                      # WorkOS OAuth in your browser

# 3. run
python main.py
```

Type a prompt (or press Enter for the default) and the agent stars the repo.

## Notes

- Use **production** mode at `swytchcode init` — sandbox won't perform the real call.
- The `.swytchcode/` project state and your `.env` are gitignored; regenerate the
  former with the `init` / `get` / `add` commands above.
