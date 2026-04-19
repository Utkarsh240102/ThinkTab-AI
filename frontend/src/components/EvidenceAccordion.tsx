import { useState } from "react";
import { type EvidenceItem } from "../hooks/useSSEChat";

/* ─────────────────────────────────────────────────────────────
   EvidenceAccordion Component
   
   A collapsible drawer used to display the raw text snippets 
   that the AI used to generate its answer. 
   Keeps the chat UI clean while allowing users to verify facts.
─────────────────────────────────────────────────────────────── */

interface EvidenceAccordionProps {
  evidence: EvidenceItem[];
}

export default function EvidenceAccordion({ evidence }: EvidenceAccordionProps) {
  const [isOpen, setIsOpen] = useState(false);

  // If there is no evidence, don't render anything at all
  if (!evidence || evidence.length === 0) return null;

  return (
    <div style={{ marginTop: "4px" }}>
      {/* ── Accordion Toggle Button ── */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "4px 8px",
          border: "1px solid var(--glass-border)",
          borderRadius: "6px",
          background: "rgba(255, 255, 255, 0.05)",
          color: "var(--text-secondary)",
          fontSize: "11px",
          fontWeight: 500,
          cursor: "pointer",
          transition: "all 0.2s ease",
          fontFamily: "inherit",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(255, 255, 255, 0.1)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(255, 255, 255, 0.05)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
        }}
      >
        <span>📎 View {evidence.length} {evidence.length === 1 ? "Source" : "Sources"}</span>
        {/* Chevron icon (rotates when opened) */}
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s ease",
          }}
        >
          <path d="M18 15l-6-6-6 6" />
        </svg>
      </button>

      {/* ── Collapsible Content Area ── */}
      {isOpen && (
        <div
          className="animate-fade-in-up"
          style={{
            marginTop: "8px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            paddingLeft: "6px",
            borderLeft: "2px solid var(--glass-border)",
          }}
        >
          {evidence.map((ev, i) => (
            <div
              key={i}
              style={{
                background: "rgba(0, 0, 0, 0.2)",
                borderRadius: "6px",
                padding: "8px 10px",
                border: "1px solid rgba(255, 255, 255, 0.03)",
              }}
            >
              <div
                style={{
                  fontSize: "10px",
                  color: "var(--accent-primary)",
                  fontWeight: 600,
                  marginBottom: "4px",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Source: {ev.source_id}
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--text-secondary)",
                  lineHeight: 1.5,
                  wordBreak: "break-word",
                }}
              >
                {/* 
                  Render the snippet. If it's too long, you can clamp it with CSS later, 
                  but for now we just show the whole snippet extracted by the AI 
                */}
                "{ev.snippet}"
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
