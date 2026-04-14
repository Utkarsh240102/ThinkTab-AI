import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.graph.state import GraphState
from app.graph.fast_mode import run_fast_mode
from app.graph.auto_router import route_query
from app.graph.deep_mode import deep_mode_graph

router = APIRouter()

DEEP_NODE_MESSAGES = {
    "contextualize_query": "Understanding question... 🤔",
    "retrieve_and_rerank": "Searching documents... 🔍",
    "eval_docs": "Evaluating document relevance... ⚖️",
    "rewrite_for_web": "Preparing web search...",
    "search_web": "Searching the web... 🌐",
    "crag_refiner": "Refining context... ✨",
    "generate_draft": "Drafting answer... ✍️",
    "check_hallucination": "Fact-checking answer... 🕵️‍♂️",
    "revise_answer": "Revising answer to remove hallucinations... 🔄",
    "check_usefulness": "Verifying answer usefulness... 🎯",
    "rewrite_question": "Rewriting question for better results... 🔄"
}


# ─────────────────────────────────────────────────────────────
# Request Models — Validates incoming JSON from Chrome Extension
# ─────────────────────────────────────────────────────────────

class ContextItem(BaseModel):
    """A single source sent from the frontend (webpage tab or uploaded document)."""
    source_id: str          # e.g. "https://stripe.com/pricing" or "my_doc.pdf"
    content: str            # Full markdown text extracted from the source


class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: str               # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """The full request body sent by the Chrome Extension."""
    query: str
    mode: str = "auto"      # "fast", "deep", or "auto"
    contexts: List[ContextItem] = []
    chat_history: Optional[List[ChatMessage]] = []


# ─────────────────────────────────────────────────────────────
# SSE Helper — Formats a Python dict into an SSE data line
# ─────────────────────────────────────────────────────────────

def sse_event(data: dict) -> str:
    """
    Formats a dict as a Server-Sent Event string.
    The frontend reads lines starting with 'data:' and parses the JSON.

    Example output:
        data: {"type": "status", "value": "Searching the web..."}\\n\\n
    """
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────
# Main Streaming Route
# ─────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    POST /api/chat

    Accepts a query + contexts from the Chrome Extension.
    Returns a Server-Sent Events (SSE) stream.
    """

    async def event_stream():
        try:
            # ── Step 1: Initialize State ────────────────
            state: GraphState = {
                "query": request.query,
                "original_query": request.query,
                "mode": request.mode,
                "selected_mode": None,
                "chat_history": [msg.model_dump() for msg in request.chat_history] if request.chat_history else [],
                "contexts": [ctx.model_dump() for ctx in request.contexts] if request.contexts else [],
                "docs": [],
                "good_docs": [],
                "refined_context": "",
                "crag_verdict": None,
                "web_query": "",
                "web_docs": [],
                "draft_answer": "",
                "final_answer": "",
                "evidence": [],
                "confidence_score": 0.0,
                "reasoning_summary": "",
                "is_supported": None,
                "is_useful": None,
                "revision_retries": 0,
                "retrieval_retries": 0
            }

            # ── Step 2: Auto Router (Mode Selection) ────────────────
            if request.mode == "auto":
                selected_mode = route_query(state)
                yield sse_event({"type": "mode", "value": f"Auto → Selected: {selected_mode.title()} " + ("⚡" if selected_mode == "fast" else "🧠")})
            else:
                selected_mode = request.mode
                yield sse_event({"type": "mode", "value": f"{selected_mode.title()} Mode " + ("⚡" if selected_mode == "fast" else "🧠")})
                
            state["selected_mode"] = selected_mode

            # ── Helper for Deep Mode Execution ────────────────
            async def execute_deep_mode(current_state: GraphState):
                # LangGraph astream yields events as each node completes
                async for output in deep_mode_graph.astream(current_state):
                    for node_name, state_update in output.items():
                        if node_name in DEEP_NODE_MESSAGES:
                            yield sse_event({"type": "status", "value": DEEP_NODE_MESSAGES[node_name]})
                        
                        # Merge state updates locally so we can track the final answer
                        current_state.update(state_update)
                
                # Streaming the final answer struct
                yield sse_event({
                    "type": "final",
                    "answer": current_state.get("final_answer") or current_state.get("draft_answer") or "I couldn't find an answer to your question.",
                    "evidence": current_state.get("evidence", []),
                    "confidence_score": current_state.get("confidence_score", 0.0),
                    "reasoning_summary": current_state.get("reasoning_summary", "")
                })

            # ── Step 3: Run Selected Pipeline ────────────────
            if selected_mode == "fast":
                safety_net_triggered = False
                async for event_str in run_fast_mode(state):
                    # Robustly detect the safety net by parsing the SSE JSON
                    # instead of fragile raw string matching
                    is_safety_net = False
                    try:
                        if event_str.startswith("data:"):
                            payload = json.loads(event_str[5:].strip())
                            if (payload.get("type") == "final" and
                                payload.get("answer", "").strip().lower() == "i cannot find the answer on this page."):
                                is_safety_net = True
                    except Exception:
                        pass  # If parsing fails, treat as a normal event

                    if is_safety_net:
                        safety_net_triggered = True
                        break  # Don't yield the failure final event — we'll upgrade instead
                    yield event_str
                    await asyncio.sleep(0.1)
                    
                if safety_net_triggered:
                    # ── Safety Net: Run Deep Mode ────────────────
                    yield sse_event({"type": "status", "value": "Information not found locally. Upgrading to Deep Search... 🧠"})
                    state["selected_mode"] = "deep"
                    
                    async for event in execute_deep_mode(state):
                        yield event
                    
            else:
                # ── Run Deep Mode ────────────────
                async for event in execute_deep_mode(state):
                    yield event

        except Exception as e:
            import traceback
            print(f"[Event Stream Error] {traceback.format_exc()}")
            yield sse_event({
                "type": "error",
                "value": f"An internal error occurred: {str(e)}"
            })
            yield sse_event({
                "type": "final",
                "answer": "An internal error occurred. Please try again.",
                "evidence": [],
                "confidence_score": 0.0,
                "reasoning_summary": f"Error Details: {str(e)}"
            })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Prevents Nginx from buffering the stream
        }
    )


# ─────────────────────────────────────────────────────────────
# Pre-Embed Route (Optional background call from extension)
# ─────────────────────────────────────────────────────────────

@router.post("/embed")
async def embed_source(context: ContextItem):
    """
    POST /api/embed

    Allows the Chrome Extension to pre-embed a page in the background
    as soon as the user lands on it, so the first query is instant.
    """
    from app.services.vector_store import embedding_cache
    embedding_cache.get_or_embed(context.content, context.source_id)
    return {"status": "cached", "source_id": context.source_id}


# ─────────────────────────────────────────────────────────────
# Cache Invalidation Route
# ─────────────────────────────────────────────────────────────

@router.delete("/cache/{source_id}")
async def clear_cache(source_id: str):
    """
    DELETE /api/cache/{source_id}

    Manually evict a specific source from the embedding cache.
    """
    # For now, just return a success message.
    # Full eviction logic will be added when needed.
    return {"status": "evicted", "source_id": source_id}
