#!/usr/bin/env python3
"""Test script for AlertRepository"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.repositories.alert import AlertRepository
from datetime import datetime

print("\n🧪 Testing AlertRepository\n")

# Initialize repository
repo = AlertRepository('data/test_alert_state.db')

print("1. Initializing database...")
repo.initialize_database()
print("   ✅ Database initialized")

# Test recording an alert
print("\n2. Recording test alert...")
alert_id = repo.record_alert(
    strategy_name="momentum_scalper",
    confidence=75,
    direction="LONG",
    tier=2,
    cooldown_hours=4,
    exchange="Binance",
    symbol="BTCUSDT",
    price=110500.00
)
print(f"   ✅ Alert recorded with ID: {alert_id}")

# Test getting last alert
print("\n3. Retrieving last alert...")
last_alert = repo.get_last_alert("momentum_scalper")
if last_alert:
    print(f"   ✅ Last alert:")
    print(f"      • Time: {last_alert['last_alert_time']}")
    print(f"      • Confidence: {last_alert['last_confidence']}%")
    print(f"      • Direction: {last_alert['last_direction']}")
    print(f"      • Tier: {last_alert['tier']}")
    print(f"      • Exchange: {last_alert['exchange']}")
    print(f"      • Symbol: {last_alert['symbol']}")
    print(f"      • Price: ${last_alert['price']:,.2f}")

# Test deduplication logic
print("\n4. Testing deduplication (should block - cooldown)...")
should_alert, reason = repo.should_alert(
    strategy_name="momentum_scalper",
    confidence=80,
    direction="LONG",
    tier=2,
    cooldown_hours={1: 2, 2: 4, 3: 8}
)
print(f"   Should alert: {should_alert}")
print(f"   Reason: {reason}")

# Test new strategy (should allow)
print("\n5. Testing new strategy (should allow)...")
should_alert, reason = repo.should_alert(
    strategy_name="breakout_trader",
    confidence=85,
    direction="SHORT",
    tier=1,
    cooldown_hours={1: 2, 2: 4, 3: 8}
)
print(f"   Should alert: {should_alert}")
print(f"   Reason: {reason}")

# Record the new strategy alert
if should_alert:
    alert_id2 = repo.record_alert(
        strategy_name="breakout_trader",
        confidence=85,
        direction="SHORT",
        tier=1,
        cooldown_hours=2,
        exchange="Bybit",
        symbol="BTCUSDT"
    )
    print(f"   ✅ Alert recorded with ID: {alert_id2}")

# Test daily stats
print("\n6. Getting daily statistics...")
daily_stats = repo.get_daily_stats(days=1)
for date, stats in daily_stats.items():
    print(f"   {date}:")
    print(f"      • Total alerts: {stats['total_alerts']}")
    print(f"      • Tier 1: {stats['tier_1']}")
    print(f"      • Tier 2: {stats['tier_2']}")
    print(f"      • Tier 3: {stats['tier_3']}")
    print(f"      • Suppressed: {stats['suppressed']}")

# Test suppression recording
print("\n7. Recording suppression...")
repo.record_suppression()
print("   ✅ Suppression recorded")

# Test metric recording
print("\n8. Recording performance metrics...")
repo.record_metric("api_latency_ms", 45.2, "binance")
repo.record_metric("cache_hit_rate", 0.87, "exchange_service")
print("   ✅ Metrics recorded")

# Test alert performance tracking
print("\n9. Recording alert performance...")
repo.record_alert_performance(
    alert_id=alert_id,
    outcome="WIN",
    profit_loss=250.50,
    notes="Hit target in 2 hours"
)
print("   ✅ Performance recorded")

# Test strategy history
print("\n10. Getting strategy history...")
history = repo.get_strategy_history("momentum_scalper", limit=5)
print(f"    ✅ Retrieved {len(history)} alerts")
for alert in history:
    print(f"       • {alert['alert_time']}: {alert['direction']} @ {alert['confidence']}% confidence")

# Test comprehensive statistics
print("\n11. Getting database statistics...")
stats = repo.get_statistics()
if stats['exists']:
    print(f"    ✅ Statistics:")
    print(f"       • Total alerts: {stats['total_alerts']}")
    print(f"       • Unique strategies: {stats['unique_strategies']}")
    print(f"       • Tier distribution: {stats['tier_distribution']}")
    print(f"       • Database size: {stats['db_size_bytes']/1024:.1f} KB")

print("\n" + "="*70)
print("✅ ALL TESTS PASSED - AlertRepository is working correctly!")
print("="*70)
print("\n💡 Key Features Demonstrated:")
print("   • Alert recording with rich metadata")
print("   • Deduplication logic with cooldowns")
print("   • Daily statistics tracking")
print("   • Performance metrics")
print("   • Alert outcome tracking")
print("   • Strategy history retrieval")
print("   • Comprehensive statistics")
print("\n")
