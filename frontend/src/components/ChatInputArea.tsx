import React, { useRef } from "react";
import ModeSelector, { type Mode } from "./ModeSelector";
import QueryInput from "./QueryInput";
import type { Context } from "../hooks/useSSEChat";

interface ChatInputAreaProps {
  // Input props
  query: string;
  setQuery: (q: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  onStop: () => void;

  // Toolbar props
  selectedMode: Mode;
  setSelectedMode: (m: Mode) => void;
  chatHistoryLength: number;
  onExportChat: () => void;

  // Pinned tab props
  pinnedContexts: Context[];
  onPinTab: () => void;
  onClearPinned: () => void;
  onRemovePinned: (sourceId: string) => void;

  // PDF props
  pdfContext: { source_id: string; content: string } | null;
  onRemovePDF: () => void;
  isPDFLoading: boolean;
  pdfStatusText: string;
  pdfError: string | null;
  clearPDFError: () => void;
  onPDFFileSelected: (file: File) => void;
}

export default function ChatInputArea({
  query,
  setQuery,
  onSubmit,
  isLoading,
  onStop,
  selectedMode,
  setSelectedMode,
  chatHistoryLength,
  onExportChat,
  pinnedContexts,
  onPinTab,
  onClearPinned,
  onRemovePinned,
  pdfContext,
  onRemovePDF,
  isPDFLoading,
  pdfStatusText,
  pdfError,
  clearPDFError,
  onPDFFileSelected,
}: ChatInputAreaProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div style={{ position: "relative" }}>
      {/* ── PDF Error Toast ── */}
      {pdfError && (
        <div
          style={{
            margin: "0 16px 8px",
            padding: "8px 12px",
            borderRadius: "8px",
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.3)",
            color: "#ef4444",
            fontSize: "12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "8px",
          }}
        >
          <span>⚠️ {pdfError}</span>
          <button
            onClick={clearPDFError}
            style={{
              background: "none",
              border: "none",
              color: "#ef4444",
              cursor: "pointer",
              fontSize: "14px",
              padding: 0,
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* ── Active PDF Badge ── */}
      {pdfContext && (
        <div
          style={{
            margin: "0 16px 6px",
            padding: "5px 10px",
            borderRadius: "20px",
            background: "rgba(99,102,241,0.12)",
            border: "1px solid rgba(99,102,241,0.3)",
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "11px",
            color: "var(--text-accent)",
            maxWidth: "calc(100% - 32px)",
          }}
        >
          <span>📄</span>
          {/* Truncate very long filenames so they don't overflow */}
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              maxWidth: "200px",
            }}
          >
            {pdfContext.source_id}
          </span>
          <button
            onClick={onRemovePDF}
            title="Remove PDF"
            style={{
              background: "none",
              border: "none",
              color: "var(--text-secondary)",
              cursor: "pointer",
              fontSize: "14px",
              padding: 0,
              lineHeight: 1,
              flexShrink: 0,
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Toolbar row: mode selector + PDF attach button */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "8px 16px 0",
          borderTop: "1px solid var(--glass-border)",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        <ModeSelector
          selected={selectedMode}
          onChange={setSelectedMode}
          disabled={isLoading}
        />

        <button
          onClick={onExportChat}
          disabled={chatHistoryLength === 0}
          title="Export chat as Markdown"
          style={{
            border: "1px solid var(--glass-border)",
            borderRadius: "8px",
            padding: "5px 10px",
            background: "rgba(255,255,255,0.05)",
            color: "var(--text-secondary)",
            fontSize: "12px",
            fontWeight: 500,
            fontFamily: "inherit",
            cursor: chatHistoryLength === 0 ? "not-allowed" : "pointer",
            opacity: chatHistoryLength === 0 ? 0.45 : 1,
            transition: "all 0.2s ease",
            whiteSpace: "nowrap",
          }}
        >
          Export
        </button>

        <button
          onClick={onPinTab}
          disabled={isLoading}
          title={`Pin current tab${
            pinnedContexts.length ? ` (${pinnedContexts.length} pinned)` : ""
          }`}
          style={{
            border: "1px solid var(--glass-border)",
            borderRadius: "8px",
            padding: "5px 10px",
            background: "rgba(255,255,255,0.05)",
            color: "var(--text-secondary)",
            fontSize: "12px",
            fontWeight: 500,
            fontFamily: "inherit",
            cursor: isLoading ? "not-allowed" : "pointer",
            opacity: isLoading ? 0.45 : 1,
            transition: "all 0.2s ease",
            whiteSpace: "nowrap",
          }}
        >
          {pinnedContexts.length > 0
            ? `Pinned (${pinnedContexts.length})`
            : "Pin Current Tab 📌"}
        </button>

        <button
          onClick={onClearPinned}
          disabled={pinnedContexts.length === 0}
          title="Clear pinned tabs"
          style={{
            border: "1px solid var(--glass-border)",
            borderRadius: "8px",
            padding: "5px 10px",
            background: "rgba(255,255,255,0.05)",
            color: "var(--text-secondary)",
            fontSize: "12px",
            fontWeight: 500,
            fontFamily: "inherit",
            cursor: pinnedContexts.length === 0 ? "not-allowed" : "pointer",
            opacity: pinnedContexts.length === 0 ? 0.45 : 1,
            transition: "all 0.2s ease",
            whiteSpace: "nowrap",
          }}
        >
          Clear Pinned
        </button>

        {/* Spacer pushes attach button to the right */}
        <div style={{ flex: 1 }} />

        {/* ── PDF Attach Button ── */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isPDFLoading || isLoading}
          title={
            isPDFLoading
              ? pdfStatusText || "Parsing..."
              : pdfContext
              ? `PDF attached: ${pdfContext.source_id}`
              : "Attach a PDF"
          }
          style={{
            background: pdfContext
              ? "rgba(99,102,241,0.22)"
              : "rgba(255,255,255,0.08)",
            border: pdfContext
              ? "1px solid rgba(99,102,241,0.55)"
              : "1px solid rgba(165,180,252,0.38)",
            borderRadius: "8px",
            padding: "6px 8px",
            minWidth: "34px",
            minHeight: "32px",
            cursor: isPDFLoading ? "wait" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-primary)",
            transition: "all 0.2s ease",
            opacity: isPDFLoading ? 0.6 : 1,
            boxShadow: pdfContext
              ? "0 0 14px rgba(99,102,241,0.28)"
              : "0 0 10px rgba(165,180,252,0.12)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = pdfContext
              ? "rgba(99,102,241,0.3)"
              : "rgba(165,180,252,0.16)";
            (e.currentTarget as HTMLButtonElement).style.borderColor =
              "rgba(165,180,252,0.65)";
            (e.currentTarget as HTMLButtonElement).style.color = "white";
            (e.currentTarget as HTMLButtonElement).style.boxShadow =
              "0 0 16px rgba(165,180,252,0.3)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = pdfContext
              ? "rgba(99,102,241,0.22)"
              : "rgba(255,255,255,0.08)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = pdfContext
              ? "rgba(99,102,241,0.55)"
              : "rgba(165,180,252,0.38)";
            (e.currentTarget as HTMLButtonElement).style.color =
              "var(--text-primary)";
            (e.currentTarget as HTMLButtonElement).style.boxShadow = pdfContext
              ? "0 0 14px rgba(99,102,241,0.28)"
              : "0 0 10px rgba(165,180,252,0.12)";
          }}
        >
          {isPDFLoading ? (
            // Spinning loader while PDF is being parsed
            <svg
              className="animate-spin"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
            >
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
          ) : (
            // Paperclip icon
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          )}
        </button>

        {/* Hidden file input — only accepts PDF files */}
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          style={{ display: "none" }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) {
              onPDFFileSelected(file);
            }
          }}
        />
      </div>

      {pinnedContexts.length > 0 && (
        <div
          style={{
            margin: "8px 16px 0",
            display: "flex",
            flexWrap: "wrap",
            gap: "6px",
          }}
        >
          {pinnedContexts.map((ctx) => (
            <span
              key={ctx.source_id}
              title={ctx.source_id}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                maxWidth: "100%",
                padding: "4px 6px 4px 8px",
                borderRadius: "999px",
                background: "rgba(16,185,129,0.12)",
                border: "1px solid rgba(16,185,129,0.28)",
                color: "var(--status-success)",
                fontSize: "11px",
                lineHeight: 1.3,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {ctx.source_id}
              </span>
              <button
                onClick={() => onRemovePinned(ctx.source_id)}
                title={`Remove ${ctx.source_id}`}
                style={{
                  width: "16px",
                  height: "16px",
                  borderRadius: "50%",
                  border: "none",
                  background: "rgba(16,185,129,0.2)",
                  color: "var(--status-success)",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "12px",
                  lineHeight: 1,
                  padding: 0,
                  flexShrink: 0,
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input textarea */}
      <QueryInput
        value={query}
        onChange={setQuery}
        onSubmit={onSubmit}
        isLoading={isLoading}
        onStop={onStop}
      />
    </div>
  );
}
