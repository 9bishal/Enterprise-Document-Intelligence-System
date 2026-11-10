import math
import os
import threading
import time
from typing import Any, Optional

from redisvl.extensions.cache.llm import SemanticCache
from redisvl.utils.vectorize.base import BaseVectorizer

from .config import CACHE_SPECS, REDIS_URL, SEMANTIC_SIMILARITY_THRESHOLD, CacheType
from .metrics import CACHE_HITS, CACHE_LATENCY, CACHE_MISSES, CACHE_SET_TOTAL

EMBEDDING_MODEL_NAME = os.getenv("INTRADOC_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("INTRADOC_EMBEDDING_DIM", "384"))
LOCAL_CACHE_MAX_ENTRIES = int(os.getenv("INTRADOC_LOCAL_CACHE_ENTRIES", "200"))


class _SharedVectorizer(BaseVectorizer):
    """Valid redisvl vectorizer reusing the single embedding model from
    app.vector_store, so we never load a second copy in the same process
    (avoids OOM crashes). Satisfies redisvl>=0.23 BaseVectorizer contract."""

    model: str = EMBEDDING_MODEL_NAME
    dims: int = EMBEDDING_DIM

    def _embed(self, text: Any = "", content: Any = "", **kwargs) -> list[float]:
        from app.vector_store import embeddings_model as _shared_model
        return [float(x) for x in _shared_model.embed_query(content or text)]

    def _embed_many(self, texts: Any = None, contents: Any = None, **kwargs) -> list[list[float]]:
        from app.vector_store import embeddings_model as _shared_model
        items = list(contents or texts or [])
        return [[float(x) for x in e] for e in _shared_model.embed_documents(items)]


def _shared_vectorizer():
    return _SharedVectorizer(model=EMBEDDING_MODEL_NAME, dims=EMBEDDING_DIM)


def _build_backend():
    ttl = CACHE_SPECS[CacheType.SEMANTIC_RESPONSE].ttl_seconds or None
    distance_threshold = round(1 - SEMANTIC_SIMILARITY_THRESHOLD, 4)
    vectorizer = _shared_vectorizer()
    return SemanticCache(
        name="intradoc_semantic_cache",
        redis_url=REDIS_URL,
        vectorizer=vectorizer,
        distance_threshold=distance_threshold,
        ttl=ttl,
    )


class _LocalSemanticCache:
    """Small in-process fallback so caching still works when Redis/RediSearch
    is unavailable. It lives for the lifetime of the Gunicorn worker."""

    def __init__(self):
        self._entries: list[dict] = []
        self._lock = threading.Lock()
        self._ttl = CACHE_SPECS[CacheType.SEMANTIC_RESPONSE].ttl_seconds

    @staticmethod
    def _embed(text: str) -> list[float]:
        from app.vector_store import embeddings_model as _shared_model
        return [float(x) for x in _shared_model.embed_query(text)]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_a * norm_b)

    def lookup(self, query_text: str) -> Optional[dict]:
        vector = self._embed(query_text)
        now = time.time()
        with self._lock:
            if self._ttl:
                self._entries = [e for e in self._entries if now - e["ts"] <= self._ttl]
            best = None
            best_score = -1.0
            for entry in self._entries:
                score = self._cosine(vector, entry["vector"])
                if score > best_score:
                    best = entry
                    best_score = score
        if best is not None and best_score >= SEMANTIC_SIMILARITY_THRESHOLD:
            return {
                "response": best["response"],
                "similarity": best_score,
                "metadata": best["metadata"],
            }
        return None

    def store(self, query_text: str, response: str, doc_ids: Optional[list[str]] = None) -> None:
        entry = {
            "vector": self._embed(query_text),
            "response": response,
            "metadata": {"doc_ids": doc_ids or []},
            "ts": time.time(),
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > LOCAL_CACHE_MAX_ENTRIES:
                self._entries = self._entries[-LOCAL_CACHE_MAX_ENTRIES:]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class SemanticResponseCache:
    def __init__(self):
        self.cache_type = CacheType.SEMANTIC_RESPONSE
        self._local = _LocalSemanticCache()
        try:
            self._backend = _build_backend()
        except Exception as exc:
            self._backend = None
            print(f"Redis semantic cache unavailable; using in-process cache: {exc}")

    def lookup(self, query_text: str) -> Optional[dict]:
        start = time.perf_counter()
        if self._backend is not None:
            try:
                hits = self._backend.check(prompt=query_text)
                CACHE_LATENCY.labels(self.cache_type.value, "get").observe(time.perf_counter() - start)
                if hits:
                    CACHE_HITS.labels(self.cache_type.value).inc()
                    top = hits[0]
                    return {
                        "response": top.get("response"),
                        "similarity": 1 - float(top.get("vector_distance", 0.0)),
                        "metadata": top.get("metadata"),
                    }
            except Exception as exc:
                print(f"Redis semantic cache lookup failed; using in-process cache: {exc}")
        try:
            cached = self._local.lookup(query_text)
        except Exception as exc:
            print(f"In-process semantic cache lookup failed: {exc}")
            cached = None
        if cached is not None:
            CACHE_HITS.labels(self.cache_type.value).inc()
            return cached
        CACHE_MISSES.labels(self.cache_type.value).inc()
        return None

    def store(self, query_text: str, response: str, doc_ids: Optional[list[str]] = None) -> None:
        start = time.perf_counter()
        try:
            self._local.store(query_text, response, doc_ids=doc_ids)
        except Exception as exc:
            print(f"In-process semantic cache store failed: {exc}")
        if self._backend is not None:
            try:
                self._backend.store(
                    prompt=query_text,
                    response=response,
                    metadata={"doc_ids": doc_ids or []},
                )
                CACHE_SET_TOTAL.labels(self.cache_type.value).inc()
                CACHE_LATENCY.labels(self.cache_type.value, "set").observe(time.perf_counter() - start)
            except Exception as exc:
                print(f"Redis semantic cache store failed; kept in-process copy: {exc}")

    def invalidate_for_document(self, doc_id: str, reason: str = "document_updated") -> int:
        if self._backend is not None:
            try:
                self._backend.clear()
            except Exception:
                pass
        self._local.clear()
        return -1

    def flush_type(self, reason: str = "manual") -> int:
        if self._backend is not None:
            try:
                self._backend.clear()
            except Exception:
                pass
        self._local.clear()
        return -1
