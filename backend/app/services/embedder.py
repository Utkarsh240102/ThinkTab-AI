from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# Embedding Model: Local HuggingFace sentence-transformers
# Runs 100% locally — no API key, no rate limits, no quota.
# all-MiniLM-L6-v2: 80MB, fast CPU inference, great quality
# ─────────────────────────────────────────────────────────────
print("[Embedder] Loading local embedding model (all-MiniLM-L6-v2)...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)
print("[Embedder] Local embedding model ready. ✅")

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
