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

class IntentClassification(BaseModel):
    intent: Literal["simple", "complex"] = Field(
        description="Classify the query as 'simple' (factual lookup) or 'complex' (reasoning/comparison)"
    )

CLASSIFIER_SYSTEM_PROMPT = """You are a fast intent classifier.
Classify the user's query as either 'simple' or 'complex'.
Simple = single factual lookup or direct question.
Complex = multi-step reasoning, comparison, deep analysis, or subjective evaluation.
Return exactly the structured JSON."""

def route_query(state: GraphState) -> Literal["fast", "deep"]:
    """
    Auto Mode Router: Decides whether to use Fast Mode or Deep Mode.
    Uses a cascading decision tree for minimal latency.
    """
    query = state["query"].lower()
    contexts = state.get("contexts", [])

    # Tier 1: Document Count Check (0ms)
    if len(contexts) > 1:
        print("[Auto Router] > 1 contexts found. Routing to DEEP.")
        return "deep"

    # Tier 2: Keyword Rule Check (0ms)
    if any(keyword in query for keyword in DEEP_MODE_SIGNALS):
        print("[Auto Router] Complex keyword detected. Routing to DEEP.")
        return "deep"

    # Tier 3: LLM Intent Classifier (~300ms)
    print("[Auto Router] Using LLM to classify intent...")
    messages = [
        SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
        HumanMessage(content=f"Query: {state['query']}")
    ]
    
    structured_llm = fast_llm.with_structured_output(IntentClassification)
    try:
        result: IntentClassification = structured_llm.invoke(messages)
        if result.intent == "complex":
            print("[Auto Router] LLM classified intent as Complex. Routing to DEEP.")
            return "deep"
        else:
            print("[Auto Router] LLM classified intent as Simple. Routing to FAST.")
            return "fast"
    except Exception as e:
        # Fallback progressively if classification parsing fails
        print(f"[Auto Router] Classification failed, defaulting to DEEP. Error: {e}")
        return "deep"
