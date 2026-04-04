from app.graph.nodes.retrieval import retrieve_and_rerank

state = {
    "query": "What are Stripe transaction fees?",
    "original_query": "What are Stripe transaction fees?",
    "contexts": [{
        "source_id": "stripe.com",
        "content": (
            "Stripe charges 2.9 percent plus 30 cents per successful transaction. "
            "For international cards, an additional 1.5 percent fee applies. "
            "Stripe also offers volume discounts for businesses processing over 1 million dollars monthly. "
            "Our customer support team is available 24/7. "
            "We also offer free pizza on Fridays at the office."
        )
    }],
    "mode": "fast", "selected_mode": "fast",
    "chat_history": [], "docs": None, "good_docs": None,
    "refined_context": None, "crag_verdict": None,
    "web_query": None, "web_docs": None, "draft_answer": None,
    "final_answer": None, "evidence": None, "confidence_score": None,
    "reasoning_summary": None, "is_supported": None, "is_useful": None,
    "revision_retries": 0, "retrieval_retries": 0
}

result = retrieve_and_rerank(state)
print(f"\nTotal chunks kept: {len(result['docs'])}")
for i, doc in enumerate(result["docs"]):
    print(f"[{i+1}] {doc.page_content}")
