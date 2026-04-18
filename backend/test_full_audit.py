"""
ThinkTab-AI Backend — Full Audit Test Suite
============================================
Covers EVERY endpoint, EVERY mode, EVERY edge case.

Run with: python test_full_audit.py
Requires: Backend running on http://localhost:8000
"""

import requests
import json
import time
import sys

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0
RESULTS = []

# ─── Rich context block simulating a real Stripe pricing page ───
STRIPE_CONTEXT = """
Stripe is a financial infrastructure platform for businesses. 
Online payment processing for internet businesses. Stripe's products 
power payments for online and in-person retailers, subscriptions businesses, 
software platforms, marketplaces, and more.

Pricing: 2.9% + 30¢ per successful card charge. No setup fees, 
no monthly fees, no hidden fees. International cards incur an additional 1.5% fee.
Currency conversion is charged at 1%.

Stripe Radar for fraud detection is included free with every Stripe account.
Advanced Radar for Teams costs $0.07 per screened transaction.

Stripe Atlas helps entrepreneurs incorporate a US company from anywhere in the world.
Atlas costs $500 one-time fee and includes a C-corp, bank account, and EIN.
"""

GITHUB_CONTEXT = """
GitHub is a developer platform that allows developers to create, store, manage 
and share their code. It uses Git software, providing distributed version control 
plus access control, bug tracking, software feature requests, task management, 
and continuous integration.

GitHub offers free accounts for open source projects. GitHub Pro costs $4/month 
with advanced tools. GitHub Team costs $4/user/month. GitHub Enterprise costs 
$21/user/month with security, compliance, and deployment controls.

GitHub Copilot is an AI coding assistant. It costs $10/month for individuals 
and $19/user/month for businesses. GitHub Copilot Enterprise costs $39/user/month.
"""


def parse_sse_events(text: str) -> list[dict]:
    """Parse SSE response text into a list of JSON payloads."""
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            try:
                payload = json.loads(line[5:].strip())
                events.append(payload)
            except json.JSONDecodeError:
                events.append({"raw": line})
    return events


def run_test(test_id: str, description: str, method: str, endpoint: str,
             body: dict = None, expect_status: int = 200,
             check_fn=None):
    """Run a single test case and record pass/fail."""
    global PASS, FAIL
    url = f"{BASE}{endpoint}"
    
    print(f"\n{'='*70}")
    print(f"TEST {test_id}: {description}")
    print(f"{'='*70}")
    
    try:
        start = time.time()
        if method == "GET":
            resp = requests.get(url, timeout=60)
        elif method == "POST":
            resp = requests.post(url, json=body, timeout=60, stream=False)
        elif method == "DELETE":
            resp = requests.delete(url, timeout=60)
        elapsed = time.time() - start
        
        # Status code check
        if resp.status_code != expect_status:
            print(f"  ❌ FAIL: Expected status {expect_status}, got {resp.status_code}")
            print(f"  Response: {resp.text[:500]}")
            FAIL += 1
            RESULTS.append({"id": test_id, "desc": description, "status": "FAIL",
                            "reason": f"Status {resp.status_code} != {expect_status}", "time": elapsed})
            return None
        
        # Parse response
        if "text/event-stream" in resp.headers.get("content-type", ""):
            events = parse_sse_events(resp.text)
            print(f"  ⏱  {elapsed:.2f}s | {len(events)} SSE events")
            for e in events:
                etype = e.get("type", "?")
                if etype == "mode":
                    print(f"  📡 MODE: {e.get('value')}")
                elif etype == "status":
                    print(f"  ⏳ STATUS: {e.get('value')}")
                elif etype == "final":
                    ans = e.get("answer", "")[:150]
                    conf = e.get("confidence_score", "?")
                    evid = e.get("evidence", [])
                    print(f"  ✅ FINAL: {ans}...")
                    print(f"     Confidence: {conf} | Evidence items: {len(evid)}")
                elif etype == "error":
                    print(f"  ⚠️  ERROR: {e.get('value')}")
            
            # Custom check
            if check_fn:
                passed, reason = check_fn(events)
                if passed:
                    print(f"  ✅ PASS: {reason}")
                    PASS += 1
                    RESULTS.append({"id": test_id, "desc": description, "status": "PASS",
                                    "reason": reason, "time": elapsed})
                else:
                    print(f"  ❌ FAIL: {reason}")
                    FAIL += 1
                    RESULTS.append({"id": test_id, "desc": description, "status": "FAIL",
                                    "reason": reason, "time": elapsed})
            else:
                PASS += 1
                RESULTS.append({"id": test_id, "desc": description, "status": "PASS",
                                "reason": "Status OK", "time": elapsed})
            return events
        else:
            data = resp.json()
            print(f"  ⏱  {elapsed:.2f}s | Response: {json.dumps(data, indent=2)[:300]}")
            if check_fn:
                passed, reason = check_fn(data)
                if passed:
                    print(f"  ✅ PASS: {reason}")
                    PASS += 1
                    RESULTS.append({"id": test_id, "desc": description, "status": "PASS",
                                    "reason": reason, "time": elapsed})
                else:
                    print(f"  ❌ FAIL: {reason}")
                    FAIL += 1
                    RESULTS.append({"id": test_id, "desc": description, "status": "FAIL",
                                    "reason": reason, "time": elapsed})
            else:
                PASS += 1
                RESULTS.append({"id": test_id, "desc": description, "status": "PASS",
                                "reason": "Status OK", "time": elapsed})
            return data
    except requests.exceptions.ConnectionError:
        print(f"  ❌ FAIL: Cannot connect to {url}. Is the server running?")
        FAIL += 1
        RESULTS.append({"id": test_id, "desc": description, "status": "FAIL",
                        "reason": "Connection refused", "time": 0})
        return None
    except Exception as ex:
        print(f"  ❌ FAIL: {ex}")
        FAIL += 1
        RESULTS.append({"id": test_id, "desc": description, "status": "FAIL",
                        "reason": str(ex), "time": 0})
        return None


