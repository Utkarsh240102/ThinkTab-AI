/* ─────────────────────────────────────────────────────────────
   Header Component
   
   The top bar of the ThinkTab AI panel.
   Displays:
     - Animated logo icon (brain / sparkle)
     - App title with gradient text
     - A subtitle showing the current active mode
─────────────────────────────────────────────────────────────── */

interface HeaderProps {
  /** The text shown under the title — e.g. "Fast Mode ⚡" or "Deep Mode 🧠" */
  activeMode?: string;
}

export default function Header({ activeMode }: HeaderProps) {
  return (
    <header
      className="flex items-center gap-3 px-5 py-4 border-b"
      style={{ borderColor: "var(--glass-border)" }}
    >
      {/* ── Logo Icon ── */}
      <div
        className="flex items-center justify-center w-9 h-9 rounded-xl flex-shrink-0"
        style={{
          background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
          boxShadow: "0 0 16px rgba(99,102,241,0.5)",
        }}
      >
        {/* Brain SVG Icon */}
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.44-4.66" />
          <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.44-4.66" />
        </svg>
      </div>

      {/* ── Title + Mode Badge ── */}
      <div className="flex flex-col min-w-0">
        <h1
          className="text-base font-bold leading-tight gradient-text"
          style={{ letterSpacing: "-0.01em" }}
        >
          ThinkTab AI
        </h1>

        {/* Mode badge — only shown when a mode has been selected */}
        {activeMode ? (
          <span
            className="text-xs font-medium mt-0.5 animate-fade-in-up"
            style={{ color: "var(--text-accent)" }}
          >
            {activeMode}
          </span>
        ) : (
          <span
            className="text-xs mt-0.5"
            style={{ color: "var(--text-secondary)" }}
          >
            Your intelligent browsing assistant
          </span>
        )}
      </div>

      {/* ── Spacer pushes status dot to the right ── */}
      <div className="ml-auto flex items-center gap-2">
        {/* Live connection indicator */}
        <div
          className="w-2 h-2 rounded-full"
          style={{
            background: "var(--status-success)",
            boxShadow: "0 0 6px var(--status-success)",
          }}
          title="Backend connected"
        />
      </div>
    </header>
  );
}
