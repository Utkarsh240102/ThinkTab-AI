from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# Embedding Model: Google Generative AI
# Free to use, high quality, works natively with LangChain
# ─────────────────────────────────────────────────────────────
embeddings = GoogleGenerativeAIEmbeddings(
    model=settings.EMBEDDING_MODEL,        # "models/gemini-embedding-001"
    google_api_key=settings.GOOGLE_API_KEY,
)

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
