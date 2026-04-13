from langgraph.graph import StateGraph, END

from app.graph.state import GraphState

# ── Import all individual nodes ────────────────────────────────────────────────
from app.graph.nodes.contextualizer import contextualize_query
from app.graph.nodes.retrieval import retrieve_and_rerank
from app.graph.nodes.crag_evaluator import eval_docs
from app.graph.nodes.web_search import rewrite_for_web, search_web
from app.graph.nodes.crag_refiner import crag_refiner
from app.graph.nodes.generation import generate_fast as generate_draft
from app.graph.nodes.hallucination_grader import check_hallucination, revise_answer
from app.graph.nodes.answer_grader import check_usefulness, rewrite_question


# ─────────────────────────────────────────────────────────────────────────────
# Routing Functions (Conditional Edges)
# These are simple functions that READ the GraphState and return the NAME
# of the next node to execute. LangGraph uses these to decide which path to take.
# ─────────────────────────────────────────────────────────────────────────────

def route_after_crag(state: GraphState) -> str:
    """
    Called after crag_evaluator completes.
    Reads the CRAG verdict and decides the next node:

    - CORRECT   → skip web search, go straight to sentence-level refinement
    - INCORRECT → local docs are useless, go to web search instead
    - AMBIGUOUS → local docs are mixed quality, supplement with web search
    """
    verdict = state.get("crag_verdict", "INCORRECT")
    print(f"[Router] CRAG verdict: {verdict}")

    if verdict == "CORRECT":
        return "crag_refiner"       # Local docs are good enough
    else:
        return "rewrite_for_web"    # INCORRECT or AMBIGUOUS → web search


def route_after_hallucination_check(state: GraphState) -> str:
    """
    Called after check_hallucination completes.
    Reads is_supported and decides the next node:

    - True  → answer is grounded, proceed to usefulness check
    - False → hallucination detected, revise the answer
    """
    is_supported = state.get("is_supported", False)
    revision_retries = state.get("revision_retries", 0)

    if is_supported:
        print("[Router] Answer is grounded. Moving to usefulness check.")
        return "check_usefulness"
    else:
        print(f"[Router] Hallucination detected. Revision attempt #{revision_retries}.")
        return "revise_answer"


def route_after_usefulness_check(state: GraphState) -> str:
    """
    Called after check_usefulness completes.
    Reads is_useful and decides the next node:

    - True  → answer is useful, we are DONE
    - False → answer is off-topic, rewrite the question and re-retrieve
    """
    is_useful = state.get("is_useful", False)
    retrieval_retries = state.get("retrieval_retries", 0)

    if is_useful:
        print("[Router] Answer is useful. Pipeline complete.")
        return END
    else:
        print(f"[Router] Answer not useful. Re-retrieval attempt #{retrieval_retries}.")
        return "rewrite_question"


# ─────────────────────────────────────────────────────────────────────────────
# Build the Deep Mode StateGraph
# ─────────────────────────────────────────────────────────────────────────────

def build_deep_mode_graph():
    """
    Constructs and compiles the full Deep Mode LangGraph pipeline.

    Returns a compiled graph that can be invoked with an initial GraphState:
        result = deep_mode_graph.invoke(initial_state)
    """

    # ── Step 1: Create a new StateGraph using our shared state schema ──────
    graph = StateGraph(GraphState)

    # ── Step 2: Register all nodes ─────────────────────────────────────────
    # Each .add_node(name, function) call registers a worker.
    # The name is how we reference this node in edges below.
    graph.add_node("contextualize_query",    contextualize_query)
    graph.add_node("retrieve_and_rerank",    retrieve_and_rerank)
    graph.add_node("eval_docs",              eval_docs)
    graph.add_node("rewrite_for_web",        rewrite_for_web)
    graph.add_node("search_web",             search_web)
    graph.add_node("crag_refiner",           crag_refiner)
    graph.add_node("generate_draft",         generate_draft)
    graph.add_node("check_hallucination",    check_hallucination)
    graph.add_node("revise_answer",          revise_answer)
    graph.add_node("check_usefulness",       check_usefulness)
    graph.add_node("rewrite_question",       rewrite_question)

    # ── Step 3: Set the entry point ────────────────────────────────────────
    # This is the FIRST node that runs when the graph is invoked.
    graph.set_entry_point("contextualize_query")

    # ── Step 4: Define NORMAL edges (unconditional, always run next) ────────
    # contextualize → retrieve → evaluate docs
    graph.add_edge("contextualize_query", "retrieve_and_rerank")
    graph.add_edge("retrieve_and_rerank", "eval_docs")

    # Web search path: rewrite query → search → refine
    graph.add_edge("rewrite_for_web", "search_web")
    graph.add_edge("search_web",      "crag_refiner")

    # CORRECT path also leads to refiner (no web search needed)
    graph.add_edge("crag_refiner",    "generate_draft")

    # After generation, always check for hallucinations
    graph.add_edge("generate_draft",  "check_hallucination")

    # If revision is needed, go back to hallucination check after revising
    graph.add_edge("revise_answer",   "check_hallucination")

    # If question rewrite is needed, go back to retrieval for a fresh attempt
    graph.add_edge("rewrite_question", "retrieve_and_rerank")

    # ── Step 5: Define CONDITIONAL edges (if/else routing) ─────────────────
    # After CRAG evaluation: CORRECT → refiner, INCORRECT/AMBIGUOUS → web search
    graph.add_conditional_edges(
        "eval_docs",
        route_after_crag,
        {
            "crag_refiner":    "crag_refiner",    # CORRECT path
            "rewrite_for_web": "rewrite_for_web", # INCORRECT / AMBIGUOUS path
        }
    )

    # After hallucination check: grounded → usefulness check, not grounded → revise
    graph.add_conditional_edges(
        "check_hallucination",
        route_after_hallucination_check,
        {
            "check_usefulness": "check_usefulness", # Grounded path
            "revise_answer":    "revise_answer",    # Hallucination path
        }
    )

    # After usefulness check: useful → END, not useful → rewrite question
    graph.add_conditional_edges(
        "check_usefulness",
        route_after_usefulness_check,
        {
            END:                END,                # Done! 
            "rewrite_question": "rewrite_question", # Not useful path
        }
    )

    # ── Step 6: Compile the graph ──────────────────────────────────────────
    # This validates all edges and nodes, then returns a runnable object.
    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Global instance — import this everywhere in the app
# ─────────────────────────────────────────────────────────────────────────────
deep_mode_graph = build_deep_mode_graph()
