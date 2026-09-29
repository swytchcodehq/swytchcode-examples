import { Agent, run, setTracingDisabled, type AgentInputItem } from "@openai/agents";
import { Swytchcode } from "@swytchcode/runtime";
import { OpenAIAgentsProvider } from "@swytchcode/runtime/providers/openai-agents";

// The agent replaces the old rule-based parser: the model reads the message and
// decides which Swytchcode method(s) to call. `@openai/agents` runs the
// tool-use loop; `OpenAIAgentsProvider` turns each enabled method into a tool
// whose `execute` shells out to `swytchcode exec`.

setTracingDisabled(true); // no OpenAI trace uploads for a local demo

/**
 * Canonical IDs enabled in .swytchcode/tooling.json that the agent may call.
 * Destructive Calendar methods (calendar.event.delete, calendar.clear.create, ...)
 * are deliberately absent here AND blocked by the `no-calendar-deletes` guard in
 * .swytchcode/integrations/policies.json, so adding one back later still fails.
 */
const ENABLED_TOOLS = [
  "gmail.user.profile.get",
  "gmail.user.messages.get",
  "gmail.user.messages.get1",
  "gmail.user.send.create1",
  "gmail.user.drafts.create",
  "calendar.me.calendarList.list",
  "calendar.event.get",
  "calendar.event.get1",
  "calendar.event.create",
  "calendar.event.quickAdd.create",
];

let agentPromise: Promise<Agent> | null = null;

async function build(): Promise<Agent> {
  const swx = new Swytchcode(new OpenAIAgentsProvider());
  const tools = await swx.tools.get({ tools: ENABLED_TOOLS });

  const today = new Date().toLocaleDateString("en-CA");
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

  const instructions = [
    "You act on the user's connected Google account through the provided tools.",
    "",
    "WHAT YOU CAN DO, and nothing else:",
    "- Read and search Gmail messages.",
    "- Read Google Calendar events.",
    "- Create a NEW calendar event when the user clearly asks to add/schedule one.",
    "",
    "WHAT YOU CANNOT DO: delete, cancel, move, reschedule, or edit any event or",
    "email; empty a calendar; change settings; send email unless the user explicitly",
    "asks you to send one. You have no tools for these. If the user asks for any of",
    "them, reply in one sentence that you cannot do it and stop. Do NOT try a",
    "workaround, and NEVER create an event to represent a deletion or cancellation.",
    "",
    "RULES:",
    '- Always pass userId "me" to Gmail tools and calendarId "primary" to Calendar tools.',
    `- Today is ${today} (${tz}). Resolve relative dates ("tomorrow", "next Friday", "this week") against that.`,
    "- Only call calendar.event.create / calendar.event.quickAdd.create when the user",
    "  is asking to add a genuinely new event. The event title must be the user's",
    "  event name, never a phrase like \"delete ...\" or \"cancel ...\".",
    "- Gmail search: put Gmail query syntax in the q parameter, e.g. `is:unread from:stripe newer_than:7d`.",
    "- When listing emails, fetch each message's metadata so you can show sender, subject and date.",
    "- Do not call the same tool twice with basically the same arguments. If a tool",
    "  fails or is blocked by policy, report what it said and stop. Never retry in a loop.",
    "- If a tool result mentions missing credentials, tell the user to run the matching",
    "  `swytchcode auth connect` command, then stop.",
    "- Keep answers short. Light markdown only: `- ` bullets, `**bold**` for a title.",
    "  Never invent data a tool did not return.",
  ].join("\n");

  return new Agent({
    name: "Gmail + Calendar assistant",
    model: process.env.OPENAI_MODEL || "gpt-4o-mini",
    instructions,
    tools,
  });
}

function getAgent(): Promise<Agent> {
  if (!agentPromise) {
    agentPromise = build().catch((err) => {
      agentPromise = null; // let the next request retry the build
      throw err;
    });
  }
  return agentPromise;
}

export type ChatTurn = { reply: string; history: AgentInputItem[]; toolsUsed: string[] };

export async function chat(history: AgentInputItem[], message: string): Promise<ChatTurn> {
  const agent = await getAgent();

  let result;
  try {
    result = await run(agent, [...history, { role: "user", content: message }], { maxTurns: 8 });
  } catch (err) {
    // The SDK throws MaxTurnsExceeded if the model keeps calling tools without
    // settling on an answer. Surface it plainly instead of a raw stack.
    if (err instanceof Error && /max turns/i.test(err.message)) {
      return {
        reply:
          "I couldn't complete that in a reasonable number of steps and stopped. " +
          "If you were asking me to delete or change something, I can't do that here.",
        history,
        toolsUsed: [],
      };
    }
    throw err;
  }

  const toolsUsed = Array.from(
    new Set(
      result.newItems
        .filter((i) => i.type === "tool_call_item")
        .map((i) => (i as { rawItem?: { name?: string } }).rawItem?.name)
        .filter((n): n is string => Boolean(n))
        .map((n) => n.replace(/_/g, ".")),
    ),
  );

  const reply = String(result.finalOutput ?? "").trim() || "(no answer)";
  return { reply, history: result.history, toolsUsed };
}