import json
from pydantic import BaseModel, Field
from typing import List, AsyncGenerator
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import GraphState
from app.services.llm_service import fast_llm
from app.graph.nodes.contextualizer import contextualize_query
from app.graph.nodes.retrieval import retrieve_and_rerank
from app.graph.nodes.generation import generate_fast

class KeepIndices(BaseModel):
    keep: List[int] = Field(description="List of integer indices (0-indexed) of the chunks to keep")

BATCH_CRAG_SYSTEM_PROMPT = """You are a strict relevance filter. Your job is to drop garbage chunks.
You will be given a user question and a numbered list of text paragraphs.
Return the indices of the paragraphs that directly help answer or relate to the question.
If a paragraph is just navigation menus, cookie policies, or off-topic boilerplate, DROP it.
Return the indices to keep. If none are useful, return an empty list."""

def batch_crag_filter(state: GraphState) -> GraphState:
    """
    Fast Mode Batch CRAG Filter (Quality Gate)
    
    Takes the top reranked chunks and passes them in a single batch prompt
    to gpt-4o-mini to drop obvious garbage (e.g., cookie banners, nav bars).
    """
    query = state["query"]
    docs = state.get("docs", [])
    
    if not docs:
        print("[Fast CRAG] No docs to filter.")
        return {**state, "good_docs": []}

    print(f"[Fast CRAG] Filtering {len(docs)} chunks...")
    
    paragraphs_text = ""
    for i, doc in enumerate(docs):
        paragraphs_text += f"\n[{i}] {doc.page_content}\n"
        
    messages = [
        SystemMessage(content=BATCH_CRAG_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {query}\n\nParagraphs:{paragraphs_text}")
    ]
    
    structured_llm = fast_llm.with_structured_output(KeepIndices)
    try:
        result: KeepIndices = structured_llm.invoke(messages)
        keep_indices = result.keep
    except Exception as e:
        print(f"[Fast CRAG] Filter failed to parse JSON, keeping all. Error: {e}")
        keep_indices = list(range(len(docs)))
        
    good_docs = [docs[i] for i in keep_indices if i < len(docs)]
    
    print(f"[Fast CRAG] Kept {len(good_docs)} out of {len(docs)} chunks.")
    
    return {
        **state,
        "good_docs": good_docs
    }

async def run_fast_mode(initial_state: GraphState) -> AsyncGenerator[str, None]:
    """
    Fast Mode Pipeline Runner (yields SSE strings)
    
    Contextualize -> Retrieve -> Re-rank -> Batch Filter -> Generate
    """
    state = initial_state
    
    def sse(event_type: str, data: dict):
        payload = {"type": event_type, **data}
        return f"data: {json.dumps(payload)}\n\n"

    # Step 1: Contextualize
    # Only show the "Understanding question..." status if there is chat history.
    # With no history the contextualizer skips the LLM call entirely (instant),
    # so showing a status event would cause a confusing flicker with nothing behind it.
    if initial_state.get("chat_history"):
        yield sse("status", {"value": "Understanding question... 🤔"})
    state = contextualize_query(state)

    # Step 2: Retrieve & Re-rank
    yield sse("status", {"value": "Retrieving relevant paragraphs... "})
    state = retrieve_and_rerank(state)

    
    # Step 3: Fast CRAG Filter
    yield sse("status", {"value": "Filtering out noise... "})
    state = batch_crag_filter(state)
    
    # Step 4: Generate Answer
    yield sse("status", {"value": "Writing answer... "})
    state = generate_fast(state)
    
    # Check Safety Net for upgrade
    final_ans = state.get("final_answer") or ""
    if final_ans.strip().lower() == "i cannot find the answer on this page.":
        print("[Fast Mode] Safety net triggered: Information not found -> Upgrading to Deep Mode")
        # Note: endpoints.py handles the "Upgrading to Deep Search" status message
        # to avoid showing it twice in the UI
        
        # In a full implementation, you would trigger Deep Mode here.
        # For now, we return the Fast Mode failure gracefully.
        
    yield sse("final", {
        "answer": state.get("final_answer", ""),
        "evidence": state.get("evidence", []),
        "confidence_score": state.get("confidence_score", 0.0),
        "reasoning_summary": state.get("reasoning_summary", "")
    })

