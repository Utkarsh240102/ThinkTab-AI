import React from "react";

/* ─────────────────────────────────────────────────────────────
   SoftHITLButton Component
   
   A specialized button that appears beneath a Fast mode response.
   Allows the user to easily upgrade their query to "Deep Mode"
   if they are unsatisfied with the quick answer.
─────────────────────────────────────────────────────────────── */

interface SoftHITLButtonProps {
  /** The function to call when the user clicks the button */
  onClick: () => void;
  /** Whether the button should be disabled (e.g. while loading) */
  disabled?: boolean;
}

export default function SoftHITLButton({ onClick, disabled = false }: SoftHITLButtonProps) {
  return (
    <div className="animate-fade-in-up" style={{ display: "flex", justifyContent: "flex-start", marginTop: "4px" }}>
      <button
        onClick={onClick}
        disabled={disabled}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "6px 14px",
          borderRadius: "8px",
          background: "rgba(139, 92, 246, 0.15)", // Subtle purple glow
          border: "1px solid rgba(139, 92, 246, 0.3)",
          color: "var(--text-primary)",
          fontSize: "12px",
          fontWeight: 500,
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          transition: "all 0.2s ease",
          fontFamily: "inherit",
          boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
        }}
        /* Hover effect added via standard React event handlers since we aren't using Tailwind */
        onMouseEnter={(e) => {
          if (!disabled) {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(139, 92, 246, 0.25)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(139, 92, 246, 0.5)";
          }
        }}
        onMouseLeave={(e) => {
          if (!disabled) {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(139, 92, 246, 0.15)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(139, 92, 246, 0.3)";
          }
        }}
      >
        <span style={{ fontSize: "14px" }}>🧠</span>
        Switch to Deep Mode
      </button>
    </div>
  );
}
