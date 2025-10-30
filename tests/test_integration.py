#!/usr/bin/env python3
"""Integration tests for refactored architecture"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_module_imports():
    """Test that all refactored modules import successfully"""
    print("Testing module imports...")

    # Core models
    from src.models.market import MarketData, ExchangeType
    print("✓ Market models")

    from src.models.config import Config
    print("✓ Config model")

    # Services
    from src.services.exchange import ExchangeService
    print("✓ Exchange service")

    # Repositories
    from src.repositories.market import MarketRepository
    from src.repositories.alert import AlertRepository
    print("✓ Repositories")

    # Clients
    from src.clients.binance import BinanceClient
    from src.clients.hyperliquid import HyperLiquidClient
    print("✓ Exchange clients")

    # Utilities
    from src.utils.cache import TTLCache
    print("✓ Cache utility")

    # Alert system (migrated modules)
    from src.alerts.state_db import AlertStateDB
    from src.alerts.queue import AlertQueue
    from src.alerts.kalman_filter import MetricsSmoothing
    print("✓ Alert system modules")

    print("\n✅ All module imports successful!\n")


def test_cache_functionality():
    """Test cache works correctly"""
    print("Testing cache functionality...")

    from src.utils.cache import TTLCache
    import time

    cache = TTLCache(default_ttl=2)

    # Test set/get
    cache.set('key1', 'value1')
    assert cache.get('key1') == 'value1', "Cache get failed"
    print("✓ Cache set/get works")

    # Test expiration
    time.sleep(3)
    assert cache.get('key1') is None, "Cache expiration failed"
    print("✓ Cache expiration works")

    # Test clear
    cache.set('key2', 'value2')
    cache.clear()
    assert cache.get('key2') is None, "Cache clear failed"
    print("✓ Cache clear works")

    print("\n✅ Cache tests passed!\n")


def test_exchange_client_interface():
    """Test exchange clients follow correct interface"""
    print("Testing exchange client interface...")

    from src.clients.binance import BinanceClient
    from src.clients.hyperliquid import HyperLiquidClient

    clients = [BinanceClient(), HyperLiquidClient()]

    for client in clients:
        # Check required properties exist
        assert hasattr(client, 'exchange_type'), f"{client.__class__.__name__} missing exchange_type"
        print(f"✓ {client.__class__.__name__} has exchange_type")

        # Check required methods exist
        assert hasattr(client, 'fetch_volume'), f"{client.__class__.__name__} missing fetch_volume"
        print(f"✓ {client.__class__.__name__} has fetch_volume")

    print("\n✅ Exchange client interface tests passed!\n")


def test_alert_state_db():
    """Test alert state database"""
    print("Testing alert state database...")

    from src.alerts.state_db import AlertStateDB
    import tempfile
    import os

    # Use temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = AlertStateDB(db_path)
        print("✓ AlertStateDB initialized")

        # Test should_alert method
        strategy = "Test Strategy"
        cooldown_config = {1: 1, 2: 2, 3: 4, 4: 8}  # Tier -> hours

        # First call should allow alert
        should, reason = db.should_alert(
            strategy,
            confidence=90,
            direction="long",
            tier=1,
            cooldown_hours=cooldown_config
        )
        assert should, f"First alert should be allowed, got: {reason}"
        print("✓ Initial alert allowed")

        # Record the alert
        db.record_alert(strategy, confidence=90, direction="long", tier=1, cooldown_hours=1)
        print("✓ Alert recorded")

        # Second call within cooldown should deny
        should, reason = db.should_alert(
            strategy,
            confidence=90,
            direction="long",
            tier=1,
            cooldown_hours=cooldown_config
        )
        assert not should, f"Alert within cooldown should be denied, got: {reason}"
        print("✓ Cooldown logic working")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)

    print("\n✅ Alert state DB tests passed!\n")


def test_pydantic_models():
    """Test Pydantic models work correctly"""
    print("Testing Pydantic models...")

    from src.models.market import MarketData, ExchangeType
    from pydantic import ValidationError

    # Test valid data
    market = MarketData(
        exchange=ExchangeType.BINANCE,
        volume_24h=1000000,
        open_interest=500000
    )
    assert market.exchange == ExchangeType.BINANCE
    print("✓ Valid market data creation works")

    # Test validation
    try:
        invalid = MarketData(
            exchange=ExchangeType.BINANCE,
            volume_24h=-1000  # Should fail (negative volume)
        )
        assert False, "Validation should have failed"
    except ValidationError:
        print("✓ Validation correctly rejects negative volume")

    print("\n✅ Pydantic model tests passed!\n")


def main():
    """Run all integration tests"""
    print("=" * 60)
    print("INTEGRATION TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        test_module_imports,
        test_cache_functionality,
        test_exchange_client_interface,
        test_alert_state_db,
        test_pydantic_models
    ]

    failed = []

    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"❌ {test_func.__name__} FAILED: {e}\n")
            failed.append((test_func.__name__, str(e)))

    print("=" * 60)
    if failed:
        print(f"❌ {len(failed)} test(s) failed:")
        for name, error in failed:
            print(f"  - {name}: {error}")
        return 1
    else:
        print(f"✅ All {len(tests)} integration tests passed!")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
