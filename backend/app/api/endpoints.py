import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

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
        await asyncio.sleep(0.5)   # Small delay to simulate processing

        # ── Step 2: Stream fake status updates ────────────────
        fake_statuses = [
            "Reading sources...",
            "Evaluating chunk relevance...",
            "Filtering sentences...",
            "Writing answer...",
            "Checking for hallucinations...",
        ]

        for status in fake_statuses:
            yield sse_event({"type": "status", "value": status})
            await asyncio.sleep(0.4)   # Simulate time between steps

        # ── Step 3: Send a fake final answer ──────────────────
        yield sse_event({
            "type": "final",
            "answer": f"[TEST] This is a simulated answer to: '{request.query}'",
            "evidence": [
                {
                    "source": ctx.source_id,
                    "snippet": ctx.content[:100] + "..."  # First 100 chars of each source
                }
                for ctx in request.contexts
            ],
            "confidence_score": 0.99,
            "reasoning_summary": "This is a test run. Real AI logic coming in Step 4."
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
