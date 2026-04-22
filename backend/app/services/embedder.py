from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from app.core.config import settings
import os

# ─────────────────────────────────────────────────────────────
# Embedding Model: BAAI/bge-m3 (Local)
# ─────────────────────────────────────────────────────────────
# ✔ 100+ languages (English, Hindi, Arabic, Chinese...)
# ✔ 8192 token context window (16x larger than standard models)
# ✔ Dense + Sparse + Multi-vector retrieval (3 strategies in 1)
# ✔ #1 on MTEB Multilingual leaderboard
# ✔ ~2.2 GB, runs on CPU, no API key needed
# ✔ Cached in: ThinkTab-AI/models/
# ─────────────────────────────────────────────────────────────

# Resolve the project root (ThinkTab-AI/) and create models/ folder if needed
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
_model_cache  = os.path.join(_project_root, "models")
os.makedirs(_model_cache, exist_ok=True)

print(f"[Embedder] Loading BAAI/bge-m3 → cache: {_model_cache}")
print("[Embedder] First run will download ~2.2 GB. Subsequent runs load from cache instantly.")
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
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", " ", ""],  # Tries paragraph → sentence → word splits
)


def chunk_and_embed(content: str, source_id: str) -> FAISS:
    """
    Takes raw webpage/document text and converts it to a searchable FAISS index.

    Args:
        content:   The raw markdown/text content extracted from the webpage or PDF.
        source_id: The identifier for this source (e.g. URL or filename).
                   This is stored as metadata on each chunk so we can cite the source later.

    Returns:
        A FAISS vector store index ready for similarity search.
    """
    # Step 1: Split the raw text into chunks
    chunks = text_splitter.create_documents(
        texts=[content],
        metadatas=[{"source": source_id}]  # Tag every chunk with its source
    )

    # Step 2: Embed all chunks and store in FAISS
    faiss_index = FAISS.from_documents(chunks, embeddings)

    return faiss_index
