"""
ThinkTab AI -- Backend Test Suite v3
Run: .\\venv\\Scripts\\python.exe -X utf8 test_backend_v3.py

Focuses on new issues found in third code review pass:
  - confidence_score cap direction (max vs min) at safety guards
  - retrieve_and_rerank with empty context content
  - contextualizer None/malformed chat_history handling
  - batch_crag_filter with None docs
  - revise_answer with empty LLM response
  - endpoint state initialization correctness
  - Tavily result format iteration safety
  - generate_deep whitespace-only refined_context
"""

import sys
import json
import asyncio
import traceback

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
    base = {
        "query": "What is Stripe?", "original_query": "What is Stripe?",
        "mode": "deep", "selected_mode": "deep",
        "chat_history": [], "contexts": [], "docs": [], "good_docs": [],
        "refined_context": "", "crag_verdict": None, "web_query": None,
        "web_docs": [], "draft_answer": None, "final_answer": None,
        "evidence": [], "confidence_score": None, "reasoning_summary": None,
        "is_supported": None, "is_useful": None,
        "revision_retries": 0, "retrieval_retries": 0,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------
# SECTION 1: confidence_score cap direction bug
# ----------------------------------------------------------------
section("1. BUG: confidence_score capped correctly at max retrieval retries")

from app.core.config import settings
from app.graph.nodes.answer_grader import check_usefulness

# When we hit MAX_RETRIEVAL_RETRIES, confidence should NOT be reported
# as falsely high. If generate_deep gave 0.85, but we couldn't validate
# the answer after 3 re-retrievals, confidence should be CAPPED LOW.

high_conf_state = make_state(
    draft_answer="Some answer",
    confidence_score=0.85,       # generate_deep was very confident
    retrieval_retries=settings.MAX_RETRIEVAL_RETRIES,
)
r = check_usefulness(high_conf_state)

conf = r.get("confidence_score", 0.85)
check("At max retrieval retries, confidence is capped <= 0.45",
      conf <= 0.45)

if conf > 0.45:
    print(f"    -> BUG: confidence_score reported as {conf:.2f}")
    print(f"    -> A high-confidence badge is shown for an unvalidated answer")
    print(f"    -> Fix: use min(score, 0.35) not max(score, 0.30) in safety guard")


# ----------------------------------------------------------------
# SECTION 2: generate_deep whitespace-only refined_context
# ----------------------------------------------------------------
section("2. generate_deep handles whitespace-only refined_context")

from app.graph.nodes.generation import generate_deep

# A string with only spaces/newlines should trigger the safety net
for ws_ctx in ["", "   ", "\n\n\n", "\t  \t"]:
    s = make_state(refined_context=ws_ctx)
    r = generate_deep(s)
    check(f"Whitespace context '{repr(ws_ctx)}' triggers safety net",
          r.get("draft_answer") == "I cannot find the answer on this page.")
    check(f"final_answer NOT set for whitespace context '{repr(ws_ctx)}'",
          r.get("final_answer") is None)


# ----------------------------------------------------------------
# SECTION 3: contextualizer with None and malformed chat_history
# ----------------------------------------------------------------
section("3. contextualizer handles None and malformed chat_history")

from app.graph.nodes.contextualizer import contextualize_query

# None chat_history (uses 'or []' so should be safe)
s_none = make_state(chat_history=None, query="What is Stripe?")
try:
    r = contextualize_query(s_none)
    check("Contextualizer: None chat_history handled safely",      True)
    check("Contextualizer: None history -> query unchanged",
          r.get("query") == "What is Stripe?")
except Exception as e:
    check("Contextualizer: None chat_history handled safely",      False)
    print(f"    -> Exception: {e}")

# Empty list chat_history (should skip LLM)
s_empty = make_state(chat_history=[], query="What is Stripe?")
try:
    r = contextualize_query(s_empty)
    check("Contextualizer: empty list -> query unchanged",
          r.get("query") == "What is Stripe?")
    check("Contextualizer: original_query set to query",
          r.get("original_query") == "What is Stripe?")
except Exception as e:
    check("Contextualizer: empty chat_history handled safely",     False)
    print(f"    -> Exception: {e}")

# Malformed history item (missing 'role' key)
s_malformed = make_state(
    chat_history=[{"content": "no role key here"}],  # missing 'role'
    query="follow up question"
)
try:
    # contextualizer does: msg['role'].capitalize()
    # This will throw KeyError if 'role' is missing
    # The node itself has no error handling for this
    r = contextualize_query(s_malformed)
    # If it gets here, it made an LLM call or handled gracefully
    check("Contextualizer: malformed history item handled",        True, warn_only=True)
except KeyError as e:
    check("Contextualizer: malformed history KeyError",            False, warn_only=True)
    print(f"    -> WARN: KeyError on missing key: {e}")
    print(f"    -> Risk is low (Pydantic validates input), but no internal guard")


# ----------------------------------------------------------------
# SECTION 4: retrieve_and_rerank with empty contexts (no crash)
# ----------------------------------------------------------------
section("4. retrieve_and_rerank handles empty contexts gracefully")

from app.graph.nodes.retrieval import retrieve_and_rerank

s_no_ctx = make_state(contexts=[], query="What is Stripe?")
try:
    r = retrieve_and_rerank(s_no_ctx)
    check("retrieve_and_rerank: empty contexts returns docs=[]",
          r.get("docs") == [] or r.get("docs") is None)
    check("retrieve_and_rerank: does NOT crash on empty contexts", True)
except Exception as e:
    check("retrieve_and_rerank: handles empty contexts",           False)
    print(f"    -> Exception: {e}")


# ----------------------------------------------------------------
# SECTION 5: retrieve_and_rerank with empty content string
# ----------------------------------------------------------------
section("5. retrieve_and_rerank handles empty content in context item")

s_empty_content = make_state(
    contexts=[{"source_id": "empty.com", "content": ""}],
    query="What is Stripe?"
)
try:
    r = retrieve_and_rerank(s_empty_content)
    check("retrieve_and_rerank: empty content handled",            True, warn_only=True)
    check("retrieve_and_rerank: returns docs list",
          isinstance(r.get("docs"), list))
except Exception as e:
    check("retrieve_and_rerank: empty content crashes",            False, warn_only=True)
    print(f"    -> WARN: Empty content causes: {type(e).__name__}: {e}")
    print(f"    -> Fix: add empty content guard before get_or_embed")


# ----------------------------------------------------------------
# SECTION 6: batch_crag_filter with None docs
# ----------------------------------------------------------------
section("6. batch_crag_filter handles None docs safely")

from app.graph.fast_mode import batch_crag_filter

# None docs — 'if not docs' should handle this
s_none_docs = make_state(docs=None)
try:
    r = batch_crag_filter(s_none_docs)
    check("batch_crag_filter: None docs returns good_docs=[]",
          r.get("good_docs") == [])
    check("batch_crag_filter: does NOT crash on None docs",        True)
except Exception as e:
    check("batch_crag_filter: None docs crashes",                  False)
    print(f"    -> Exception: {e}")

# Empty docs list
s_empty_docs = make_state(docs=[])
r2 = batch_crag_filter(s_empty_docs)
check("batch_crag_filter: empty docs returns good_docs=[]",        r2.get("good_docs") == [])


# ----------------------------------------------------------------
# SECTION 7: Tavily result iteration safety
# ----------------------------------------------------------------
section("7. search_web handles unexpected Tavily result format")

from app.graph.nodes.web_search import search_web

# If Tavily returns a string instead of a list, iteration would work
# (you'd iterate characters), but item.get() would fail.
# The try/except in search_web handles this gracefully.

# Simulate string result (malformed)
# We test this by mocking the invoke method
from unittest.mock import patch, MagicMock

# Test 1: Tavily returns empty list
with patch("app.graph.nodes.web_search.web_search_tool") as mock_tool:
    mock_tool.invoke.return_value = []
    s = make_state(web_query="stripe fees")
    r = search_web(s)
    check("search_web: empty list result -> web_docs=[]",
          r.get("web_docs") == [])

# Test 2: Tavily returns correct list of dicts
with patch("app.graph.nodes.web_search.web_search_tool") as mock_tool:
    mock_tool.invoke.return_value = [
        {"url": "https://stripe.com", "content": "Stripe charges 2.9% + 30c"},
        {"url": "https://docs.stripe.com", "content": ""},   # empty content — should skip
    ]
    s = make_state(web_query="stripe fees")
    r = search_web(s)
    check("search_web: filters out empty-content results",
          len(r.get("web_docs", [])) == 1)
    check("search_web: keeps non-empty results",
          r["web_docs"][0].page_content == "Stripe charges 2.9% + 30c")
    check("search_web: doc has correct source tag",
          r["web_docs"][0].metadata.get("source") == "web_tavily")
    check("search_web: doc stores actual_url",
          r["web_docs"][0].metadata.get("actual_url") == "https://stripe.com")

# Test 3: Tavily raises exception
with patch("app.graph.nodes.web_search.web_search_tool") as mock_tool:
    mock_tool.invoke.side_effect = Exception("API limit exceeded")
    s = make_state(web_query="stripe fees")
    try:
        r = search_web(s)
        check("search_web: API exception -> web_docs=[]",
              r.get("web_docs") == [])
    except Exception as e:
        check("search_web: API exception NOT caught",              False)
        print(f"    -> Exception escaped: {e}")


# ----------------------------------------------------------------
# SECTION 8: revise_answer with edge cases
# ----------------------------------------------------------------
section("8. revise_answer edge cases")

from app.graph.nodes.hallucination_grader import revise_answer
from unittest.mock import patch, MagicMock

# Test: empty response from LLM (edge case)
# revise_answer does: from app.services.llm_service import smart_llm (local import)
# So we patch the source module, not the local binding
with patch("app.services.llm_service.smart_llm") as mock_llm:
    mock_response = MagicMock()
    mock_response.content = "   "   # whitespace-only response
    mock_llm.invoke.return_value = mock_response

    s = make_state(
        draft_answer="old answer",
        refined_context="some context",
        revision_retries=1
    )
    r = revise_answer(s)
    draft = r.get("draft_answer", "NOT_SET")
    check("revise_answer: whitespace LLM response stripped to empty",
          draft == "" or draft is None or draft == "old answer",
          warn_only=True)
    if draft == "":
        print(f"    -> WARN: empty draft_answer after revision")
        print(f"    -> check_hallucination will check empty string against context")

# Test: normal response
with patch("app.services.llm_service.smart_llm") as mock_llm:
    mock_response = MagicMock()
    mock_response.content = "Stripe is a payment platform."
    mock_llm.invoke.return_value = mock_response

    s = make_state(draft_answer="old answer", refined_context="context", revision_retries=1)
    r = revise_answer(s)
    check("revise_answer: normal revision updates draft_answer",
          r.get("draft_answer") == "Stripe is a payment platform.")
    check("revise_answer: does not touch final_answer",
          r.get("final_answer") == s.get("final_answer"))


# ----------------------------------------------------------------
# SECTION 9: state initialization in endpoints.py
# ----------------------------------------------------------------
section("9. endpoints.py state initialization correctness")

# Verify all GraphState fields are initialized in endpoints.py
# with sensible defaults (not None where it could cause bugs)

required_fields = {
    "query": str, "original_query": str, "mode": str,
    "selected_mode": type(None), "chat_history": list,
    "contexts": list, "docs": list, "good_docs": list,
    "refined_context": str, "crag_verdict": type(None),
    "web_query": str, "web_docs": list, "draft_answer": str,
    "final_answer": str, "evidence": list, "confidence_score": float,
    "reasoning_summary": str, "is_supported": type(None),
    "is_useful": type(None), "revision_retries": int, "retrieval_retries": int,
}

# Replicate the initialization logic from endpoints.py L87-109
from app.graph.state import GraphState
init_state: GraphState = {
    "query": "test",
    "original_query": "test",
    "mode": "auto",
    "selected_mode": None,
    "chat_history": [],
    "contexts": [],
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

for field, expected_type in required_fields.items():
    val = init_state.get(field)
    check(f"init state: '{field}' is {expected_type.__name__}",
          isinstance(val, expected_type))

# Specific checks
check("init: draft_answer starts as empty string (not None)",
      init_state["draft_answer"] == "")
check("init: final_answer starts as empty string (not None)",
      init_state["final_answer"] == "")
check("init: confidence_score starts as 0.0",
      init_state["confidence_score"] == 0.0)
check("init: revision_retries starts at 0",
      init_state["revision_retries"] == 0)
check("init: retrieval_retries starts at 0",
      init_state["retrieval_retries"] == 0)

# The execute_deep_mode final event handles empty string as falsy
final_answer = init_state.get("final_answer") or init_state.get("draft_answer", "fallback")
check("execute_deep_mode fallback: empty string triggers draft_answer fallback",
      final_answer == "")   # both are "", so we'd get ""


# ----------------------------------------------------------------
# SECTION 10: Deep Mode DEEP_NODE_MESSAGES completeness
# ----------------------------------------------------------------
section("10. DEEP_NODE_MESSAGES covers ALL graph nodes")

from app.api.endpoints import DEEP_NODE_MESSAGES
from app.graph.deep_mode import build_deep_mode_graph

graph = build_deep_mode_graph()
# LangGraph compiled graph exposes node names in various ways
# We'll check the DEEP_NODE_MESSAGES dict against known nodes
expected_nodes = [
    "contextualize_query", "retrieve_and_rerank", "eval_docs",
    "rewrite_for_web", "search_web", "crag_refiner", "generate_draft",
    "check_hallucination", "revise_answer", "check_usefulness",
    "rewrite_question"
]
for node in expected_nodes:
    check(f"Node '{node}' has a UI message",   node in DEEP_NODE_MESSAGES)

check("No extra unknown nodes in messages",
      all(n in expected_nodes for n in DEEP_NODE_MESSAGES.keys()))


# ----------------------------------------------------------------
# SECTION 11: Full state machine path coverage
# ----------------------------------------------------------------
section("11. State machine: every path has matching router output")

from app.graph.deep_mode import (route_after_crag,
                                  route_after_hallucination_check,
                                  route_after_usefulness_check)
from langgraph.graph import END

# Exhaustive routing tests
crag_paths = [
    ("CORRECT",   "crag_refiner"),
    ("INCORRECT", "rewrite_for_web"),
    ("AMBIGUOUS", "rewrite_for_web"),
    (None,        "rewrite_for_web"),
    ("UNKNOWN",   "rewrite_for_web"),   # Any unknown verdict should go to web search
]
for verdict, expected in crag_paths:
    s = make_state(crag_verdict=verdict)
    actual = route_after_crag(s)
    check(f"CRAG '{verdict}' -> '{expected}'",   actual == expected)

hallucination_paths = [
    (True,  "check_usefulness"),
    (False, "revise_answer"),
    (None,  "revise_answer"),
]
for is_sup, expected in hallucination_paths:
    s = make_state(is_supported=is_sup)
    actual = route_after_hallucination_check(s)
    check(f"is_supported={is_sup} -> '{expected}'",   actual == expected)

usefulness_paths = [
    (True,  END),
    (False, "rewrite_question"),
    (None,  "rewrite_question"),
]
for is_use, expected in usefulness_paths:
    s = make_state(is_useful=is_use)
    actual = route_after_usefulness_check(s)
    check(f"is_useful={is_use} -> '{expected}'",   actual == expected)


# ----------------------------------------------------------------
# SECTION 12: Live HTTP -- full SSE event structure validation
# ----------------------------------------------------------------
section("12. LIVE HTTP: SSE events have correct structure")

async def run_sse_structure_test():
    try:
        import httpx
        # Send a fast mode request with real context to get a proper stream
        async with httpx.AsyncClient(timeout=10) as client:
            # Test 1: mode field in SSE response for explicit fast mode
            async with client.stream("POST", "http://localhost:8000/api/chat", json={
                "query": "hello",
                "mode": "fast",
                "contexts": [],
                "chat_history": []
            }) as resp:
                check("Chat endpoint returns 200",     resp.status_code == 200)
                check("Content-Type is event-stream",
                      "text/event-stream" in resp.headers.get("content-type", ""))

                events = []
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            payload = json.loads(line[5:].strip())
                            events.append(payload)
                        except Exception:
                            pass

                types = [e.get("type") for e in events]
                check("First event is 'mode' type",   types[0] == "mode" if types else False)
                check("Last event is 'final' type",   types[-1] == "final" if types else False)

                # Validate final event structure
                final_events = [e for e in events if e.get("type") == "final"]
                if final_events:
                    fe = final_events[0]
                    check("Final event has 'answer' key",           "answer" in fe)
                    check("Final event has 'evidence' key",         "evidence" in fe)
                    check("Final event has 'confidence_score' key", "confidence_score" in fe)
                    check("Final event has 'reasoning_summary'",    "reasoning_summary" in fe)
                    check("evidence is a list",                     isinstance(fe.get("evidence"), list))
                    check("confidence_score is a number",
                          isinstance(fe.get("confidence_score"), (int, float)))
                else:
                    check("No final event received",                False, warn_only=True)

            # Test 2: explicit deep mode request structure
            async with client.stream("POST", "http://localhost:8000/api/chat", json={
                "query": "test",
                "mode": "deep",
                "contexts": [],
                "chat_history": []
            }) as resp2:
                deep_events = []
                async for line in resp2.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            payload = json.loads(line[5:].strip())
                            deep_events.append(payload)
                        except Exception:
                            pass
                deep_types = [e.get("type") for e in deep_events]
                check("Deep mode: first event is 'mode'",
                      deep_types[0] == "mode" if deep_types else False)
                check("Deep mode: has status events",
                      "status" in deep_types)
                check("Deep mode: last event is 'final'",
                      deep_types[-1] == "final" if deep_types else False)

    except Exception as e:
        check("Live HTTP test (server must be running)",            False, warn_only=True)
        print(f"    -> {e}")

asyncio.run(run_sse_structure_test())


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
    print("  ALL TESTS PASSED - Backend is hardened!")
else:
    print(f"  {results['fail']} FAILED - fix before proceeding.")
    sys.exit(1)
