import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.api.errors import problem_from_request

_SKIP_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


def _client_host(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, requests_per_minute: int) -> None:
        super().__init__(app)
        self._rpm = max(1, requests_per_minute)
        self._window_seconds = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _is_allowed(self, client: str) -> bool:
        now = time.monotonic()
        bucket = self._hits[client]
        while bucket and now - bucket[0] > self._window_seconds:
            bucket.popleft()
        if len(bucket) >= self._rpm:
            return False
        bucket.append(now)
        return True

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return await call_next(request)

        client = _client_host(request)
        if not self._is_allowed(client):
            return problem_from_request(
                request,
                status=429,
                title="Too Many Requests",
                detail=f"Rate limit exceeded ({self._rpm} requests per minute).",
                type_uri="https://wiktionary-to-mdx/errors/rate-limit",
            )
        return await call_next(request)
