/* ─────────────────────────────────────────────────────────────
   ModeSelector — Popup Dropdown (Claude-style)

   A small trigger button lives in the toolbar above the input.
   Clicking it opens a vertical popup panel above with 3 mode
   cards, each showing a title + description.
   The selected card gets a highlighted accent border.
─────────────────────────────────────────────────────────────── */

import { useState, useRef, useEffect } from "react";

export type Mode = "auto" | "fast" | "deep";

interface ModeSelectorProps {
  selected:  Mode;
  onChange:  (mode: Mode) => void;
  disabled?: boolean;
}

const MODES = [
  {
    value:       "auto" as Mode,
    label:       "Auto",
    icon:        "🤖",
    description: "AI decides the best mode automatically based on your query complexity.",
  },
  {
    value:       "fast" as Mode,
    label:       "Fast",
    icon:        "⚡",
    description: "Quick answer directly from your page. Use for simple, direct questions.",
  },
  {
    value:       "deep" as Mode,
    label:       "Deep",
    icon:        "🧠",
    description: "Full CRAG + web search pipeline. Use for complex research or analysis.",
  },
];

export default function ModeSelector({ selected, onChange, disabled = false }: ModeSelectorProps) {
  const [open, setOpen] = useState(false);
  const containerRef    = useRef<HTMLDivElement>(null);

  /* Close popup when user clicks outside */
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const currentMode = MODES.find((m) => m.value === selected)!;

  function select(mode: Mode) {
    onChange(mode);
    setOpen(false);
  }

  return (
    /* Wrapper must be position:relative so the popup anchors to it */
    <div ref={containerRef} style={{ position: "relative", display: "inline-block" }}>

      {/* ── Trigger Button ── */}
      <button
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        style={{
          display:        "flex",
          alignItems:     "center",
          gap:            "5px",
          padding:        "5px 10px",
          borderRadius:   "8px",
          border:         "1px solid var(--glass-border)",
          background:     open ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.05)",
          color:          "var(--text-secondary)",
          fontSize:       "12px",
          fontWeight:     500,
          fontFamily:     "inherit",
          cursor:         disabled ? "not-allowed" : "pointer",
          opacity:        disabled ? 0.5 : 1,
          transition:     "all 0.2s ease",
          whiteSpace:     "nowrap",
        }}
        title="Switch response mode"
      >
        <span style={{ fontSize: "13px" }}>{currentMode.icon}</span>
        <span>{currentMode.label}</span>
        {/* Chevron — rotates up when open */}
        <svg
          width="10" height="10" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s ease" }}
        >
          <path d="M18 15l-6-6-6 6" />
        </svg>
      </button>

      {/* ── Popup Panel ── */}
      {open && (
        <div
          className="animate-fade-in-up"
          style={{
            position:     "absolute",
            bottom:       "calc(100% + 8px)",  /* Appears above the trigger */
            left:         0,
            width:        "280px",
            borderRadius: "14px",
            overflow:     "hidden",
            background:   "rgba(18, 18, 35, 0.95)",
            border:       "1px solid var(--glass-border)",
            backdropFilter: "blur(20px)",
            boxShadow:    "0 -8px 32px rgba(0,0,0,0.5)",
            zIndex:       100,
          }}
        >
          {/* Label row */}
          <div style={{
            padding:      "10px 14px 6px",
            fontSize:     "11px",
            fontWeight:   600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color:        "var(--text-secondary)",
          }}>
            Response mode
          </div>

          {/* Mode cards */}
          {MODES.map((mode) => {
            const isActive = selected === mode.value;
            return (
              <button
                key={mode.value}
                onClick={() => select(mode.value)}
                style={{
                  display:       "flex",
                  flexDirection: "column",
                  alignItems:    "flex-start",
                  gap:           "3px",
                  width:         "100%",
                  padding:       "10px 14px",
                  border:        "none",
                  borderLeft:    isActive
                    ? "3px solid var(--accent-primary)"
                    : "3px solid transparent",
                  background:    isActive
                    ? "rgba(99,102,241,0.12)"
                    : "transparent",
                  cursor:        "pointer",
                  textAlign:     "left",
                  transition:    "all 0.15s ease",
                  fontFamily:    "inherit",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)";
                }}
                onMouseLeave={(e) => {
                  if (!isActive) (e.currentTarget as HTMLElement).style.background = "transparent";
                }}
              >
                {/* Mode name */}
                <span style={{
                  fontSize:   "13px",
                  fontWeight: isActive ? 600 : 500,
                  color:      isActive ? "var(--text-primary)" : "var(--text-secondary)",
                  display:    "flex",
                  alignItems: "center",
                  gap:        "6px",
                }}>
                  <span>{mode.icon}</span>
                  {mode.label}
                </span>
                {/* Description */}
                <span style={{
                  fontSize:   "12px",
                  color:      "var(--text-secondary)",
                  lineHeight: 1.4,
                  opacity:    0.75,
                }}>
                  {mode.description}
                </span>
              </button>
            );
          })}

          {/* Bottom padding */}
          <div style={{ height: "6px" }} />
        </div>
      )}
    </div>
  );
}
