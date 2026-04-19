/* ─────────────────────────────────────────────────────────────
   useSSEChat — Custom React Hook
   
   This hook is the bridge between the React UI and the FastAPI
   backend. It uses the browser's native Fetch + ReadableStream
   API to consume Server-Sent Events (SSE) in real time.

   FLOW:
     1. User submits a query → `sendQuery()` is called
     2. We open a POST fetch stream to /api/chat
     3. The backend sends events line-by-line, e.g.:
          data: {"type": "mode",   "value": "Fast Mode ⚡"}
          data: {"type": "status", "value": "Retrieving paragraphs..."}
          data: {"type": "final",  "answer": "...", "evidence": [...]}
     4. We parse each line and update React state progressively
     5. The UI re-renders with each new event automatically

   ABORT SUPPORT:
     An AbortController lets us cancel in-flight requests
     (used for the Soft HITL "Switch to Deep" feature later).
─────────────────────────────────────────────────────────────── */

import { useState, useCallback, useRef, useEffect } from "react";

// ── Types ──────────────────────────────────────────────────────

export interface EvidenceItem {
  source_id: string;
  snippet:   string;
}

export interface FinalAnswer {
  answer:             string;
  evidence:           EvidenceItem[];
  confidence_score:   number;
  reasoning_summary:  string;
}

export interface Context {
  source_id: string;
  content:   string;
}

export interface ChatHistoryItem {
  role:    "user" | "assistant";
  content: string;
}

// ── The Hook ───────────────────────────────────────────────────

/* In dev: requests go through Vite proxy → localhost:8000
   In production (Chrome Extension): swap this to the real backend URL */
const BACKEND_URL = "http://127.0.0.1:8000";

export function useSSEChat() {
  const [isLoading,   setIsLoading]   = useState(false);
  const [statusText,  setStatusText]  = useState("");
  const [displayMode, setDisplayMode] = useState<string | undefined>(undefined);
  const [finalAnswer, setFinalAnswer] = useState<FinalAnswer | null>(null);
  const [error,       setError]       = useState<string | null>(null);

  /* AbortController lives in a ref so it persists across renders */
  const abortRef = useRef<AbortController | null>(null);

  /* Clean up any in-flight request on unmount */
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  /* ── Main function: send a query, stream the response ── */
  const sendQuery = useCallback(async (
    query:       string,
    mode:        "auto" | "fast" | "deep",
    contexts:    Context[]         = [],
    chatHistory: ChatHistoryItem[] = [],
  ) => {
    /* Cancel any previous streaming request first */
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    /* Reset all state for the new request */
    setIsLoading(true);
    setStatusText("Connecting...");
    setDisplayMode(undefined);
    setFinalAnswer(null);
    setError(null);

    try {
      /* Open the stream — POST to /api/chat */
      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          mode,
          contexts,
          chat_history: chatHistory,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Server error ${response.status}: ${text}`);
      }

      /* ── Read the stream line by line ── */
      const reader  = response.body!.getReader();
      const decoder = new TextDecoder();
      let   buffer  = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        /* Decode the binary chunk into text and accumulate in buffer */
        buffer += decoder.decode(value, { stream: true });

        /* Split on newlines; keep the last (possibly incomplete) chunk */
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();

          /* SSE lines always start with "data:" — skip anything else */
          if (!trimmed.startsWith("data:")) continue;

          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);

            /* Route each event type to the correct state update */
            switch (event.type) {
              case "mode":
                /* e.g. "Fast Mode ⚡" or "Auto → Selected: Deep 🧠" */
                setDisplayMode(event.value);
                break;

              case "status":
                /* e.g. "Retrieving relevant paragraphs..." */
                setStatusText(event.value);
                break;

              case "final":
                /* The complete answer — triggers the assistant message to appear */
                setFinalAnswer({
                  answer:            event.answer            ?? "",
                  evidence:          event.evidence          ?? [],
                  confidence_score:  event.confidence_score  ?? 0,
                  reasoning_summary: event.reasoning_summary ?? "",
                });
                break;

              case "error":
                setError(event.value ?? "An unknown error occurred.");
                break;
            }
          } catch {
            /* Silently skip malformed JSON lines */
          }
        }
      }

    } catch (err: unknown) {
      /* AbortError is expected when we cancel a request — not an error */
      if (err instanceof Error && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Connection failed. Is the backend running?");
    } finally {
      setIsLoading(false);
      setStatusText("");
    }
  }, []);

  /* ── Cancel the current in-flight request ── */
  const abort = useCallback(() => {
    abortRef.current?.abort();
    setIsLoading(false);
    setStatusText("");
  }, []);

  return { isLoading, statusText, displayMode, finalAnswer, error, sendQuery, abort };
}
