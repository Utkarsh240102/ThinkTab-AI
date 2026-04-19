import { useState, useRef, useEffect } from "react";
import Header from "./Header";
import EmptyState from "./EmptyState";
import QueryInput from "./QueryInput";
import ModeSelector, { type Mode } from "./ModeSelector";
import StatusBubble from "./StatusBubble";
import SoftHITLButton from "./SoftHITLButton";
import EvidenceAccordion from "./EvidenceAccordion";
import ErrorBubble from "./ErrorBubble";
import { useSSEChat, type EvidenceItem, type ChatHistoryItem } from "../hooks/useSSEChat";

// ── Message types ──────────────────────────────────────────────

interface UserMessage {
  id:      string;
  role:    "user";
  content: string;
}

interface AssistantMessage {
  id:               string;
  role:             "assistant";
  answer:           string;
  evidence:         EvidenceItem[];
  confidence_score: number;
  mode:             string;
}

interface ErrorMessage {
  id:      string;
  role:    "error";
  message: string;
}

type Message = UserMessage | AssistantMessage | ErrorMessage;

// ── Component ─────────────────────────────────────────────────

export default function ChatShell() {
  const [query,        setQuery]        = useState("");
  const [messages,     setMessages]     = useState<Message[]>([]);
  const [selectedMode, setSelectedMode] = useState<Mode>("auto");
  const [chatHistory,  setChatHistory]  = useState<ChatHistoryItem[]>([]);
  const [lastQuery,    setLastQuery]    = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  /* The real SSE hook — replaces the old setTimeout stub */
  const { isLoading, statusText, displayMode, finalAnswer, error, sendQuery, abort } = useSSEChat();

  /* ── When a final answer arrives, add it to the message list ── */
  useEffect(() => {
    if (!finalAnswer) return;

    const assistantMsg: AssistantMessage = {
      id:               crypto.randomUUID(),
      role:             "assistant",
      answer:           finalAnswer.answer,
      evidence:         finalAnswer.evidence,
      confidence_score: finalAnswer.confidence_score,
      mode:             displayMode ?? "",
    };

    setMessages((prev) => [...prev, assistantMsg]);

    /* Update chat history so the Contextualizer can resolve pronouns */
    setChatHistory((prev) => [
      ...prev,
      { role: "assistant", content: finalAnswer.answer },
    ]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finalAnswer]);

  /* ── When an error arrives, show it as an Error message ── */
  useEffect(() => {
    if (!error) return;
    const errMsg: ErrorMessage = {
      id:      crypto.randomUUID(),
      role:    "error",
      message: error,
    };
    setMessages((prev) => [...prev, errMsg]);
  }, [error]);

  /* Auto-scroll to bottom on new messages or status */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, statusText]);

  /* ── Submit handler ── */
  async function handleSubmit() {
    if (!query.trim() || isLoading) return;

    const userMsg: UserMessage = {
      id:      crypto.randomUUID(),
      role:    "user",
      content: query.trim(),
    };

    /* Add user message immediately for instant feedback */
    setMessages((prev) => [...prev, userMsg]);

    /* Track in chat history for the Contextualizer */
    const updatedHistory: ChatHistoryItem[] = [
      ...chatHistory,
      { role: "user", content: query.trim() },
    ];
    setChatHistory(updatedHistory);
    setLastQuery(query.trim());

    /* ── Chrome Extension Scraper Bridge ── */
    let scrapedContexts: any[] = [];

    // Safely check if we are running inside the actual Chrome Extension
    // so we don't break our local Vite dev environment.
    if (typeof chrome !== "undefined" && chrome.tabs) {
      try {
        // Find the active tab in the current window
        const [activeTab] = await new Promise<chrome.tabs.Tab[]>((resolve) => {
          chrome.tabs.query({ active: true, currentWindow: true }, resolve);
        });

        if (activeTab && activeTab.id) {
          // Ask the content script injected into that tab to scrape text
          const response = await new Promise<any>((resolve) => {
            chrome.tabs.sendMessage(
              activeTab.id!, 
              { action: "SCRAPE_PAGE_CONTEXT" }, 
              resolve
            );
          });
          
          if (response && response.contexts) {
            // Map the simple strings back into the expected Context objects
            scrapedContexts = response.contexts.map((str: string, index: number) => ({
              source_id: `Tab Context ${index}`,
              content: str
            }));
          }
        }
      } catch (err) {
        // Warning if the page blocks extension scripts (e.g. chrome:// urls)
        console.warn("Could not scrape tab context:", err);
      }
    }

    /* Fire the real backend call — now injecting the scraped contexts securely from the browser */
    sendQuery(query.trim(), selectedMode, scrapedContexts, updatedHistory);

    setQuery("");
  }

  /* ── Soft HITL Logic: Cancel and Switch to Deep ── */
  function handleSwitchToDeep() {
    abort(); // Immediately kill the Fast stream if still running
    setSelectedMode("deep");
    sendQuery(lastQuery, "deep", [], chatHistory);
  }

  /* ── Confidence badge color ── */
  function confidenceColor(score: number): string {
    if (score >= 0.8) return "var(--status-success)";
    if (score >= 0.5) return "var(--status-thinking)";
    return "var(--status-error)";
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

        {/* 1. Header — shows mode reported by backend */}
        <Header activeMode={displayMode} />

        {/* 2. Mode selector removed from here — now lives in the bottom toolbar */}

        {/* 3. Message area */}
        <main style={{ flex: 1, overflowY: "auto", padding: "12px 16px 16px" }}>
          {messages.length === 0 && !isLoading ? (
            <EmptyState onPromptClick={setQuery} />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>

              {messages.map((msg, index) => {
                const isFinalMessage = index === messages.length - 1;
                return (
                <div key={msg.id} className="animate-fade-in-up"
                  style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>

                  {msg.role === "error" ? (
                    /* ── System Error Bubble ── */
                    <ErrorBubble 
                      message={msg.message} 
                      onRetry={() => {
                        // Re-fire the last known query without adding a new user message to the UI
                        abort(); 
                        sendQuery(lastQuery, selectedMode, [], chatHistory);
                      }} 
                    />
                  ) : msg.role === "user" ? (
                    /* ── User bubble ── */
                    <div style={{
                      fontSize: "13px", lineHeight: 1.6,
                      padding: "10px 16px", borderRadius: "18px",
                      borderBottomRightRadius: "4px", maxWidth: "85%",
                      background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
                      color: "white",
                    }}>
                      {msg.content}
                    </div>
                  ) : (
                    /* ── Assistant bubble ── */
                    <div style={{ maxWidth: "92%", display: "flex", flexDirection: "column", gap: "6px" }}>
                      <div style={{
                        fontSize: "13px", lineHeight: 1.7,
                        padding: "12px 16px", borderRadius: "18px",
                        borderBottomLeftRadius: "4px",
                        background: "var(--glass-bg)",
                        border: "1px solid var(--glass-border)",
                        color: "var(--text-primary)",
                      }}>
                        {msg.answer}
                      </div>

                      {/* Evidence Accordion + Confidence badge */}
                      {(msg.evidence.length > 0 || msg.confidence_score > 0) && (
                        <div style={{ display: "flex", flexDirection: "column", gap: "6px", paddingLeft: "4px" }}>
                          
                          {/* Confidence badge */}
                          {msg.confidence_score > 0 && (
                            <div style={{ display: "flex" }}>
                              <span style={{
                                fontSize: "11px", padding: "2px 8px",
                                borderRadius: "99px",
                                background: `${confidenceColor(msg.confidence_score)}20`,
                                border: `1px solid ${confidenceColor(msg.confidence_score)}50`,
                                color: confidenceColor(msg.confidence_score),
                              }}>
                                {Math.round(msg.confidence_score * 100)}% confident
                              </span>
                            </div>
                          )}

                          {/* Collapsible evidence */}
                          {msg.evidence.length > 0 && (
                            <EvidenceAccordion evidence={msg.evidence} />
                          )}

                        </div>
                      )}
                      {/* ── SOFT HITL: Switch to Deep Mode ── */}
                      {msg.role === "assistant" && isFinalMessage && msg.mode.includes("Fast") && (
                        <div style={{ marginTop: "4px" }}>
                          <SoftHITLButton 
                            onClick={handleSwitchToDeep} 
                            disabled={isLoading} 
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )})}

              {/* Live status while streaming */}
              {isLoading && statusText && (
                <StatusBubble text={statusText} />
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </main>

        {/* 4. Bottom section — mode trigger + input (position:relative anchors the popup) */}
        <div style={{ position: "relative" }}>
          {/* Toolbar row: mode selector trigger */}
          <div style={{
            display:        "flex",
            alignItems:     "center",
            padding:        "8px 16px 0",
            borderTop:      "1px solid var(--glass-border)",
          }}>
            <ModeSelector
              selected={selectedMode}
              onChange={setSelectedMode}
              disabled={isLoading}
            />
          </div>

          {/* Input textarea */}
          <QueryInput
            value={query}
            onChange={setQuery}
            onSubmit={handleSubmit}
            isLoading={isLoading}
          />
        </div>
      </div>
    </div>
  );
}
