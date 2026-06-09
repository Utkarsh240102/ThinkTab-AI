import json
import asyncio
import re
import fitz                                          # PyMuPDF — server-side PDF parser
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal, Optional

from app.graph.state import GraphState
from app.graph.fast_mode import run_fast_mode
from app.graph.auto_router import route_query
from app.graph.deep_mode import deep_mode_graph
from app.services.llm_service import fast_llm
from langchain_core.messages import SystemMessage, HumanMessage

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}

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
    mode: Literal["fast", "deep", "auto"] = "auto"  # Validated: rejects anything else with 422
    contexts: List[ContextItem] = []
    chat_history: Optional[List[ChatMessage]] = []
    history_summary: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# PDF Upload Response Model
# ─────────────────────────────────────────────────────────────

class PDFUploadResponse(BaseModel):
    """Returned after server-side PDF parsing."""
    source_id:  str   # Original filename e.g. "research.pdf"
    content:    str   # Full extracted text from all pages
    page_count: int   # Number of pages in the PDF


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
# PDF Upload Route — Server-side fallback for scanned PDFs
# ─────────────────────────────────────────────────────────────

# Hard file size limit: 20 MB. Named constant — not a magic number.
MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

@router.post("/upload-pdf", response_model=PDFUploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    POST /api/upload-pdf

    Accepts a raw PDF file upload (multipart/form-data).
    Uses PyMuPDF (fitz) to extract text server-side.
    Returns extracted text, filename, and page count as JSON.

    This endpoint is called by the frontend ONLY as a fallback
    when pdfjs-dist (client-side) returned less than 100 characters,
    indicating the PDF is likely a scanned/image-only document.
    """

    # ── Guard 1: Validate file type ──────────────────────────────────────────
    # Check the content type sent by the browser.
    # Only accept PDFs — reject Word docs, images, etc.
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=415,  # 415 = Unsupported Media Type
            detail="Only PDF files are accepted. Please upload a .pdf file."
        )

    # ── Guard 2: Read file bytes ─────────────────────────────────────────────
    # We read the entire file into memory as raw bytes.
    # This is safe because of the size guard below.
    file_bytes = await file.read()

    # ── Guard 3: File size limit ─────────────────────────────────────────────
    # Reject files larger than 20 MB to protect server memory.
    # We check AFTER reading so we have the actual byte count.
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        size_mb = len(file_bytes) / 1024 / 1024
        raise HTTPException(
            status_code=413,  # 413 = Content Too Large
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed size is 20 MB."
        )

    # ── Guard 4: PDF Magic Signature ─────────────────────────────────────────
    # Even if the content-type is correct, the file might be renamed or corrupted.
    # All valid PDFs must start with the magic bytes '%PDF-'.
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=415,
            detail="The uploaded file is not a valid PDF document (missing magic signature)."
        )

    # ── Extract text using PyMuPDF (Offloaded to thread) ─────────────────────
    def _extract_pdf_text(raw_bytes: bytes) -> tuple[str, int]:
        pdf_doc = fitz.open(stream=raw_bytes, filetype="pdf")
        page_texts = []
        for page in pdf_doc:
            page_text = page.get_text("text").strip()
            if page_text:
                page_texts.append(page_text)
        page_count = len(pdf_doc)
        pdf_doc.close()
        return "\n\n".join(page_texts), page_count

    try:
        # Run the heavy C++ extraction in a background thread so we don't block the async event loop
        full_text, page_count = await asyncio.to_thread(_extract_pdf_text, file_bytes)

        print(f"[PDF Upload] Parsed '{file.filename}' — {page_count} pages, {len(full_text)} chars extracted.")

        return PDFUploadResponse(
            source_id=file.filename or "uploaded_document.pdf",
            content=full_text,
            page_count=page_count,
        )

    except Exception as e:
        # Catch any PyMuPDF parsing error and return a clean HTTP error
        print(f"[PDF Upload] ERROR parsing '{file.filename}': {e}")
        raise HTTPException(
            status_code=422,  # 422 = Unprocessable Entity
            detail=f"Could not parse the PDF file. It may be corrupted or encrypted."
        )


# ─────────────────────────────────────────────────────────────
# Summarize History Route
# ─────────────────────────────────────────────────────────────

class SummarizeHistoryRequest(BaseModel):
    old_messages: List[ChatMessage]
    current_summary: Optional[str] = None

@router.post("/summarize-history")
async def summarize_history(req: SummarizeHistoryRequest):
    msg_text = "\n".join(
        [f"{m.role}: {m.content}" for m in req.old_messages]
    )

    prompt = (
        "Summarize the following chat messages into a short, concise paragraph. "
        "Focus purely on preserving the user's original goals, context, and constraints.\n\n"
    )

    if req.current_summary:
        prompt += f"Previous Summary: {req.current_summary}\n\n"

    prompt += f"New Messages to incorporate:\n{msg_text}"

    # Run in a thread to avoid blocking the event loop
    response = await asyncio.to_thread(
        fast_llm.invoke,
        [HumanMessage(content=prompt)]
    )

    return {"summary": response.content}


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
            # ── Guard: Reject empty / whitespace-only queries immediately ──
            if not request.query or not request.query.strip():
                print("[Endpoint] Empty query received — short-circuiting pipeline.")
                yield sse_event({"type": "mode", "value": "Fast Mode ⚡"})
                yield sse_event({
                    "type": "final",
                    "answer": "Please enter a question to get started.",
                    "evidence": [],
                    "confidence_score": 0.0,
                    "reasoning_summary": "Query was empty."
                })
                return

            # ── Step 1: Initialize State ────────────────
            state: GraphState = {
                "query": request.query,
                "original_query": request.query,
                "mode": request.mode,
                "selected_mode": None,
                "chat_history": [msg.model_dump() for msg in request.chat_history] if request.chat_history else [],
                "history_summary": request.history_summary,
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
                if selected_mode == "chat":
                    mode_label = "💬 Chat"
                elif selected_mode == "fast":
                    mode_label = "Auto → Selected: Fast ⚡"
                else:
                    mode_label = "Auto → Selected: Deep 🧠"
                yield sse_event({"type": "mode", "value": mode_label})
            else:
                selected_mode = request.mode
                yield sse_event({"type": "mode", "value": f"{selected_mode.title()} Mode " + ("⚡" if selected_mode == "fast" else "🧠")})

            state["selected_mode"] = selected_mode

            # ── Step 2.5: Conversational Bypass (Chat Mode) ──────────────
            # If the router detected small talk / greetings, skip ALL retrieval
            # pipelines and directly call the LLM for an instant reply.
            if selected_mode == "chat":
                print("[Chat Bypass] Conversational query detected. Skipping RAG pipeline.")

                # Build messages from chat history + current query
                summary_text = f"\n\n[Previous Conversation Summary]: {request.history_summary}" if request.history_summary else ""
                
                chat_messages = [
                    SystemMessage(content=(
                        "You are ThinkTab AI, a friendly and intelligent browser assistant. "
                        "The user is making casual conversation or asking about the chat history. "
                        "Respond warmly and naturally based on the provided conversation context. "
                        "Keep your reply concise. Do not mention documents, sources, or retrieval."
                        f"{summary_text}"
                    ))
                ]

                # Add previous conversation turns for context
                for turn in (request.chat_history or []):
                    if turn.role == "user":
                        chat_messages.append(HumanMessage(content=turn.content))
                    else:
                        from langchain_core.messages import AIMessage
                        chat_messages.append(AIMessage(content=turn.content))

                # Add the current user message
                chat_messages.append(HumanMessage(content=request.query))

                # Call the fast LLM directly — no RAG, no search
                reply = fast_llm.invoke(chat_messages)
                reply_text = reply.content if hasattr(reply, "content") else str(reply)

                print(f"[Chat Bypass] Reply: {reply_text[:80]}...")
                yield sse_event({
                    "type": "final",
                    "answer": reply_text,
                    "evidence": [],
                    "confidence_score": 1.0,
                    "reasoning_summary": "Conversational response — no retrieval needed."
                })
                return  # ← Exit the event stream immediately, skip all pipeline code

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
                    # ── Safety Net: Upgrade to Deep Mode ────────────────
                    # Update the mode badge in the frontend header so the user
                    # sees the ACTUAL mode that produced the answer, not "Fast"
                    yield sse_event({"type": "mode", "value": "Auto → Upgraded to Deep 🧠"})
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
            # Log the full error server-side for debugging
            print(f"[Event Stream Error] {traceback.format_exc()}")
            # Sanitize the error message before sending to the client —
            # prevents API keys from leaking in error bodies (e.g. Groq/OpenRouter errors)
            _raw = str(e)
            _safe = re.sub(r'(sk-|key-|Bearer )[a-zA-Z0-9\-_\.]+', '[REDACTED]', _raw)
            yield sse_event({
                "type": "error",
                "value": f"An internal error occurred: {_safe}"
            })
            yield sse_event({
                "type": "final",
                "answer": f"**Oops! An internal error occurred.**\n\n```text\n{_safe}\n```\n\nPlease try again.",
                "evidence": [],
                "confidence_score": 0.0,
                "reasoning_summary": f"Error Details: {_safe}"
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
    # Guard: Reject empty content — FAISS crashes on zero-length text
    if not context.content or not context.content.strip():
        print(f"[Embed] Skipping empty content for source '{context.source_id}'")
        return {"status": "skipped", "source_id": context.source_id, "reason": "empty content"}

    from app.services.vector_store import embedding_cache
    # ensure_embedded: parses and embeds fresh content if source_id not found in ChromaDB
    # We run this in a thread since it might do heavy chunking + embedding
    import asyncio
    await asyncio.to_thread(embedding_cache.ensure_embedded, context.content, context.source_id)
    return {"status": "cached", "source_id": context.source_id}


# ─────────────────────────────────────────────────────────────
# Cache Invalidation Route
# ─────────────────────────────────────────────────────────────

@router.delete("/cache/{source_id}")
async def clear_cache(source_id: str):
    """
    DELETE /api/cache/{source_id}

    Evicts a specific source from the embedding cache so the next query
    will re-embed fresh content. Called by the Chrome Extension when a
    page is updated and the old embedding needs to be invalidated.
    """
    from app.services.vector_store import embedding_cache
    from fastapi import HTTPException

    evicted = embedding_cache.delete_by_source_id(source_id)
    if not evicted:
        raise HTTPException(
            status_code=404,
            detail=f"Source '{source_id}' not found in cache. It may not have been embedded yet."
        )
    return {"status": "evicted", "source_id": source_id}
