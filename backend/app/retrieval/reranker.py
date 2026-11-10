import os
from functools import lru_cache

RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(RERANKER_MODEL_NAME)

_rerank_cache_enabled = False
_rerank_cache = None

def _init_rerank_cache():
    global _rerank_cache_enabled, _rerank_cache
    if _rerank_cache_enabled:
        return
    try:
        from django_backend.cache.domain_caches import RerankingCache
        from django_backend.cache.base import make_hash
        _rerank_cache = RerankingCache()
        _rerank_cache.make_hash = make_hash
        _rerank_cache_enabled = True
    except Exception:
        _rerank_cache_enabled = False

def _rerank_cache_key(query: str, candidates: list[dict]) -> str:
    chunk_ids = sorted(c.get("id", "") for c in candidates)
    return _rerank_cache.make_hash(query, chunk_ids) if _rerank_cache else ""

def rerank(query: str, candidates: list[dict], top_k: int = 4) -> list[dict]:
    if not candidates:
        return []
    if os.getenv("INTRADOC_RERANK", "1").lower() in ("0", "false", "no"):
        return candidates[:top_k]
    _init_rerank_cache()
    if _rerank_cache_enabled:
        key = _rerank_cache_key(query, candidates)
        cached = _rerank_cache.get(key)
        if cached is not None:
            if isinstance(cached, dict) and "ranked" in cached:
                return cached["ranked"][:top_k]
            return cached[:top_k]
    pairs = [(query, c["text"]) for c in candidates]
    try:
        scores = _model().predict(pairs)
        for chunk, score in zip(candidates, scores):
            chunk["rerank_score"] = round(float(score), 4)
        ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
        if _rerank_cache_enabled:
            key = _rerank_cache_key(query, candidates)
            doc_ids = sorted(set(c.get("doc_id", "") for c in candidates))
            _rerank_cache.set(key, {"ranked": ranked}, doc_ids=doc_ids)
        return ranked[:top_k]
    except Exception as e:
        print(f"Reranker error: {e}")
        return candidates[:top_k]
