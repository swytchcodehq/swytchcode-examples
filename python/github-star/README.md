# ⭐ GitHub Star Agent (Python)

An AI agent that stars a GitHub repository — with **zero credential wrangling**.

The agent gets one instruction ("star the repo") and a single [Swytchcode](https://swytchcode.com)
tool. It decides to call the tool; Swytchcode runs the real GitHub API call
(`PUT /user/starred/{owner}/{repo}`).

Built with the **OpenAI Agents SDK** + **Swytchcode**.

## ✨ The magic: no tokens in your code

Look through [`main.py`](./main.py) — there is **no GitHub token** anywhere, and
none in your `.env` either. Thanks to Swytchcode's credential system (ENGG-159),
you connect a provider **once** and every run just works:

```bash
swytchcode auth connect github
```

That stores your GitHub credential **encrypted, locally** (`~/.swytchcode/credentials.db`).
At execution time Swytchcode resolves it automatically and injects it into the
GitHub call. If you ever run the agent without connecting first, you get a clean,
actionable message — *"Missing credentials for github — run `swytchcode auth connect github`"* —
instead of a raw `401`.

> Running `swytchcode exec user.starred.update` directly in a terminal is even
> smoother: the CLI pauses and offers to connect GitHub **inline**, then continues.

## Prerequisites

- Python 3.10+
- The Swytchcode CLI on your `PATH`: `npm install -g swytchcode`
- An OpenAI API key (the agent's brain)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then add your OPENAI_API_KEY
swytchcode auth connect github   # one-time; no token goes in your code
```

## Run

```bash
python main.py
```

You'll see the agent load its Swytchcode tool, reason about the request, call the
star tool, and confirm — with tidy terminal output courtesy of [`rich`](https://github.com/Textualize/rich).

## What's under the hood

| Piece | Value |
| --- | --- |
| Agent framework | OpenAI Agents SDK (`openai-agents`) |
| Tool runtime | `swytchcode-runtime` (`Swytchcode` + `OpenAIAgentsProvider`) |
| Canonical ID | `user.starred.update` → `PUT /user/starred/{owner}/{repo}` |
| Auth | Resolved by Swytchcode from its encrypted local store (ENGG-159) |

The activated tool lives in [`.swytchcode/tooling.json`](./.swytchcode/tooling.json);
the GitHub integration bundle is vendored under `.swytchcode/integrations/` so the
example is self-contained.

## License

MIT
