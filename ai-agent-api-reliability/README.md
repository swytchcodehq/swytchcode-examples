# AI Agent API Reliability

An engineering demonstration of what can go wrong when an application or AI agent interacts with a production API.

The project starts with a deliberately fragile GitHub API integration that reports success even when the request fails. It then exposes the real API response and finishes with a Gemini-powered agent using Swytchcode as the execution layer for a controlled GitHub operation.

The central question is not simply:

> Can an AI agent call an API?

It is:

> How do we know what the agent requested, what actually executed, whether the action was allowed, what the API returned, and whether the external state actually changed?

---

## Why This Project Exists

A local success message is not proof that a production API operation succeeded.

In a real integration, failures can come from authentication, permissions, API changes, incorrect inputs, network issues, or the API returning a result that the application does not correctly interpret.

This project demonstrates that problem using a deliberately small GitHub starring example:

1. `naive.py` makes a GitHub API request, hides any exception, and prints success unconditionally.
2. `naive_check.py` performs the same request but inspects GitHub's actual response, exposing the `401 Unauthorized` failure.
3. The controlled agent example gives Gemini access to an explicitly enabled GitHub action.
4. Swytchcode performs the authenticated API operation and returns the result to the agent.
5. `swy audit network` provides an execution history that can be inspected afterward.

The goal is to make the difference between **reported success** and **verified execution** visible.

---

## Demonstration Scenario

The example uses a GitHub repository-star operation because it is a simple external side effect that can be verified independently.

### Naive approach

```text
Application
    |
    v
GitHub API
    |
    +----> Request fails
    |
    v
Exception is swallowed
    |
    v
"Done! Starred..."
```

The application reports success even though the external operation did not succeed.

### Controlled agent approach

```text
User instruction
       |
       v
     Gemini
       |
       v
  Tool request
       |
       v
Swytchcode runtime
       |
       v
   GitHub API
       |
       v
Execution result
       |
       v
     Gemini
```

Gemini decides which available action to request. The execution layer performs the authenticated API operation and returns its result.

---

## Repository Structure

```text
ai-agent-api-reliability/
│
├── README.md
├── .gitignore
│
├── naive-api-failure/
│   ├── naive.py
│   └── naive_check.py
│
└── swytchcode-agent/
    ├── main.py
    └── .env.example
```

The working environment also contains local-only files such as:

```text
swytchcode-agent/
├── .env
├── venv/
└── .swytchcode/
```

These are intentionally excluded from version control.

- `.env` contains local secrets.
- `venv/` contains the local Python virtual environment.
- `.swytchcode/` contains local Swytchcode project/integration state.

---

## Naive API Failure

The `naive-api-failure` directory demonstrates the initial reliability problem.

### `naive.py`

The script constructs a PUT request to GitHub's starred-repository endpoint for:

```text
octocat/Hello-World
```

The implementation intentionally:

- uses a nonfunctional demonstration token
- makes the HTTP request
- suppresses the exception
- prints a success message regardless of the result

The important failure is not that the API rejected the request.

The important failure is that the application hid the rejection and reported success anyway.

**Run**

```bash
cd naive-api-failure
python3 naive.py
```

The demonstration prints a success message even though the GitHub operation did not actually succeed.

### `naive_check.py`

`naive_check.py` performs the same request but actually inspects GitHub's response.

Instead of discarding the error, it reports the HTTP status and response body.

In the demonstrated setup, the intentionally invalid credential results in:

```text
401 Unauthorized
```

with a bad-credentials response from GitHub.

**Run**

```bash
python3 naive_check.py
```

This makes the difference clear:

```text
naive.py
    -> "Done!"

naive_check.py
    -> 401 Unauthorized
```

### Important security note

The token value in these demonstration scripts is intentionally nonfunctional.

It is not a real GitHub credential.

Do not replace the demonstration value with a real credential and commit it to the repository.

If you need to test authenticated GitHub requests locally, use a secure credential-handling approach rather than embedding a real token directly in source code.

---

## Controlled AI-Agent Demonstration

The `swytchcode-agent` directory contains the AI-agent portion of the project.

The agent uses:

- Gemini for reasoning and tool selection
- Swytchcode as the execution layer
- GitHub as the production API

The important separation is:

```text
Gemini
  |
  | decides what action to request
  v
Swytchcode
  |
  | performs the authenticated operation
  v
GitHub
```

The GitHub credential is handled by the execution layer rather than being passed to Gemini as model input.

This repository demonstrates a constrained tool-access pattern. It is not intended to claim that any single framework provides a universal solution to AI-agent security or reliability.

### Tool Access

The GitHub integration contains multiple starred-repository operations.

For this demonstration, the project explicitly enables:

```text
github.starred.update
```

The available tool names can be checked with:

```bash
swy list | grep starred
```

The specific action is then enabled with:

```bash
swy add method github.starred.update
```

This distinction is important:

```text
GitHub integration downloaded
        |
        v
Available actions discovered
        |
        v
Specific action explicitly enabled
        |
        v
Agent can request the enabled action
```

The agent is therefore not automatically given unrestricted access to every GitHub operation.



### Prerequisites
- Python 3.10+
- Node.js and npm
- A Gemini API key
- A GitHub account with permission to manage starred repositories
- Swytchcode CLI
- Network access to GitHub and Gemini


### Swytchcode Setup

Initialize the Swytchcode project from the `swytchcode-agent` directory:

```bash
cd swytchcode-agent
swy init
```

Then retrieve the GitHub integration:

```bash
swy get github
```

Check which starred-repository actions are available:

