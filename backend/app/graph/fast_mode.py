from pydantic import BaseModel, Field
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import GraphState
from app.services.llm_service import fast_llm

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
