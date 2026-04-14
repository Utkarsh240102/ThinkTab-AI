from typing import List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.services.llm_service import smart_llm
from app.graph.state import GraphState


# ─────────────────────────────────────────────────────────────
# Structured Output Schema
# ─────────────────────────────────────────────────────────────
class EvidenceItem(BaseModel):
    source: str = Field(description="The source_id of the document used, e.g. 'stripe.com'")
    snippet: str = Field(description="The exact sentence or short phrase used as evidence")


class FinalOutput(BaseModel):
    reasoning_summary: str = Field(description="A short plain-English explanation of how the answer was derived")
    answer: str = Field(description="The markdown-formatted final answer. MUST cite sources using [Source Name] format inline. If the answer is not found, this MUST be exactly 'I cannot find the answer on this page.'")
    evidence: List[EvidenceItem] = Field(description="List of evidence items used to formulate the answer")
    confidence_score: float = Field(description="A score between 0.0 and 1.0 indicating confidence in the answer")


# ─────────────────────────────────────────────────────────────
# Shared System Prompt (used by both Fast and Deep generators)
# ─────────────────────────────────────────────────────────────
GENERATOR_SYSTEM_PROMPT = """You are an expert AI assistant answering questions based ONLY on the provided context.

RULES:
1. Answer using ONLY the information in the provided context. Do NOT use outside knowledge.
2. If context does not contain the answer, return EXACTLY: "I cannot find the answer on this page."
3. Cite sources inline using brackets, e.g., "Stripe charges 2.9% [stripe.com]".
4. Extract exact short snippets for the evidence list.
5. Provide a confidence score (0.0 to 1.0) and a short reasoning summary."""

# Alias for backwards compatibility with fast_mode.py
FAST_GENERATOR_SYSTEM_PROMPT = GENERATOR_SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────
# Fast Mode Generator
# ─────────────────────────────────────────────────────────────
def generate_fast(state: GraphState) -> GraphState:
    """
    Fast Mode Generator

    Reads from: state["good_docs"] — chunks that survived Batch CRAG filter
    Writes to:  state["final_answer"] — directly shown to the user

    Used exclusively by the Fast Mode linear pipeline.
    Does NOT go through Self-RAG validation (hallucination/usefulness checks).
    """
    query = state["query"]
    good_docs = state.get("good_docs", [])

    if not good_docs:
        print("[Generation - Fast] No docs after filtering. Triggering safety net.")
        return {
            **state,
            "final_answer": "I cannot find the answer on this page.",
            "evidence": [],
            "confidence_score": 0.0,
            "reasoning_summary": "Extracted context was not relevant to the query."
        }

    print(f"[Generation - Fast] Generating answer using {len(good_docs)} chunks...")

    context_text = ""
    for i, doc in enumerate(good_docs):
        source = doc.metadata.get("source", "unknown")
        context_text += f"\n--- Chunk {i+1} (Source: {source}) ---\n{doc.page_content}\n"

    messages = [
        SystemMessage(content=GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {query}\n\nContext:\n{context_text}")
    ]

    structured_llm = smart_llm.with_structured_output(FinalOutput)
    try:
        result: FinalOutput = structured_llm.invoke(messages)
        print(f"[Generation - Fast] Done. Confidence: {(result.confidence_score * 100):.1f}%")
        return {
            **state,
            "final_answer": str(result.answer),
            "evidence": [item.model_dump() for item in result.evidence],
            "confidence_score": result.confidence_score,
            "reasoning_summary": str(result.reasoning_summary)
        }
    except Exception as e:
        print(f"[Generation - Fast] Error: {e}")
        return {
            **state,
            "final_answer": "I cannot find the answer on this page.",
            "evidence": [],
            "confidence_score": 0.0,
            "reasoning_summary": "An error occurred during generation."
        }


# ─────────────────────────────────────────────────────────────
# Deep Mode Generator — THE CRITICAL DIFFERENCE
# ─────────────────────────────────────────────────────────────
def generate_deep(state: GraphState) -> GraphState:
    """
    Deep Mode Generator

    Reads from: state["refined_context"] — CRAG sentence-level filtered string
    Writes to:  state["draft_answer"]  ← NOT final_answer yet!

    The draft MUST pass both Self-RAG checks before becoming final_answer:
        check_hallucination (IsSUP) → revise_answer if fails
        check_usefulness    (IsUSE) → rewrite_question if fails

    Only after both checks pass does draft_answer become final_answer.

    Key differences from generate_fast:
    - Reads refined_context (dense, sentence-filtered string) not raw chunk docs
    - Writes to draft_answer so hallucination/usefulness graders can inspect it
    - Never directly sets final_answer (that is done by check_usefulness on success)
    """
    query = state["query"]
    refined_context = state.get("refined_context", "")

    if not refined_context or not refined_context.strip():
        print("[Generation - Deep] No refined context. Cannot generate.")
        return {
            **state,
            "draft_answer": "I cannot find the answer on this page.",
            "evidence": [],
            "confidence_score": 0.0,
            "reasoning_summary": "No relevant context survived CRAG refinement."
        }

    print(f"[Generation - Deep] Generating draft from {len(refined_context)} chars of refined context...")

    messages = [
        SystemMessage(content=GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {query}\n\nContext:\n{refined_context}")
    ]

    structured_llm = smart_llm.with_structured_output(FinalOutput)
    try:
        result: FinalOutput = structured_llm.invoke(messages)
        print(f"[Generation - Deep] Draft ready. Confidence: {(result.confidence_score * 100):.1f}%")
        return {
            **state,
            "draft_answer": result.answer,          # Goes to Self-RAG checks, NOT the user yet
            "evidence": [item.model_dump() for item in result.evidence],
            "confidence_score": result.confidence_score,
            "reasoning_summary": result.reasoning_summary
        }
    except Exception as e:
        print(f"[Generation - Deep] Error: {e}")
        return {
            **state,
            "draft_answer": "I cannot find the answer on this page.",
            "evidence": [],
            "confidence_score": 0.0,
            "reasoning_summary": "An error occurred during deep generation."
        }