```bash
swy list | grep starred
```

Enable the action used by this project:

```bash
swy add method github.starred.update
```

GitHub authorization is handled separately:

```bash
swy auth connect github
```

Authentication is performed through GitHub's normal authorization flow. The project does not place the GitHub credential in `main.py` or in the Gemini prompt.

### Preview the API Operation

Before making the live request, the operation can be previewed with:

```bash
swy exec github.starred.update \
  --param owner=octocat \
  --param repo=Hello-World \
  --explain
```

The preview shows the intended operation without making the real API request.

This provides a useful inspection step before executing an external side effect.

### Execute the GitHub Operation

The same operation can then be executed for real:

```bash
swy exec github.starred.update \
  --param owner=octocat \
  --param repo=Hello-World
```

The demonstrated successful GitHub response is:

```text
204
```

The result can then be verified independently by querying the repository's starred state or checking GitHub directly.

For example:

```bash
swy exec github.starred.get \
  --param owner=octocat \
  --param repo=Hello-World
```

### Gemini Configuration

The agent uses a Gemini API key stored in a local `.env` file.

The repository includes:

```text
swytchcode-agent/.env.example
```

Create your local environment file:

```bash
cd swytchcode-agent
cp .env.example .env
```

Then set:

```text
GEMINI_API_KEY=your_gemini_api_key_here
```

Do not commit `.env`.

The application loads the environment file using `python-dotenv`.

### Python Environment

Create the local virtual environment:

```bash
cd swytchcode-agent
python3 -m venv venv
```

Install the dependencies used by `main.py`:

```bash
./venv/bin/pip install swytchcode-runtime google-genai python-dotenv
```

The main dependencies are:

- `swytchcode-runtime`
- `google-genai`
- `python-dotenv`

### How `main.py` Works

`main.py` connects Gemini's function-calling interface to the GitHub tools provided by the Swytchcode runtime.

At a high level:

```text
User instruction
       |
       v
Gemini receives the available tool definitions
       |
       v
Gemini requests an action
       |
       v
Swytchcode executes the action
       |
       v
GitHub returns a result
       |
       v
Result is returned to Gemini
```

One of the important execution boundaries in the code is:

```python
result = tool.execute(args)
```

This is where a selected tool request is handed to the execution layer.

The model can decide which available operation it wants to request, but the authenticated external operation is performed through the runtime.

### Running the Agent

From `swytchcode-agent/`:

```bash
./venv/bin/python main.py "Star the octocat/Hello-World repo for me"
```

The agent can also handle another repository request:

```bash
./venv/bin/python main.py "Can you go star facebook/react for me?"
```

During execution, the application shows the tool request, the execution result, and the model's final response.

The exact model response can vary depending on the model version, repository state, credentials, and API response.

### Resetting the Demonstration State

For repeatable testing, the repository can be returned to a known state by removing the star and checking the result:

```bash
swy exec github.starred.delete \
  --param owner=octocat \
  --param repo=Hello-World
```

Then:

```bash
swy exec github.starred.get \
  --param owner=octocat \
  --param repo=Hello-World
```

A `404` response confirms that the repository is not currently starred.

This makes it possible to verify the agent's effect before and after execution.

### Verification and Audit

The final demonstration step is:

```bash
swy audit network
```

The audit is used to inspect the network/API execution history and distinguish requested actions from actual execution results when the information is available.

This is particularly important for agent-based systems because the model's response alone should not be treated as proof that an external operation happened.

The audit trail provides another source of evidence for what was actually executed.

---

## Reliability Lessons

The project illustrates several practical lessons for production API and AI-agent integrations.

**1. Do not swallow API failures**

An exception that disappears is an observability problem.

An application should not print a success message simply because execution reached the end of a function.

**2. Check the actual API response**

A request should be considered successful only after the returned result is checked and interpreted correctly.

**3. Separate decision-making from execution**

An AI model can decide which action it wants to take without directly holding the production API credential or directly implementing the API call.

**4. Restrict available actions**

Agents should only receive access to the operations required for the task.

In this demonstration, the project explicitly enables:

```text
github.starred.update
```

rather than exposing every possible GitHub operation.

**5. Keep credentials out of source code and model input**

Production credentials should be handled through a secure execution environment rather than embedded directly in application source or model prompts.

**6. Make execution observable**

A useful system should make it possible to answer:

- What did the agent request?
- What was actually executed?
- Was the action allowed?
- What did the API return?
- Did the external state change?
- Can the execution be inspected afterward?

---

## Security Considerations

Never commit credentials to this repository.

The repository intentionally ignores:

```text
.env
venv/
.venv/
.swytchcode/
```

The demonstration token in the naive scripts is intentionally nonfunctional.

For real integrations:

- keep API keys and access tokens outside source control
- use the minimum permissions required
- avoid passing production credentials to an LLM
- review the operations made available to an agent
- verify externally visible side effects rather than trusting model-generated success messages

---

## Key Takeaway

The difficult part of an AI/API integration is not simply getting an AI model to call an endpoint.

The difficult part is making the execution path understandable and verifiable.

At the beginning of this demonstration:

```text
API fails
   |
   v
error is swallowed
   |
   v
"Done!"
```

At the end:

```text
User request
   |
   v
Model decision
   |
   v
Controlled execution
   |
   v
Real API result
   |
   v
Verification
   |
   v
Audit trail
```

The difference is the ability to distinguish what the system said happened from what actually happened.

---

## Demo

This repository accompanies a technical demonstration showing the failure mode, investigation, controlled agent execution, and final audit trail.



---

## License

No license is currently specified for this repository.