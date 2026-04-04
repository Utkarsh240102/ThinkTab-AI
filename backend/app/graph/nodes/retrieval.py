from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from app.services.vector_store import embedding_cache
from app.graph.state import GraphState
from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# Cross-Encoder Re-ranker
# Loaded once at startup — NOT on every request (expensive!)
# BAAI/bge-reranker-base is a small, fast, high-quality model
# ─────────────────────────────────────────────────────────────
print("[Retrieval] Loading Cross-Encoder re-ranker model...")
reranker = CrossEncoder("BAAI/bge-reranker-base")
print("[Retrieval] Re-ranker ready.")


def retrieve_and_rerank(state: GraphState) -> GraphState:
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

    all_docs: list[Document] = []

    # Step 1: Retrieve top K chunks from each source
    for ctx in contexts:
        source_id = ctx["source_id"]
        content = ctx["content"]

        print(f"[Retrieval] Searching FAISS for source: {source_id}")

        # get_or_embed: returns cached FAISS index or embeds fresh
        faiss_index = embedding_cache.get_or_embed(content, source_id)

        # Retrieve top K candidates (default: 10 from config)
        raw_docs = faiss_index.similarity_search(
            query,
            k=settings.FAST_MODE_RETRIEVE_K
        )

        print(f"[Retrieval] Retrieved {len(raw_docs)} raw chunks from {source_id}")
        all_docs.extend(raw_docs)

    # Guard: If no docs retrieved at all, return empty
    if not all_docs:
        print("[Retrieval] WARNING: No documents found in any source!")
        return {**state, "docs": []}

    # Step 2: Re-rank all collected chunks
    print(f"[Retrieval] Re-ranking {len(all_docs)} total chunks...")

    # Build (query, chunk_text) pairs for the Cross-Encoder
    pairs = [(query, doc.page_content) for doc in all_docs]

    # Score each pair — higher score = more relevant
    scores = reranker.predict(pairs)

    # Zip scores with docs and sort by score descending
    scored_docs = sorted(
        zip(scores, all_docs),
        key=lambda x: x[0],
        reverse=True
    )

    # Keep only the top N after re-ranking (default: 5 from config)
    top_docs = [doc for _, doc in scored_docs[:settings.FAST_MODE_RERANK_TOP_K]]

    print(f"[Retrieval] Kept top {len(top_docs)} chunks after re-ranking.")
    for i, doc in enumerate(top_docs):
        source = doc.metadata.get("source", "unknown")
        print(f"  [{i+1}] Source: {source} | Preview: {doc.page_content[:80]}")

    return {
        **state,
        "docs": top_docs,
    }
