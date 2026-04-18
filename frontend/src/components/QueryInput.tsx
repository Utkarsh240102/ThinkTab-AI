"use client";

/* ─────────────────────────────────────────────────────────────
   QueryInput Component

   The bottom input bar where the user types their question.
   Features:
     - Auto-resizes as the user types multiple lines
     - Send on Enter key (Shift+Enter for new line)
     - Disabled + loading state while the AI is thinking
     - Animated gradient send button
─────────────────────────────────────────────────────────────── */

import { useRef, useEffect, KeyboardEvent } from "react";

interface QueryInputProps {
  /** The current typed value of the input */
  value: string;
  /** Called every time the user types a character */
  onChange: (value: string) => void;
  /** Called when the user presses Send or hits Enter */
  onSubmit: () => void;
  /** When true: disables the input and shows a loading indicator */
  isLoading: boolean;
}

export default function QueryInput({
  value,
  onChange,
  onSubmit,
  isLoading,
}: QueryInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* ── Auto-resize the textarea height as the user types ── */
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";          // Reset first to shrink if text deleted
    ta.style.height = `${ta.scrollHeight}px`; // Then grow to fit content
  }, [value]);

  /* ── Handle keyboard shortcuts ── */
  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter alone = submit. Shift+Enter = newline (default textarea behaviour).
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault(); // Stop the default newline being inserted
      if (!isLoading && value.trim()) {
        onSubmit();
      }
    }
  }

  const canSubmit = !isLoading && value.trim().length > 0;

  return (
    <div
      className="px-4 py-3 border-t"
      style={{ borderColor: "var(--glass-border)" }}
    >
      <div
        className="flex items-end gap-2 rounded-xl px-3 py-2"
        style={{
          background: "rgba(255,255,255,0.05)",
          border: "1px solid var(--glass-border)",
          transition: "border-color 0.2s ease",
        }}
        onFocus={() => {}}  // Border glow handled via CSS below
      >
        {/* ── Textarea ── */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder={
            isLoading
              ? "Thinking..."
              : "Ask anything about this page... (Enter to send)"
          }
          rows={1}
          className="flex-1 resize-none bg-transparent outline-none text-sm leading-relaxed py-1"
          style={{
            color: "var(--text-primary)",
            caretColor: "var(--accent-primary)",
            maxHeight: "120px",  // Cap at ~5 lines, then scroll
            overflowY: "auto",
          }}
        />

        {/* ── Send Button ── */}
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-200"
          style={{
            background: canSubmit
              ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
              : "rgba(255,255,255,0.06)",
            boxShadow: canSubmit ? "0 0 14px rgba(99,102,241,0.5)" : "none",
            cursor: canSubmit ? "pointer" : "not-allowed",
            transform: canSubmit ? "scale(1)" : "scale(0.95)",
            opacity: canSubmit ? 1 : 0.4,
          }}
          title="Send (Enter)"
        >
          {isLoading ? (
            /* Spinner when loading */
            <svg
              className="animate-spin"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2.5"
            >
              <path d="M21 12a9 9 0 1 1-6.22-8.56" />
            </svg>
          ) : (
            /* Arrow-up icon when idle */
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          )}
        </button>
      </div>

      {/* ── Hint text ── */}
      <p
        className="text-center text-xs mt-2"
        style={{ color: "var(--text-secondary)", opacity: 0.5 }}
      >
        Shift+Enter for new line
      </p>
    </div>
  );
}
