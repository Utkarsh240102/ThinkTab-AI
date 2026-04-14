import re
from pydantic import BaseModel, Field
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import GraphState
from app.services.llm_service import fast_llm

class KeepIndices(BaseModel):
    keep: List[int] = Field(description="List of integer indices (0-indexed) of the sentences to keep")

REFINER_SYSTEM_PROMPT = """You are a precision editor. Your job is to extract ONLY the sentences strictly necessary to answer the user's question.
You will be given a numbered list of sentences extracted from various sources.
Return the indices of the sentences that contain relevant facts, claims, or context needed to answer the question.
Drop ANY sentence that is filler, off-topic, boilerplate, or redundant.
Return the structured JSON array of indices to keep. If none are useful, return an empty list."""

def crag_refiner(state: GraphState) -> GraphState:
    """
    Deep Mode Node: CRAG Sentence Refiner
    
    Aggregates all 'good' local docs and any recovered 'web' docs.
    Splits them into individual sentences.
    Batches them into a single prompt for gpt-4o-mini.
    Returns a single, hyper-dense string of only the relevant facts.
    """
    query = state["query"]
    
    # 1. Aggregate all available context chunks
    # IMPORTANT: use 'or []' not state.get(key, []) because if the key EXISTS
    # in the dict with value None, state.get(key, []) returns None, causing TypeError
    all_chunks = (state.get("good_docs") or []) + (state.get("web_docs") or [])
    
    if not all_chunks:
        print("[CRAG Refiner] No documents available to refine.")
        return {**state, "refined_context": ""}
        
    print(f"[CRAG Refiner] Splitting {len(all_chunks)} chunks into sentences...")
    
    # 2. Split chunks into sentences, retaining their source_id for citation
    all_sentences = []
    
    # Basic regex to split by period, exclamation, or question mark followed by a space
    sentence_splitter = re.compile(r'(?<=[.!?])\s+')
    
    for chunk in all_chunks:
        source_id = chunk.metadata.get("source", "unknown")
        raw_sentences = sentence_splitter.split(chunk.page_content.strip())
        
        for s in raw_sentences:
            s = s.strip()
            if len(s) > 10:  # Ignore tiny fragments like "Inc." or "Yes."
                all_sentences.append({"text": s, "source": source_id})
                
    if not all_sentences:
        return {**state, "refined_context": ""}
        
    # 3. Format the sentences into a numbered list for the LLM
    numbered_list = ""
    for i, s_dict in enumerate(all_sentences):
        numbered_list += f"[{i}] {s_dict['text']}\n"
        
    # 4. Call gpt-4o-mini to filter the exact indices
    print(f"[CRAG Refiner] Asking LLM to filter {len(all_sentences)} sentences...")
    
    messages = [
        SystemMessage(content=REFINER_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {query}\n\nSentences:\n{numbered_list}")
    ]
    
    structured_llm = fast_llm.with_structured_output(KeepIndices)
    
    try:
        result: KeepIndices = structured_llm.invoke(messages)
        keep_indices = result.keep
    except Exception as e:
        print(f"[CRAG Refiner] LLM parsing failed: {e}. Keeping all sentences as fallback.")
        keep_indices = list(range(len(all_sentences)))
        
    # 5. Reconstruct the clean, dense context block
    refined_sentences = [all_sentences[i] for i in keep_indices if i < len(all_sentences)]
    
    print(f"[CRAG Refiner] Kept {len(refined_sentences)} out of {len(all_sentences)} sentences.")
    
    # Group sentences by their source so the final generator knows where they came from
    from typing import Dict, List
    source_map: Dict[str, List[str]] = {}
    for s_dict in refined_sentences:
        src = s_dict["source"]
        if src not in source_map:
            source_map[src] = []
        source_map[src].append(s_dict["text"])
        
    final_context_parts = []
    for src, sentences in source_map.items():
        joined_text = " ".join(sentences)
        final_context_parts.append(f"--- SOURCE: {src} ---\n{joined_text}")
        
    refined_context_string = "\n\n".join(final_context_parts)
    
    return {
        **state,
        "refined_context": refined_context_string
    }
