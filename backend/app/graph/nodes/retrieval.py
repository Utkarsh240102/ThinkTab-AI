import os
import asyncio
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from app.services.vector_store import embedding_cache
from app.graph.state import GraphState
from app.core.config import settings
from rank_bm25 import BM25Okapi

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
    source_chunks = {}

    # ── BUG2-003 FIX: Structured Source-Intent Filtering ───────────────────────
    # The Contextualizer now explicitly determines which sources the user 
    # wants to search and populates state["target_source_ids"].
    target_source_ids = state.get("target_source_ids", [])
    
    if not target_source_ids:
        print("[Retrieval] Target source list is empty. Searching all available sources.")
    else:
        print(f"[Retrieval] Deterministic routing to {len(target_source_ids)} specific sources.")
    # ── End BUG2-003 FIX ─────────────────────────────────────────────────────

    # Step 1: Retrieve top K chunks from each source
    for ctx in contexts:
        source_id = ctx["source_id"]
        content = ctx["content"]

        # ── Deterministic source-intent gate ───────────────────────────────────
        # IMPORTANT: Use flexible matching, NOT exact equality.
        # The Contextualizer returns short labels like "Active Tab" or "Pinned Tab"
        # but source_ids in the DB are full strings like "Active Tab: United States - Wikipedia".
        # We match if any target is a prefix of the source_id OR the source_id starts with any target.
        def _is_targeted(sid: str, targets: list[str]) -> bool:
            sid_lower = sid.lower()
            for t in targets:
                t_lower = t.lower()
                # Exact match OR prefix match in either direction
                if t_lower == sid_lower or sid_lower.startswith(t_lower) or t_lower.startswith(sid_lower):
                    return True
            return False

        if target_source_ids and not _is_targeted(source_id, target_source_ids):
            print(f"[Retrieval] Skipping '{source_id}' (not in target_source_ids)")
            continue
        # ── End deterministic source-intent gate ───────────────────────────────

        # Guard: skip empty or whitespace-only content — FAISS.from_documents
        # crashes with IndexError when there are no chunks to embed
        if not content or not content.strip():
            print(f"[Retrieval] WARNING: Skipping empty content for source '{source_id}'")
            continue

        print(f"[Retrieval] Searching ChromaDB for source: {source_id}")

        # ensure_embedded: parses and embeds fresh content if source_id not found in ChromaDB
        await asyncio.to_thread(embedding_cache.ensure_embedded, content, source_id)

        raw_scored_docs = await asyncio.to_thread(
            embedding_cache.vector_store.similarity_search_with_score,
            query,
            k=retrieve_k,
            filter={"source": source_id}
        )

        print(f"[Retrieval] Retrieved {len(raw_scored_docs)} raw chunks from {source_id}")
        if not raw_scored_docs:
            source_chunks[source_id] = []
            continue
            
        MIN_BM25_LENGTH = 100
        bm25_eligible = [(i, doc) for i, (doc, _) in enumerate(raw_scored_docs) if len(doc.page_content) >= MIN_BM25_LENGTH]
        
        bm25_scores = [0.0] * len(raw_scored_docs)
        if bm25_eligible:
            tokenized_corpus = [doc.page_content.lower().split() for _, doc in bm25_eligible]
            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.lower().split()
            valid_scores = bm25.get_scores(tokenized_query)
            for idx_in_valid, (orig_idx, _) in enumerate(bm25_eligible):
                bm25_scores[orig_idx] = valid_scores[idx_in_valid]
        
        source_chunks[source_id] = [
            (semantic_score, bm25_scores[i], doc) 
            for i, (doc, semantic_score) in enumerate(raw_scored_docs)
        ]

    # Step 2: Normalize the scores for each source independently
    for sid, chunks in source_chunks.items():
        if not chunks:
            continue
        sem_scores = [sem for sem, _, _ in chunks]
        bm25_scores = [bm25 for _, bm25, _ in chunks]
        
        min_sem, max_sem = min(sem_scores), max(sem_scores)
        min_bm25, max_bm25 = min(bm25_scores), max(bm25_scores)
        
        normalized_chunks = []
        for sem, bm25, doc in chunks:
            norm_sem = 1.0 if max_sem == min_sem else (sem - min_sem) / (max_sem - min_sem)
            norm_bm25 = 1.0 if max_bm25 == min_bm25 else (bm25 - min_bm25) / (max_bm25 - min_bm25)
            normalized_chunks.append((norm_sem, norm_bm25, doc))
        source_chunks[sid] = normalized_chunks

    # Step 3: Apply Reciprocal Rank Fusion
    for sid, chunks in source_chunks.items():
        if not chunks:
            continue
        # Assign semantic rank
        chunks.sort(key=lambda x: x[0], reverse=True)
        sem_ranked = [(ns, nb, doc, rank) for rank, (ns, nb, doc) in enumerate(chunks, 1)]
        
        # Assign bm25 rank
        sem_ranked.sort(key=lambda x: x[1], reverse=True)
        rrf_chunks = []
        for bm25_rank, (ns, nb, doc, sem_rank) in enumerate(sem_ranked, 1):
            rrf_score = (1 / (60 + sem_rank)) + (1 / (60 + bm25_rank))
            rrf_chunks.append((rrf_score, doc))
            
        # Sort all chunks by rrf_score descending
        rrf_chunks.sort(key=lambda x: x[0], reverse=True)
        source_chunks[sid] = rrf_chunks

    # Step 4: Flatten all per-source RRF-ranked chunks into the single all_chunks list
    all_chunks = []
    for chunks in source_chunks.values():
        all_chunks.extend(chunks)
        
    all_docs = [doc for _, doc in all_chunks]

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
    _orig_for_summary = state.get("original_query", "").lower()
    is_summary = any(kw in query.lower() for kw in SUMMARY_KEYWORDS) or any(kw in _orig_for_summary for kw in SUMMARY_KEYWORDS)

    # Boost chunk budget for multi-source queries so each source gets adequate representation
    num_active_sources = len(set(doc.metadata.get("source", "unknown") for doc in all_docs))
    if num_active_sources > 1:
        min_per_source = 3
        boosted_k = max(rerank_top_k, num_active_sources * min_per_source)
        if boosted_k > rerank_top_k:
            print(f"[Retrieval] Boosting rerank_top_k from {rerank_top_k} to {boosted_k} for {num_active_sources} sources")
            rerank_top_k = boosted_k

    if is_summary:
        print("[Retrieval] Summary intent detected. Bypassing CrossEncoder and interleaving sources.")
        docs_by_source = {}
        for doc in all_docs:
            src = doc.metadata.get("source", "unknown")
            if src not in docs_by_source:
                docs_by_source[src] = []
            docs_by_source[src].append(doc)

        # Guarantee each source gets at least min_per_source chunks before round-robin fills the rest
        top_docs = []
        guaranteed_per_source = min(3, rerank_top_k // max(len(docs_by_source), 1))
        for src in list(docs_by_source.keys()):
            for _ in range(guaranteed_per_source):
                if docs_by_source[src]:
                    top_docs.append(docs_by_source[src].pop(0))

        # Fill remaining budget via round-robin
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
