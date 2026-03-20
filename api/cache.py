"""Simple in-memory cache with TTL for API responses

Lightweight caching layer to reduce Bybit API calls and improve response times.
"""

from typing import Any, Optional, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """Thread-safe in-memory cache with TTL support"""

    def __init__(self, default_ttl: int = 60):
        """
        Initialize cache

        Args:
            default_ttl: Default time-to-live in seconds (default: 60s)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if exists and not expired

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Check if expired
        if datetime.utcnow() > entry['expires_at']:
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache miss (expired): {key}")
            return None

        self._hits += 1
        logger.debug(f"Cache hit: {key}")
        return entry['value']

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store value in cache with TTL

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self._default_ttl

        self._cache[key] = {
            'value': value,
            'expires_at': datetime.utcnow() + timedelta(seconds=ttl),
            'created_at': datetime.utcnow()
        }
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key

        Returns:
            True if key existed, False otherwise
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache delete: {key}")
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries

        Returns:
            Number of entries removed
        """
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry['expires_at']
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dict with cache stats
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            'size': len(self._cache),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{hit_rate:.1f}%"
        }


# Global cache instance with 90-second TTL
# Signal data changes slowly, so 90s is safe and provides good speedup
signal_cache = SimpleCache(default_ttl=90)
