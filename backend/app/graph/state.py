from typing import TypedDict, List, Literal, Optional


class GraphState(TypedDict):
    """
    The shared notebook passed between every LangGraph node.

    Think of it as a tray on an assembly line. Each worker (node) reads
    from it, does their job, and writes their result back into it before
    passing it to the next worker.

    Every field is Optional because at the START of a pipeline, most fields
    are empty — they get filled in as the graph progresses.
    """

    # ─── Input Fields ─────────────────────────────────────────────────────────
    query: str
    # The current working query (may be rewritten by contextualizer or question rewriter)

    original_query: str
    # The raw query exactly as the user typed it — preserved for reference

    mode: Literal["fast", "deep", "auto"]
    # The mode the user selected in the Chrome Extension

    selected_mode: Optional[Literal["fast", "deep"]]
    # What the Auto Router resolved the mode to (only set when mode="auto")

    chat_history: Optional[List[dict]]
    # Last N messages: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    # Used by the Query Contextualizer to resolve follow-up questions

    contexts: List[dict]
    # All sources sent from the frontend:
    # [{"source_id": "stripe.com", "content": "...markdown text..."}, ...]

    # ─── Retrieval Fields ─────────────────────────────────────────────────────
    docs: Optional[List]
    # Raw chunks retrieved from FAISS — not filtered yet

    good_docs: Optional[List]
    # Chunks that passed the CRAG relevance scoring threshold

    refined_context: Optional[str]
    # Final clean string of relevant sentences after CRAG sentence-level filtering
    # This is what gets fed directly to the final LLM for generation

    # ─── CRAG Fields ──────────────────────────────────────────────────────────
    crag_verdict: Optional[Literal["CORRECT", "INCORRECT", "AMBIGUOUS"]]
    # CORRECT  → internal docs are good, proceed to refinement
    # INCORRECT → all docs are bad, trigger web search fallback
    # AMBIGUOUS → mixed quality, use both local docs AND web search

    web_query: Optional[str]
    # The rewritten, Google-friendly search query (set after CRAG verdict is INCORRECT/AMBIGUOUS)

    web_docs: Optional[List]
    # Documents fetched from Serper (Google) web search, tagged with source="web_serper"

    # ─── Generation Fields ────────────────────────────────────────────────────
    draft_answer: Optional[str]
    # The initial answer written by the LLM — NOT shown to the user yet
    # Must pass both Self-RAG checks before becoming final_answer

    final_answer: Optional[str]
    # The validated, user-ready answer after passing IsSUP and IsUSE checks

    evidence: Optional[List[dict]]
    # Exact text snippets used to write the answer:
    # [{"source": "stripe.com", "snippet": "Stripe charges 2.9% + 30c..."}]

    confidence_score: Optional[float]
    # 0.0 to 1.0 — how confident we are in the answer
    # High (>0.75): local sources, no rewrites needed
    # Medium (0.5-0.75): some web search or minor rewrites
    # Low (<0.5): heavy rewrites, all-web sources, or max retries hit

    reasoning_summary: Optional[str]
    # Short plain-English explanation of how the answer was derived
    # e.g. "Compared 3 tabs and supplemented with 1 web search result"

    # ─── Self-RAG Validation Fields ───────────────────────────────────────────
    is_supported: Optional[bool]
    # IsSUP check result: True = every claim in draft_answer is backed by refined_context
    # False = hallucination detected → trigger revise_answer node

    is_useful: Optional[bool]
    # IsUSE check result: True = the answer actually addresses the user's question
    # False = answer is off-topic or unhelpful → trigger rewrite_question node

    # ─── Safety Guard Counters ────────────────────────────────────────────────
    revision_retries: Optional[int]
    # Tracks how many times we've looped through revise_answer
    # Stops at MAX_REVISION_RETRIES (default: 3) to prevent infinite loops

    retrieval_retries: Optional[int]
    # Tracks how many times we've looped through rewrite_question → retrieve loop
    # Stops at MAX_RETRIEVAL_RETRIES (default: 3) to prevent infinite loops
