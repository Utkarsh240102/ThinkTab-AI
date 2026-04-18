import requests
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document

from app.graph.state import GraphState
from app.services.llm_service import fast_llm
from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# Serper Google Search — direct HTTP, no extra library required
# ─────────────────────────────────────────────────────────────
SERPER_ENDPOINT = "https://google.serper.dev/search"


def _search_serper(query: str, num_results: int = 5) -> list:
    """
    Call the Serper Google Search API and return a normalised list of
    {"url": str, "content": str} dicts ready for the RAG pipeline.

    Priority order of extracted snippets:
    1. answerBox  — direct fact from Google's featured snippet (highest quality)
    2. knowledgeGraph — structured entity description
    3. organic results — standard search-result snippets
    """
    api_key = settings.SERPER_API_KEY
    if not api_key:
        print("[Serper] ❌ SERPER_API_KEY is not set in .env — web search disabled.")
        return []

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num_results}

    try:
        resp = requests.post(SERPER_ENDPOINT, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Serper] ❌ Request failed: {e}")
        return []

    results: list = []

    # 1. Answer Box — Google's featured snippet / direct answer
    ab = data.get("answerBox", {})
    if ab:
        text = ab.get("snippet") or ab.get("answer") or ""
        if text:
            results.append({
                "url": ab.get("link", "google_answer_box"),
                "content": text
            })
            print(f"[Serper] ✅ Answer Box: {text[:100]}")

    # 2. Knowledge Graph — entity description  
    kg = data.get("knowledgeGraph", {})
    if kg.get("description"):
        results.append({
            "url": kg.get("descriptionLink", "google_knowledge_graph"),
            "content": kg["description"]
        })

    # 3. Organic search results — up to num_results snippets
    for item in data.get("organic", []):
        snippet = item.get("snippet", "").strip()
        url = item.get("link", "web_serper")
        if snippet:
            results.append({"url": url, "content": snippet})

    print(f"[Serper] Found {len(results)} total snippets")
    return results


# ─────────────────────────────────────────────────────────────
# System Prompt for the Web Query Rewriter
# ─────────────────────────────────────────────────────────────
REWRITE_SYSTEM_PROMPT = """You are a master SEO specialist.
Your job is to rewrite a conversational user question into a dense, keyword-rich search query optimized for an internet search engine like Google.

RULES:
1. Remove filler words (e.g., "what is", "can you tell me", "I wonder").
2. Focus strictly on the core entities, nouns, and verbs.
3. Use conversation history (if provided) to resolve any vague pronouns (it, they, that company) into explicit names.
4. Output ONLY the optimized search string. Do not include quotes, explanations, or preamble."""


def rewrite_for_web(state: GraphState) -> GraphState:
    """
    Deep Mode Node: Web Query Rewriter

    Takes the user's conversational query and history, and distils it
    into a powerful, keyword-heavy search string for the Serper API.
    """
    original_query = state["query"]
    chat_history = state.get("chat_history", [])

    print(f"[Web Search] Rewriting query for search engine: '{original_query}'")

    recent_history = chat_history[-4:]
    history_text = "\n".join([
        f"{msg['role'].capitalize()}: {msg['content']}"
        for msg in recent_history
    ])

    prompt = f"""Conversation history:
{history_text}

Latest user question to rewrite for search:
{original_query}

Optimized Search String:"""

    messages = [
        SystemMessage(content=REWRITE_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]

    response = fast_llm.invoke(messages)
    optimized_query = str(response.content).strip().strip('"').strip("'")

    print(f"[Web Search] Optimized Query: '{optimized_query}'")

    return {
        **state,
        "web_query": optimized_query
    }


def search_web(state: GraphState) -> GraphState:
    """
    Deep Mode Node: Serper (Google) Web Search

    Executes a Google search via the Serper API using the optimised query.
    Maps the returned snippets into LangChain Document objects, tagging
    them identically to local webpage chunks so the generator can cite them.
    """
    search_query = state.get("web_query", state["query"])

    print(f"[Web Search] Searching Serper (Google) for: '{search_query}'...")

    try:
        raw_results = _search_serper(search_query, num_results=5)
    except Exception as e:
        print(f"[Web Search] ERROR: Search failed: {e}")
        raw_results = []

    web_docs = []

    for item in raw_results:
        content = item.get("content", "").strip()
        url = item.get("url", "web_serper")

        if content:
            doc = Document(
                page_content=content,
                metadata={"source": "web_serper", "actual_url": url}
            )
            web_docs.append(doc)

    print(f"[Web Search] Recovered {len(web_docs)} web snippets.")
    for i, doc in enumerate(web_docs):
        print(f"  [Web {i+1}] ({doc.metadata['actual_url'][:60]}) {doc.page_content[:80]}...")

    return {
        **state,
        "web_docs": web_docs
    }
