from langchain_core.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch
from langchain_core.documents import Document

from app.graph.state import GraphState
from app.services.llm_service import fast_llm
from app.core.config import settings

# Initialize the Tavily Web Search Tool (new langchain_tavily package)
web_search_tool = TavilySearch(
    max_results=5,
    topic="general",
)

# System Prompt for the Web Query Rewriter
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
    
    Takes the user's conversational query and history, and distills it 
    into a powerful, keyword-heavy search string for the Tavily API.
    """
    original_query = state["query"]
    chat_history = state.get("chat_history", [])
    
    print(f"[Web Search] Rewriting query for search engine: '{original_query}'")
    
    # We only include the last 4 messages to keep the prompt laser-focused
    recent_history = chat_history[-4:]
    history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in recent_history])
    
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
    optimized_query = response.content.strip().strip('"').strip("'")
    
    print(f"[Web Search] Optimized Query: '{optimized_query}'")
    
    return {
        **state,
        "web_query": optimized_query
    }


def search_web(state: GraphState) -> GraphState:
    """
    Deep Mode Node: Tavily Web Search
    
    Executes a search against the live internet using the optimized string.
    Maps the returned JSON snippets into LangChain Document objects, tagging
    them identically to local webpage chunks so the generator can cite them.
    """
    search_query = state.get("web_query", state["query"])
    
    print(f"[Web Search] Searching Tavily for: '{search_query}'...")
    
    try:
        # returns [{ "url": "...", "content": "..." }, ...]
        tavily_results = web_search_tool.invoke({"query": search_query})
    except Exception as e:
        print(f"[Web Search] ERROR: Tavily search failed: {e}")
        tavily_results = []
        
    web_docs = []
    
    for item in tavily_results:
        content = item.get("content", "").strip()
        url = item.get("url", "web_tavily")
        
        if content:
            # We strictly tag the source_id as "web_tavily" and store the exact URL 
            # so the UI can later group these under the 🌐 icon
            doc = Document(
                page_content=content,
                metadata={"source": "web_tavily", "actual_url": url}
            )
            web_docs.append(doc)
            
    print(f"[Web Search] Recovered {len(web_docs)} web snippets.")
    for i, doc in enumerate(web_docs):
        print(f"  [Web {i+1}] {doc.page_content[:80]}...")
        
    return {
        **state,
        "web_docs": web_docs
    }
