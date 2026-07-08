# ⭐ GitHub Star Agent (TypeScript)

An AI agent that stars a GitHub repository — with **zero credential wrangling**.

The agent gets one instruction ("star the repo") and a single [Swytchcode](https://swytchcode.com)
tool. It decides to call the tool; Swytchcode runs the real GitHub API call
(`PUT /user/starred/{owner}/{repo}`).

Built with the **OpenAI Agents SDK** (`@openai/agents`) + **Swytchcode**, with
premium terminal output courtesy of [`chalk`](https://github.com/chalk/chalk) and
[`ora`](https://github.com/sindresorhus/ora).

## ✨ The magic: no tokens in your code

Look through [`index.ts`](./index.ts) — there is **no GitHub token** anywhere, and
none in your `.env` either. Thanks to Swytchcode's credential system (ENGG-159),
you connect a provider **once** and every run just works:

```bash
swytchcode auth connect github
```

That stores your GitHub credential **encrypted, locally** (`~/.swytchcode/credentials.db`).
At execution time Swytchcode resolves it automatically and injects it into the
GitHub call. If you run the agent without connecting first, you get a clean,
actionable message — *"Missing credentials for github — run `swytchcode auth connect github`"* —
instead of a raw `401`.

## Prerequisites

- Node.js 18+
- The Swytchcode CLI on your `PATH`: `npm install -g swytchcode`
- An OpenAI API key (the agent's brain)

## Setup

```bash
npm install
cp .env.example .env            # then add your OPENAI_API_KEY
swytchcode auth connect github  # one-time; no token goes in your code
```

## Run

```bash
npm start        # runs: tsx index.ts
```

(You can also type-check without running: `npm run typecheck`.)

## What's under the hood

| Piece | Value |
| --- | --- |
| Agent framework | OpenAI Agents SDK (`@openai/agents`) |
| Tool runtime | `swytchcode-runtime` (`Swytchcode` + `OpenAIAgentsProvider`) |
| Canonical ID | `user.starred.update` → `PUT /user/starred/{owner}/{repo}` |
| Auth | Resolved by Swytchcode from its encrypted local store (ENGG-159) |

The activated tool lives in [`.swytchcode/tooling.json`](./.swytchcode/tooling.json);
the GitHub integration bundle is vendored under `.swytchcode/integrations/` so the
example is self-contained.

## License

MIT
