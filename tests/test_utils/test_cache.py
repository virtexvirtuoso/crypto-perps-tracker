"""Tests for TTL cache"""

import time
import pytest
from src.utils.cache import TTLCache


class TestTTLCache:
    """Test suite for TTL cache"""

    def test_cache_get_set(self, cache):
        """Test basic get/set operations"""
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'

    def test_cache_miss(self, cache):
        """Test cache miss returns None"""
        assert cache.get('nonexistent') is None

    def test_cache_expiration(self):
        """Test that cached values expire after TTL"""
        cache = TTLCache(default_ttl=1)  # 1 second TTL
        cache.set('key1', 'value1')

        # Value should exist immediately
        assert cache.get('key1') == 'value1'

        # Wait for expiration
        time.sleep(1.1)

        # Value should be expired
        assert cache.get('key1') is None

    def test_cache_clear(self, cache):
        """Test clearing cache"""
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        assert cache.size() == 2

        cache.clear()
        assert cache.size() == 0
        assert cache.get('key1') is None

    def test_cache_size(self, cache):
        """Test cache size tracking"""
        assert cache.size() == 0

        cache.set('key1', 'value1')
        assert cache.size() == 1

        cache.set('key2', 'value2')
        assert cache.size() == 2

        # Overwriting doesn't increase size
        cache.set('key1', 'new_value')
        assert cache.size() == 2

    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries"""
        cache = TTLCache(default_ttl=1)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        time.sleep(1.1)

        removed = cache.cleanup_expired()
        assert removed == 2
        assert cache.size() == 0

    def test_cache_hit_rate(self, cache):
        """Test hit rate calculation"""
        assert cache.hit_rate == 0.0

        cache.set('key1', 'value1')
        cache.get('key1')  # Hit
        assert cache.hit_rate == 1.0

        cache.get('nonexistent')  # Miss
        assert cache.hit_rate == 0.5

        cache.get('key1')  # Hit
        assert cache.hit_rate == 2/3

    def test_cache_stats(self, cache):
        """Test cache statistics"""
        cache.set('key1', 'value1')
        cache.get('key1')  # Hit
        cache.get('nonexistent')  # Miss

        stats = cache.stats()
        assert stats['size'] == 1
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5
        assert stats['ttl'] == 60

    def test_cache_repr(self, cache):
        """Test string representation"""
        cache.set('key1', 'value1')
        cache.get('key1')

        repr_str = repr(cache)
        assert 'TTLCache' in repr_str
        assert 'size=1' in repr_str
        assert 'ttl=60s' in repr_str

    def test_cache_thread_safety(self, cache):
        """Test that cache is thread-safe"""
        import threading

        def writer(key, value):
            for i in range(100):
                cache.set(f'{key}_{i}', value)

        def reader(key):
            for i in range(100):
                cache.get(f'{key}_{i}')

        threads = []
        for i in range(5):
            t1 = threading.Thread(target=writer, args=(f'thread{i}', f'value{i}'))
            t2 = threading.Thread(target=reader, args=(f'thread{i}',))
            threads.extend([t1, t2])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No assertions needed - just checking no exceptions occur
