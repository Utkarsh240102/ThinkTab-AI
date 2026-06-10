import json
from typing import List
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from app.services.llm_service import fast_llm
from app.graph.state import GraphState


class QueryAnalysis(BaseModel):
    standalone_query: str = Field(description="The rewritten standalone query with generic UI terms replaced by their concrete topics.")
    target_source_ids: List[str] = Field(description="An exact list of source_ids the user is referring to. If the user is asking a general question or wants to search everything, return an empty list.")


# ─────────────────────────────────────────────────────────────
# System prompt for the Structured AI Router
# ─────────────────────────────────────────────────────────────
CONTEXTUALIZER_SYSTEM_PROMPT = """You are a Structured AI Router. Your job is to rewrite the user's latest question into a fully standalone question AND determine exactly which document sources the user wants to search.

Rules for standalone_query:
- Resolve ALL pronouns and references using the conversation history (e.g. "it", "that", "the second one", "them").
- CRITICAL: Aggressively substitute vague nouns like "the two webpages", "both documents", "the pinned tab", or "the active tab" with their actual concrete topics based on the conversation history or the provided context sources.
- Do NOT answer the question — only rewrite it.
- Do NOT add new information or assumptions.
- If the question is already standalone and clear, return it exactly as-is.

Rules for target_source_ids:
- Look at the AVAILABLE CONTEXT SOURCES. If the user's query refers to specific UI elements (e.g., "pinned tab", "this page", "the pdf"), you MUST output the exact string `source_id` for those documents.
- If the user asks to compare things, output the `source_id`s for all relevant documents.
- If the user asks a general question and does not specify a source, return an empty list `[]`.
"""

def contextualize_query(state: GraphState) -> GraphState:
    """
    LangGraph Node: Structured Query Contextualizer & Router
    """

    query = state["query"]
    chat_history = state.get("chat_history") or []
    contexts = state.get("contexts", [])

    # ── BUG 1 FIX: Deterministic Universal Scope Guard ────────────────────────
    ALL_SIGNALS = [
        "all tab", "all tabs", "all the tab", "all the tabs",
        "every tab", "each tab", "all of them", "all sources",
        "all documents", "all pages", "explain all", "summarize all"
    ]
    
    _query_lower = query.lower()
    _last_msg = chat_history[-1].get("content", "").lower() if chat_history else ""
    
    if any(sig in _query_lower or sig in _last_msg for sig in ALL_SIGNALS):
        print(f"[Contextualizer] 'All Tabs' universal scope detected deterministically. Bypassing LLM.")
        return {
            **state,
            "original_query": query,
            "query": query, # leave unchanged
            "target_source_ids": [ctx.get("source_id") for ctx in contexts]
        }
    # ── End BUG 1 FIX ─────────────────────────────────────────────────────────

    available_sources = [ctx.get("source_id", "Unknown") for ctx in contexts]
    source_mapping_text = f"\n\nAVAILABLE CONTEXT SOURCES:\n{json.dumps(available_sources, indent=2)}\n"

    # Build the last 4 messages of history as a readable string
    recent_history = chat_history[-4:]
    history_text = "\n".join([
        f"{msg.get('role', 'user').capitalize()}: {msg.get('content', '')}"
        for msg in recent_history
        if msg.get("content")
    ])

    summary_text = (
        f"\n\n[Previous Conversation Summary]: {state['history_summary']}\n\n"
        if state.get("history_summary")
        else ""
    )

    system_prompt = CONTEXTUALIZER_SYSTEM_PROMPT + summary_text + source_mapping_text

    print(f"[Contextualizer] Analyzing intent for: '{query}'")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Conversation history:\n{history_text}\n\nLatest question:\n{query}")
    ]

    structured_llm = fast_llm.with_structured_output(QueryAnalysis)
    try:
        result: QueryAnalysis = structured_llm.invoke(messages)
        rewritten_query = result.standalone_query.strip()
        target_sources = result.target_source_ids
    except Exception as e:
        print(f"[Contextualizer] Structured parsing failed: {e}. Falling back to defaults.")
        rewritten_query = query
        target_sources = []

    print(f"[Contextualizer] Rewritten query: '{rewritten_query}'")
    print(f"[Contextualizer] Target sources: {target_sources}")

    return {
        **state,
        "original_query": query,
        "query": rewritten_query,
        "target_source_ids": target_sources
    }
