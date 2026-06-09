import os
import threading
from langchain_chroma import Chroma
import chromadb
from app.services.embedder import text_splitter, embeddings
from app.core.config import settings
from langchain_core.documents import Document

class VectorStoreFacade:
    """
    Facade handling business logic: persistent embedding storage via ChromaDB.
    """
    def __init__(self):
        # Initialize Persistent Chroma Client
        chroma_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../chroma_data"))
        os.makedirs(chroma_dir, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self.collection_name = "thinktab_contexts"
        
        # Initialize LangChain Chroma wrapper
        self.vector_store = Chroma(
            client=self.client,
            collection_name=self.collection_name,
            embedding_function=embeddings
        )
        
        self._lock = threading.Lock()

    def ensure_embedded(self, content: str, source_id: str) -> None:
        """
        Embeds the content into ChromaDB if it doesn't already exist for the given source_id.
        """
        with self._lock:
            # Check if this source_id is already embedded
            existing = self.vector_store.get(where={"source": source_id}, limit=1)
            if existing and existing.get("ids") and len(existing["ids"]) > 0:
                print(f"[ChromaDB] Source '{source_id}' is already embedded. Skipping.")
                return

            print(f"[ChromaDB] Embedding new content for source '{source_id}'...")
            # Step 1: Split the raw text into chunks
            chunks = text_splitter.create_documents(
                texts=[content],
                metadatas=[{"source": source_id}]  # Tag every chunk with its source
            )

            # Step 2: Add chunks to ChromaDB
            if chunks:
                self.vector_store.add_documents(chunks)
                print(f"[ChromaDB] Embedded {len(chunks)} chunks for '{source_id}'.")
            else:
                print(f"[ChromaDB] No chunks produced for '{source_id}'.")

    def search(self, query: str, source_id: str, k: int = 5) -> list[Document]:
        """
        Searches ChromaDB for the top k documents matching the query, filtered by source_id.
        """
        print(f"[ChromaDB] Searching top {k} chunks for source: {source_id}")
        return self.vector_store.similarity_search(
            query,
            k=k,
            filter={"source": source_id}
        )

    def delete_by_source_id(self, source_id: str) -> bool:
        """
        Deletes all chunks associated with a source_id.
        """
        with self._lock:
            existing = self.vector_store.get(where={"source": source_id})
            if existing and existing.get("ids") and len(existing["ids"]) > 0:
                self.vector_store.delete(ids=existing["ids"])
                print(f"[ChromaDB] Deleted source '{source_id}'.")
                return True
            return False

# ─────────────────────────────────────────────────────────────
# Global singleton instance — import this everywhere in the app
# ─────────────────────────────────────────────────────────────
embedding_cache = VectorStoreFacade()
