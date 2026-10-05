# CreateOS + Swytchcode starter

This is a starter template for building and running code in a [CreateOS](https://createos.sh) sandbox, using the OpenAI Agents SDK. [Swytchcode](https://www.swytchcode.com) sits between the model and the CreateOS API.

The same CreateOS methods work from JavaScript/TypeScript and other frameworks: [JavaScript runtime](https://docs.swytchcode.com/runtime-sdk/javascript/), [Anthropic SDK](https://docs.swytchcode.com/quickstarts/anthropic-sdk/), [Vercel AI SDK](https://docs.swytchcode.com/quickstarts/vercel-ai-sdk/). More are listed in the [docs](https://docs.swytchcode.com/). 

 The full agent reference is [skills.md](https://www.swytchcode.com/skills.md).

## Clone

```powershell
git clone https://github.com/swytchcodehq/swytchcode-examples
cd swytchcode-examples/swytchcode-createos-starter-template
```

Run the rest of this guide from that folder.

## What you need

- Python 3.10 or newer
- Node.js, only if you install the CLI with npm
- An OpenAI API key
- A CreateOS API key from [your CreateOS profile](https://createos.sh/app/profile)
- A Swytchcode account

The CLI binary is `swytchcode`. `swy` is the same command. Examples below use `swy`.

## 1. Install the Swytchcode CLI

Pick one.

PowerShell:

```powershell
irm https://cli.swytchcode.com/install.ps1 | iex
swy --version
```

macOS or Linux:

```bash
curl -fsSL https://cli.swytchcode.com/install.sh | sh
swy --version
```

npm, any OS:

```bash
npm install -g swytchcode
swy --version
```

## 2. Create a virtual environment

From this folder:

```powershell
python -m venv .venv
```

## 3. Activate it

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If Windows blocks the script, call the venv Python directly:

```powershell
.\.venv\Scripts\python agent.py
```

macOS or Linux:

```bash
source .venv/bin/activate
```

## 4. Install the Python packages

```powershell
pip install -r requirements.txt
```

That installs `swytchcode-runtime`, `openai-agents`, and `python-dotenv`.

## 5. Add your OpenAI key

```powershell
copy .env.example .env
```

Open `.env` and set:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

Do not commit `.env`. The CreateOS key does not go in this file. Swytchcode stores it encrypted when you connect the provider in step 8.

## 6. Sign in to Swytchcode

This is your Swytchcode account, not the CreateOS key.

```powershell
swy login
swy whoami
```

`swy login` prints a device-login URL. Add `--open` if you want the CLI to open the browser:

```powershell
swy login --open
```

The session is stored at `~/.swytchcode/auth.json`. For CI, set `SWYTCHCODE_TOKEN` in the job environment. The CLI does not load `.env` by itself.

Confirm the project is healthy:

```powershell
swy doctor
```

## 7. Install CreateOS

CreateOS is already enabled in `.swytchcode/tooling.json`. `bootstrap` downloads that bundle.

```powershell
swy bootstrap
swy list tooling
```

## 8. Connect the CreateOS API key

```powershell
swy auth connect CreateOS
```

Paste the key from [your CreateOS profile](https://createos.sh/app/profile) when asked. Confirm it:

```powershell
swy auth status
```

You should see `createos` with type `api_key_header`. The header name is `X-Api-Key`.

Check the key against CreateOS before you trust it:

```powershell
curl.exe -sS https://api.sb.createos.sh/v1/whoami -H "X-Api-Key: PASTE_KEY_HERE"
```

A valid key returns your user id. `invalid api key` means the token is not a CreateOS API key.

## 9. Add the guard policies

`swy policy add` creates `.swytchcode/integrations/policies.json` and appends each rule. You do not write that file yourself. The first command creates it.

`policies.example.json` is a reference for the file those commands produce, including `not` groups and tests. The CLI flags below add one condition per rule. Nested `not` groups are in the example file only.

```powershell
swy policy add --non-interactive `
  --name "Do not destroy CreateOS resources" `
  --id do-not-destroy-createos-resources `
  --target "fc_spawn_control_plane.*" `
  --field '$http_method' `
  --operator "==" `
  --value DELETE `
  --action POLICY_BLOCKED `
  --message "Deleting CreateOS resources is blocked in this starter." `
  --hint "Leave the sandbox running. Remove this policy before you delete a sandbox."

swy policy add --non-interactive `
  --name "Builder uses devbox" `
  --id builder-uses-devbox `
  --target fc_spawn_control_plane.sandbox.create `
  --field body.rootfs `
  --operator "!=" `
  --value devbox:1 `
  --action POLICY_BLOCKED `
  --message "This builder only creates sandboxes with rootfs devbox:1." `
  --hint "Set body.rootfs to devbox:1."

swy policy add --non-interactive `
  --name "No wipe the guest" `
  --id no-wipe-the-guest `
  --target fc_spawn_control_plane.exec.create `
  --field '$strings' `
  --operator matches `
  --value '(?i)rm\s+-rf|\bshutdown\b|\breboot\b|\bmkfs\b' `
  --action POLICY_BLOCKED `
  --message "That command would wipe or stop the sandbox." `
  --hint "Delete only the files this task created, under /tmp/build."

swy policy validate
swy policy list
```

`validate` checks the generated file.

The three rules:

| Rule | What it stops |
|---|---|
| `do-not-destroy-createos-resources` | Any CreateOS call whose HTTP method is `DELETE`, including `sandbox.delete`. |
| `builder-uses-devbox` | `sandbox.create` unless `rootfs` is `devbox:1`. |
| `no-wipe-the-guest` | An example denylist for exec arguments that match `rm -rf`, `shutdown`, `reboot`, or `mkfs`. |

`no-wipe-the-guest` is only an example. The regex does not catch other forms, such as `rm -fr`, `rm --recursive --force`, `poweroff`, or `dd`. Treat it as a starting point, not full protection.

Prove a block without spending a sandbox. CreateOS is never called. The reply category is `policy_denied`.

```powershell
'{"params":{"id":"sb_example"}}' | swy exec fc_spawn_control_plane.sandbox.delete --json
```

```powershell
'{"body":{"shape":"s-1vcpu-1gb","rootfs":"desktop:1"}}' | swy exec fc_spawn_control_plane.sandbox.create --json
```

After a block:

```powershell
swy audit policy
```

## 10. Run the agent

```powershell
python agent.py
```

## Add another policy

`swy policy add` writes `.swytchcode/integrations/policies.json`. One command, one condition. `policies.example.json` is a reference for that generated file.

```powershell
swy policy add
swy policy list
swy policy validate
swy policy remove POLICY_ID
swy audit policy
```

Schema and more rules: [policies.json](https://docs.swytchcode.com/configuration/policy-json/). [How to set up policy guardrails](https://www.swytchcode.com/blogs/how-to-set-up-policy-guardrails-for-ai-agents-with-swytchcode).

## Further reading

- [skills.md](https://www.swytchcode.com/skills.md)
- [OpenAI Agents quickstart](https://docs.swytchcode.com/quickstarts/openai-sdk/)
- [What is an execution layer](https://www.swytchcode.com/blogs/what-is-an-execution-layer-why-ai-agents-need-one)
- [tooling.json, manifest.json, and policies.json](https://www.swytchcode.com/blogs/tooling-json-manifest-json-and-policies-json-explained-swytchcode-s-config-files)
- [swy exec](https://www.swytchcode.com/blogs/swy-exec-explained-inputs-outputs-and-exit-codes)
- [Connect Swytchcode to the OpenAI Agents SDK](https://www.swytchcode.com/blogs/connect-swytchcode-to-the-openai-agents-sdk-setup-guide-and-example)
- [AI agent posts](https://www.swytchcode.com/blogs/ai-agents)
