"""
Star a GitHub repository with an AI agent — powered by Swytchcode.

The agent is given ONE instruction ("star the repo") and ONE tool: a thin wrapper
around Swytchcode's `exec`. The agent decides to call it; Swytchcode runs the real
GitHub API call (PUT /user/starred/{owner}/{repo}).

The magic (ENGG-159): notice there is NO GitHub token anywhere in this file.
Swytchcode resolves the credential at execution time from its encrypted local
store. Connect once with `swytchcode auth connect github` and every run "just
works" — no secrets in code, no secrets in your environment.
"""
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

# The published Swytchcode runtime exposes `exec`, which shells out to the
# Swytchcode CLI to run a canonical tool. We wrap it as a native agent tool below.
from swytchcode_runtime import exec as swytchcode_exec

# OpenAI Agents SDK (pip install openai-agents).
from agents import Agent, Runner, function_tool

load_dotenv()
console = Console()

# The repository the agent will star (override via .env if you like).
TARGET_OWNER = os.environ.get("TARGET_REPO_OWNER", "swytchcode")
TARGET_REPO = os.environ.get("TARGET_REPO_NAME", "swytchcode-examples")

# The Swytchcode canonical tool: "star a repo for the authenticated user".
STAR_TOOL = "user.starred.update"


@function_tool
def star_github_repo(owner: str, repo: str) -> str:
    """Star a GitHub repository for the authenticated user.

    Args:
        owner: The repository owner or organization (e.g. "swytchcode").
        repo: The repository name (e.g. "swytchcode-examples").
    """
    # No Authorization is passed — Swytchcode injects the GitHub credential from
    # its encrypted local store at execution time (see `swytchcode auth connect github`).
    swytchcode_exec(STAR_TOOL, {"owner": owner, "repo": repo})
    return f"Successfully starred {owner}/{repo}."


def preflight() -> None:
    """Fail early, and kindly, if the one required key is missing."""
    if not os.environ.get("OPENAI_API_KEY"):
        console.print(
            Panel(
                Text.from_markup(
                    "[bold red]OPENAI_API_KEY is not set.[/]\n\n"
                    "The agent needs it to think. Add it to a [bold].env[/] file "
                    "(see [bold].env.example[/]) or export it, then re-run.\n\n"
                    "You do [bold]not[/] need a GitHub token — Swytchcode handles that.",
                ),
                title="Missing OpenAI key",
                border_style="red",
            )
        )
        sys.exit(1)


def banner() -> None:
    console.print()
    console.print(
        Panel(
            Text.from_markup(
                "[bold]⭐ GitHub Star Agent[/]\n"
                "[dim]An AI agent stars a repo using one Swytchcode tool.[/]\n\n"
                f"Target  : [cyan]{TARGET_OWNER}/{TARGET_REPO}[/]\n"
                f"Tool    : [magenta]{STAR_TOOL}[/]  [dim](PUT /user/starred/…)[/]\n"
                "Secrets : [green]none in this file[/] — resolved by Swytchcode at runtime",
            ),
            border_style="yellow",
            title="Swytchcode × OpenAI Agents",
            subtitle="powered by swytchcode-runtime",
        )
    )


def main() -> int:
    preflight()
    banner()

    agent = Agent(
        name="GitHub Star Agent",
        instructions=(
            "You are a concise assistant that manages GitHub via provided tools. "
            "When asked to star a repository, call the star_github_repo tool with the "
            "correct owner and repo, then confirm in one short sentence. Do not ask for "
            "tokens or credentials — they are handled outside of you."
        ),
        tools=[star_github_repo],
    )

    prompt = (
        f"Star the {TARGET_OWNER}/{TARGET_REPO} repository on GitHub using your "
        f"available tools. The owner is '{TARGET_OWNER}' and the repo is '{TARGET_REPO}'."
    )
    console.print(Rule("[dim]agent[/]"))
    console.print(f"[dim]prompt →[/] {prompt}\n")

    # If GitHub isn't connected yet, Swytchcode returns a clear, actionable error
    # ("missing credentials for github — run `swytchcode auth connect github`")
    # instead of a raw 401. It surfaces here as a tool error.
    try:
        with console.status("[bold cyan]Agent is thinking and acting…", spinner="earth"):
            result = Runner.run_sync(agent, prompt)
    except Exception as exc:  # noqa: BLE001 — surface any failure cleanly to the user
        console.print(
            Panel(
                Text.from_markup(
                    f"[red]{exc}[/]\n\n"
                    "If this mentions missing credentials, connect GitHub once:\n"
                    "  [bold]swytchcode auth connect github[/]",
                ),
                title="Run failed",
                border_style="red",
            )
        )
        return 1

    console.print()
    console.print(
        Panel(
            Text.from_markup(
                f"[bold green]Done![/]\n\n{result.final_output}\n\n"
                f"[dim]View it:[/] https://github.com/{TARGET_OWNER}/{TARGET_REPO}/stargazers",
            ),
            title="⭐ Repository starred",
            border_style="green",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
