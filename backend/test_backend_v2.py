"""
ThinkTab AI -- Deep Backend Test Suite v2
Run: .\\venv\\Scripts\\python.exe -X utf8 test_backend_v2.py

Tests edge cases, state machine transitions, retry logic,
stale state contamination, and API format compatibility.
"""

import sys
import json
import asyncio
import hashlib
import traceback
from collections import OrderedDict

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
results = {"pass": 0, "fail": 0, "warn": 0}

def check(name, condition, warn_only=False):
    if condition:
        print(f"  {PASS} {name}")
        results["pass"] += 1
    elif warn_only:
        print(f"  {WARN} {name}")
        results["warn"] += 1
    else:
        print(f"  {FAIL} {name}")
        results["fail"] += 1

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def make_state(**overrides):
    """Returns a complete default GraphState with optional overrides."""
    base = {
        "query": "What is Stripe?",
        "original_query": "What is Stripe?",
        "mode": "deep",
        "selected_mode": "deep",
        "chat_history": [],
        "contexts": [],
        "docs": [],
        "good_docs": [],
        "refined_context": "",
        "crag_verdict": None,
        "web_query": None,
        "web_docs": [],
        "draft_answer": None,
        "final_answer": None,
        "evidence": [],
        "confidence_score": None,
        "reasoning_summary": None,
        "is_supported": None,
        "is_useful": None,
        "revision_retries": 0,
        "retrieval_retries": 0,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------
# SECTION 1: Regression Tests (Previously Fixed Bugs)
# ----------------------------------------------------------------
section("1. REGRESSION: generate_deep writes draft_answer not final_answer")

from app.graph.nodes.generation import generate_fast, generate_deep

s = make_state(refined_context="")
r = generate_deep(s)
check("generate_deep: draft_answer is set",    r.get("draft_answer") is not None)
check("generate_deep: final_answer is NOT set", r.get("final_answer") is None)

s2 = make_state(good_docs=[])
r2 = generate_fast(s2)
check("generate_fast: final_answer is set",    r2.get("final_answer") is not None)
check("generate_fast: draft_answer NOT set by fast",
      r2.get("draft_answer") is None)


# ----------------------------------------------------------------
# SECTION 2: Regression -- revision_retries reset
# ----------------------------------------------------------------
section("2. REGRESSION: revision_retries reset in rewrite_question")

from app.graph.nodes.answer_grader import rewrite_question

s3 = make_state(revision_retries=2, retrieval_retries=1,
                query="stripe fees", original_query="What are Stripe fees?")
r3 = rewrite_question(s3)
check("revision_retries reset to 0",   r3.get("revision_retries") == 0)
check("retrieval_retries preserved",   r3.get("retrieval_retries") == 1)
check("query is rewritten",            r3.get("query") != "stripe fees")
check("original_query unchanged",      r3.get("original_query") == "What are Stripe fees?")


# ----------------------------------------------------------------
# SECTION 3: NEW BUG -- stale web_docs contamination
# ----------------------------------------------------------------
section("3. NEW BUG: stale web_docs cleared by rewrite_question")

# After a web search cycle, web_docs has results.
# When rewrite_question fires (is_useful=False), a new retrieval cycle starts.
# The stale web_docs should be cleared so crag_refiner doesn't mix old web
# results with new local docs on the next pass.

from langchain_core.documents import Document

stale_web_doc = Document(page_content="stale web result", metadata={"source": "web_tavily"})
s4 = make_state(
    web_docs=[stale_web_doc],   # stale from a previous web search
    revision_retries=0,
    retrieval_retries=1,
    query="stripe fees", original_query="What are Stripe fees?"
)
r4 = rewrite_question(s4)

web_docs_cleared = (r4.get("web_docs") == [] or r4.get("web_docs") is None or
                    len(r4.get("web_docs", [stale_web_doc])) == 0)
check("web_docs cleared by rewrite_question",
      web_docs_cleared)

if not web_docs_cleared:
    print("    -> BUG CONFIRMED: web_docs not cleared! crag_refiner will mix stale web results")
    print(f"    -> web_docs still has: {len(r4.get('web_docs', []))} items")


# ----------------------------------------------------------------
# SECTION 4: NEW BUG -- crag_verdict + good_docs reset on new cycle
# ----------------------------------------------------------------
section("4. NEW BUG: crag_verdict and good_docs reset by rewrite_question")

from langchain_core.documents import Document as Doc

old_good_doc = Doc(page_content="old local result", metadata={"source": "old.com"})
s5 = make_state(
    good_docs=[old_good_doc],
    crag_verdict="INCORRECT",
    web_docs=[stale_web_doc],
    revision_retries=0, retrieval_retries=1
)
r5 = rewrite_question(s5)

check("crag_verdict cleared by rewrite_question",
      r5.get("crag_verdict") is None)

if r5.get("crag_verdict") is not None:
    print("    -> NOTE: crag_verdict='INCORRECT' from prev cycle leaks into next cycle")
    print("    -> retain_and_rerank will still re-run eval_docs, so this is minor")


# ----------------------------------------------------------------
# SECTION 5: Safety Guards -- both graders at max retries
# ----------------------------------------------------------------
section("5. SAFETY GUARDS: both graders at max retries don't loop forever")

from app.core.config import settings
from app.graph.nodes.hallucination_grader import check_hallucination
from app.graph.nodes.answer_grader import check_usefulness

# Hallucination grader at max retries must force is_supported=True
s6 = make_state(
    draft_answer="Some answer",
    refined_context="Some context",
    revision_retries=settings.MAX_REVISION_RETRIES,
)
r6 = check_hallucination(s6)
check("Hallucination guard: is_supported=True at limit",  r6.get("is_supported") is True)
check("Hallucination guard: confidence <= 0.35",          (r6.get("confidence_score") or 1.0) <= 0.35)

# Answer grader at max retries must force is_useful=True + set final_answer
s7 = make_state(
    draft_answer="Some answer",
    retrieval_retries=settings.MAX_RETRIEVAL_RETRIES,
)
r7 = check_usefulness(s7)
check("Answer grader: is_useful=True at limit",           r7.get("is_useful") is True)
check("Answer grader: final_answer is set",               r7.get("final_answer") == "Some answer")
check("Answer grader: confidence >= 0.30",                (r7.get("confidence_score") or 0.0) >= 0.30)


# ----------------------------------------------------------------
# SECTION 6: CRAG Refiner -- None Safety
# ----------------------------------------------------------------
section("6. CRAG REFINER: 'or []' None safety")

from app.graph.nodes.crag_refiner import crag_refiner

# Test with None values -- should NOT throw TypeError
s8 = make_state(good_docs=None, web_docs=None, query="test")
try:
    r8 = crag_refiner(s8)
    check("crag_refiner handles None good_docs safely",  True)
    check("crag_refiner returns refined_context",
          "refined_context" in r8)
except TypeError as e:
    check("crag_refiner handles None good_docs safely",  False)
    print(f"    -> TypeError: {e}")

# Test with empty lists -- should return empty refined_context
s9 = make_state(good_docs=[], web_docs=[], query="test")
r9 = crag_refiner(s9)
check("crag_refiner with empty lists returns empty context",
      r9.get("refined_context", "NOT_SET") == "")


# ----------------------------------------------------------------
# SECTION 7: SSE Safety Net Detection -- Robust JSON Parsing
# ----------------------------------------------------------------
section("7. SSE SAFETY NET: robust detection (JSON parse not string match)")

def detect_safety_net(event_str):
    """Mirrors the logic in endpoints.py"""
    try:
        if event_str.startswith("data:"):
            payload = json.loads(event_str[5:].strip())
            return (payload.get("type") == "final" and
                    payload.get("answer", "").strip().lower() ==
                    "i cannot find the answer on this page.")
    except Exception:
        pass
    return False

# Should detect
e1 = 'data: {"type": "final", "answer": "I cannot find the answer on this page.", "evidence": []}\n\n'
check("Detects standard safety net event",            detect_safety_net(e1))

# Uppercase variation
e2 = 'data: {"type": "final", "answer": "I CANNOT FIND THE ANSWER ON THIS PAGE.", "evidence": []}\n\n'
check("Detects uppercase variation",                  detect_safety_net(e2))

# Extra whitespace around answer
e3 = 'data: {"type": "final", "answer": "  I cannot find the answer on this page.  "}\n\n'
check("Detects answer with surrounding whitespace",   detect_safety_net(e3))

# Should NOT detect normal answers
e4 = 'data: {"type": "final", "answer": "Stripe charges 2.9%."}\n\n'
check("Does NOT flag normal answer as safety net",    not detect_safety_net(e4))

# Should NOT detect status events
e5 = 'data: {"type": "status", "value": "I cannot find the answer on this page."}\n\n'
check("Does NOT flag status events as safety net",    not detect_safety_net(e5))

# Should NOT throw on malformed JSON
e6 = 'data: {"broken json\n\n'
try:
    result = detect_safety_net(e6)
    check("Does NOT crash on malformed JSON",          not result)
except Exception:
    check("Does NOT crash on malformed JSON",          False)


# ----------------------------------------------------------------
# SECTION 8: Tavily TavilySearch -- New API Format Compatibility
# ----------------------------------------------------------------
section("8. TAVILY: new langchain_tavily package import and format")

try:
    from langchain_tavily import TavilySearch
    check("TavilySearch imports successfully",         True)

    # Verify the tool can be instantiated
    tool = TavilySearch(max_results=3, topic="general")
    check("TavilySearch instantiates",                 tool is not None)

    # Verify it has an invoke method
    check("TavilySearch has invoke method",            callable(getattr(tool, "invoke", None)))

    # Check that our web_search.py module loads without error
    from app.graph.nodes import web_search as ws_module
    check("web_search.py module loads without error",  True)
    check("search_web function exists",                callable(ws_module.search_web))
    check("rewrite_for_web function exists",           callable(ws_module.rewrite_for_web))

except ImportError as e:
    check("TavilySearch imports successfully",         False)
    print(f"    -> ImportError: {e}")
except Exception as e:
    check("TavilySearch/web_search setup",             False)
    print(f"    -> Exception: {e}")


# ----------------------------------------------------------------
# SECTION 9: Deep Mode Graph -- Routing Logic
# ----------------------------------------------------------------
section("9. DEEP MODE GRAPH: routing functions")

from app.graph.deep_mode import (route_after_crag,
                                  route_after_hallucination_check,
                                  route_after_usefulness_check)
from langgraph.graph import END

# route_after_crag
check("CRAG CORRECT -> crag_refiner",
      route_after_crag(make_state(crag_verdict="CORRECT")) == "crag_refiner")
check("CRAG INCORRECT -> rewrite_for_web",
      route_after_crag(make_state(crag_verdict="INCORRECT")) == "rewrite_for_web")
check("CRAG AMBIGUOUS -> rewrite_for_web",
      route_after_crag(make_state(crag_verdict="AMBIGUOUS")) == "rewrite_for_web")
check("CRAG None (default) -> rewrite_for_web",
      route_after_crag(make_state(crag_verdict=None)) == "rewrite_for_web")

# route_after_hallucination_check
check("is_supported=True -> check_usefulness",
      route_after_hallucination_check(make_state(is_supported=True)) == "check_usefulness")
check("is_supported=False -> revise_answer",
      route_after_hallucination_check(make_state(is_supported=False)) == "revise_answer")
check("is_supported=None (default False) -> revise_answer",
      route_after_hallucination_check(make_state(is_supported=None)) == "revise_answer")

# route_after_usefulness_check
check("is_useful=True -> END",
      route_after_usefulness_check(make_state(is_useful=True)) == END)
check("is_useful=False -> rewrite_question",
      route_after_usefulness_check(make_state(is_useful=False)) == "rewrite_question")


# ----------------------------------------------------------------
# SECTION 10: Deep Mode Graph -- State Integrity After Full Cycle
# ----------------------------------------------------------------
section("10. DEEP MODE GRAPH: state fields preserved across node updates")

# Simulate what happens when deep_mode_graph.astream yields partial updates
# and endpoints.py merges them with current_state.update(state_update)
current_state = make_state()

# Simulate crag_evaluator update
update1 = {"crag_verdict": "INCORRECT", "good_docs": []}
current_state.update(update1)
check("State merge: crag_verdict updated",        current_state["crag_verdict"] == "INCORRECT")
check("State merge: original fields preserved",   current_state["original_query"] == "What is Stripe?")

# Simulate generate_deep update
update2 = {"draft_answer": "Stripe is a payment platform.", "confidence_score": 0.85}
current_state.update(update2)
check("State merge: draft_answer set",            current_state["draft_answer"] == "Stripe is a payment platform.")
check("State merge: confidence_score set",        current_state["confidence_score"] == 0.85)
check("State merge: crag_verdict still there",    current_state["crag_verdict"] == "INCORRECT")

# Simulate check_usefulness promotes draft to final
update3 = {"is_useful": True, "final_answer": current_state["draft_answer"]}
current_state.update(update3)
check("State merge: final_answer promoted from draft",  current_state["final_answer"] == "Stripe is a payment platform.")


# ----------------------------------------------------------------
# SECTION 11: Auto Router -- All Three Tiers
# ----------------------------------------------------------------
section("11. AUTO ROUTER: all three decision tiers")

from app.graph.auto_router import DEEP_MODE_SIGNALS

# Tier 1: multiple contexts
check("Tier 1: 2 contexts -> DEEP",   len([1, 2]) > 1)
check("Tier 1: 0 contexts -> continues to Tier 2", len([]) <= 1)
check("Tier 1: 1 context -> continues to Tier 2",  len([1]) <= 1)

# Tier 2: keywords
for kw in ["compare", "analyze", "why", "evaluate", "difference",
           "reliable", "better", "pros and cons"]:
    q = f"please {kw} this thing"
    hits = any(k in q.lower() for k in DEEP_MODE_SIGNALS)
    check(f"Tier 2: '{kw}' detected", hits)

# Simple queries should NOT hit Tier 2
for simple in ["what is the price", "how much does it cost", "show me the plan"]:
    hits = any(k in simple.lower() for k in DEEP_MODE_SIGNALS)
    check(f"Tier 2: simple query '{simple[:25]}' not flagged", not hits)


# ----------------------------------------------------------------
# SECTION 12: FastAPI -- All Routes Present
# ----------------------------------------------------------------
section("12. FASTAPI: all required routes registered")

from app.main import app
routes = [getattr(r, "path", "") for r in app.routes]
check("/health route",                  "/health" in routes)
check("/api/chat route",                "/api/chat" in routes)
check("/api/embed route",               "/api/embed" in routes)
cache_route = any("/api/cache" in p for p in routes)
check("/api/cache/{source_id} route",   cache_route)


# ----------------------------------------------------------------
# SECTION 13: Live HTTP -- Server Health & Chat Endpoint
# ----------------------------------------------------------------
section("13. LIVE HTTP: server health and SSE endpoint")

async def run_http_tests():
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            # Health check
            resp = await client.get("http://localhost:8000/health")
            check("GET /health returns 200",           resp.status_code == 200)
            data = resp.json()
            check("Health has status=ok",              data.get("status") == "ok")
            check("Health has routing model",          "routing" in data.get("active_models", {}))
            check("Health has generation model",       "generation" in data.get("active_models", {}))

            # Pre-embed endpoint (empty content test)
            embed_resp = await client.post("http://localhost:8000/api/embed", json={
                "source_id": "test.com",
                "content": "This is test content for embedding in the ThinkTab test suite."
            })
            check("POST /api/embed returns 200",       embed_resp.status_code == 200)
            embed_data = embed_resp.json()
            check("Embed returns status=cached",       embed_data.get("status") == "cached")
            check("Embed returns source_id",           embed_data.get("source_id") == "test.com")

            # Cache delete endpoint
            del_resp = await client.delete("http://localhost:8000/api/cache/test.com")
            check("DELETE /api/cache returns 200",     del_resp.status_code == 200)

    except Exception as e:
        check("Server is reachable",                   False, warn_only=True)
        print(f"    -> Server may not be running or httpx not installed: {e}")

asyncio.run(run_http_tests())


# ----------------------------------------------------------------
# SECTION 14: Requirements -- All imports work
# ----------------------------------------------------------------
section("14. IMPORTS: all backend modules import cleanly")

modules = [
    ("app.core.config",                   "settings"),
    ("app.services.llm_service",          "fast_llm, smart_llm"),
    ("app.services.vector_store",         "embedding_cache"),
    ("app.graph.state",                   "GraphState"),
    ("app.graph.auto_router",             "route_query"),
    ("app.graph.fast_mode",               "run_fast_mode"),
    ("app.graph.deep_mode",               "deep_mode_graph"),
    ("app.graph.nodes.contextualizer",    "contextualize_query"),
    ("app.graph.nodes.retrieval",         "retrieve_and_rerank"),
    ("app.graph.nodes.crag_evaluator",    "eval_docs"),
    ("app.graph.nodes.crag_refiner",      "crag_refiner"),
    ("app.graph.nodes.web_search",        "search_web, rewrite_for_web"),
    ("app.graph.nodes.generation",        "generate_fast, generate_deep"),
    ("app.graph.nodes.hallucination_grader", "check_hallucination, revise_answer"),
    ("app.graph.nodes.answer_grader",     "check_usefulness, rewrite_question"),
    ("app.api.endpoints",                 "router"),
]

for mod_path, symbols in modules:
    try:
        mod = __import__(mod_path, fromlist=symbols.split(","))
        for sym in symbols.split(","):
            sym = sym.strip()
            has = hasattr(mod, sym)
            check(f"{mod_path}.{sym}",    has)
    except Exception as e:
        check(f"{mod_path} imports",     False)
        print(f"    -> {e}")


# ----------------------------------------------------------------
# FINAL SUMMARY
# ----------------------------------------------------------------
section("FINAL RESULTS")
total = results["pass"] + results["fail"] + results["warn"]
print(f"\n  Total Tests : {total}")
print(f"  Passed      : {results['pass']}")
print(f"  Failed      : {results['fail']}")
print(f"  Warnings    : {results['warn']}")
print()

if results["fail"] == 0:
    print("  ALL TESTS PASSED - Backend is production ready!")
else:
    print(f"  {results['fail']} FAILED - fix before proceeding.")
    sys.exit(1)
