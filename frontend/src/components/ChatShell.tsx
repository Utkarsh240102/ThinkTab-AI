"use client";

/* ─────────────────────────────────────────────────────────────
   ChatShell Component — The Main UI Container

   This is the glass panel that holds the entire ThinkTab AI
   interface. It acts as the "frame" that wraps:
     - Header (top bar)
     - Message area (middle, scrollable)
     - QueryInput (bottom, fixed)

   It manages the local state for:
     - `query`     — what the user is currently typing
     - `messages`  — the conversation history (placeholder for now)
     - `isLoading` — true while the backend is processing

   In Sub-step 11, we will replace the stub `handleSubmit` with
   the real SSE streaming hook that calls the backend.
─────────────────────────────────────────────────────────────── */

import { useState, useRef, useEffect } from "react";
import Header from "./Header";
import EmptyState from "./EmptyState";
import QueryInput from "./QueryInput";

/* ── TypeScript type for a single message in the chat ── */
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export default function ChatShell() {
  const [query, setQuery]       = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeMode, setActiveMode] = useState<string | undefined>(undefined);

  /* Ref to the bottom of the message list — used to auto-scroll */
  const bottomRef = useRef<HTMLDivElement>(null);

  /* ── Auto-scroll to bottom whenever messages update ── */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ── STUB: Submit handler (will be replaced in Step 11) ──
     For now it just adds a placeholder user message and a
     dummy "thinking" assistant message so we can see the UI. */
  function handleSubmit() {
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: query.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuery("");       // Clear the input
    setIsLoading(true); // Show loading state
    setActiveMode("Fast Mode ⚡");

    /* Simulate a response after 1.5s (placeholder only) */
    setTimeout(() => {
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "This is a placeholder response. The real SSE streaming backend will be connected in Sub-step 11.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
  }

  /* ── Handle clicking an example prompt chip ── */
  function handlePromptClick(prompt: string) {
    setQuery(prompt);
  }

  return (
    /*
      Outer container: full viewport height, flexbox column.
      The glass panel is centered in the page for desktop,
      but in production it will fill the Chrome extension sidebar.
    */
    <div
      className="flex items-center justify-center min-h-screen p-4"
      style={{ background: "var(--bg-primary)" }}
    >
      {/* ── Glass Panel ── */}
      <div
        className="glass-strong flex flex-col w-full animate-slide-in-right"
        style={{
          maxWidth: "420px",
          height: "calc(100vh - 32px)",
          maxHeight: "760px",
          overflow: "hidden",
        }}
      >

        {/* ── 1. Fixed Header ── */}
        <Header activeMode={activeMode} />

        {/* ── 2. Scrollable Message Area ── */}
        <main
          className="flex-1 overflow-y-auto"
          style={{ padding: "16px", overflowX: "hidden" }}
        >
          {/* Show EmptyState when there are no messages yet */}
          {messages.length === 0 && !isLoading ? (
            <EmptyState onPromptClick={handlePromptClick} />
          ) : (
            <div className="flex flex-col gap-3">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex animate-fade-in-up ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className="text-sm leading-relaxed px-4 py-2.5 rounded-2xl max-w-[85%]"
                    style={
                      msg.role === "user"
                        ? {
                            /* User message — accent gradient bubble */
                            background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
                            color: "white",
                            borderBottomRightRadius: "4px",
                          }
                        : {
                            /* Assistant message — glass bubble */
                            background: "var(--glass-bg)",
                            border: "1px solid var(--glass-border)",
                            color: "var(--text-primary)",
                            borderBottomLeftRadius: "4px",
                          }
                    }
                  >
                    {msg.content}
                  </div>
                </div>
              ))}

              {/* ── Thinking indicator ── */}
              {isLoading && (
                <div className="flex justify-start animate-fade-in-up">
                  <div
                    className="px-4 py-3 rounded-2xl"
                    style={{
                      background: "var(--glass-bg)",
                      border: "1px solid var(--glass-border)",
                      borderBottomLeftRadius: "4px",
                    }}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="thinking-dot" />
                      <span className="thinking-dot" />
                      <span className="thinking-dot" />
                    </div>
                  </div>
                </div>
              )}

              {/* ── Invisible anchor at the bottom for auto-scroll ── */}
              <div ref={bottomRef} />
            </div>
          )}
        </main>

        {/* ── 3. Fixed Input Bar ── */}
        <QueryInput
          value={query}
          onChange={setQuery}
          onSubmit={handleSubmit}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
