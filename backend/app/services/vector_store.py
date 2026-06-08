import hashlib
import threading
from collections import OrderedDict
from typing import TypeVar, Generic, Callable, Optional

from langchain_community.vectorstores import FAISS
from app.services.embedder import chunk_and_embed
from app.core.config import settings

T = TypeVar("T")

class ThreadSafeLRUCache(Generic[T]):
    """
    A generic, data-agnostic thread-safe LRU cache.
    Handles memory management, eviction, and locking independently of business logic.
    """
    def __init__(self, max_size: int | None = None, on_evict: Optional[Callable[[str], None]] = None):
        self.cache: OrderedDict[str, T] = OrderedDict()
        self.max_size = max_size or settings.MAX_CACHE_PAGES
        self._lock = threading.RLock()
        self.on_evict = on_evict

    def get(self, key: str) -> T | None:
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        return None

    def set(self, key: str, value: T) -> None:
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                self.cache[key] = value
                return

            if len(self.cache) >= self.max_size:
                evicted_key, _ = self.cache.popitem(last=False)
                print(f"[Cache EVICT] Cache full ({self.max_size} items). Removed oldest entry {evicted_key[:8]}...")
                if self.on_evict:
                    self.on_evict(evicted_key)

            self.cache[key] = value

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    @property
    def size(self) -> int:
        with self._lock:
            return len(self.cache)


class VectorStoreFacade:
    """
    Facade handling business logic: content hashing, embedding, and caching FAISS indexes.
    """
    def __init__(self):
        # Pass a callback to clean up our reverse lookup map when the cache evicts an item
        self._cache = ThreadSafeLRUCache[FAISS](
            max_size=settings.MAX_CACHE_PAGES, 
            on_evict=self._handle_eviction
        )
        self._source_id_to_key: dict[str, str] = {}
        self._lock = threading.RLock()

    def _handle_eviction(self, evicted_key: str) -> None:
        with self._lock:
            self._source_id_to_key = {
                sid: k for sid, k in self._source_id_to_key.items() if k != evicted_key
            }

    def _make_key(self, content: str, source_id: str = "") -> str:
        combined = f"{source_id}::{content}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get_or_embed(self, content: str, source_id: str) -> FAISS:
        key = self._make_key(content, source_id)

        with self._lock:
            old_key = self._source_id_to_key.get(source_id)
            if old_key and old_key != key:
                self._cache.delete(old_key)
                print(f"[Cache UPDATE] Content changed for '{source_id}'. Evicted stale entry {old_key[:8]}...")

            cached = self._cache.get(key)
            if cached is not None:
                print(f"[Cache HIT] Reusing existing FAISS index for hash {key[:8]}...")
                self._source_id_to_key[source_id] = key
                return cached

        print(f"[Cache MISS] No cached index found for hash {key[:8]}...")
        
        # Embed OUTSIDE the lock
        print(f"[Cache SET] Embedding new content for source '{source_id}'...")
        faiss_index = chunk_and_embed(content, source_id)

        with self._lock:
            # Check again to avoid duplicate work if another thread just embedded it
            cached_again = self._cache.get(key)
            if cached_again is not None:
                return cached_again
                
            self._cache.set(key, faiss_index)
            self._source_id_to_key[source_id] = key

        return faiss_index

    def delete_by_source_id(self, source_id: str) -> bool:
        with self._lock:
            key = self._source_id_to_key.get(source_id)
            if key is None:
                print(f"[Cache DELETE] source_id '{source_id}' not found in cache.")
                return False

            deleted = self._cache.delete(key)
            del self._source_id_to_key[source_id]
            if deleted:
                print(f"[Cache DELETE] Evicted '{source_id}' (hash {key[:8]}...) from cache.")
            return deleted

    @property
    def size(self) -> int:
        return self._cache.size

# ─────────────────────────────────────────────────────────────
# Global singleton instance — import this everywhere in the app
# ─────────────────────────────────────────────────────────────
embedding_cache = VectorStoreFacade()
