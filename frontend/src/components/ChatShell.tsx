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
import ReactMarkdown from "react-markdown";
import { usePDFParser } from "../hooks/usePDFParser";

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
  const bottomRef  = useRef<HTMLDivElement>(null);
  // Hidden file input ref — we programmatically click it when the 📎 button is pressed
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* PDF context: null = no PDF loaded, object = a PDF is attached */
  const [pdfContext, setPdfContext] = useState<{ source_id: string; content: string } | null>(null);

  /* The real SSE hook — replaces the old setTimeout stub */
  const { isLoading, statusText, displayMode, finalAnswer, error, sendQuery, abort } = useSSEChat();

  /* PDF parsing hook */
  const { parseFile, isLoading: isPDFLoading, statusText: pdfStatusText, error: pdfError, clearError: clearPDFError } = usePDFParser();

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

  const BACKEND_URL = "http://127.0.0.1:8000";

  /* ── Reusable Tab Scraper ── */
  async function scrapeActiveTab(): Promise<any[]> {
    let scrapedContexts: any[] = [];
    if (typeof chrome !== "undefined" && chrome.tabs) {
      try {
        const [activeTab] = await new Promise<chrome.tabs.Tab[]>((resolve) => {
          chrome.tabs.query({ active: true, lastFocusedWindow: true }, resolve);
        });

        if (activeTab && activeTab.id) {
          const response = await new Promise<any>((resolve) => {
            chrome.tabs.sendMessage(activeTab.id!, { action: "SCRAPE_PAGE_CONTEXT" }, resolve);
          });
          
          if (response && response.contexts) {
            scrapedContexts = response.contexts.map((str: string) => ({
              source_id: `Active Tab`,
              content: str
            }));
          }
        }
      } catch (err) {
        console.warn("Could not scrape tab context:", err);
      }
    }
    return scrapedContexts;
  }

  /* ── Pre-embed on Extension Open ── */
  useEffect(() => {
    async function preEmbedPage() {
      const contexts = await scrapeActiveTab();
      if (contexts.length > 0) {
        try {
          // Send the first (and only) context item to the embed endpoint
          await fetch(`${BACKEND_URL}/api/embed`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(contexts[0])
          });
          console.log("✅ Page pre-embedded successfully.");
        } catch (err) {
          console.warn("Failed to pre-embed page:", err);
        }
      }
    }
    preEmbedPage();
  }, []);

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

    /* ── Scrape the active webpage context ── */
    const scrapedContexts = await scrapeActiveTab();

    /* ── Merge webpage + PDF contexts ── */
    // We MERGE both — not replace — so the RAG pipeline can search
    // across the webpage AND the PDF at the same time.
    const allContexts = [...scrapedContexts];
    if (pdfContext) {
      allContexts.push(pdfContext);
    }

    /* Fire the backend call with all available contexts */
    sendQuery(query.trim(), selectedMode, allContexts, updatedHistory);

    setQuery("");
  }

  /* ── Soft HITL Logic: Cancel and Switch to Deep ── */
  function handleSwitchToDeep() {
    abort(); // Immediately kill the Fast stream if still running
    setSelectedMode("deep");
    sendQuery(lastQuery, "deep", [], chatHistory);
  }

  /* ── Clear Chat Logic ── */
  function handleClearChat() {
    if (isLoading) abort();
    setMessages([]);
    setChatHistory([]);
    setLastQuery("");
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
        <Header activeMode={displayMode} onClearChat={handleClearChat} />

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
                      <div className="markdown-body" style={{
                        fontSize: "13px", lineHeight: 1.7,
                        padding: "12px 16px", borderRadius: "18px",
                        borderBottomLeftRadius: "4px",
                        background: "var(--glass-bg)",
                        border: "1px solid var(--glass-border)",
                        color: "var(--text-primary)",
                      }}>
                        <ReactMarkdown>{msg.answer}</ReactMarkdown>
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

          {/* ── PDF Error Toast ── */}
          {pdfError && (
            <div style={{
              margin: "0 16px 8px",
              padding: "8px 12px",
              borderRadius: "8px",
              background: "rgba(239,68,68,0.12)",
              border: "1px solid rgba(239,68,68,0.3)",
              color: "#ef4444",
              fontSize: "12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "8px",
            }}>
              <span>⚠️ {pdfError}</span>
              <button
                onClick={clearPDFError}
                style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: "14px", padding: 0 }}
              >×</button>
            </div>
          )}

          {/* ── Active PDF Badge ── */}
          {pdfContext && (
            <div style={{
              margin: "0 16px 6px",
              padding: "5px 10px",
              borderRadius: "20px",
              background: "rgba(99,102,241,0.12)",
              border: "1px solid rgba(99,102,241,0.3)",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "11px",
              color: "var(--text-accent)",
              maxWidth: "calc(100% - 32px)",
            }}>
              <span>📄</span>
              {/* Truncate very long filenames so they don't overflow */}
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "200px" }}>
                {pdfContext.source_id}
              </span>
              <button
                onClick={() => setPdfContext(null)}
                title="Remove PDF"
                style={{
                  background: "none", border: "none",
                  color: "var(--text-secondary)", cursor: "pointer",
                  fontSize: "14px", padding: 0, lineHeight: 1,
                  flexShrink: 0,
                }}
              >×</button>
            </div>
          )}

          {/* Toolbar row: mode selector + PDF attach button */}
          <div style={{
            display:    "flex",
            alignItems: "center",
            padding:    "8px 16px 0",
            borderTop:  "1px solid var(--glass-border)",
            gap:        "8px",
          }}>
            <ModeSelector
              selected={selectedMode}
              onChange={setSelectedMode}
              disabled={isLoading}
            />

            {/* Spacer pushes attach button to the right */}
            <div style={{ flex: 1 }} />

            {/* ── PDF Attach Button ── */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isPDFLoading || isLoading}
              title={pdfContext ? `PDF attached: ${pdfContext.source_id}` : "Attach a PDF"}
              style={{
                background:   pdfContext ? "rgba(99,102,241,0.15)" : "transparent",
                border:       pdfContext ? "1px solid rgba(99,102,241,0.4)" : "1px solid var(--glass-border)",
                borderRadius: "6px",
                padding:      "4px 6px",
                cursor:       isPDFLoading ? "wait" : "pointer",
                display:      "flex",
                alignItems:   "center",
                justifyContent: "center",
                color:        pdfContext ? "var(--accent-primary)" : "var(--text-secondary)",
                transition:   "all 0.2s ease",
                opacity:      isPDFLoading ? 0.6 : 1,
              }}
              onMouseEnter={(e) => {
                if (!pdfContext) {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.08)";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)";
                }
              }}
              onMouseLeave={(e) => {
                if (!pdfContext) {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
                }
              }}
              title={isPDFLoading ? (pdfStatusText || "Parsing...") : "Attach a PDF"}
            >
              {isPDFLoading ? (
                // Spinning loader while PDF is being parsed
                <svg className="animate-spin" width="13" height="13" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : (
                // Paperclip icon
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                </svg>
              )}
            </button>

            {/* Hidden file input — only accepts PDF files */}
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              style={{ display: "none" }}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                // Reset input value so selecting the same file again triggers onChange
                e.target.value = "";
                if (!file) return;

                const result = await parseFile(file);
                if (result) {
                  const newContext = { source_id: result.fileName, content: result.text };
                  setPdfContext(newContext);

                  // ── Silent Pre-Embed ──────────────────────────────────────────
                  // Send the PDF text to the backend immediately after parsing,
                  // so FAISS embeds it in the background while the user types.
                  // By the time they press Send, the first query will be instant.
                  try {
                    await fetch(`${BACKEND_URL}/api/embed`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(newContext),
                    });
                    console.log(`✅ PDF "${result.fileName}" pre-embedded (${result.pageCount} pages).`);
                  } catch {
                    // Pre-embed failure is non-critical — the query will still work,
                    // it'll just embed on demand at query time instead.
                    console.warn("[PDF] Pre-embed failed — will embed on first query.");
                  }

                  if (result.isScanned) {
                    console.warn("[PDF] Scanned PDF detected — text extraction may be incomplete.");
                  }
                }
              }}
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
