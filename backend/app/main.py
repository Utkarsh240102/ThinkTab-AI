import os
from dotenv import load_dotenv

# Load .env FIRST before any other imports that might need API keys
# This ensures LangSmith tracing variables are set before LangChain initializes
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.api.endpoints import router as api_router  # noqa: E402
import traceback  # noqa: E402
import re  # noqa: E402

app = FastAPI(title="ThinkTab AI Backend")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[Global Error Handler] {traceback.format_exc()}")
    _raw = str(exc)
    _safe = re.sub(r'(sk-|key-|Bearer )[a-zA-Z0-9\-_\.]+', '[REDACTED]', _raw)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred.", "error": _safe}
    )

# Allow the Chrome Extension to talk to this server
app.add_middleware(
    CORSMiddleware,
    # In production, this would be restricted to chrome-extension:// IDs
    allow_origin_regex=r"^(chrome-extension://.*|http://localhost:\d+|http://127\.0\.0\.1:\d+)$",
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
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
