/* ─────────────────────────────────────────────────────────────
   ModeSelector Component

   A compact 3-button toggle that lets the user pick between:
     - Auto 🤖  — backend decides Fast or Deep automatically
     - Fast ⚡  — low-latency, direct RAG answer
     - Deep 🧠  — full CRAG + Self-RAG pipeline

   The selected mode is stored in ChatShell and sent to the
   backend with every query.
─────────────────────────────────────────────────────────────── */

export type Mode = "auto" | "fast" | "deep";

interface ModeSelectorProps {
  selected: Mode;
  onChange: (mode: Mode) => void;
  disabled?: boolean;
}

const MODES: { value: Mode; label: string; icon: string; description: string }[] = [
  { value: "auto", label: "Auto",  icon: "🤖", description: "Let AI decide the best mode"        },
  { value: "fast", label: "Fast",  icon: "⚡", description: "Quick answer from your page"         },
  { value: "deep", label: "Deep",  icon: "🧠", description: "Full analysis with web search"       },
];

export default function ModeSelector({ selected, onChange, disabled = false }: ModeSelectorProps) {
  return (
    <div style={{ padding: "10px 16px 0" }}>
      <div
        style={{
          display: "flex",
          gap: "6px",
          background: "rgba(255,255,255,0.04)",
          border: "1px solid var(--glass-border)",
          borderRadius: "12px",
          padding: "4px",
        }}
        role="group"
        aria-label="Response mode selector"
      >
        {MODES.map(({ value, label, icon, description }) => {
          const isActive = selected === value;
          return (
            <button
              key={value}
              onClick={() => !disabled && onChange(value)}
              disabled={disabled}
              title={description}
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "5px",
                padding: "6px 4px",
                borderRadius: "8px",
                border: "none",
                cursor: disabled ? "not-allowed" : "pointer",
                fontSize: "12px",
                fontWeight: isActive ? 600 : 400,
                fontFamily: "inherit",
                transition: "all 0.2s ease",
                /* Active state — gradient pill */
                background: isActive
                  ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                  : "transparent",
                color: isActive ? "white" : "var(--text-secondary)",
                boxShadow: isActive ? "0 0 12px rgba(99,102,241,0.4)" : "none",
                transform: isActive ? "scale(1.02)" : "scale(1)",
                opacity: disabled ? 0.5 : 1,
              }}
            >
              <span style={{ fontSize: "13px" }}>{icon}</span>
              <span>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
