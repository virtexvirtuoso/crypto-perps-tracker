"""TTL (Time-To-Live) cache implementation for reducing API calls"""

import time
from typing import Any, Optional, Dict
from threading import Lock


class TTLCache:
    """Thread-safe TTL cache with automatic expiration

    This cache stores key-value pairs with a time-to-live (TTL).
    Expired entries are automatically removed on access.

    Usage:
        cache = TTLCache(default_ttl=300)  # 5 minutes
        cache.set('key', 'value')
        value = cache.get('key')  # Returns 'value' or None if expired
    """

    def __init__(self, default_ttl: int = 300):
        """Initialize TTL cache

        Args:
            default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired

        Args:
            key: Cache key

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            # Check if expired
            age = time.time() - self._timestamps[key]
            if age >= self.default_ttl:
                # Expired, remove from cache
                del self._cache[key]
                del self._timestamps[key]
                self._misses += 1
                return None

            # Cache hit
            self._hits += 1
            return self._cache[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL override

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override in seconds
        """
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()

            # TTL override not implemented in this simple version
            # Could be added by storing per-key TTLs

    def clear(self) -> None:
        """Clear all cached values"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._hits = 0
            self._misses = 0

    def size(self) -> int:
        """Get number of cached items

        Returns:
            Number of items in cache
        """
        with self._lock:
            return len(self._cache)

    def cleanup_expired(self) -> int:
        """Remove all expired entries

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, timestamp in self._timestamps.items()
                if current_time - timestamp >= self.default_ttl
            ]

            for key in expired_keys:
                del self._cache[key]
                del self._timestamps[key]

            return len(expired_keys)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate

        Returns:
            Hit rate as a float between 0 and 1, or 0 if no accesses
        """
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                'size': len(self._cache),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': self.hit_rate,
                'ttl': self.default_ttl,
            }

    def __repr__(self) -> str:
        """String representation of cache"""
        stats = self.stats()
        return (
            f"TTLCache(size={stats['size']}, ttl={stats['ttl']}s, "
            f"hits={stats['hits']}, misses={stats['misses']}, "
            f"hit_rate={stats['hit_rate']:.1%})"
        )
