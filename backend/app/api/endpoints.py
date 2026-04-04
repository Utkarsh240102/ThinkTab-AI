import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.graph.state import GraphState
from app.graph.fast_mode import run_fast_mode

router = APIRouter()


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

    Current state: Streams FAKE test events to verify the SSE pipeline works.
    In later steps, this will be replaced with real Fast/Deep Mode AI logic.
    """

    async def event_stream():
        # ── Step 1: Acknowledge mode selection ────────────────
        yield sse_event({
            "type": "mode",
            "value": f"Mode received: {request.mode.upper()} — Query: '{request.query}'"
        })
        await asyncio.sleep(0.1)   # Small delay to simulate processing

        # ── Step 2: Run Fast Mode Pipeline ────────────────
        state: GraphState = {
            "query": request.query,
            "original_query": request.query,
            "mode": "fast",
            "selected_mode": "fast",
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

        async for event_str in run_fast_mode(state):
            yield event_str
            await asyncio.sleep(0.1)

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
