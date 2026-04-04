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
# Fast Mode Generator System Prompt
# ─────────────────────────────────────────────────────────────
FAST_GENERATOR_SYSTEM_PROMPT = """You are an expert AI assistant answering questions based ONLY on the provided context.

RULES:
1. You must answer the question using ONLY the information in the provided context paragraphs.
2. Do NOT use outside knowledge.
3. If the context does not contain the answer, you MUST return exactly this for the answer field: "I cannot find the answer on this page."
4. If you find the answer, cite your sources inline using brackets, e.g., "Stripe charges 2.9% [stripe.com]".
5. Extract exact short snippets for your evidence list.
6. Provide a confidence score (0.0 to 1.0) and a short reasoning summary."""

def generate_fast(state: GraphState) -> GraphState:
    """
    Fast Mode Generator

    Uses 'smart_llm' (Groq) to generate a structured
    answer from the filtered context chunks.
    """
    query = state["query"]
    good_docs = state.get("good_docs", [])
    
    if not good_docs:
        print("[Generation] No relevant documents survived filtering. Triggering safety net.")
        return {
            **state,
            "final_answer": "I cannot find the answer on this page.",
            "evidence": [],
            "confidence_score": 0.0,
            "reasoning_summary": "Extracted context was not relevant to the query."
        }
        
    print(f"[Generation] Generating fast answer using {len(good_docs)} chunks...")
    
    context_text = ""
    for i, doc in enumerate(good_docs):
        source = doc.metadata.get("source", "unknown")
        context_text += f"\n--- Chunk {i+1} (Source: {source}) ---\n{doc.page_content}\n"
        
    messages = [
        SystemMessage(content=FAST_GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {query}\n\nContext:\n{context_text}")
    ]
    
    structured_llm = smart_llm.with_structured_output(FinalOutput)
    try:
        result: FinalOutput = structured_llm.invoke(messages)
        
        print(f"[Generation] Answer generated with {(result.confidence_score * 100):.1f}% confidence.")
        
        return {
            **state,
            "final_answer": result.answer,
            "evidence": [item.model_dump() for item in result.evidence],
            "confidence_score": result.confidence_score,
            "reasoning_summary": result.reasoning_summary
        }
    except Exception as e:
        print(f"[Generation] Error generating response: {e}")
        return {
            **state,
            "final_answer": "I cannot find the answer on this page.",
            "evidence": [],
            "confidence_score": 0.0,
            "reasoning_summary": "An error occurred during generation."
        }