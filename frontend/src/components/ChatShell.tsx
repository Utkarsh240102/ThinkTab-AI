import { useState, useRef, useEffect } from "react";
import Header from "./Header";
import EmptyState from "./EmptyState";
import QueryInput from "./QueryInput";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function ChatShell() {
  const [query, setQuery]         = useState("");
  const [messages, setMessages]   = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeMode, setActiveMode] = useState<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);

  /* Auto-scroll to latest message */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  /* STUB — will be replaced with real SSE hook in Step 11 */
  function handleSubmit() {
    if (!query.trim() || isLoading) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: query.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setIsLoading(true);
    setActiveMode("Fast Mode ⚡");

    setTimeout(() => {
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "This is a placeholder. Real SSE streaming with the backend will be connected in Sub-step 11. 🚀",
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsLoading(false);
    }, 1500);
  }

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", padding: "16px",
    }}>
      {/* Glass panel */}
      <div className="glass-strong animate-slide-in-right" style={{
        display: "flex", flexDirection: "column",
        width: "100%", maxWidth: "420px",
        height: "calc(100vh - 32px)", maxHeight: "760px",
        overflow: "hidden",
      }}>

        {/* Header */}
        <Header activeMode={activeMode} />

        {/* Message area */}
        <main style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
          {messages.length === 0 && !isLoading ? (
            <EmptyState onPromptClick={setQuery} />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {messages.map((msg) => (
                <div key={msg.id} className="animate-fade-in-up"
                  style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
                  <div style={{
                    fontSize: "13px", lineHeight: 1.6,
                    padding: "10px 16px", borderRadius: "18px",
                    maxWidth: "85%",
                    ...(msg.role === "user" ? {
                      background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
                      color: "white",
                      borderBottomRightRadius: "4px",
                    } : {
                      background: "var(--glass-bg)",
                      border: "1px solid var(--glass-border)",
                      color: "var(--text-primary)",
                      borderBottomLeftRadius: "4px",
                    }),
                  }}>
                    {msg.content}
                  </div>
                </div>
              ))}

              {/* Thinking dots */}
              {isLoading && (
                <div className="animate-fade-in-up" style={{ display: "flex", justifyContent: "flex-start" }}>
                  <div style={{
                    padding: "12px 16px", borderRadius: "18px", borderBottomLeftRadius: "4px",
                    background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                  }}>
                    <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                      <span className="thinking-dot" />
                      <span className="thinking-dot" />
                      <span className="thinking-dot" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </main>

        {/* Input */}
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
