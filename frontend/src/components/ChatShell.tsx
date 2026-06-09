import { useState, useRef, useEffect } from "react";
import Header from "./Header";
import EmptyState from "./EmptyState";
import MessageList from "./MessageList";
import PipelineStatus from "./PipelineStatus";
import ChatInputArea from "./ChatInputArea";
import { useSSEChat, type EvidenceItem, type ChatHistoryItem, type Context } from "../hooks/useSSEChat";
import { usePDFParser } from "../hooks/usePDFParser";
import type { Mode } from "./ModeSelector";

// ── Message types ──────────────────────────────────────────────

export interface UserMessage {
  id:      string;
  role:    "user";
  content: string;
}

export interface AssistantMessage {
  id:               string;
  role:             "assistant";
  answer:           string;
  evidence:         EvidenceItem[];
  confidence_score: number;
  mode:             string;
  isTyping?:        boolean;
}

export interface ErrorMessage {
  id:      string;
  role:    "error";
  message: string;
}

export type Message = UserMessage | AssistantMessage | ErrorMessage;

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

  // NOTE: We have removed the useEffect that pushes `error` to `messages`. 
  // PipelineStatus now handles the error bubble directly to eliminate cascading re-renders!

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
  }, [messages, isLoading, statusText, error]);

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
          source_id: `Active Tab: ${activeTab.title || "Unknown Page"}`,
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

  async function handleRetry() {
    abort();
    const scrapedContexts = await scrapeActiveTab();
    const allContexts = [...scrapedContexts];
    if (pdfContext) allContexts.push(pdfContext);
    sendQuery(lastQuery, selectedMode, allContexts, chatHistory);
  }

  async function handlePDFFileSelected(file: File) {
    const result = await parseFile(file);
    if (result) {
      const newContext = { source_id: result.fileName, content: result.text };
      setPdfContext(newContext);

      // ── Silent Pre-Embed ──────────────────────────────────────────
      try {
        await fetch(`${BACKEND_URL}/api/embed`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newContext),
        });
        console.log(`✅ PDF "${result.fileName}" pre-embedded (${result.pageCount} pages).`);
      } catch {
        console.warn("[PDF] Pre-embed failed — will embed on first query.");
      }

      if (result.isScanned) {
        console.warn("[PDF] Scanned PDF detected — text extraction may be incomplete.");
      }
    }
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

        {/* 2. Message area */}
        <main style={{ flex: 1, overflowY: "auto", padding: "12px 16px 16px" }}>
          {messages.length === 0 && !isLoading ? (
            <EmptyState onPromptClick={setQuery} />
          ) : (
            <>
              <MessageList 
                messages={messages}
                isLoading={isLoading}
                onRetry={handleRetry}
                onSwitchToDeep={handleSwitchToDeep}
                onTypingDone={handleTypingDone}
                bottomRef={bottomRef}
              />
              
              <PipelineStatus 
                isLoading={isLoading}
                statusText={statusText}
                error={error}
                onRetry={handleRetry}
              />
            </>
          )}
        </main>

        {/* 3. Bottom section — mode trigger + input */}
        <ChatInputArea 
          query={query}
          setQuery={setQuery}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onStop={abort}
          selectedMode={selectedMode}
          setSelectedMode={setSelectedMode}
          chatHistoryLength={chatHistory.length}
          onExportChat={handleExportChat}
          pinnedContexts={pinnedContexts}
          onPinTab={handlePinTab}
          onClearPinned={() => setPinnedContexts([])}
          onRemovePinned={(sourceId) => setPinnedContexts((prev) => prev.filter((p) => p.source_id !== sourceId))}
          pdfContext={pdfContext}
          onRemovePDF={() => setPdfContext(null)}
          isPDFLoading={isPDFLoading}
          pdfStatusText={pdfStatusText}
          pdfError={pdfError}
          clearPDFError={clearPDFError}
          onPDFFileSelected={handlePDFFileSelected}
        />
      </div>
    </div>
  );
}
