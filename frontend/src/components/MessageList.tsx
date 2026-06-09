import React from "react";
import ErrorBubble from "./ErrorBubble";
import TypewriterMarkdown from "./TypewriterMarkdown";
import EvidenceAccordion from "./EvidenceAccordion";
import SoftHITLButton from "./SoftHITLButton";
import type { Message } from "./ChatShell";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onRetry: () => void;
  onSwitchToDeep: () => void;
  onTypingDone: (id: string) => void;
  bottomRef: React.RefObject<HTMLDivElement>;
}

export default function MessageList({
  messages,
  isLoading,
  onRetry,
  onSwitchToDeep,
  onTypingDone,
  bottomRef,
}: MessageListProps) {
  function confidenceColor(score: number): string {
    if (score >= 0.8) return "var(--status-success)";
    if (score >= 0.5) return "var(--status-thinking)";
    return "var(--status-error)";
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {messages.map((msg, index) => {
        const isFinalMessage = index === messages.length - 1;
        return (
          <div
            key={msg.id}
            className="animate-fade-in-up"
            style={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            {msg.role === "user" ? (
              <div
                style={{
                  fontSize: "13px",
                  lineHeight: 1.6,
                  padding: "10px 16px",
                  borderRadius: "18px",
                  borderBottomRightRadius: "4px",
                  maxWidth: "85%",
                  background:
                    "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
                  color: "white",
                }}
              >
                {msg.content}
              </div>
            ) : (
              <div
                style={{
                  maxWidth: "92%",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                <div
                  className="markdown-body"
                  style={{
                    fontSize: "13px",
                    lineHeight: 1.7,
                    padding: "12px 16px",
                    borderRadius: "18px",
                    borderBottomLeftRadius: "4px",
                    background: "var(--glass-bg)",
                    border: "1px solid var(--glass-border)",
                    color: "var(--text-primary)",
                  }}
                >
                  <TypewriterMarkdown
                    text={msg.answer}
                    enabled={Boolean(msg.isTyping)}
                    onDone={() => onTypingDone(msg.id)}
                  />
                </div>

                {!msg.isTyping &&
                  (msg.evidence.length > 0 || msg.confidence_score > 0) && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                        paddingLeft: "4px",
                      }}
                    >
                      {msg.confidence_score > 0 && (
                        <div style={{ display: "flex" }}>
                          <span
                            style={{
                              fontSize: "11px",
                              padding: "2px 8px",
                              borderRadius: "99px",
                              background: `${confidenceColor(
                                msg.confidence_score
                              )}20`,
                              border: `1px solid ${confidenceColor(
                                msg.confidence_score
                              )}50`,
                              color: confidenceColor(msg.confidence_score),
                            }}
                          >
                            {Math.round(msg.confidence_score * 100)}% confident
                          </span>
                        </div>
                      )}

                      {msg.evidence.length > 0 && (
                        <EvidenceAccordion evidence={msg.evidence} />
                      )}
                    </div>
                  )}

                {!msg.isTyping &&
                  msg.role === "assistant" &&
                  isFinalMessage &&
                  msg.mode.includes("Fast") && (
                    <div style={{ marginTop: "4px" }}>
                      <SoftHITLButton
                        onClick={onSwitchToDeep}
                        disabled={isLoading}
                      />
                    </div>
                  )}
              </div>
            )}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
