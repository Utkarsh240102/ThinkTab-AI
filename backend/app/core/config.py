import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env from the root project directory (ThinkTab-AI/.env)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../../.env"))

class Settings(BaseSettings):
    # API Keys
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    LANGCHAIN_API_KEY: str = ""
    
    # Models
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    GROQ_MODEL: str = "meta-llama/llama-3.3-70b-versatile"
    
    # Cache & Thresholds
    MAX_CACHE_PAGES: int = 20
    UPPER_CRAG_THRESHOLD: float = 0.7
    LOWER_CRAG_THRESHOLD: float = 0.3

    class Config:
        env_file = "../../../.env"
        extra = "ignore"

settings = Settings()
