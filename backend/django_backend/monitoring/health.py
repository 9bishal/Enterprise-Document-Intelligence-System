from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def health_live(request):
    return JsonResponse({"status": "ok"})

@require_GET
def health_ready(request):
    deps = {"redis": False, "chromadb": False, "database": False}
    try:
        from django_backend.cache.base import get_redis
        r = get_redis()
        r.ping()
        deps["redis"] = True
    except Exception:
        pass
    try:
        import chromadb
        client = chromadb.HttpClient(host="localhost", port=8001)
        client.heartbeat()
        deps["chromadb"] = True
    except Exception:
        # Fallback: backend uses PersistentClient (file-based), not HttpClient
        # If PersistentClient path exists, consider chromadb healthy for degraded check
        try:
            import os
            chroma_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "chroma")
            if os.path.exists(chroma_path):
                deps["chromadb"] = True
        except Exception:
            pass
    try:
        from django.db import connection
        connection.ensure_connection()
        deps["database"] = True
    except Exception:
        pass
    all_ok = all(deps.values())
    status_code = 200 if all_ok else 503
    return JsonResponse({"status": "ok" if all_ok else "degraded", "dependencies": deps}, status=status_code)

@require_GET
def cache_stats(request):
    try:
        from ..cache.config import CacheType
        from ..cache.manager import CacheManager
        from ..cache.metrics import CACHE_HITS, CACHE_MISSES, CACHE_SET_TOTAL

        cm = CacheManager()
        stats = cm.stats()

        per_cache = {}
        total_hits = 0
        total_misses = 0
        total_sets = 0
        for cache_type in CacheType:
            label = cache_type.value
            hits = int(CACHE_HITS.labels(label)._value.get())
            misses = int(CACHE_MISSES.labels(label)._value.get())
            sets = int(CACHE_SET_TOTAL.labels(label)._value.get())
            lookups = hits + misses
            per_cache[label] = {
                "hits": hits,
                "misses": misses,
                "sets": sets,
                "hit_rate": round(hits / lookups, 4) if lookups else 0.0,
            }
            total_hits += hits
            total_misses += misses
            total_sets += sets

        lookups = total_hits + total_misses
        stats["per_cache"] = per_cache
        stats["totals"] = {
            "hits": total_hits,
            "misses": total_misses,
            "sets": total_sets,
            "hit_rate": round(total_hits / lookups, 4) if lookups else 0.0,
        }
        return JsonResponse(stats)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
