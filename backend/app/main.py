import os
from dotenv import load_dotenv

# Load .env FIRST before any other imports that might need API keys
# This ensures LangSmith tracing variables are set before LangChain initializes
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import router as api_router

app = FastAPI(title="ThinkTab AI Backend")

# Allow the Chrome Extension to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this would be restricted to chrome-extension:// IDs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "active_models": {
            "routing": settings.OPENROUTER_MODEL,
            "generation": settings.GROQ_MODEL,
            "embedding": settings.EMBEDDING_MODEL
        }
    }

# Register all /api routes (chat, embed, cache)
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    # Always run via uvicorn to ensure the Python path is set correctly.
    # This is equivalent to: uvicorn app.main:app --reload
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
