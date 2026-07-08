/**
 * Star a GitHub repository with an AI agent — powered by Swytchcode.
 *
 * The agent gets one instruction ("star the repo") and one tool: a thin wrapper
 * around Swytchcode's `exec`. It decides to call the tool; Swytchcode runs the
 * real GitHub API call (PUT /user/starred/{owner}/{repo}).
 *
 * The magic (ENGG-159): there is NO GitHub token in this file or your env.
 * Swytchcode resolves the credential at execution time from its encrypted local
 * store. Connect once with `swytchcode auth connect github` and every run works.
 */
import "dotenv/config";
import chalk from "chalk";
import ora from "ora";
import { z } from "zod";
import { Agent, run, tool } from "@openai/agents";
import { exec } from "swytchcode-runtime";

const TARGET_OWNER = process.env.TARGET_REPO_OWNER ?? "swytchcode";
const TARGET_REPO = process.env.TARGET_REPO_NAME ?? "swytchcode-examples";

// The Swytchcode canonical tool: "star a repo for the authenticated user".
const STAR_TOOL = "user.starred.update";

// Wrap Swytchcode's `exec` as a native OpenAI Agents tool. No Authorization is
// passed — Swytchcode injects the GitHub credential from its encrypted local
// store at execution time (see `swytchcode auth connect github`).
const starGithubRepo = tool({
  name: "star_github_repo",
  description: "Star a GitHub repository for the authenticated user.",
  parameters: z.object({
    owner: z.string().describe('Repository owner or org, e.g. "swytchcode".'),
    repo: z.string().describe('Repository name, e.g. "swytchcode-examples".'),
  }),
  execute: async ({ owner, repo }) => {
    await exec(STAR_TOOL, { owner, repo });
    return `Successfully starred ${owner}/${repo}.`;
  },
});

function banner(): void {
  const line = chalk.yellow("─".repeat(58));
  console.log(`\n${line}`);
  console.log(`${chalk.bold.yellow("  ⭐ GitHub Star Agent")}   ${chalk.dim("Swytchcode × OpenAI Agents")}`);
  console.log(`  ${chalk.dim("An AI agent stars a repo using one Swytchcode tool.")}`);
  console.log("");
  console.log(`  ${chalk.bold("Target ")} : ${chalk.cyan(`${TARGET_OWNER}/${TARGET_REPO}`)}`);
  console.log(`  ${chalk.bold("Tool   ")} : ${chalk.magenta(STAR_TOOL)} ${chalk.dim("(PUT /user/starred/…)")}`);
  console.log(`  ${chalk.bold("Secrets")} : ${chalk.green("none in this file")} ${chalk.dim("— resolved by Swytchcode at runtime")}`);
  console.log(`${line}\n`);
}

async function main(): Promise<void> {
  if (!process.env.OPENAI_API_KEY) {
    console.error(chalk.red.bold("OPENAI_API_KEY is not set."));
    console.error(
      chalk.dim(
        "The agent needs it to think. Add it to a .env file (see .env.example).\n" +
          "You do NOT need a GitHub token — Swytchcode handles that.",
      ),
    );
    process.exit(1);
  }

  banner();

  const agent = new Agent({
    name: "GitHub Star Agent",
    instructions:
      "You are a concise assistant that manages GitHub via provided tools. When " +
      "asked to star a repository, call the star_github_repo tool with the correct " +
      "owner and repo, then confirm in one short sentence. Do not ask for tokens or " +
      "credentials — they are handled outside of you.",
    tools: [starGithubRepo],
  });

  const prompt =
    `Star the ${TARGET_OWNER}/${TARGET_REPO} repository on GitHub using your available ` +
    `tools. The owner is '${TARGET_OWNER}' and the repo is '${TARGET_REPO}'.`;
  console.log(chalk.dim(`prompt → ${prompt}\n`));

  // If GitHub isn't connected, Swytchcode returns a clear, actionable error
  // ("missing credentials for github — run `swytchcode auth connect github`")
  // instead of a raw 401. It surfaces here as a tool error.
  const thinking = ora({ text: chalk.cyan("Agent is thinking and acting…"), spinner: "earth" }).start();
  try {
    const result = await run(agent, prompt);
    thinking.succeed(chalk.green("Agent finished"));
    console.log("");
    console.log(chalk.green.bold("⭐ Repository starred"));
    console.log(chalk.white(String(result.finalOutput ?? "")));
    console.log(chalk.dim(`View it: https://github.com/${TARGET_OWNER}/${TARGET_REPO}/stargazers`));
  } catch (err) {
    thinking.fail(chalk.red("Run failed"));
    console.error(chalk.red(err instanceof Error ? err.message : String(err)));
    console.error(chalk.dim("If this mentions missing credentials, connect GitHub once:"));
    console.error(chalk.bold("  swytchcode auth connect github"));
    process.exitCode = 1;
  }
}

void main();
