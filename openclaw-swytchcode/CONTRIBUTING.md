# Contributing to OpenClaw × Swytchcode Demo

Thanks for your interest in contributing! This is a demo repo showing how OpenClaw and Swytchcode work together.

---

## Ways to contribute

- Add new issue classification types in `classifier.go`
- Add new comment templates in `templates.go`
- Use `swytchcode search` to find additional GitHub tools to integrate
- Improve the local keyword fallback classifier
- Add support for other issue trackers (GitLab, Jira)

---

## Getting started

1. Fork the repo
2. Clone your fork
3. Follow the setup steps in [README.md](./README.md)
4. Make your changes
5. Test on a **private repo with seeded fake issues** — never test on public repos
6. Open a PR with a clear description of what you changed and why

---

## Guidelines

- **Never test automation on public repos** — always use a private test repo first
- Keep the max comments per run at 5 or below
- All API calls must go through `swytchcode exec` — never call GitHub API directly
- New issue types need both a classifier entry in `classifier.go` and a template in `templates.go`
- The bot must never crash — add fallbacks for any new MCP calls

---

## Project structure

```
main.go        # Entry point — orchestrates fetch → classify → comment → log
classifier.go  # Add new issue types here
commenter.go   # GitHub API calls via swytchcode exec
templates.go   # Add new comment templates here
logger.go      # CSV logging — do not modify
```

---

## Questions?

Open an issue or reach out via [swytchcode.com](https://cli.swytchcode.com).
