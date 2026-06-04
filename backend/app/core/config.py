from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Keys
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    TAVILY_API_KEY: str = ""   # kept for backward compat; unused if Serper is active
    SERPER_API_KEY: str = ""
    LANGCHAIN_API_KEY: str = ""
    
    # Models
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # Cache & Thresholds
    MAX_CACHE_PAGES: int = 20
    UPPER_CRAG_THRESHOLD: float = 0.7
    LOWER_CRAG_THRESHOLD: float = 0.3

    # Self-RAG Retry Limits
    MAX_REVISION_RETRIES: int = 3    # Max times to revise a hallucinating answer (IsSUP)
    MAX_RETRIEVAL_RETRIES: int = 3   # Max times to rewrite + re-retrieve if answer is useless (IsUSE)

    # Fast Mode Retrieval Settings
    FAST_MODE_RETRIEVE_K: int = 10   # How many chunks FAISS fetches initially
    FAST_MODE_RERANK_TOP_K: int = 5  # How many chunks survive after re-ranking

    # Deep Mode Retrieval Settings
    DEEP_MODE_RETRIEVE_K: int = 15   # Fetch more chunks for deep analysis
    DEEP_MODE_RERANK_TOP_K: int = 8  # Keep more chunks to feed into CRAG batch evaluator

    class Config:
        # BUG-013 FIX: removed env_file = "../../../.env" — that path is CWD-relative
        # and breaks if uvicorn is started from any directory other than backend/.
        # main.py loads .env first (anchored to __file__) before this module is
        # imported, so pydantic_settings picks up all vars from os.environ automatically.
        extra = "ignore"

settings = Settings()
