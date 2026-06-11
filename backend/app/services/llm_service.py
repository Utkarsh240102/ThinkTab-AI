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
# Smart Brain: llama-3.3-70b via Groq with Cascading Fallbacks
# Used for: final answer generation, draft writing,
#           answer revision, direct question answering
# ─────────────────────────────────────────────────────────────
_groq_keys = [k.strip() for k in settings.GROQ_API_KEYS.split(",") if k.strip()]
# Fallback to single key if GROQ_API_KEYS is not provided
_primary_groq_key = _groq_keys[0] if _groq_keys else settings.GROQ_API_KEY

_primary_llm = ChatGroq(
    model=settings.GROQ_MODEL,                 # "meta-llama/llama-3.3-70b-versatile"
    api_key=_primary_groq_key,
    temperature=0.2,                           # Slight creativity for fluent answers
    max_tokens=2048,                           # Enough for detailed structured answers
)

_fallbacks = []

# Backup Groq keys
if len(_groq_keys) > 1:
    for key in _groq_keys[1:]:
        _fallbacks.append(ChatGroq(
            model=settings.GROQ_MODEL,
            api_key=key,
            temperature=0.2,
            max_tokens=2048,
        ))

# Emergency OpenRouter fallback
_emergency_fallback = ChatOpenAI(
    model=settings.OPENROUTER_MODEL,
    openai_api_key=settings.OPENROUTER_API_KEY,
    openai_api_base="https://openrouter.ai/api/v1",
    temperature=0.2,
    max_tokens=2048,
)
_fallbacks.append(_emergency_fallback)

# Chain them together
smart_llm = _primary_llm.with_fallbacks(_fallbacks)
