from langchain_core.messages import HumanMessage, SystemMessage
from app.services.llm_service import fast_llm
from app.graph.state import GraphState


# ─────────────────────────────────────────────────────────────
# System prompt for the contextualizer
# ─────────────────────────────────────────────────────────────
CONTEXTUALIZER_SYSTEM_PROMPT = """You are a query rewriter. Your ONLY job is to rewrite the user's latest question into a fully standalone question.

Rules:
- Resolve ALL pronouns and references using the conversation history (e.g. "it", "that", "the second one", "them")
- Do NOT add new information or assumptions
- Do NOT answer the question — only rewrite it
- If the question is already standalone and clear, return it exactly as-is
- Return ONLY the rewritten question, nothing else. No explanations, no preamble."""


def contextualize_query(state: GraphState) -> GraphState:
    """
    LangGraph Node: Query Contextualizer

    Rewrites vague follow-up questions into standalone questions
    using the conversation history.

    Examples:
        "explain the second one more" → "Can you explain the second pricing tier of Stripe in more detail?"
        "why is it faster?"           → "Why is Stripe's payment processing faster than PayPal's?"
        "What is Stripe?"             → "What is Stripe?" (already standalone, returned as-is)

    Skips the LLM call entirely if there is no chat history (first message).
    """

    query = state["query"]
    chat_history = state.get("chat_history") or []

    # ── Skip if this is the first message (no history to resolve) ──
    if not chat_history:
        print("[Contextualizer] No chat history — using query as-is.")
        return {
            **state,
            "original_query": query,  # Preserve the raw query
            "query": query,           # No change needed
        }

    # ── Build the last 4 messages of history as a readable string ──
    # We only use the last 4 to keep the prompt short and cheap
    recent_history = chat_history[-4:]
    history_text = "\n".join([
        f"{msg.get('role', 'user').capitalize()}: {msg.get('content', '')}"
        for msg in recent_history
        if msg.get("content")   # skip empty messages
    ])

    print(f"[Contextualizer] Resolving references in: '{query}'")

    # ── Call gpt-4o-mini to rewrite the query ──
    messages = [
        SystemMessage(content=CONTEXTUALIZER_SYSTEM_PROMPT),
        HumanMessage(content=f"""Conversation history:
{history_text}

Latest question to rewrite:
{query}""")
    ]

    response = fast_llm.invoke(messages)
    rewritten_query = response.content.strip()

    print(f"[Contextualizer] Rewritten: '{rewritten_query}'")

    return {
        **state,
        "original_query": query,          # Always keep the raw user query
        "query": rewritten_query,          # Replace with the standalone version
    }
