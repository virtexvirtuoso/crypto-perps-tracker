"""
Dashboard Caching Layer
Implements in-memory caching to reduce API calls and improve performance
"""

import time
from typing import Dict, Any, Optional, Callable
from threading import Lock
from functools import wraps

class SimpleCache:
    """Simple thread-safe in-memory cache with TTL"""

    def __init__(self, ttl_seconds: int = 30):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if time.time() - entry['timestamp'] < self.ttl:
                    return entry['value']
                else:
                    del self.cache[key]
            return None

    def set(self, key: str, value: Any):
        """Set value in cache with current timestamp"""
        with self._lock:
            self.cache[key] = {
                'value': value,
                'timestamp': time.time()
            }

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self.cache.clear()

# Global cache instance for dashboard
dashboard_cache = SimpleCache(ttl_seconds=30)  # 30 second cache

def cached(cache_key_func: Optional[Callable] = None, ttl_seconds: int = 30):
    """
    Decorator to cache function results

    Args:
        cache_key_func: Optional function to generate cache key from args
        ttl_seconds: Time to live in seconds
    """
    def decorator(func):
        cache = SimpleCache(ttl_seconds=ttl_seconds)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                key = cache_key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache  # Expose cache for manual clearing if needed
        return wrapper

    return decorator
