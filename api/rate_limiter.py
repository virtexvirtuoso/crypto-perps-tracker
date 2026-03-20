"""
Simple Rate Limiter for FastAPI

Provides in-memory rate limiting for sensitive endpoints.
Uses sliding window algorithm for accurate rate limiting.

Usage:
    from api.rate_limiter import RateLimiter, rate_limit

    # As dependency
    @router.post("/collect")
    async def trigger_collection(
        _: None = Depends(rate_limit(requests=5, window=60))
    ):
        ...

    # Or with limiter instance
    limiter = RateLimiter(requests=5, window=60)
    limiter.check("endpoint_key")  # Raises HTTPException if rate exceeded
"""

import time
from collections import defaultdict
from typing import Optional, Dict, List, Callable
from fastapi import HTTPException, Request, Depends
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    Tracks request timestamps per key (IP, endpoint, user, etc.)
    and enforces rate limits.
    """

    def __init__(
        self,
        requests: int = 10,
        window: int = 60,
        key_prefix: str = "",
    ):
        """
        Initialize rate limiter.

        Args:
            requests: Maximum requests allowed in the window
            window: Time window in seconds
            key_prefix: Prefix for all keys (e.g., endpoint name)
        """
        self.requests = requests
        self.window = window
        self.key_prefix = key_prefix

        # Storage: key -> list of timestamps
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        """
        Check if request is allowed and record it.

        Args:
            key: Unique identifier (IP, user ID, etc.)

        Returns:
            True if request is allowed

        Raises:
            HTTPException 429 if rate limit exceeded
        """
        full_key = f"{self.key_prefix}:{key}" if self.key_prefix else key
        now = time.time()
        window_start = now - self.window

        # Clean old requests
        self._requests[full_key] = [
            ts for ts in self._requests[full_key]
            if ts > window_start
        ]

        # Check limit
        if len(self._requests[full_key]) >= self.requests:
            retry_after = int(
                self._requests[full_key][0] + self.window - now
            )
            logger.warning(
                f"Rate limit exceeded for {full_key}: "
                f"{len(self._requests[full_key])}/{self.requests} requests"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too many requests",
                    "limit": self.requests,
                    "window_seconds": self.window,
                    "retry_after_seconds": max(1, retry_after),
                },
                headers={"Retry-After": str(max(1, retry_after))}
            )

        # Record request
        self._requests[full_key].append(now)
        return True

    def get_stats(self, key: str) -> Dict:
        """Get current rate limit stats for a key."""
        full_key = f"{self.key_prefix}:{key}" if self.key_prefix else key
        now = time.time()
        window_start = now - self.window

        # Clean old requests
        recent = [
            ts for ts in self._requests.get(full_key, [])
            if ts > window_start
        ]

        return {
            "key": full_key,
            "requests_used": len(recent),
            "requests_limit": self.requests,
            "requests_remaining": max(0, self.requests - len(recent)),
            "window_seconds": self.window,
        }


# Pre-configured limiters for different endpoint types

# Strict limiter for expensive operations (data collection)
collect_limiter = RateLimiter(
    requests=5,      # 5 requests
    window=300,      # per 5 minutes
    key_prefix="collect",
)

# Moderate limiter for control endpoints
control_limiter = RateLimiter(
    requests=10,     # 10 requests
    window=60,       # per minute
    key_prefix="control",
)

# Standard limiter for data endpoints
data_limiter = RateLimiter(
    requests=60,     # 60 requests
    window=60,       # per minute
    key_prefix="data",
)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header for proxied requests
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP in the chain
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


def rate_limit(
    requests: int = 10,
    window: int = 60,
    key_func: Optional[Callable[[Request], str]] = None,
) -> Callable:
    """
    Dependency factory for rate limiting endpoints.

    Args:
        requests: Maximum requests allowed in window
        window: Time window in seconds
        key_func: Optional function to extract key from request
                  (default: client IP)

    Usage:
        @router.post("/collect")
        async def trigger_collection(
            _: None = Depends(rate_limit(requests=5, window=300))
        ):
            ...
    """
    limiter = RateLimiter(requests=requests, window=window)

    async def dependency(request: Request):
        if key_func:
            key = key_func(request)
        else:
            key = get_client_ip(request)
        limiter.check(key)
        return None

    return dependency


# Convenience dependencies for common patterns

async def rate_limit_collect(request: Request):
    """Rate limit for collection endpoints (5 per 5 minutes)."""
    key = get_client_ip(request)
    collect_limiter.check(key)


async def rate_limit_control(request: Request):
    """Rate limit for control endpoints (10 per minute)."""
    key = get_client_ip(request)
    control_limiter.check(key)


async def rate_limit_data(request: Request):
    """Rate limit for data endpoints (60 per minute)."""
    key = get_client_ip(request)
    data_limiter.check(key)
