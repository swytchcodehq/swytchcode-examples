import { getSession } from "@/lib/session";
import { chat } from "@/lib/agent";

export const runtime = "nodejs"; // the agent shells out to the `swytchcode` binary
export const maxDuration = 60;

export async function POST(req: Request) {
  const { message = "", sessionId = "anon" } = await req.json();

  if (!message.trim()) {
    return Response.json({ reply: "Ask me about your mail or calendar.", calls: [] });
  }
  if (!process.env.OPENAI_API_KEY) {
    return Response.json({ reply: "Set OPENAI_API_KEY in .env.local, then restart the dev server.", calls: [] });
  }

  const session = getSession(sessionId);
  try {
    const { reply, history, calls } = await chat(session.history, message);
    session.history = history;
    return Response.json({ reply, calls });
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    return Response.json({ reply: `The agent errored: ${detail}`, calls: [] }, { status: 500 });
  }
}
