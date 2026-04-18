/* ─────────────────────────────────────────────────────────────
   EmptyState Component
   
   Shown in the message area when there are no messages yet.
   Its job is to:
     1. Look beautiful (not a blank white void)
     2. Show the user what they can do ("Ask me anything...")
     3. Surface 3 example prompt chips to lower the barrier
        to asking a first question
─────────────────────────────────────────────────────────────── */

interface EmptyStateProps {
  /** Called when the user clicks one of the example prompt chips */
  onPromptClick: (prompt: string) => void;
}

const EXAMPLE_PROMPTS = [
  "Summarize this page for me",
  "What are the key points here?",
  "Compare this with what I know",
];

export default function EmptyState({ onPromptClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-10 text-center animate-fade-in-up">

      {/* ── Glowing icon ── */}
      <div
        className="mb-5 flex items-center justify-center w-16 h-16 rounded-2xl"
        style={{
          background: "linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.2))",
          border: "1px solid rgba(99,102,241,0.3)",
          boxShadow: "0 0 40px rgba(99,102,241,0.15)",
        }}
      >
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="url(#icon-gradient)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <defs>
            <linearGradient id="icon-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%"   stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
          </defs>
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <path d="M12 17h.01" />
        </svg>
      </div>

      {/* ── Heading ── */}
      <h2
        className="text-lg font-semibold mb-2"
        style={{ color: "var(--text-primary)" }}
      >
        Ask about this page
      </h2>

      {/* ── Sub-text ── */}
      <p
        className="text-sm leading-relaxed mb-6 max-w-[220px]"
        style={{ color: "var(--text-secondary)" }}
      >
        I can answer questions, summarize content, and find information from the page you&apos;re reading.
      </p>

      {/* ── Example Prompt Chips ── */}
      <div className="flex flex-col gap-2 w-full">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onPromptClick(prompt)}
            className="btn-ghost text-left text-sm px-4 py-2.5 w-full transition-all duration-200"
            style={{ color: "var(--text-secondary)" }}
          >
            <span style={{ color: "var(--accent-primary)", marginRight: "8px" }}>→</span>
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
