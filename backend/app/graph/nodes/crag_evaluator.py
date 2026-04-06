from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import GraphState
from app.services.llm_service import fast_llm
from app.core.config import settings

class CRAGScore(BaseModel):
    score: float = Field(description="A relevance score between 0.0 and 1.0 (e.g., 0.8)")

CRAG_SYSTEM_PROMPT = """You are an objective document relevance grader.
Read the user's question and the provided document chunk.
Score how relevant the document is to answering the question on a scale of 0.0 to 1.0.
0.0 = completely irrelevant or off-topic.
1.0 = contains the exact answer or highly relevant facts.
Return only the structured JSON score."""

def eval_docs(state: GraphState) -> GraphState:
    """
    Deep Mode CRAG Evaluator.
    
    Iterates through retrieved docs and asks gpt-4o-mini to grade them.
    Assigns:
    - CORRECT: If any chunk > UPPER_CRAG_THRESHOLD (0.7)
    - INCORRECT: If all chunks < LOWER_CRAG_THRESHOLD (0.3)
    - AMBIGUOUS: Else (mixed/weak relevance)
    """
    query = state["query"]
    docs = state.get("docs", [])
    
    if not docs:
        print("[CRAG Evaluator] No documents retrieved. Verdict: INCORRECT.")
        return {**state, "crag_verdict": "INCORRECT", "good_docs": []}
        
    print(f"[CRAG Evaluator] Grading {len(docs)} documents against query...")
    
    good_docs = []
    highest_score = 0.0
    
    structured_llm = fast_llm.with_structured_output(CRAGScore)
    
    for i, doc in enumerate(docs):
        messages = [
            SystemMessage(content=CRAG_SYSTEM_PROMPT),
            HumanMessage(content=f"Question: {query}\n\nDocument Chunk:\n{doc.page_content}")
        ]
        
        try:
            result: CRAGScore = structured_llm.invoke(messages)
            score = result.score
            print(f"  [Chunk {i+1}] Score: {score} | Source: {doc.metadata.get('source', 'unknown')}")
        except Exception as e:
            print(f"  [Chunk {i+1}] Scoring failed: {e}. Assuming 0.0")
            score = 0.0
            
        if score > highest_score:
            highest_score = score
            
        # We physically keep any document that isn't terrible
        if score >= settings.LOWER_CRAG_THRESHOLD:
            good_docs.append(doc)
            
    # Decide the verdict based on the highest scoring document
    if highest_score >= settings.UPPER_CRAG_THRESHOLD:
        verdict = "CORRECT"
    elif highest_score < settings.LOWER_CRAG_THRESHOLD:
        verdict = "INCORRECT"
    else:
        verdict = "AMBIGUOUS"
        
    print(f"[CRAG Evaluator] Highest Score: {highest_score:.2f} -> Verdict: {verdict}")
    print(f"[CRAG Evaluator] Passing {len(good_docs)} good chunks forward.")
    
    return {
        **state,
        "crag_verdict": verdict,
        "good_docs": good_docs
    }