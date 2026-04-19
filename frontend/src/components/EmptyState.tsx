interface EmptyStateProps {
  onPromptClick: (prompt: string) => void;
}

const EXAMPLE_PROMPTS = [
  "Summarize this page for me",
  "What are the key points here?",
  "Compare this with what I know",
];

export default function EmptyState({ onPromptClick }: EmptyStateProps) {
  return (
    <div className="animate-fade-in-up" style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      height: "100%", padding: "40px 24px", textAlign: "center",
    }}>
      {/* Icon */}
      <div style={{
        width: "64px", height: "64px", borderRadius: "18px", marginBottom: "20px",
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.2))",
        border: "1px solid rgba(99,102,241,0.3)",
        boxShadow: "0 0 40px rgba(99,102,241,0.15)",
      }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
          strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
          stroke="url(#grad)">
          <defs>
            <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
          </defs>
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <path d="M12 17h.01" />
        </svg>
      </div>

      {/* Text */}
      <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
        Ask about this page
      </h2>
      <p style={{
        fontSize: "13px", lineHeight: 1.6,
        color: "var(--text-secondary)", maxWidth: "220px", marginBottom: "24px",
      }}>
        I can answer questions, summarize content, and find information from the page you're reading.
      </p>

      {/* Prompt chips */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%" }}>
        {EXAMPLE_PROMPTS.map((prompt) => (
          <button key={prompt} className="btn-ghost"
            onClick={() => onPromptClick(prompt)}
            style={{ textAlign: "left", fontSize: "13px", padding: "10px 16px" }}>
            <span style={{ color: "var(--accent-primary)", marginRight: "8px" }}>→</span>
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
