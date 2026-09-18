"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, SendHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ScoutView } from "@/components/scout-app";

type ChatMessage = { role: "user" | "agent"; text: string };

const SUGGESTIONS = [
  "Explain BF-PRODUCT-003",
  "Show recent failed runs",
  "Find flows without automation",
  "Explain the last NEEDS_REVIEW",
];

function renderMessageText(
  text: string,
  onNavigate: (target: { view: ScoutView; flowId?: string; runId?: string }) => void
) {
  const parts = text.split(/(\[\[(?:flow|run):[^\]]+\]\])/g);
  return parts.map((part, i) => {
    const flow = part.match(/^\[\[flow:(BF-[A-Z0-9-]+)\]\]$/);
    const run = part.match(/^\[\[run:(run_[a-z0-9]+)\]\]$/i);
    if (flow) {
      return (
        <button
          key={i}
          type="button"
          className="agent-link font-mono"
          onClick={() => onNavigate({ view: "flows", flowId: flow[1] })}
        >
          {flow[1]}
        </button>
      );
    }
    if (run) {
      return (
        <button
          key={i}
          type="button"
          className="agent-link font-mono"
          onClick={() => onNavigate({ view: "runs", runId: run[1] })}
        >
          {run[1]}
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export function AgentChatFab({
  onNavigate,
}: {
  onNavigate: (target: { view: ScoutView; flowId?: string; runId?: string }) => void;
}) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;
      setMessages((m) => [...m, { role: "user", text: trimmed }]);
      setInput("");
      setBusy(true);
      try {
        const res = await fetch("/api/agent-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed }),
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || "Agent unavailable");
        setMessages((m) => [...m, { role: "agent", text: String(json.reply || "") }]);
      } catch (e) {
        setMessages((m) => [
          ...m,
          { role: "agent", text: e instanceof Error ? e.message : "Unable to reach ScoutAI Agent." },
        ]);
      } finally {
        setBusy(false);
      }
    },
    [busy]
  );

  return (
    <>
      {open ? (
        <div className="agent-chat-panel" role="dialog" aria-label="ScoutAI Agent">
          <div className="agent-chat-panel__header">
            <div className="agent-chat-panel__title-row">
              <strong>ScoutAI Agent</strong>
              <button type="button" className="icon-button" onClick={() => setOpen(false)} aria-label="Close chat">
                <X size={18} />
              </button>
            </div>
            <p className="text-muted text-sm">Connected to ScoutAI workspace</p>
          </div>

          <div className="agent-chat-messages" ref={listRef}>
            {messages.length === 0 ? (
              <div className="agent-chat-welcome">
                <p>Ask ScoutAI about your QA workspace.</p>
                <div className="suggestion-row">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} type="button" className="suggestion-chip" onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            {messages.map((msg, idx) => (
              <div key={idx} className={msg.role === "user" ? "agent-msg--user" : "agent-msg--agent"}>
                {msg.role === "agent" ? renderMessageText(msg.text, onNavigate) : msg.text}
              </div>
            ))}
            {busy ? (
              <div className="agent-msg--agent">
                <Loader2 size={16} className="status-badge-spin" aria-label="Thinking" />
              </div>
            ) : null}
          </div>

          <form
            className="agent-chat-input-row"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about flows, runs, evidence…"
              aria-label="Message ScoutAI Agent"
              disabled={busy}
            />
            <Button type="submit" size="icon" className="btn-black" disabled={busy || !input.trim()} aria-label="Send">
              <SendHorizontal size={18} />
            </Button>
          </form>
        </div>
      ) : null}

      <button
        type="button"
        className="agent-fab"
        aria-label="Open ScoutAI Agent"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="agent-fab__icon" aria-hidden />
      </button>
    </>
  );
}
