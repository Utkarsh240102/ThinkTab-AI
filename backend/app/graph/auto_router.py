from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import GraphState
from app.services.llm_service import fast_llm

DEEP_MODE_SIGNALS = [
    "compare", "analyze", "why", "evaluate", "difference",
    "reliable", "better", "pros and cons", "cross-reference",
    "validate", "summarize all", "across", "between"
]

# ─────────────────────────────────────────────────────────────
# Intent Classification Schema — Now with 3 categories:
#   "chat"    → greeting / small talk / pleasantry (NEW)
#   "simple"  → single factual question
#   "complex" → multi-step reasoning / comparison
# ─────────────────────────────────────────────────────────────
class IntentClassification(BaseModel):
    intent: Literal["chat", "simple", "complex"] = Field(
        description=(
            "Classify the query intent:\n"
            "- 'chat': greeting, small talk, thank you, or conversational pleasantry "
            "that does NOT require factual retrieval (e.g. 'hi', 'how are you', 'thanks', 'bye').\n"
            "- 'simple': a direct factual question requiring a single lookup.\n"
            "- 'complex': multi-step reasoning, comparison, or deep analysis."
        )
    )

CLASSIFIER_SYSTEM_PROMPT = """You are a fast query intent classifier for a RAG-based AI assistant.

Classify every incoming user query into exactly ONE of three categories:

1. "chat"    → The message is a greeting, farewell, small talk, or social pleasantry.
               It does NOT need any document search or factual retrieval.
               Examples: "hi", "hello", "hey", "how are you", "thanks", "thank you",
               "bye", "good morning", "what's up", "you there?", "okay", "cool", "got it"

2. "simple"  → A direct factual question that needs a single document lookup.
               Examples: "what is the price?", "who wrote this?", "when was it founded?"

3. "complex" → Requires multi-step reasoning, comparison, analysis, or evaluation.
               Examples: "compare the pros and cons", "why did this happen?", "analyze the argument"

Return exactly the structured JSON with the 'intent' field."""


def route_query(state: GraphState) -> Literal["chat", "fast", "deep"]:
    """
    Auto Mode Router: Decides whether to use Chat Bypass, Fast Mode, or Deep Mode.

    Uses a 3-tier cascading decision tree for minimal latency:
    Tier 1: Context count check (0ms)
    Tier 2: Keyword rule check (0ms)
    Tier 3: LLM intent classification (~300ms) — now with "chat" detection
    """
    query = state["query"].lower().strip()
    contexts = state.get("contexts", [])

    # ── Tier 1: Document Count Check (0ms) ──────────────────────────────
    # Multiple contexts = user is researching across sources = Deep Mode
    if len(contexts) > 1:
        print("[Auto Router] > 1 contexts found. Routing to DEEP.")
        return "deep"

    # ── Tier 2: Keyword Rule Check (0ms) ────────────────────────────────
    # Explicit deep-reasoning keywords → skip to Deep Mode immediately
    if any(keyword in query for keyword in DEEP_MODE_SIGNALS):
        print("[Auto Router] Complex keyword detected. Routing to DEEP.")
        return "deep"

    # ── Tier 3: LLM Intent Classifier (~300ms) ──────────────────────────
    # Ask gpt-4o-mini to classify into chat / simple / complex
    print("[Auto Router] Using LLM to classify intent...")
    messages = [
        SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
        HumanMessage(content=f"Query: {state['query']}")
    ]

    structured_llm = fast_llm.with_structured_output(IntentClassification)
    try:
        result: IntentClassification = structured_llm.invoke(messages)

        if result.intent == "chat":
            print("[Auto Router] LLM classified intent as Chat. Routing to CONVERSATIONAL BYPASS.")
            return "chat"
        elif result.intent == "complex":
            print("[Auto Router] LLM classified intent as Complex. Routing to DEEP.")
            return "deep"
        else:
            print("[Auto Router] LLM classified intent as Simple. Routing to FAST.")
            return "fast"

    except Exception as e:
        # Safe fallback: if classification fails, use Deep Mode (most capable)
        print(f"[Auto Router] Classification failed, defaulting to DEEP. Error: {e}")
        return "deep"

