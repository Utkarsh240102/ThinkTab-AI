from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# Fast Brain: gpt-4o-mini via OpenRouter
# Used for: routing, CRAG scoring, sentence filtering,
#           Self-RAG grounding checks, intent classification
# ─────────────────────────────────────────────────────────────
fast_llm = ChatOpenAI(
    model=settings.OPENROUTER_MODEL,           # "openai/gpt-4o-mini"
    openai_api_key=settings.OPENROUTER_API_KEY,
    openai_api_base="https://openrouter.ai/api/v1",
    temperature=0,                             # Deterministic for logic tasks
    max_tokens=512,                            # Keep routing calls short and cheap
)

# ─────────────────────────────────────────────────────────────
# Smart Brain: llama-3.3-70b via Groq
# Used for: final answer generation, draft writing,
#           answer revision, direct question answering
# ─────────────────────────────────────────────────────────────
smart_llm = ChatGroq(
    model=settings.GROQ_MODEL,                 # "meta-llama/llama-3.3-70b-versatile"
    api_key=settings.GROQ_API_KEY,
    temperature=0.2,                           # Slight creativity for fluent answers
    max_tokens=2048,                           # Enough for detailed structured answers
)