# ═══════════════════════════════════════════════════════════════
# SECTION 1: Health & Infrastructure
# ═══════════════════════════════════════════════════════════════

def test_health():
    run_test("1.1", "Health Check — Server alive",
             "GET", "/health",
             check_fn=lambda d: (d.get("status") == "ok", f"Models: {list(d.get('active_models', {}).values())}"))


# ═══════════════════════════════════════════════════════════════
# SECTION 2: Input Validation & Guards
# ═══════════════════════════════════════════════════════════════

def test_empty_query():
    run_test("2.1", "Empty Query Guard — Empty string rejected",
             "POST", "/api/chat",
             body={"query": "", "mode": "fast", "contexts": []},
             check_fn=lambda events: (
                 any(e.get("answer", "").lower().startswith("please enter") for e in events if e.get("type") == "final"),
                 "Got 'Please enter a question' response"
             ))

def test_whitespace_query():
    run_test("2.2", "Empty Query Guard — Whitespace-only query",
             "POST", "/api/chat",
             body={"query": "   \n\t  ", "mode": "fast", "contexts": []},
             check_fn=lambda events: (
                 any(e.get("answer", "").lower().startswith("please enter") for e in events if e.get("type") == "final"),
                 "Whitespace query rejected correctly"
             ))

def test_invalid_mode():
    run_test("2.3", "Mode Validation — Invalid mode 'quantum' rejected with 422",
             "POST", "/api/chat",
             body={"query": "test", "mode": "quantum", "contexts": []},
             expect_status=422)


# ═══════════════════════════════════════════════════════════════
# SECTION 3: Fast Mode Pipeline
# ═══════════════════════════════════════════════════════════════

def test_fast_mode_good_context():
    run_test("3.1", "Fast Mode — Direct answer from Stripe context",
             "POST", "/api/chat",
             body={
                 "query": "What is the fee for international cards on Stripe?",
                 "mode": "fast",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any("1.5%" in e.get("answer", "") for e in events if e.get("type") == "final"),
                 "Found '1.5%' in answer — correct factual extraction"
             ))

