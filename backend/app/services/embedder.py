from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
import os

# ─────────────────────────────────────────────────────────────
# Embedding Model: BAAI/bge-m3 (Local)
# ─────────────────────────────────────────────────────────────
# ✔ 100+ languages (English, Hindi, Arabic, Chinese...)
# ✔ 8192 token context window (16x larger than standard models)
# ✔ Dense + Sparse + Multi-vector retrieval (3 strategies in 1)
# ✔ ~2.2 GB, runs on CPU, no API key needed
# Model is cached inside the project at: ThinkTab-AI/models/
# ─────────────────────────────────────────────────────────────

# Resolve the project root (ThinkTab-AI/) and create models/ folder if needed
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
_model_cache  = os.path.join(_project_root, "models")
os.makedirs(_model_cache, exist_ok=True)

print(f"[Embedder] Loading BAAI/bge-m3 → cache: {_model_cache}")
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-m3",
    cache_folder=_model_cache,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)
print("[Embedder] BAAI/bge-m3 ready. ✅ Supports 100+ languages, 8192 token context.")

# ─────────────────────────────────────────────────────────────
# Text Splitter
# chunk_size=500  → each chunk is at most 500 characters
# chunk_overlap=50 → 50 characters overlap between chunks so
#                    we never cut a sentence in the middle
# ─────────────────────────────────────────────────────────────
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,  # Increased from 50 → catches boundary cases like split sentences
    # BUG FIX: removed "." from separators — period-splitting breaks decimal numbers
    # (8.52 → "8" + ".52"), abbreviations (B.Tech, Dr.), and URLs (github.com).
    # Falling back to " " (word boundary) instead is safer and keeps numbers intact.
    separators=["\n\n", "\n", " ", ""],
)


# ─────────────────────────────────────────────────────────────
# We no longer handle FAISS storage here.
# `embeddings` and `text_splitter` are exported for vector_store.py
# ─────────────────────────────────────────────────────────────
