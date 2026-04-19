/* ─────────────────────────────────────────────────────────────
   StatusBubble Component

   Shows a live pipeline status message while the AI is thinking.
   Replaces the plain "thinking dots" with an informative label
   like "Evaluating document relevance... ⚖️"
─────────────────────────────────────────────────────────────── */

interface StatusBubbleProps {
  text: string;
}

export default function StatusBubble({ text }: StatusBubbleProps) {
  return (
    <div className="animate-fade-in-up" style={{ display: "flex", justifyContent: "flex-start" }}>
      <div style={{
        padding: "10px 14px",
        borderRadius: "18px",
        borderBottomLeftRadius: "4px",
        background: "var(--glass-bg)",
        border: "1px solid var(--glass-border)",
        display: "flex",
        alignItems: "center",
        gap: "10px",
        maxWidth: "85%",
      }}>
        {/* Animated dots */}
        <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
          <span className="thinking-dot" />
          <span className="thinking-dot" />
          <span className="thinking-dot" />
        </div>
        {/* Status text */}
        <span style={{
          fontSize: "12px",
          color: "var(--text-secondary)",
          lineHeight: 1.4,
        }}>
          {text}
        </span>
      </div>
    </div>
  );
}
