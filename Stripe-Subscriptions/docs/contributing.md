# Contributing

## Prerequisites

- Node.js >= 20
- npm >= 10
- Swytchcode CLI installed and authenticated (`swytchcode login`)
- Stripe CLI for local webhook testing

## Workflow

1. Fork / branch from `main`.
2. Install: `npm install`.
3. Set up env: `cp .env.example .env` and fill in credentials.
4. For any new Stripe integration call:
   - `swytchcode search` → find the integration
   - `swytchcode get stripe` if not already added
   - `swytchcode add <canonical_id>` to enable the method/workflow
   - `swytchcode info <canonical_id>` to inspect the contract
   - Generate code that delegates to the Swytchcode runtime
5. Add or update tests in the relevant service.
6. Run `npm run typecheck && npm run lint && npm run test` before opening a PR.

## Commit style

Conventional commits — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.

## Adding a new service

1. Create `services/<name>/` with its own `package.json` and `tsconfig.json` extending `tsconfig.base.json`.
2. Register the service in [service-index.md](service-index.md).
3. Add an example wiring under `examples/` if the service exposes HTTP routes.
