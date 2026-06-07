import { useState, useEffect } from "react";

interface HeaderProps {
  activeMode?: string;
  onClearChat?: () => void;
}

function handleReload() {
  // chrome.runtime.reload() is only available inside the real Chrome Extension.
  // It gracefully falls back in the Vite dev environment.
  if (typeof chrome !== "undefined" && chrome.runtime?.reload) {
    chrome.runtime.reload();
  } else {
    window.location.reload();
  }
}

export default function Header({ activeMode, onClearChat }: HeaderProps) {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    async function pingBackend() {
      try {
        const response = await fetch("http://127.0.0.1:8000/api/health");
        setIsOnline(response.ok);
      } catch {
        setIsOnline(false);
      }
    }

    pingBackend();
    const intervalId = setInterval(pingBackend, 10000);

    return () => clearInterval(intervalId);
  }, []);

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
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <h1 className="gradient-text"
            style={{ fontSize: "15px", fontWeight: 700, letterSpacing: "-0.01em", lineHeight: 1.2 }}>
            ThinkTab AI
          </h1>
          <div style={{
            width: "8px", height: "8px", borderRadius: "50%",
            background: isOnline ? "var(--status-success)" : "var(--status-error)",
            boxShadow: `0 0 6px ${isOnline ? "var(--status-success)" : "var(--status-error)"}`,
            flexShrink: 0,
          }} title={isOnline ? "Backend Online" : "Backend Offline"} />
        </div>
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

      {/* Right side: Clear Chat + Reload button */}
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "10px" }}>

        {/* Clear Chat Button */}
        {onClearChat && (
          <button
            onClick={onClearChat}
            title="Clear Chat"
            style={{
              background: "transparent",
              border: "1px solid var(--glass-border)",
              borderRadius: "6px",
              padding: "4px 6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-secondary)",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.1)"; // faint red hover
              (e.currentTarget as HTMLButtonElement).style.color = "#ef4444"; // red icon
              (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(239, 68, 68, 0.3)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "transparent";
              (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--glass-border)";
            }}
          >
            {/* Trash SVG icon */}
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18" />
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
            </svg>
          </button>
        )}

        {/* Reload Extension Button */}
        <button
          onClick={handleReload}
          title="Reload extension"
          style={{
            background: "transparent",
            border: "1px solid var(--glass-border)",
            borderRadius: "6px",
            padding: "4px 6px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-secondary)",
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.08)";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
          }}
        >
          {/* Circular refresh SVG icon */}
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
          </svg>
        </button>

      </div>
    </header>
  );
}
