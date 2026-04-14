from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from app.services.llm_service import fast_llm
from app.graph.state import GraphState
from app.core.config import settings


# ─────────────────────────────────────────────────────────────
# Pydantic Schema for Structured Output
# Forces gpt-4o-mini to return a clean, parseable verdict
# ─────────────────────────────────────────────────────────────
class HallucinationVerdict(BaseModel):
    score: str = Field(
        description="'yes' if the answer is fully grounded in the context. 'no' if it contains hallucinations."
    )
    reason: str = Field(
        description="A short one-sentence explanation of why the answer is grounded or hallucinating."
    )


# Bind the structured output schema to our fast LLM
hallucination_checker = fast_llm.with_structured_output(HallucinationVerdict)


# ─────────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────────
HALLUCINATION_SYSTEM_PROMPT = """You are a strict fact-checker. Your job is to verify if an AI-generated answer is fully supported by the provided context.

Rules:
- Answer 'yes' ONLY if every single claim in the answer can be directly traced back to the context.
- Answer 'no' if the answer contains ANY fact, number, date, or claim not present in the context.
- Do NOT use your own knowledge. Only use what is in the context.
- Be strict. Even one unsupported claim means 'no'."""


def check_hallucination(state: GraphState) -> GraphState:
    """
    LangGraph Node: Hallucination Grader (IsSUP Check)

    Validates that every claim in the draft answer is supported
    by the refined context retrieved from our documents.

    Flow:
        - 'yes' → answer is grounded, pass to answer_grader
        - 'no'  → hallucination detected, increment retry counter,
                  send to revise_answer node

    Safety Guard:
        If revision_retries >= MAX_REVISION_RETRIES, we stop looping
        and mark is_supported=True to exit the loop gracefully,
        returning the best answer we have with a low confidence score.
    """

    draft_answer = state.get("draft_answer", "")
    refined_context = state.get("refined_context", "")
    revision_retries = state.get("revision_retries", 0)

    # ── Safety Guard: Max retries reached ─────────────────────
    if revision_retries >= settings.MAX_REVISION_RETRIES:
        print(f"[Hallucination Grader] Max retries ({settings.MAX_REVISION_RETRIES}) reached. Accepting best answer.")
        return {
            **state,
            "is_supported": True,            # Force exit the revision loop
            "confidence_score": 0.35,        # Always 0.35 at safety guard — constant low-confidence signal
            "reasoning_summary": f"Answer accepted after {revision_retries} revision attempts. Confidence is low."
        }

    print(f"[Hallucination Grader] Checking draft answer (attempt {revision_retries + 1}/{settings.MAX_REVISION_RETRIES})...")

    # ── Build the grading prompt ──────────────────────────────
    messages = [
        SystemMessage(content=HALLUCINATION_SYSTEM_PROMPT),
        HumanMessage(content=f"""CONTEXT (the only allowed source of truth):
---
{refined_context}
---

DRAFT ANSWER TO CHECK:
---
{draft_answer}
---

Is every claim in the draft answer supported by the context above?""")
    ]

    # ── Call gpt-4o-mini with structured output ───────────────
    verdict: HallucinationVerdict = hallucination_checker.invoke(messages)

    print(f"[Hallucination Grader] Verdict: {verdict.score.upper()} — {verdict.reason}")

    if verdict.score.lower() == "yes":
        # Answer is grounded — pass forward
        return {
            **state,
            "is_supported": True,
        }
    else:
        # Hallucination detected — increment counter and trigger revision
        return {
            **state,
            "is_supported": False,
            "revision_retries": revision_retries + 1,
        }


def revise_answer(state: GraphState) -> GraphState:
    """
    LangGraph Node: Answer Revision

    Called when check_hallucination returns is_supported=False.
    Forces the Smart Brain (Groq) to rewrite the draft answer
    using ONLY the refined context — no creativity allowed.
    """
    from app.services.llm_service import smart_llm

    refined_context = state.get("refined_context", "")
    query = state.get("original_query", state.get("query", ""))
    revision_retries = state.get("revision_retries", 0)

    print(f"[Revise Answer] Rewriting answer strictly from context (revision #{revision_retries})...")

    messages = [
        SystemMessage(content="""You are a strict answer writer. 
Rewrite the answer to the user's question using ONLY the information in the provided context.
Do NOT include any fact, number, or claim that is not explicitly stated in the context.
If the context does not contain enough information, say so honestly."""),
        HumanMessage(content=f"""CONTEXT:
---
{refined_context}
---

USER'S QUESTION: {query}

Write a clean, accurate answer using only the context above:""")
    ]

    response = smart_llm.invoke(messages)
    # Cast response.content to string to prevent Union errors if the message returns structured chunks
    revised_draft = str(response.content).strip()

    print(f"[Revise Answer] Revision complete. New draft length: {len(revised_draft)} chars")

    # Guard: if the LLM returns an empty string, keep the original draft
    # to avoid falsely passing hallucination check on an empty string and
    # triggering an infinite usefulness loop.
    if not revised_draft:
        print("[Revise Answer] WARNING: LLM returned empty string. Keeping previous draft.")
        revised_draft = state.get("draft_answer", "")

    return {
        **state,
        "draft_answer": revised_draft,
    }