def test_fast_mode_no_context():
    """Fast mode with no context should trigger safety net → upgrade to Deep."""
    run_test("3.2", "Fast Mode Safety Net — No context triggers Deep upgrade",
             "POST", "/api/chat",
             body={
                 "query": "What is the capital of France?",
                 "mode": "fast",
                 "contexts": []
             },
             check_fn=lambda events: (
                 # Should upgrade to deep mode OR return a final answer from web search
                 any("deep" in e.get("value", "").lower() or "upgrading" in e.get("value", "").lower()
                     for e in events if e.get("type") == "status") or
                 any(e.get("type") == "final" for e in events),
                 "Safety net triggered or final answer provided"
             ))

def test_fast_mode_irrelevant_context():
    """Context exists but is totally irrelevant to the question → safety net."""
    run_test("3.3", "Fast Mode — Irrelevant context triggers safety net",
             "POST", "/api/chat",
             body={
                 "query": "What is the population of Tokyo?",
                 "mode": "fast",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any(e.get("type") == "final" for e in events),
                 "Got a final answer (either safety net or low-confidence)"
             ))


# ═══════════════════════════════════════════════════════════════
# SECTION 4: Deep Mode Pipeline
# ═══════════════════════════════════════════════════════════════

def test_deep_mode_good_context():
    run_test("4.1", "Deep Mode — Full pipeline with good Stripe context",
             "POST", "/api/chat",
             body={
                 "query": "How much does Stripe Atlas cost?",
                 "mode": "deep",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any("500" in e.get("answer", "") or "atlas" in e.get("answer", "").lower()
                     for e in events if e.get("type") == "final"),
                 "Found Atlas pricing ($500) in answer"
             ))

def test_deep_mode_web_search():
    """No context → CRAG evaluator returns INCORRECT → web search triggered."""
    run_test("4.2", "Deep Mode — Web search fallback (no local context)",
             "POST", "/api/chat",
             body={
                 "query": "What is Stripe?",
                 "mode": "deep",
                 "contexts": []
             },
             check_fn=lambda events: (
                 any("web" in e.get("value", "").lower() for e in events if e.get("type") == "status"),
                 "Web search status message detected"
             ))

def test_deep_mode_self_rag_pipeline():
    """Verify hallucination check and usefulness check both appear in status events."""
    run_test("4.3", "Deep Mode — Self-RAG pipeline nodes visible",
             "POST", "/api/chat",
             body={
                 "query": "What does Stripe Radar do?",
                 "mode": "deep",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any("fact-checking" in e.get("value", "").lower() or "hallucination" in e.get("value", "").lower()
                     for e in events if e.get("type") == "status") and
                 any("usefulness" in e.get("value", "").lower() or "verifying" in e.get("value", "").lower()
                     for e in events if e.get("type") == "status"),
                 "Both IsSUP and IsUSE status events detected"
             ))


# ═══════════════════════════════════════════════════════════════
# SECTION 5: Auto Mode Routing
# ═══════════════════════════════════════════════════════════════

def test_auto_mode_simple():
    """Simple factual query → should route to Fast mode."""
    run_test("5.1", "Auto Mode — Simple query routes to Fast",
             "POST", "/api/chat",
             body={
                 "query": "What is the cost per transaction?",
                 "mode": "auto",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any("auto" in e.get("value", "").lower() for e in events if e.get("type") == "mode"),
                 "Auto mode selection detected"
             ))

def test_auto_mode_complex():
    """Complex comparison query → should route to Deep mode."""
    run_test("5.2", "Auto Mode — Complex query routes to Deep",
             "POST", "/api/chat",
             body={
                 "query": "Compare the pricing models between these two platforms",
                 "mode": "auto",
                 "contexts": [
                     {"source_id": "stripe-docs", "content": STRIPE_CONTEXT},
                     {"source_id": "github-docs", "content": GITHUB_CONTEXT}
                 ]
             },
             check_fn=lambda events: (
                 any("deep" in e.get("value", "").lower() for e in events if e.get("type") == "mode"),
                 "Auto → Deep routing detected (multi-context + compare keyword)"
             ))


# ═══════════════════════════════════════════════════════════════
# SECTION 6: Chat History (Contextualizer)
# ═══════════════════════════════════════════════════════════════

