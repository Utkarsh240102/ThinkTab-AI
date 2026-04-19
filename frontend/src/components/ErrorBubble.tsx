/* ─────────────────────────────────────────────────────────────
   ErrorBubble Component
   
   A distinct, red-tinted UI element to display system errors.
   Separates failures from normal Assistant messages to avoid 
   user confusion. Includes a built-in Retry button.
─────────────────────────────────────────────────────────────── */

interface ErrorBubbleProps {
  message: string;
  onRetry: () => void;
}

export default function ErrorBubble({ message, onRetry }: ErrorBubbleProps) {
  return (
    <div className="animate-fade-in-up" style={{ display: "flex", justifyContent: "flex-start", maxWidth: "92%" }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          padding: "12px 16px",
          borderRadius: "18px",
          borderBottomLeftRadius: "4px",
          background: "rgba(239, 68, 68, 0.1)", // Red translucent
          border: "1px solid rgba(239, 68, 68, 0.3)",
        }}
      >
        {/* Error Header + Message */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
          <span style={{ fontSize: "14px", marginTop: "2px" }}>⚠️</span>
          <div>
            <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--status-error)", marginBottom: "2px" }}>
              Connection Error
            </div>
            <div style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
              {message}
            </div>
          </div>
        </div>

        {/* Retry Button */}
        <button
          onClick={onRetry}
          style={{
            alignSelf: "flex-start",
            display: "flex",
            alignItems: "center",
            gap: "5px",
            padding: "5px 12px",
            borderRadius: "6px",
            background: "rgba(239, 68, 68, 0.15)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "var(--status-error)",
            fontSize: "11px",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s ease",
            fontFamily: "inherit",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.25)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.15)";
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
          </svg>
          Retry request
        </button>
      </div>
    </div>
  );
}
