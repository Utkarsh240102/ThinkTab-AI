import asyncio
import json
from app.graph.fast_mode import run_fast_mode
from app.graph.state import GraphState

async def test():
    state: GraphState = {
        "query": "What is the fee for international cards?",
        "original_query": "What is the fee for international cards?",
        "mode": "fast",
        "selected_mode": "fast",
        "chat_history": [
            {"role": "user", "content": "What are the standard pricing plans?"},
            {"role": "assistant", "content": "Stripe charges 2.9% + 30c per transaction."}
        ],
        "contexts": [
            {
                "source_id": "stripe.com",
                "content": "Stripe is a payment processor. The standard fee is 2.9% + 30c. For international cards, there is an additional 1% fee. Currency conversion adds another 1%."
            }
        ],
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

    try:
        print("Starting Fast Mode Pipeline Test...\n")
        async for event in run_fast_mode(state):
            print(f"SSE Event: {event.strip()}")
            if event.startswith("data:"):
                data = json.loads(event.replace("data: ", "", 1).strip())
                if data["type"] == "final":
                    print("\n--- FINAL ANSWER ---")
                    print(data["answer"])
                    print("\n--- EVIDENCE ---")
                    for ev in data.get("evidence", []):
                        print(f"[{ev['source']}] {ev['snippet']}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test())
