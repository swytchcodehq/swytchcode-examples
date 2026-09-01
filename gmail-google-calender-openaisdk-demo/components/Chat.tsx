"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Turn = { role: "you" | "agent"; text: string; calls?: string[] };
type Health = { gmail: boolean; calendar: boolean; email: string | null };

const EXAMPLES = [
  "Show my last 5 emails",
  "Any unread mail from stripe this week?",
  "What's on my calendar tomorrow",
  "Add lunch with Priya on Friday at 1pm",
];

export default function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);

  const sessionId = useRef("");
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      sessionId.current = localStorage.getItem("session") ?? crypto.randomUUID();
      localStorage.setItem("session", sessionId.current);
    } catch {
      sessionId.current = String(Math.random());
    }
    fetch("/api/health").then((r) => r.json()).then(setHealth).catch(() => {});
  }, []);

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  const send = useCallback(
    async (text: string) => {
      text = text.trim();
      if (!text || busy) return;
      setInput("");
      setTurns((t) => [...t, { role: "you", text }]);
      setBusy(true);
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ message: text, sessionId: sessionId.current }),
        });
        const data = await res.json();
        setTurns((t) => [...t, { role: "agent", text: data.reply, calls: data.calls }]);
      } catch {
        setTurns((t) => [...t, { role: "agent", text: "Network error. Is the dev server running?" }]);
      } finally {
        setBusy(false);
      }
    },
    [busy],
  );

  return (
    <div className="app">
      <header>
        <div className="brand">
          <strong>Gmail + Calendar</strong>
          <span>{health?.email ?? "an agent, wired up with Swytchcode"}</span>
        </div>
        <div className="pills">
          <Pill label="Gmail" on={health?.gmail} />
          <Pill label="Calendar" on={health?.calendar} />
        </div>
      </header>

      <div className="stream" ref={streamRef}>
        {turns.length === 0 && (
          <div className="empty">
            <p>Ask about your mail and calendar. The agent picks which Google API method to call.</p>
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button key={ex} onClick={() => send(ex)}>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <div className={"turn " + turn.role} key={i}>
            <span className="who">{turn.role}</span>
            <div className="bubble">{turn.text}</div>
            {turn.calls && turn.calls.length > 0 && (
              <span className="calls">ran {turn.calls.join(", ")}</span>
            )}
          </div>
        ))}

        {busy && (
          <div className="turn agent">
            <span className="who">agent</span>
            <div className="bubble dots">
              <i />
              <i />
              <i />
            </div>
          </div>
        )}
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message your mail and calendar"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function Pill({ label, on }: { label: string; on?: boolean }) {
  const state = on === undefined ? "" : on ? "on" : "off";
  return (
    <span className="pill">
      <i className={"dot " + state} />
      {label}
    </span>
  );
}
