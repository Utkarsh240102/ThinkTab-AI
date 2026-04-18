from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import GraphState
from app.services.llm_service import fast_llm
from app.core.config import settings


# ─────────────────────────────────────────────────────────────
# Pydantic Schema — Batch scoring returns one score per chunk
# ─────────────────────────────────────────────────────────────
class CRAGScoreBatch(BaseModel):
    scores: List[float] = Field(
        description=(
            "A relevance score between 0.0 and 1.0 for EACH document chunk, "
            "in the SAME ORDER they were provided. "
            "0.0 = completely irrelevant. 1.0 = directly answers the question."
        )
    )


CRAG_SYSTEM_PROMPT = """You are an objective document relevance grader.
You will be given a user question and a numbered list of document chunks.
Score how relevant EACH chunk is to answering the question on a scale of 0.0 to 1.0.
  0.0 = completely irrelevant or off-topic
  1.0 = contains the exact answer or highly relevant facts

Return a JSON list of scores in the EXACT SAME ORDER as the chunks provided.
If there are 4 chunks, return exactly 4 scores.
Return only the structured JSON."""


def eval_docs(state: GraphState) -> GraphState:
    """
    Deep Mode CRAG Evaluator (Batch Version).

    Sends ALL retrieved chunks to the LLM in ONE call instead of N separate calls.
    This is 5x faster and 5x cheaper than the old per-doc loop.

    Assigns:
    - CORRECT:   If any chunk score >= UPPER_CRAG_THRESHOLD (0.7)
    - INCORRECT: If all chunk scores < LOWER_CRAG_THRESHOLD (0.3)
    - AMBIGUOUS: Mixed/weak relevance (between thresholds)
    """
    query = state["query"]
    docs = state.get("docs", [])

    if not docs:
        print("[CRAG Evaluator] No documents retrieved. Verdict: INCORRECT.")
        return {**state, "crag_verdict": "INCORRECT", "good_docs": []}

    print(f"[CRAG Evaluator] Batch-grading {len(docs)} chunks in 1 LLM call...")

    # Build the numbered list prompt — same format as fast_mode batch CRAG
    chunks_text = ""
    for i, doc in enumerate(docs):
        chunks_text += f"\n[{i}] {doc.page_content}\n"

    messages = [
        SystemMessage(content=CRAG_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {query}\n\nDocument Chunks:{chunks_text}")
    ]

    structured_llm = fast_llm.with_structured_output(CRAGScoreBatch)

    try:
        result: CRAGScoreBatch = structured_llm.invoke(messages)
        scores = result.scores

        # Guard: if the LLM returns fewer scores than docs (rare), pad with 0.0
        if len(scores) < len(docs):
            print(f"[CRAG Evaluator] WARNING: Got {len(scores)} scores for {len(docs)} docs. Padding with 0.0")
            scores += [0.0] * (len(docs) - len(scores))

    except Exception as e:
        print(f"[CRAG Evaluator] Batch scoring failed: {e}. Assuming 0.5 for all chunks.")
        scores = [0.5] * len(docs)

    # Process scores — same logic as before, just now we have all scores at once
    good_docs = []
    highest_score = 0.0

    for i, (doc, score) in enumerate(zip(docs, scores)):
        print(f"  [Chunk {i+1}] Score: {score:.2f} | Source: {doc.metadata.get('source', 'unknown')}")

        if score > highest_score:
            highest_score = score

        if score >= settings.LOWER_CRAG_THRESHOLD:
            good_docs.append(doc)

    # Determine verdict based on highest score
    if highest_score >= settings.UPPER_CRAG_THRESHOLD:
        verdict = "CORRECT"
    elif highest_score < settings.LOWER_CRAG_THRESHOLD:
        verdict = "INCORRECT"
    else:
        verdict = "AMBIGUOUS"

    print(f"[CRAG Evaluator] Highest Score: {highest_score:.2f} → Verdict: {verdict}")
    print(f"[CRAG Evaluator] Passing {len(good_docs)} good chunks forward.")

    return {
        **state,
        "crag_verdict": verdict,
        "good_docs": good_docs
    }