interface HeaderProps {
  activeMode?: string;
}

export default function Header({ activeMode }: HeaderProps) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "16px 20px",
        borderBottom: "1px solid var(--glass-border)",
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div
        style={{
          width: "36px", height: "36px",
          borderRadius: "10px", flexShrink: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
          boxShadow: "0 0 16px rgba(99,102,241,0.5)",
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.44-4.66" />
          <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.44-4.66" />
        </svg>
      </div>

      {/* Title + mode */}
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <h1 className="gradient-text"
          style={{ fontSize: "15px", fontWeight: 700, letterSpacing: "-0.01em", lineHeight: 1.2 }}>
          ThinkTab AI
        </h1>
        {activeMode ? (
          <span className="animate-fade-in-up"
            style={{ fontSize: "11px", color: "var(--text-accent)", marginTop: "2px", fontWeight: 500 }}>
            {activeMode}
          </span>
        ) : (
          <span style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
            Your intelligent browsing assistant
          </span>
        )}
      </div>

      {/* Live dot */}
      <div style={{ marginLeft: "auto" }}>
        <div style={{
          width: "8px", height: "8px", borderRadius: "50%",
          background: "var(--status-success)",
          boxShadow: "0 0 6px var(--status-success)",
        }} title="Backend connected" />
      </div>
    </header>
  );
}
