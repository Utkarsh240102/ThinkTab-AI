import { useRef, useEffect, type KeyboardEvent } from "react";

interface QueryInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
}

export default function QueryInput({ value, onChange, onSubmit, isLoading }: QueryInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* Auto-resize textarea */
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${ta.scrollHeight}px`;
  }, [value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim()) onSubmit();
    }
  }

  const canSubmit = !isLoading && value.trim().length > 0;

  return (
    <div style={{
      padding: "8px 16px 12px",
      flexShrink: 0,
    }}>
      {/* Input row */}
      <div style={{
        display: "flex", alignItems: "flex-end", gap: "8px",
        borderRadius: "12px", padding: "8px 12px",
        background: "rgba(255,255,255,0.05)",
        border: "1px solid var(--glass-border)",
      }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder={isLoading ? "Thinking..." : "Ask anything about this page..."}
          rows={1}
          style={{
            flex: 1, resize: "none", background: "transparent",
            border: "none", outline: "none",
            fontSize: "13px", lineHeight: 1.6,
            color: "var(--text-primary)",
            caretColor: "var(--accent-primary)",
            maxHeight: "120px", overflowY: "auto",
            padding: "4px 0",
            fontFamily: "inherit",
          }}
        />

        {/* Send button */}
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          style={{
            flexShrink: 0, width: "32px", height: "32px",
            borderRadius: "8px", border: "none",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: canSubmit ? "pointer" : "not-allowed",
            transition: "all 0.2s ease",
            background: canSubmit
              ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
              : "rgba(255,255,255,0.06)",
            boxShadow: canSubmit ? "0 0 14px rgba(99,102,241,0.5)" : "none",
            opacity: canSubmit ? 1 : 0.4,
            transform: canSubmit ? "scale(1)" : "scale(0.95)",
          }}
          title="Send (Enter)"
        >
          {isLoading ? (
            <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24"
              fill="none" stroke="white" strokeWidth="2.5">
              <path d="M21 12a9 9 0 1 1-6.22-8.56" strokeLinecap="round" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          )}
        </button>
      </div>

      <p style={{
        textAlign: "center", fontSize: "11px",
        color: "var(--text-secondary)", opacity: 0.5, marginTop: "8px",
      }}>
        Shift+Enter for new line · Enter to send
      </p>
    </div>
  );
}
