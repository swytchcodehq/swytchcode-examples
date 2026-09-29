/**
 * Gmail assistant - Anthropic SDK (TypeScript), agentic mode.
 *
 * Uses the swytchcode-runtime agentic API (Swytchcode + AnthropicProvider).
 * The Swytchcode part is two lines; this file runs the tool-use loop.
 *
 * Prereqs (run once in this folder):
 *   swytchcode init
 *   swytchcode get gmail
 *   swytchcode add method gmail.user.messages.get
 *   swytchcode add method gmail.user.send.create1
 *   swytchcode add method gmail.user.modify.create
 *   swytchcode add method gmail.user.drafts.create
 *   swytchcode auth connect gmail
 */
import "dotenv/config";
import * as readline from "node:readline/promises";
import Anthropic from "@anthropic-ai/sdk";
import { Swytchcode, TOOL_USE_INSTRUCTIONS } from "@swytchcode/runtime";
import { AnthropicProvider } from "@swytchcode/runtime/providers/anthropic";

// Swytchcode: two lines to retrieve tools
const swx = new Swytchcode(new AnthropicProvider());
const tools = await swx.tools.get({ toolkits: ["gmail"] });

const anthropic = new Anthropic();
const MODEL = "claude-sonnet-5";

const SYSTEM_PROMPT = `${TOOL_USE_INSTRUCTIONS}

You are a Gmail assistant acting on the connected account - always pass userId: "me" to every Gmail tool.`;

const MAX_TOOL_TURNS = 12;

async function runAgent(prompt: string): Promise<void> {
  const messages: Anthropic.MessageParam[] = [{ role: "user", content: prompt }];

  for (let turn = 0; turn < MAX_TOOL_TURNS; turn++) {
    const response = await anthropic.messages.create({
      model: MODEL,
      max_tokens: 2048,
      thinking: { type: "disabled" },
      system: SYSTEM_PROMPT,
      tools,
      messages,
    });

    messages.push({ role: "assistant", content: response.content });

    if (response.stop_reason !== "tool_use") {
      const text = response.content.find((b) => b.type === "text")?.text;
      console.log(text || `(stopped: ${response.stop_reason})`);
      return;
    }

    const results = await swx.handleToolCalls(response);
    messages.push({ role: "user", content: results as Anthropic.ToolResultBlockParam[] });
  }

  throw new Error(`Stopped after ${MAX_TOOL_TURNS} tool-use turns.`);
}

const DEFAULT_PROMPT = "List the last 10 emails in my inbox.";
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const userInput = (await rl.question(`Prompt [${DEFAULT_PROMPT}]: `)).trim();
rl.close();

await runAgent(userInput || DEFAULT_PROMPT);
