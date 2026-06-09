import os
import asyncio
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from app.services.vector_store import embedding_cache
from app.graph.state import GraphState
from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# Cross-Encoder Re-ranker
# Saved locally to D:\PROJECTS\ThinkTab-AI\models\ instead of
# the global HuggingFace cache (~/.cache/huggingface)
# ─────────────────────────────────────────────────────────────
MODEL_CACHE_DIR = os.path.join(
    os.path.dirname(__file__),   # backend/app/graph/nodes/
    "../../../../models"          # → D:/PROJECTS/ThinkTab-AI/models/
)

print("[Retrieval] Loading Cross-Encoder re-ranker model...")
reranker = CrossEncoder(
    "BAAI/bge-reranker-base",
    max_length=512,
    cache_folder=os.path.abspath(MODEL_CACHE_DIR)
)
print("[Retrieval] Re-ranker ready.")


async def retrieve_and_rerank(state: GraphState) -> GraphState:
    """
    LangGraph Node: Retrieval + Re-ranking

    Two-stage retrieval:
    1. FAISS similarity search -> fetches top K chunks (fast, approximate)
    2. Cross-Encoder re-ranking -> scores and re-orders, keeps top N (slow, precise)

    The FAISS index is sourced from the LRU embedding cache. If the page
    was pre-embedded, this is near-instant. If not, it embeds on-the-fly.

    Updates GraphState with:
        docs -> List of top re-ranked Document chunks
    """

    query = state["query"]
    contexts = state["contexts"]
    
    # Determine which mode we are actually running in ("fast" or "deep")
    # If mode is "auto", the auto_router will have populated "selected_mode"
    actual_mode = state.get("selected_mode") or state.get("mode")
    
    if actual_mode == "deep":
        retrieve_k = settings.DEEP_MODE_RETRIEVE_K
        rerank_top_k = settings.DEEP_MODE_RERANK_TOP_K
    else:
        retrieve_k = settings.FAST_MODE_RETRIEVE_K
        rerank_top_k = settings.FAST_MODE_RERANK_TOP_K

    all_docs: list[Document] = []

    # ── BUG2-003 FIX: Source-intent filtering ────────────────────────────────
    # When a user explicitly names a source ("summarize the web page", "read
    # the PDF"), restricting retrieval to only that source prevents the
    # re-ranker from pulling chunks from the wrong place.
    
    _BOTH_SIGNALS = ["both webpages", "both pages", "all pages", "all tabs"]
    _ACTIVE_SIGNALS = ["this page", "current page", "active tab", "current tab", "this webpage", "current webpage", "the website", "the webpage", "the page"]
    _PINNED_SIGNALS = ["pinned", "pinned tab", "pinned page", "other tab", "background tab"]
    _PDF_SIGNALS = ["pdf", "document", "the file", "the resume", "uploaded file", "attached file"]

    _query_lower = query.lower()
    if any(kw in _query_lower for kw in _BOTH_SIGNALS):
        source_filter = None
        print("[Retrieval] Source intent: BOTH active and pinned sources")
    elif any(kw in _query_lower for kw in _ACTIVE_SIGNALS):
        source_filter = "active"
        print("[Retrieval] Source intent: ACTIVE TAB only")
    elif any(kw in _query_lower for kw in _PINNED_SIGNALS):
        source_filter = "pinned"
        print("[Retrieval] Source intent: PINNED TAB only")
    elif any(kw in _query_lower for kw in _PDF_SIGNALS):
        source_filter = "pdf"
        print("[Retrieval] Source intent: PDF only")
    else:
        source_filter = None
        print("[Retrieval] Source intent: all sources")
    # ── End BUG2-003 FIX ─────────────────────────────────────────────────────

    # Step 1: Retrieve top K chunks from each source
    for ctx in contexts:
        source_id = ctx["source_id"]
        content = ctx["content"]

        # ── Source-intent gate ────────────────────────────────────────────────
        # Skip this context if it doesn't match the source the user asked about.
        is_pdf = source_id.lower().endswith('.pdf')
        is_active = source_id.startswith("Active Tab")
        is_pinned = source_id.startswith("Pinned Tab")

        if source_filter == "active" and not is_active:
            print(f"[Retrieval] Skipping '{source_id}' (active-only intent)")
            continue
        if source_filter == "pinned" and not is_pinned:
            print(f"[Retrieval] Skipping '{source_id}' (pinned-only intent)")
            continue
        if source_filter == "pdf" and not is_pdf:
            print(f"[Retrieval] Skipping '{source_id}' (pdf-only intent)")
            continue
        # ── End source-intent gate ────────────────────────────────────────────

        # Guard: skip empty or whitespace-only content — FAISS.from_documents
        # crashes with IndexError when there are no chunks to embed
        if not content or not content.strip():
            print(f"[Retrieval] WARNING: Skipping empty content for source '{source_id}'")
            continue

        print(f"[Retrieval] Searching ChromaDB for source: {source_id}")

        # ensure_embedded: parses and embeds fresh content if source_id not found in ChromaDB
        await asyncio.to_thread(embedding_cache.ensure_embedded, content, source_id)

        raw_docs = await asyncio.to_thread(
            embedding_cache.search,
            query,
            source_id,
            retrieve_k
        )

        print(f"[Retrieval] Retrieved {len(raw_docs)} raw chunks from {source_id}")
        all_docs.extend(raw_docs)

    # Guard: If no docs retrieved at all, return a fallback document
    if not all_docs:
        print("[Retrieval] WARNING: No documents found in any source!")
        from langchain_core.documents import Document
        fallback = Document(
            page_content="No local context or webpage text was provided.",
            metadata={"source": "system"}
        )
        return {**state, "docs": [fallback]}

    # Step 2: Re-rank all collected chunks
    SUMMARY_KEYWORDS = ["summarize", "summary", "overview", "brief", "compare", "explain", "tell me about"]
    is_summary = any(kw in query.lower() for kw in SUMMARY_KEYWORDS)

    if is_summary:
        print("[Retrieval] Summary intent detected. Bypassing CrossEncoder and interleaving sources.")
        docs_by_source = {}
        for doc in all_docs:
            src = doc.metadata.get("source", "unknown")
            if src not in docs_by_source:
                docs_by_source[src] = []
            docs_by_source[src].append(doc)
            
        top_docs = []
        while len(top_docs) < rerank_top_k and docs_by_source:
            for src in list(docs_by_source.keys()):
                if docs_by_source[src]:
                    top_docs.append(docs_by_source[src].pop(0))
                else:
                    del docs_by_source[src]
                if len(top_docs) >= rerank_top_k:
                    break
    else:
        print(f"[Retrieval] Re-ranking {len(all_docs)} total chunks...")
        
        # Build (query, chunk_text) pairs for the Cross-Encoder
        pairs = [(query, doc.page_content) for doc in all_docs]
        
        # Score each pair — higher score = more relevant
        scores = await asyncio.to_thread(reranker.predict, pairs)
        
        # Zip scores with docs and sort by score descending
        scored_docs = sorted(zip(scores, all_docs), key=lambda x: x[0], reverse=True)
        
        # Keep only the top N after re-ranking dynamically based on mode
        top_docs = [doc for _, doc in scored_docs[:rerank_top_k]]

    print(f"[Retrieval] Kept top {len(top_docs)} chunks after re-ranking.")
    for i, doc in enumerate(top_docs):
        source = doc.metadata.get("source", "unknown")
        print(f"  [{i+1}] Source: {source} | Preview: {doc.page_content[:80]}")

    return {
        **state,
        "docs": top_docs,
    }
