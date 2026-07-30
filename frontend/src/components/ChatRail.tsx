import { CornerDownLeft, Loader2, MessageSquare, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import type { ChatResponse, ChatTurn } from "../types";

interface Entry extends ChatTurn {
  meta?: ChatResponse;
}

const SUGGESTIONS = [
  "Summarise tonight's shift.",
  "Which animals had no recorded events?",
  "What evidence supports the highest event?",
  "Where are the coverage gaps?"
];

export function ChatRail({
  scopeLabel,
  enclosureId
}: {
  scopeLabel: string;
  enclosureId: string | null;
}) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries, busy]);

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    const history: ChatTurn[] = [
      ...entries.map(({ role, content }) => ({ role, content })),
      { role: "user", content: trimmed }
    ];
    setEntries((current) => [...current, { role: "user", content: trimmed }]);
    setDraft("");
    setBusy(true);
    setError("");
    try {
      const reply = await api.chat(history, { enclosureId });
      setEntries((current) => [
        ...current,
        { role: "assistant", content: reply.answer, meta: reply }
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The assistant is unavailable");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="chat-rail" aria-label="Shift assistant">
      <header className="chat-head">
        <div>
          <span className="eyebrow">Shift assistant</span>
          <strong>{scopeLabel}</strong>
        </div>
        <MessageSquare size={17} />
      </header>

      <div className="chat-guard">
        <ShieldCheck size={14} />
        <span>
          Reads the recorded shift only. It cannot set severity, diagnose, or act on
          an enclosure.
        </span>
      </div>

      <div className="chat-scroll">
        {entries.length === 0 && (
          <div className="chat-suggestions">
            <Sparkles size={16} />
            <p>Ask about tonight's evidence.</p>
            {SUGGESTIONS.map((item) => (
              <button key={item} onClick={() => void send(item)}>
                {item}
              </button>
            ))}
          </div>
        )}

        {entries.map((entry, index) => (
          <div
            key={`${entry.role}-${index}`}
            className={entry.role === "user" ? "bubble user" : "bubble assistant"}
          >
            <p>{entry.content}</p>
            {entry.meta && (
              <div className="bubble-meta">
                {entry.meta.cited_ids.length > 0 && (
                  <span className="citations">
                    {entry.meta.cited_ids.length} cited record(s)
                  </span>
                )}
                <span className="mode-tag">
                  {entry.meta.mode === "openai"
                    ? entry.meta.model
                    : "shift record"}
                </span>
                {entry.meta.uncertainty.map((item) => (
                  <span key={item} className="uncertainty">
                    {item}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {busy && (
          <div className="bubble assistant pending">
            <Loader2 size={15} className="spin" /> Reading the shift record…
          </div>
        )}
        {error && <div className="chat-error">{error}</div>}
        <div ref={endRef} />
      </div>

      <form
        className="chat-compose"
        onSubmit={(e) => {
          e.preventDefault();
          void send(draft);
        }}
      >
        <textarea
          rows={2}
          value={draft}
          placeholder="Ask about an animal, an event, or a gap…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(draft);
            }
          }}
        />
        <button type="submit" disabled={busy || !draft.trim()} aria-label="Send">
          <CornerDownLeft size={16} />
        </button>
      </form>
    </aside>
  );
}

export default ChatRail;
