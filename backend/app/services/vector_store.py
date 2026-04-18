import hashlib
from collections import OrderedDict
from langchain_community.vectorstores import FAISS
from app.services.embedder import chunk_and_embed
from app.core.config import settings


class LRUEmbeddingCache:
    """
    An LRU (Least Recently Used) cache for FAISS vector indexes.

    How it works:
    - Stores up to `max_size` FAISS indexes in memory (default: 20).
    - Uses the SHA-256 hash of the page content as the unique cache key.
    - When the cache is full, it silently deletes the index that was
      least recently accessed to make room for the new one.
    - If the same page content is seen again, we skip re-embedding and
      instantly return the stored FAISS index.
    """

    def __init__(self, max_size: int | None = None):
        # OrderedDict remembers insertion/access order — perfect for LRU!
        self.cache: OrderedDict[str, FAISS] = OrderedDict()
        self.max_size = max_size or settings.MAX_CACHE_PAGES  # Default: 20
        # Reverse lookup: source_id → content hash key
        # Needed so we can evict by source_id (the cache key is a content hash,
        # not the source_id, so we need this map to find the right entry to delete)
        self.source_id_to_key: dict[str, str] = {}

    def _make_key(self, content: str) -> str:
        """
        Generate a unique SHA-256 fingerprint for any given text.
        Same content → same key. Any change in content → different key.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, content: str) -> FAISS | None:
        """
        Check if this content has already been embedded and cached.

        Returns the FAISS index if found (cache HIT), or None if not (cache MISS).
        On a HIT, we move the entry to the END of the OrderedDict so it is
        treated as the "most recently used" (preventing it from being evicted soon).
        """
        key = self._make_key(content)

        if key in self.cache:
            # Move to end = mark as recently used
            self.cache.move_to_end(key)
            print(f"[Cache HIT] Reusing existing FAISS index for hash {key[:8]}...")
            return self.cache[key]

        print(f"[Cache MISS] No cached index found for hash {key[:8]}...")
        return None

    def set(self, content: str, source_id: str) -> FAISS:
        """
        Embed the content, store it in the cache, and return the FAISS index.

        If the cache is already full (max_size reached), it evicts the LEAST
        recently used entry (the one at the START of the OrderedDict) first.
        """
        key = self._make_key(content)

        # If already cached, just return it (shouldn't normally happen if
        # you call get() first, but this is a safe guard)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]

        # Evict the oldest entry if we are at capacity
        if len(self.cache) >= self.max_size:
            evicted_key, _ = self.cache.popitem(last=False)  # Remove from START (oldest)
            print(f"[Cache EVICT] Cache full ({self.max_size} pages). Removed oldest entry {evicted_key[:8]}...")
            # Also clean up the reverse lookup so it doesn't grow unbounded
            self.source_id_to_key = {
                sid: k for sid, k in self.source_id_to_key.items() if k != evicted_key
            }

        # Embed the new content and store it
        print(f"[Cache SET] Embedding new content for source '{source_id}'...")
        faiss_index = chunk_and_embed(content, source_id)
        self.cache[key] = faiss_index
        self.source_id_to_key[source_id] = key  # Register in reverse lookup

        return faiss_index

    def get_or_embed(self, content: str, source_id: str) -> FAISS:
        """
        The main public method used by the rest of the app.

        1. Check the cache first (instant).
        2. If not found, embed the content and cache it.

        Usage:
            faiss_index = embedding_cache.get_or_embed(page_text, "stripe.com")
            results = faiss_index.similarity_search(query, k=10)
        """
        cached = self.get(content)
        if cached is not None:
            return cached

        return self.set(content, source_id)

    def delete_by_source_id(self, source_id: str) -> bool:
        """
        Evict a specific source from the cache by its source_id.

        Returns True if the entry was found and evicted, False if not found.

        This is called by DELETE /api/cache/{source_id} so the Chrome Extension
        can force-refresh a page when its content has changed.
        """
        key = self.source_id_to_key.get(source_id)
        if key is None:
            print(f"[Cache DELETE] source_id '{source_id}' not found in cache.")
            return False

        if key in self.cache:
            del self.cache[key]
        del self.source_id_to_key[source_id]
        print(f"[Cache DELETE] Evicted '{source_id}' (hash {key[:8]}...) from cache.")
        return True

    @property
    def size(self) -> int:
        """Returns how many entries are currently in the cache."""
        return len(self.cache)


# ─────────────────────────────────────────────────────────────
# Global singleton instance — import this everywhere in the app
# ─────────────────────────────────────────────────────────────
embedding_cache = LRUEmbeddingCache()
