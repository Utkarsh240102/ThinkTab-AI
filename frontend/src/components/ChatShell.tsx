import { useState, useRef, useEffect } from "react";
import Header from "./Header";
import EmptyState from "./EmptyState";
import QueryInput from "./QueryInput";
import ModeSelector, { type Mode } from "./ModeSelector";
import StatusBubble from "./StatusBubble";
import SoftHITLButton from "./SoftHITLButton";
import EvidenceAccordion from "./EvidenceAccordion";
import ErrorBubble from "./ErrorBubble";
import { useSSEChat, type EvidenceItem, type ChatHistoryItem, type Context } from "../hooks/useSSEChat";
import TypewriterMarkdown from "./TypewriterMarkdown";
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
  isTyping?:        boolean;
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
  const [historySummary, setHistorySummary] = useState("");
  const [lastQuery,    setLastQuery]    = useState("");
  const [pinnedContexts, setPinnedContexts] = useState<Context[]>([]);
  const bottomRef  = useRef<HTMLDivElement>(null);
  // Hidden file input ref — we programmatically click it when the 📎 button is pressed
  const fileInputRef = useRef<HTMLInputElement>(null);
  const embedReadyRef = useRef<boolean>(false);

  /* PDF context: null = no PDF loaded, object = a PDF is attached */
  const [pdfContext, setPdfContext] = useState<{ source_id: string; content: string } | null>(null);

  /* The real SSE hook — replaces the old setTimeout stub */
  const { isLoading, statusText, displayMode, finalAnswer, error, sendQuery, abort } = useSSEChat();

  /* PDF parsing hook */
  const { parseFile, isLoading: isPDFLoading, statusText: pdfStatusText, error: pdfError, clearError: clearPDFError } = usePDFParser();

  /* ── When a final answer arrives, add it to the message list ── */
  const processedAnswerRef = useRef<string | null>(null);

  useEffect(() => {
    if (!finalAnswer) {
      processedAnswerRef.current = null;
      return;
    }

    // Ensure the effect only processes each unique message once
    const answerHash = JSON.stringify(finalAnswer);
    if (processedAnswerRef.current === answerHash) return;
    processedAnswerRef.current = answerHash;

    // Safely batch state updates to prevent synchronous cascading renders
    const timeoutId = setTimeout(() => {
      const assistantMsg: AssistantMessage = {
        id:               crypto.randomUUID(),
        role:             "assistant",
        answer:           finalAnswer.answer,
        evidence:         finalAnswer.evidence,
        confidence_score: finalAnswer.confidence_score,
        mode:             displayMode ?? "",
        isTyping:         true,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      /* Update chat history so the Contextualizer can resolve pronouns */
      // BUG-007 FIX: Cap state at 60 messages (30 turns) to prevent memory leak.
      // The backend payload is independently capped at slice(-10) in useSSEChat.ts.
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant" as const, content: finalAnswer.answer },
      ].slice(-60));
    }, 0);

    return () => clearTimeout(timeoutId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finalAnswer]);

  /* ── When an error arrives, show it as an Error message ── */
  const processedErrorRef = useRef<string | null>(null);

  useEffect(() => {
    if (!error) {
      processedErrorRef.current = null;
      return;
    }

    if (processedErrorRef.current === error) return;
    processedErrorRef.current = error;

    const timeoutId = setTimeout(() => {
      const errMsg: ErrorMessage = {
        id:      crypto.randomUUID(),
        role:    "error",
        message: error,
      };
      setMessages((prev) => [...prev, errMsg]);
    }, 0);

    return () => clearTimeout(timeoutId);
  }, [error]);

  useEffect(() => {
    if (chatHistory.length > 10) {
      const messagesToDrop = chatHistory.slice(
        0,
        chatHistory.length - 10
      );

      fetch(`${BACKEND_URL}/api/summarize-history`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          old_messages: messagesToDrop,
          current_summary: historySummary || null
        })
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.summary) {
            setHistorySummary(data.summary);
          }
        })
        .catch((err) =>
          console.warn(
            "Background summarization failed:",
            err
          )
        );
    }
  }, [chatHistory, historySummary]);

  /* Auto-scroll to bottom on new messages or status */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, statusText]);

  const BACKEND_URL = "http://localhost:8000";

  /* ── Reusable Tab Scraper ── */
  async function scrapeActiveTab(): Promise<Context[]> {
    let scrapedContexts: Context[] = [];
    if (typeof chrome === "undefined" || !chrome.tabs) return scrapedContexts;

    try {
      const [activeTab] = await new Promise<chrome.tabs.Tab[]>((resolve) => {
        chrome.tabs.query({ active: true, lastFocusedWindow: true }, resolve);
      });

      if (!activeTab?.id) return scrapedContexts;
      const tabId = activeTab.id;

      // Helper: send a scrape message and resolve null on any error
      // (null means the content script is not present in this tab)
      function sendScrapeMessage(id: number): Promise<{ contexts?: string[] } | null> {
        return new Promise((resolve) => {
          chrome.tabs.sendMessage(id, { action: "SCRAPE_PAGE_CONTEXT" }, (response) => {
            if (chrome.runtime.lastError) {
              // "Could not establish connection" → content.js not injected in this tab yet
              resolve(null);
            } else {
              resolve(response);
            }
          });
        });
      }

      let response = await sendScrapeMessage(tabId);

      // ── Injection Fallback ──────────────────────────────────────────────
      // If response is null the tab was open before the extension was installed
      // (i.e., it never got the content.js "earpiece"). We inject it now and retry.
      if (response === null && chrome.scripting) {
        console.warn("[ThinkTab] Content script not found in this tab. Injecting now...");
        try {
          await chrome.scripting.executeScript({
            target: { tabId },
            files: ["content.js"],
          });
          // Brief pause so the script can register its message listener
          await new Promise((r) => setTimeout(r, 200));
          response = await sendScrapeMessage(tabId);
        } catch (injectionError) {
          // chrome:// pages, extension pages, and PDFs cannot be injected — skip silently
          console.warn("[ThinkTab] Could not inject content script (restricted page):", injectionError);
        }
      }

      if (response?.contexts) {
        scrapedContexts = response.contexts.map((str: string) => ({
          source_id: `Active Tab`,
          content: str,
        }));
      }
    } catch (err) {
      console.warn("Could not scrape tab context:", err);
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
      // Always mark as ready, even if no content or error, so we don't block chat forever
      embedReadyRef.current = true;
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
    // BUG-007 FIX: Cap state at 60 messages (30 turns) to prevent memory leak.
    // The backend payload is independently capped at slice(-10) in useSSEChat.ts.
    const updatedHistory: ChatHistoryItem[] = [
      ...chatHistory,
      { role: "user" as const, content: query.trim() },
    ].slice(-60);
    setChatHistory(updatedHistory);
    setLastQuery(query.trim());

    /* ── Scrape and Wait for Embed in Parallel (BUG2-006 fix) ── */
    // Previously: scrape ran first, THEN the embed-wait loop ran sequentially.
    // Now: both run concurrently with Promise.all — wall-clock time is
    // max(scrape, embed-wait) instead of scrape + embed-wait.
    const waitForEmbed = async () => {
      if (!embedReadyRef.current) {
        console.log("⏳ Waiting for initial page embed to finish...");
        for (let i = 0; i < 30; i++) {
          await new Promise(r => setTimeout(r, 100));
          if (embedReadyRef.current) break;
        }
      }
    };

    const [scrapedContexts] = await Promise.all([
      scrapeActiveTab(),
      waitForEmbed(),
    ]);

    /* ── Merge webpage + PDF contexts ── */
    // We MERGE both — not replace — so the RAG pipeline can search
    // across the webpage AND the PDF at the same time.
    const allContexts = [...scrapedContexts];
    allContexts.push(...pinnedContexts);
    if (pdfContext) {
      allContexts.push(pdfContext);
    }

    /* Fire the backend call with all available contexts */
    sendQuery(query.trim(), selectedMode, allContexts, updatedHistory, historySummary);

    setQuery("");
  }

  /* ── Soft HITL Logic: Cancel and Switch to Deep ── */
  async function handleSwitchToDeep() {
    abort(); // Immediately kill the Fast stream if still running
    // BUG-016 FIX: Wait 100ms after abort() before starting the new request.
    // The old stream's reader loop needs one event-loop tick to see the abort
    // signal and exit cleanly. Without this pause, the new Deep Mode request
    // can start before the old reader releases the connection, causing
    // interleaved SSE events and duplicate assistant messages in the UI.
    await new Promise(r => setTimeout(r, 100));
    setSelectedMode("deep");
    // BUG-002 FIX: Re-scrape the active tab so Deep Mode has real page content.
    const scrapedContexts = await scrapeActiveTab();
    const allContexts = [...scrapedContexts];
    if (pdfContext) allContexts.push(pdfContext);
    sendQuery(lastQuery, "deep", allContexts, chatHistory);
  }

  /* ── Clear Chat Logic ── */
  function handleClearChat() {
    if (isLoading) abort();
    setMessages([]);
    setChatHistory([]);
    setLastQuery("");
  }

  function handleExportChat() {
    const markdownText = chatHistory.length > 0
      ? chatHistory.map((msg) => {
          const heading = msg.role === "user" ? "### 🧑 User" : "### 🤖 ThinkTab";
          return `${heading}\n\n${msg.content}\n`;
        }).join("\n")
      : "# ThinkTab Chat\n\n_No messages to export yet._\n";

    const blob = new Blob([markdownText], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "ThinkTab-Chat.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function handlePinTab() {
    const scrapedContexts = await scrapeActiveTab();
    if (scrapedContexts.length === 0) return;

    let sourceId = scrapedContexts[0]?.source_id || "Pinned Tab";
    if (typeof chrome !== "undefined" && chrome.tabs) {
      const [activeTab] = await new Promise<chrome.tabs.Tab[]>((resolve) => {
        chrome.tabs.query({ active: true, lastFocusedWindow: true }, resolve);
      });
      sourceId = `Pinned Tab: ${activeTab?.title || activeTab?.url || "Unknown"}`;
    }

    setPinnedContexts((prev) => {
      if (prev.some((ctx) => ctx.source_id === sourceId)) return prev;
      return [
        ...prev,
        ...scrapedContexts.map((ctx) => ({
          ...ctx,
          source_id: sourceId,
        })),
      ];
    });
  }

  function handleTypingDone(messageId: string) {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.role === "assistant" && msg.id === messageId
          ? { ...msg, isTyping: false }
          : msg
      )
    );
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
                      onRetry={async () => {
                        // BUG-003 FIX: Re-scrape the active tab so retry has real page content.
                        // Previously passed [] which caused retrieval to always fail and
                        // forced unnecessary web search fallback on every error retry.
                        abort();
                        const scrapedContexts = await scrapeActiveTab();
                        const allContexts = [...scrapedContexts];
                        if (pdfContext) allContexts.push(pdfContext);
                        sendQuery(lastQuery, selectedMode, allContexts, chatHistory);
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
                        <TypewriterMarkdown
                          text={msg.answer}
                          enabled={Boolean(msg.isTyping)}
                          onDone={() => handleTypingDone(msg.id)}
                        />
                      </div>

                      {/* Evidence Accordion + Confidence badge */}
                      {!msg.isTyping && (msg.evidence.length > 0 || msg.confidence_score > 0) && (
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
                      {!msg.isTyping && msg.role === "assistant" && isFinalMessage && msg.mode.includes("Fast") && (
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
            flexWrap:   "wrap",
          }}>
            <ModeSelector
              selected={selectedMode}
              onChange={setSelectedMode}
              disabled={isLoading}
            />

            <button
              onClick={handleExportChat}
              disabled={chatHistory.length === 0}
              title="Export chat as Markdown"
              style={{
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                padding: "5px 10px",
                background: "rgba(255,255,255,0.05)",
                color: "var(--text-secondary)",
                fontSize: "12px",
                fontWeight: 500,
                fontFamily: "inherit",
                cursor: chatHistory.length === 0 ? "not-allowed" : "pointer",
                opacity: chatHistory.length === 0 ? 0.45 : 1,
                transition: "all 0.2s ease",
                whiteSpace: "nowrap",
              }}
            >
              Export
            </button>

            <button
              onClick={handlePinTab}
              disabled={isLoading}
              title={`Pin current tab${pinnedContexts.length ? ` (${pinnedContexts.length} pinned)` : ""}`}
              style={{
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                padding: "5px 10px",
                background: "rgba(255,255,255,0.05)",
                color: "var(--text-secondary)",
                fontSize: "12px",
                fontWeight: 500,
                fontFamily: "inherit",
                cursor: isLoading ? "not-allowed" : "pointer",
                opacity: isLoading ? 0.45 : 1,
                transition: "all 0.2s ease",
                whiteSpace: "nowrap",
              }}
            >
              {pinnedContexts.length > 0 ? `Pinned (${pinnedContexts.length})` : "Pin Current Tab 📌"}
            </button>

            <button
              onClick={() => setPinnedContexts([])}
              disabled={pinnedContexts.length === 0}
              title="Clear pinned tabs"
              style={{
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                padding: "5px 10px",
                background: "rgba(255,255,255,0.05)",
                color: "var(--text-secondary)",
                fontSize: "12px",
                fontWeight: 500,
                fontFamily: "inherit",
                cursor: pinnedContexts.length === 0 ? "not-allowed" : "pointer",
                opacity: pinnedContexts.length === 0 ? 0.45 : 1,
                transition: "all 0.2s ease",
                whiteSpace: "nowrap",
              }}
            >
              Clear Pinned
            </button>

            {/* Spacer pushes attach button to the right */}
            <div style={{ flex: 1 }} />

            {/* ── PDF Attach Button ── */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isPDFLoading || isLoading}
              title={isPDFLoading ? (pdfStatusText || "Parsing...") : pdfContext ? `PDF attached: ${pdfContext.source_id}` : "Attach a PDF"}
              style={{
                background:   pdfContext ? "rgba(99,102,241,0.22)" : "rgba(255,255,255,0.08)",
                border:       pdfContext ? "1px solid rgba(99,102,241,0.55)" : "1px solid rgba(165,180,252,0.38)",
                borderRadius: "8px",
                padding:      "6px 8px",
                minWidth:     "34px",
                minHeight:    "32px",
                cursor:       isPDFLoading ? "wait" : "pointer",
                display:      "flex",
                alignItems:   "center",
                justifyContent: "center",
                color:        "var(--text-primary)",
                transition:   "all 0.2s ease",
                opacity:      isPDFLoading ? 0.6 : 1,
                boxShadow:    pdfContext ? "0 0 14px rgba(99,102,241,0.28)" : "0 0 10px rgba(165,180,252,0.12)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = pdfContext
                  ? "rgba(99,102,241,0.3)"
                  : "rgba(165,180,252,0.16)";
                (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(165,180,252,0.65)";
                (e.currentTarget as HTMLButtonElement).style.color = "white";
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 16px rgba(165,180,252,0.3)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = pdfContext
                  ? "rgba(99,102,241,0.22)"
                  : "rgba(255,255,255,0.08)";
                (e.currentTarget as HTMLButtonElement).style.borderColor = pdfContext
                  ? "rgba(99,102,241,0.55)"
                  : "rgba(165,180,252,0.38)";
                (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)";
                (e.currentTarget as HTMLButtonElement).style.boxShadow = pdfContext
                  ? "0 0 14px rgba(99,102,241,0.28)"
                  : "0 0 10px rgba(165,180,252,0.12)";
              }}

            >
              {isPDFLoading ? (
                // Spinning loader while PDF is being parsed
                <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : (
                // Paperclip icon
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
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

          {pinnedContexts.length > 0 && (
            <div style={{
              margin: "8px 16px 0",
              display: "flex",
              flexWrap: "wrap",
              gap: "6px",
            }}>
              {pinnedContexts.map((ctx) => (
                <span
                  key={ctx.source_id}
                  title={ctx.source_id}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    maxWidth: "100%",
                    padding: "4px 6px 4px 8px",
                    borderRadius: "999px",
                    background: "rgba(16,185,129,0.12)",
                    border: "1px solid rgba(16,185,129,0.28)",
                    color: "var(--status-success)",
                    fontSize: "11px",
                    lineHeight: 1.3,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  <span style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}>
                    {ctx.source_id}
                  </span>
                  <button
                    onClick={() =>
                      setPinnedContexts((prev) =>
                        prev.filter((pinned) => pinned.source_id !== ctx.source_id)
                      )
                    }
                    title={`Remove ${ctx.source_id}`}
                    style={{
                      width: "16px",
                      height: "16px",
                      borderRadius: "50%",
                      border: "none",
                      background: "rgba(16,185,129,0.2)",
                      color: "var(--status-success)",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "12px",
                      lineHeight: 1,
                      padding: 0,
                      flexShrink: 0,
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Input textarea */}
          <QueryInput
            value={query}
            onChange={setQuery}
            onSubmit={handleSubmit}
            isLoading={isLoading}
            onStop={abort}
          />
        </div>
      </div>
    </div>
  );
}
