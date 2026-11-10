import os
import re

from django.http import HttpResponse
from django.utils.cache import patch_vary_headers

DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]


def _allowed_origins() -> list[str]:
    """Read CORS origins from the environment, falling back to local dev ports."""
    configured = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return configured or DEFAULT_DEV_ORIGINS


def _origin_matches(origin: str, allowed_origins: list[str]) -> bool:
    if origin in allowed_origins:
        return True
    for pattern in allowed_origins:
        if "*" not in pattern:
            continue
        regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
        if re.match(regex, origin):
            return True
    return False


class CORSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Dynamically exempt all /api/ endpoints from CSRF enforcement for our decoupled frontend
        if request.path.startswith("/api/"):
            request._dont_enforce_csrf_checks = True

        if request.method == "OPTIONS":
            response = HttpResponse()
        else:
            response = self.get_response(request)

        origin = request.headers.get("Origin")
        if origin and _origin_matches(origin, _allowed_origins()):
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization, X-Requested-With"
            response["Access-Control-Max-Age"] = "86400"
            patch_vary_headers(response, ["Origin"])

        return response
