import type { AgentInputItem } from "@openai/agents";

/**
 * Per-browser conversation history, kept in memory. Good enough for a local
 * single-user demo; use a real store (and trim old turns) for anything more.
 */
const sessions = new Map<string, AgentInputItem[]>();

export function getSession(id: string) {
  return {
    get history() {
      return sessions.get(id) ?? [];
    },
    set history(items: AgentInputItem[]) {
      sessions.set(id, items);
    },
  };
}