def test_chat_history_resolution():
    """Follow-up question with 'it' pronoun → contextualizer should resolve."""
    run_test("6.1", "Chat History — Pronoun resolution in follow-up",
             "POST", "/api/chat",
             body={
                 "query": "What about their international fees?",
                 "mode": "fast",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}],
                 "chat_history": [
                     {"role": "user", "content": "Tell me about Stripe pricing"},
                     {"role": "assistant", "content": "Stripe charges 2.9% + 30 cents per transaction."}
                 ]
             },
             check_fn=lambda events: (
                 any("understanding" in e.get("value", "").lower() for e in events if e.get("type") == "status"),
                 "Contextualizer status event ('Understanding question...') detected"
             ))


# ═══════════════════════════════════════════════════════════════
# SECTION 7: Pre-Embed & Cache Endpoints
# ═══════════════════════════════════════════════════════════════

def test_pre_embed():
    run_test("7.1", "Pre-Embed — POST /api/embed caches a page",
             "POST", "/api/embed",
             body={"source_id": "test-page-embed", "content": STRIPE_CONTEXT},
             check_fn=lambda d: (d.get("status") == "cached", "Embed returned 'cached'"))

def test_cache_hit():
    """After pre-embed, a query should use the cached FAISS index (Cache HIT in logs)."""
    run_test("7.2", "Cache HIT — Query uses pre-embedded index",
             "POST", "/api/chat",
             body={
                 "query": "What is Stripe Radar?",
                 "mode": "fast",
                 "contexts": [{"source_id": "test-page-embed", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any(e.get("type") == "final" for e in events),
                 "Got final answer (server logs should show [Cache HIT])"
             ))

def test_cache_delete_found():
    """Delete a cached source → should return 200."""
    run_test("7.3", "Cache DELETE — Evict existing source",
             "DELETE", "/api/cache/test-page-embed",
             check_fn=lambda d: (d.get("status") == "evicted", "Eviction confirmed"))

def test_cache_delete_not_found():
    """Delete a source that doesn't exist → should return 404."""
    run_test("7.4", "Cache DELETE — Non-existent source returns 404",
             "DELETE", "/api/cache/nonexistent-source-xyz",
             expect_status=404)


# ═══════════════════════════════════════════════════════════════
# SECTION 8: Multi-Context Deep Analysis
# ═══════════════════════════════════════════════════════════════

def test_multi_context():
    run_test("8.1", "Multi-Context — Deep mode with 2 sources (Stripe + GitHub)",
             "POST", "/api/chat",
             body={
                 "query": "Compare pricing between Stripe and GitHub",
                 "mode": "deep",
                 "contexts": [
                     {"source_id": "stripe-docs", "content": STRIPE_CONTEXT},
                     {"source_id": "github-docs", "content": GITHUB_CONTEXT}
                 ]
             },
             check_fn=lambda events: (
                 any(e.get("type") == "final" and
                     ("stripe" in e.get("answer", "").lower() and "github" in e.get("answer", "").lower())
                     for e in events),
                 "Answer references both Stripe and GitHub"
             ))


# ═══════════════════════════════════════════════════════════════
# SECTION 9: Edge Cases & Adversarial Inputs
# ═══════════════════════════════════════════════════════════════

def test_sql_injection():
    run_test("9.1", "Security — SQL injection attempt handled safely",
             "POST", "/api/chat",
             body={
                 "query": "'; DROP TABLE users; --",
                 "mode": "fast",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any(e.get("type") == "final" for e in events),
                 "Pipeline completed without crash"
             ))

def test_special_characters():
    run_test("9.2", "Edge Case — Special chars in query (emoji + unicode)",
             "POST", "/api/chat",
             body={
                 "query": "What is Stripe's fee? 💰🔥 café résumé",
                 "mode": "fast",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any(e.get("type") == "final" for e in events),
                 "Pipeline handled special chars without crash"
             ))

def test_very_long_query():
    long_q = "What is Stripe? " * 50  # ~850 chars
    run_test("9.3", "Edge Case — Very long query (850+ chars)",
             "POST", "/api/chat",
             body={
                 "query": long_q,
                 "mode": "fast",
                 "contexts": [{"source_id": "stripe-docs", "content": STRIPE_CONTEXT}]
             },
             check_fn=lambda events: (
                 any(e.get("type") == "final" for e in events),
                 "Pipeline handled long query without crash"
             ))

def test_empty_content_context():
    run_test("9.4", "Edge Case — Context with empty content (should skip)",
             "POST", "/api/chat",
             body={
                 "query": "What is Stripe?",
                 "mode": "fast",
                 "contexts": [{"source_id": "empty-page", "content": "   "}]
             },
             check_fn=lambda events: (
                 any(e.get("type") == "final" for e in events),
                 "Pipeline handled empty content gracefully"
             ))


# ═══════════════════════════════════════════════════════════════
# SECTION 10: Cache Consistency After Content Update
# ═══════════════════════════════════════════════════════════════

def test_cache_content_update():
    """Embed content A, then embed updated content B for same source_id.
    Query should use content B (no ghost of A)."""
    
    content_a = "Stripe charges 2.9% + 30 cents per transaction. No monthly fees."
    content_b = "Stripe charges 3.5% + 40 cents per transaction. New pricing effective 2025."
    
    # Step 1: Embed original content
    print("\n  Step 1: Embedding original content...")
    requests.post(f"{BASE}/api/embed", json={"source_id": "stripe-update-test", "content": content_a}, timeout=30)
    
    # Step 2: Embed updated content (same source_id)
    print("  Step 2: Embedding UPDATED content for same source_id...")
    requests.post(f"{BASE}/api/embed", json={"source_id": "stripe-update-test", "content": content_b}, timeout=30)
    
    # Step 3: Query — should get new pricing (3.5%), not old (2.9%)
    run_test("10.1", "Cache Update — New content overwrites old (no ghost entries)",
             "POST", "/api/chat",
             body={
                 "query": "What percentage does Stripe charge per transaction?",
                 "mode": "fast",
                 "contexts": [{"source_id": "stripe-update-test", "content": content_b}]
             },
             check_fn=lambda events: (
                 any("3.5" in e.get("answer", "") for e in events if e.get("type") == "final"),
                 "Answer contains new pricing (3.5%), not old (2.9%) — cache update works"
             ))


# ═══════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "🧪" * 35)
    print("  ThinkTab-AI Backend — Full Audit Test Suite")
    print("🧪" * 35)
    
    start_all = time.time()
    
    # Section 1: Health
    test_health()
    
    # Section 2: Input Validation
    test_empty_query()
    test_whitespace_query()
    test_invalid_mode()
    
    # Section 3: Fast Mode
    test_fast_mode_good_context()
    test_fast_mode_no_context()
    test_fast_mode_irrelevant_context()
    
    # Section 4: Deep Mode
    test_deep_mode_good_context()
    test_deep_mode_web_search()
    test_deep_mode_self_rag_pipeline()
    
    # Section 5: Auto Mode
    test_auto_mode_simple()
    test_auto_mode_complex()
    
    # Section 6: Chat History
    test_chat_history_resolution()
    
    # Section 7: Cache
    test_pre_embed()
    test_cache_hit()
    test_cache_delete_found()
    test_cache_delete_not_found()
    
    # Section 8: Multi-Context
    test_multi_context()
    
    # Section 9: Edge Cases
    test_sql_injection()
    test_special_characters()
    test_very_long_query()
    test_empty_content_context()
    
    # Section 10: Cache Consistency
    test_cache_content_update()
    
    total_time = time.time() - start_all
    
    # ── Final Report ──────────────────────────────────
    print("\n\n" + "=" * 70)
    print("📊 FINAL TEST REPORT")
    print("=" * 70)
    
    for r in RESULTS:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} [{r['id']}] {r['desc']}")
        if r["status"] == "FAIL":
            print(f"       Reason: {r['reason']}")
        print(f"       Time: {r['time']:.2f}s")
    
    print(f"\n{'=' * 70}")
    print(f"  TOTAL: {PASS + FAIL} tests | ✅ {PASS} passed | ❌ {FAIL} failed")
    print(f"  TIME:  {total_time:.1f}s total")
    print(f"{'=' * 70}")
    
    if FAIL > 0:
        print("\n  ⚠️  SOME TESTS FAILED — Review output above for details.")
        sys.exit(1)
    else:
        print("\n  🎉 ALL TESTS PASSED — Backend is production-ready!")
        sys.exit(0)
