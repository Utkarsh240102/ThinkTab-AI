from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from app.services.llm_service import fast_llm
from app.graph.state import GraphState
from app.core.config import settings


# ─────────────────────────────────────────────────────────────
# Pydantic Schema for Structured Output
# Forces gpt-4o-mini to return a clean, parseable verdict
# ─────────────────────────────────────────────────────────────
class UsefulnessVerdict(BaseModel):
    score: str = Field(
        description="'yes' if the answer resolves the user's question. 'no' if it is off-topic or incomplete."
    )
    reason: str = Field(
        description="A short one-sentence explanation of why the answer is or is not useful."
    )


# Bind the structured output schema to our fast LLM
usefulness_checker = fast_llm.with_structured_output(UsefulnessVerdict)


# ─────────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────────
USEFULNESS_SYSTEM_PROMPT = """You are a practical answer quality evaluator. Your job is to check if an AI-generated answer is useful to the user — not whether it's perfect.

Rules:
- Answer 'yes' if the answer makes a genuine attempt to address what the user asked.
- Answer 'yes' for summaries, even if they don't cover 100% of the source material. A summary of key points IS a valid summary.
- Answer 'yes' for word-count requests (e.g. "give me 100 words") even if the count is approximate.
- Answer 'yes' for evaluations and ratings based on provided content (e.g. "rate my resume").
- CRITICAL SOURCE RULE: If the user's question asks about "the pinned tab", "active tab", "this page", or "the pdf", they are asking about the contents of the loaded documents, NOT asking for a definition of Chrome UI features. If the answer discusses the content of those documents, you MUST answer 'yes'.
- Answer 'no' ONLY if the answer is completely off-topic, or refuses to answer entirely (e.g. "I cannot find this").
- Do NOT say 'no' just because the answer could be longer or more complete."""


def check_usefulness(state: GraphState) -> GraphState:
    """
    LangGraph Node: Answer Grader (IsUSE Check)

    Validates that the final answer actually addresses the user's
    original question — not just any question.

    Flow:
        - 'yes' → answer is useful, set as final_answer
        - 'no'  → answer is off-topic, increment retrieval_retries,
                  send to rewrite_question node

    Safety Guard:
        If retrieval_retries >= MAX_RETRIEVAL_RETRIES, we stop looping
        and accept the current answer, flagging it with a low confidence score.
    """

    # Always use the ORIGINAL query for usefulness check (not the rewritten one)
    original_query = state.get("original_query", state.get("query", ""))
    draft_answer = state.get("draft_answer", "")
    retrieval_retries = state.get("retrieval_retries", 0)

    # ── Safety Guard: Max retries reached ─────────────────────
    if retrieval_retries >= settings.MAX_RETRIEVAL_RETRIES:
        print(f"[Answer Grader] Max retrieval retries ({settings.MAX_RETRIEVAL_RETRIES}) reached. Accepting best answer.")
        return {
            **state,
            "is_useful": True,               # Force exit the retrieval loop
            "final_answer": draft_answer,
            # ── BUG FIX: Use constant 0.35, not min(score or 0.0, 0.35)
            # min(0.0 or 0.0, 0.35) = min(0.0, 0.35) = 0.0 because 0.0 is falsy in Python
            # The safety guard should ALWAYS signal low confidence (0.35), not 0.0
            "confidence_score": 0.35,
            "reasoning_summary": f"Answer accepted after {retrieval_retries} retrieval attempts. Confidence is low."
        }

    print(f"[Answer Grader] Checking if answer resolves the query (attempt {retrieval_retries + 1}/{settings.MAX_RETRIEVAL_RETRIES})...")

    # ── Build the grading prompt ──────────────────────────────
    messages = [
        SystemMessage(content=USEFULNESS_SYSTEM_PROMPT),
        HumanMessage(content=f"""USER'S ORIGINAL QUESTION:
---
{original_query}
---

AI-GENERATED ANSWER:
---
{draft_answer}
---

Does this answer directly resolve the user's question?""")
    ]

    # ── Call gpt-4o-mini with structured output ───────────────
    verdict: UsefulnessVerdict = usefulness_checker.invoke(messages)

    print(f"[Answer Grader] Verdict: {verdict.score.upper()} — {verdict.reason}")

    if verdict.score.lower() == "yes":
        # Answer is useful — promote draft to final answer
        return {
            **state,
            "is_useful": True,
            "final_answer": draft_answer,   # This is now the validated, user-ready answer
        }
    else:
        # Answer is off-topic — increment counter and trigger question rewrite
        return {
            **state,
            "is_useful": False,
            "retrieval_retries": retrieval_retries + 1,
        }


def rewrite_question(state: GraphState) -> GraphState:
    """
    LangGraph Node: Question Rewriter

    Called when check_usefulness returns is_useful=False.
    Rephrases the original query from a completely different angle
    so the next retrieval attempt can find better, more relevant chunks.

    Example:
        Original: "What are Stripe's fees for international cards?"
        Rewritten: "international transaction charges Stripe additional percentage"
    """

    original_query = state.get("original_query", state.get("query", ""))
    retrieval_retries = state.get("retrieval_retries", 0)
    target_source_ids = state.get("target_source_ids", [])
    contexts = state.get("contexts", [])
    
    # Extract source titles
    available_sources = [ctx.get("source_id", "Unknown") for ctx in contexts]

    print(f"[Question Rewriter] Rephrasing query for retrieval attempt #{retrieval_retries}...")

    messages = [
        SystemMessage(content=f"""You are a search query optimizer. 
Rephrase the user's question into a different, more specific version that might find better search results.
- Use different keywords and angles
- Make it more specific and direct
- Do NOT answer the question — only rephrase it
- Return ONLY the rephrased question, nothing else.

CRITICAL SOURCE PRESERVATION RULE:
The user's original query may reference UI labels like 'pinned tab', 'active tab', 'this page', 'the pdf', or 'the attached file'. These are NOT requests to define Chrome UI features  they are references to specific loaded documents.
- If the original query contains 'pinned tab', your rewrite MUST reference the actual content of the pinned document (from the available context titles provided below), NOT define what a pinned tab is.
- If the original query contains 'active tab' or 'this page', your rewrite MUST reference the actual content of the active page.
- NEVER convert 'explain the pinned tab' into 'What is a pinned tab?'
- CORRECT rewrite: 'explain me the pinned tab'  'Explain the content of [Pinned Tab document title]'
- WRONG rewrite: 'explain me the pinned tab'  'What is a Pinned Tab in Chrome?'

AVAILABLE CONTEXT TITLES:
{available_sources}"""),
        HumanMessage(content=f"""Original question: {original_query}
Target sources: {target_source_ids}

Rephrase this question using different keywords to improve document retrieval:""")
    ]

    response = fast_llm.invoke(messages)
    rewritten_query = str(response.content).strip()

    print(f"[Question Rewriter] Original: '{original_query}'")
    print(f"[Question Rewriter] Rewritten: '{rewritten_query}'")

    return {
        **state,
        "query": rewritten_query,       # The graph will use this new query for re-retrieval
        "target_source_ids": target_source_ids, # Keep filtering to the correct sources
        "revision_retries": 0,          # Reset revision counter for the new retrieval cycle

        # ── Clear stale data from the previous cycle ─────────────────────────
        # If we don't clear these, crag_refiner will mix the new good_docs with
        # old web results, and the routing may use a stale crag_verdict.
        "web_docs": [],                 # Old web search results are no longer relevant
        "good_docs": [],                # Old local chunks will be replaced by re-retrieval
        "crag_verdict": None,           # Force eval_docs to make a fresh verdict
    }
