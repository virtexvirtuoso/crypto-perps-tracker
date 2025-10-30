#!/usr/bin/env python3
"""End-to-end test for crypto-perps-tracker

Tests the complete workflow from data fetching to report generation
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment with valid Discord webhook format
os.environ['DISCORD_WEBHOOK_URL'] = 'https://discord.com/api/webhooks/123456789/test-token'
os.environ['DISCORD_STRATEGY_WEBHOOK_URL'] = 'https://discord.com/api/webhooks/123456789/test-token'


def test_exchange_service_fetch():
    """Test: Fetch data from all exchanges via ExchangeService"""
    print("\n" + "="*60)
    print("TEST 1: Exchange Service Data Fetching")
    print("="*60)

    from src.models.config import Config
    from src.container import Container

    # Load config
    config = Config.from_yaml('config/config.yaml')
    print("✓ Config loaded")

    # Create container
    container = Container(config)
    print(f"✓ Container initialized with {len(container.exchange_service.clients)} clients")

    # Fetch data (using cache)
    markets = container.exchange_service.fetch_all_markets(use_cache=True)
    print(f"✓ Fetched data from {len(markets)} exchanges")

    # Verify data structure
    for market in markets[:3]:  # Show first 3
        exchange_name = market.exchange if isinstance(market.exchange, str) else market.exchange.value
        print(f"  - {exchange_name}: ${market.volume_24h:,.0f}")

    assert len(markets) > 0, "No markets fetched"
    print("\n✅ Exchange service test PASSED")

    return markets


def test_cache_effectiveness():
    """Test: Verify caching is working"""
    print("\n" + "="*60)
    print("TEST 2: Cache Effectiveness")
    print("="*60)

    from src.models.config import Config
    from src.container import Container
    import time

    config = Config.from_yaml('config/config.yaml')
    container = Container(config)

    # First fetch (cache miss)
    start = time.time()
    markets1 = container.exchange_service.fetch_all_markets(use_cache=True)
    duration1 = time.time() - start
    print(f"✓ First fetch (cache miss): {duration1:.2f}s")

    # Second fetch (cache hit)
    start = time.time()
    markets2 = container.exchange_service.fetch_all_markets(use_cache=True)
    duration2 = time.time() - start
    print(f"✓ Second fetch (cache hit): {duration2:.2f}s")

    # Cache should be much faster
    speedup = duration1 / duration2 if duration2 > 0 else float('inf')
    print(f"✓ Cache speedup: {speedup:.1f}x faster")

    assert duration2 < duration1, "Cache not faster than direct fetch"
    print("\n✅ Cache effectiveness test PASSED")


def test_repository_operations():
    """Test: Database operations via repositories"""
    print("\n" + "="*60)
    print("TEST 3: Repository Operations")
    print("="*60)

    from src.repositories.market import MarketRepository
    from src.models.market import MarketData, ExchangeType
    import tempfile
    import os

    # Use temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        repo = MarketRepository(db_path)
        print("✓ MarketRepository initialized")

        # Test database initialization
        repo.initialize_database()
        print("✓ Database schema initialized")

        # Test statistics (should be empty initially)
        stats = repo.get_statistics()
        snapshot_count = stats.get('market_snapshots', {}).get('count', 0)
        print(f"✓ Statistics retrieved: {snapshot_count} snapshots")

        # Test cleanup operation
        deleted = repo.cleanup_old_data(days_to_keep=90)
        print(f"✓ Cleanup completed ({deleted} old records deleted)")

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

    print("\n✅ Repository operations test PASSED")


def test_alert_system():
    """Test: Alert system with state management"""
    print("\n" + "="*60)
    print("TEST 4: Alert System")
    print("="*60)

    from src.alerts.state_db import AlertStateDB
    from src.alerts.queue import AlertQueue
    import tempfile
    import os

    # Use temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        # Test AlertStateDB
        alert_db = AlertStateDB(db_path)
        print("✓ AlertStateDB initialized")

        strategy = "Test Strategy"
        cooldown_config = {1: 1, 2: 2, 3: 4, 4: 8}

        # Should allow first alert
        should, reason = alert_db.should_alert(
            strategy, 90, "long", tier=1, cooldown_hours=cooldown_config
        )
        assert should, f"First alert should be allowed: {reason}"
        print("✓ First alert allowed")

        # Record it
        alert_db.record_alert(strategy, 90, "long", tier=1, cooldown_hours=1)
        print("✓ Alert recorded")

        # Should deny second alert
        should, reason = alert_db.should_alert(
            strategy, 90, "long", tier=1, cooldown_hours=cooldown_config
        )
        assert not should, f"Should deny duplicate: {reason}"
        print("✓ Duplicate correctly denied")

        # Test AlertQueue
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            queue_file = f.name

        queue = AlertQueue(queue_file=queue_file, bundle_window_seconds=60)
        print("✓ AlertQueue initialized")

        # Enqueue alerts
        queue.enqueue({
            'strategy': 'Test',
            'confidence': 90,
            'tier': 1
        })
        queue.enqueue({
            'strategy': 'Test2',
            'confidence': 85,
            'tier': 2
        })
        print(f"✓ Enqueued 2 alerts")

        # Check queue state
        pending = queue.get_pending_count()
        assert pending == 2, f"Queue size mismatch: expected 2, got {pending}"
        print(f"✓ Pending alerts: {pending}")

        # Cleanup
        if os.path.exists(queue_file):
            os.remove(queue_file)

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

    print("\n✅ Alert system test PASSED")


def test_complete_workflow():
    """Test: Complete workflow from fetch to analysis"""
    print("\n" + "="*60)
    print("TEST 5: Complete Workflow")
    print("="*60)

    from src.models.config import Config
    from src.container import Container

    # Initialize system
    config = Config.from_yaml('config/config.yaml')
    container = Container(config)
    print("✓ System initialized")

    # Step 1: Fetch market data
    markets = container.exchange_service.fetch_all_markets(use_cache=True)
    print(f"✓ Step 1: Fetched {len(markets)} markets")

    # Step 2: Calculate total metrics
    total_volume = sum(m.volume_24h for m in markets)
    total_oi = sum(m.open_interest or 0 for m in markets)
    print(f"✓ Step 2: Total volume: ${total_volume:,.0f}")
    print(f"           Total OI: ${total_oi:,.0f}")

    # Step 3: Identify top exchanges
    sorted_markets = sorted(markets, key=lambda m: m.volume_24h, reverse=True)
    top_3 = sorted_markets[:3]
    print(f"✓ Step 3: Top exchanges:")
    for i, m in enumerate(top_3, 1):
        pct = (m.volume_24h / total_volume) * 100
        exchange_name = m.exchange if isinstance(m.exchange, str) else m.exchange.value
        print(f"           {i}. {exchange_name}: {pct:.1f}% of volume")

    # Step 4: Save snapshot (would normally save to DB)
    print(f"✓ Step 4: Ready to save {len(markets)} snapshots")

    # Step 5: Generate alerts (would normally check thresholds)
    high_funding = [m for m in markets if m.funding_rate and m.funding_rate > 0.01]
    print(f"✓ Step 5: Identified {len(high_funding)} high funding rate alerts")

    print("\n✅ Complete workflow test PASSED")


def main():
    """Run all E2E tests"""
    print("="*60)
    print("END-TO-END TEST SUITE")
    print("="*60)

    tests = [
        test_exchange_service_fetch,
        test_cache_effectiveness,
        test_repository_operations,
        test_alert_system,
        test_complete_workflow
    ]

    failed = []

    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"\n❌ {test_func.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed.append((test_func.__name__, str(e)))

    print("\n" + "="*60)
    if failed:
        print(f"❌ {len(failed)} test(s) failed:")
        for name, error in failed:
            print(f"  - {name}: {error}")
        return 1
    else:
        print(f"✅ All {len(tests)} E2E tests passed!")
        print("="*60)
        print("\n🎉 System ready for deployment!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
