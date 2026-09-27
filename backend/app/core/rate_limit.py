import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Callable

from backend.app.core.config import settings
from backend.app.core.errors import AppException
from fastapi import Request, status

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter for protecting abuse-sensitive endpoints.
    Provides practical rate limiting for single-instance / container deployments.
    For multi-replica distributed architectures, an external store (e.g. Redis) is recommended.
    """

    def __init__(self):
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
        self._last_cleanup = time.time()

    def _cleanup_expired(self, now: float, window_seconds: float = 300.0) -> None:
        """Periodically purges timestamps older than the maximum window."""
        if now - self._last_cleanup < 60.0:
            return
        self._last_cleanup = now
        cutoff = now - window_seconds
        stale_keys = []
        for key, timestamps in self._history.items():
            self._history[key] = [t for t in timestamps if t > cutoff]
            if not self._history[key]:
                stale_keys.append(key)
        for key in stale_keys:
            self._history.pop(key, None)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        """
        Evaluates whether a key has exceeded max_requests in window_seconds.
        Returns: (is_limited: bool, retry_after_seconds: int)
        """
        if not settings.ENABLE_RATE_LIMITING:
            return False, 0

        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            cutoff = now - window_seconds
            timestamps = [t for t in self._history[key] if t > cutoff]
            self._history[key] = timestamps

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                return True, retry_after

            self._history[key].append(now)
            return False, 0

    def reset(self) -> None:
        """Resets all recorded rate limit history (useful for test isolation)."""
        with self._lock:
            self._history.clear()


limiter = SlidingWindowRateLimiter()


def rate_limit(max_requests: int, window_seconds: float = 60.0, key_func: Callable[[Request], str] | None = None):
    """
    FastAPI dependency factory enforcing rate limits on endpoints.
    Defaults to client host IP as the tracking key.
    """

    async def dependency(request: Request):
        if not settings.ENABLE_RATE_LIMITING:
            return

        if key_func is not None:
            key = key_func(request)
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"
            endpoint = request.url.path
            key = f"{client_ip}:{endpoint}"

        limited, retry_after = limiter.is_rate_limited(key, max_requests, window_seconds)
        if limited:
            logger.warning(f"Rate limit exceeded for key '{key}'. Limit: {max_requests}/{window_seconds}s.")
            raise AppException(
                message=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                error_code="RATE_LIMIT_EXCEEDED",
                headers={"Retry-After": str(retry_after)},
                details={"retry_after": retry_after, "limit": max_requests, "window_seconds": window_seconds},
            )

    return dependency
