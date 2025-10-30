#!/usr/bin/env python3
"""
Demo: AlertService - Trading Strategy Detection

Demonstrates the AlertService capabilities:
- Strategy detection (trend following, contrarian, arbitrage)
- Alert filtering by tier and confidence
- Integration with AlertRepository for state management
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container

print("\n" + "="*80)
print("DEMO: AlertService - Trading Strategy Detection")
print("="*80)

# Initialize container
config = Config(
    app_name="Alert Service Demo",
    exchanges={"enabled": ["binance", "bybit", "okx", "gateio", "bitget"]},
    cache={"ttl": 300},
    database={"path": "data/demo_market.db"},
    alert_database={"path": "data/demo_alerts.db"}
)

container = Container(config)

# Initialize alert repository
print("\n1️⃣  Initializing Alert Repository...")
container.alert_repo.initialize_database()
print("   ✅ Repository initialized")

# Detect all trading strategies
print("\n2️⃣  Detecting Trading Strategies...")
print("   Fetching market data and analyzing conditions...")

alerts = container.alert_service.detect_all_strategies()

print(f"   ✅ Detected {len(alerts)} potential strategies")

if not alerts:
    print("\n   💡 No strategies detected with current market conditions")
    print("      Try adjusting thresholds or wait for more volatile markets")
else:
    print("\n3️⃣  All Detected Strategies:")
    print("-" * 80)

    for i, alert in enumerate(alerts, 1):
        print(f"\n   [{i}] {alert.strategy_name}")
        print(f"       Confidence: {alert.confidence}%")
        print(f"       Direction: {alert.direction}")
        print(f"       Tier: {alert.tier} ({'CRITICAL' if alert.tier == 1 else 'HIGH' if alert.tier == 2 else 'BACKGROUND'})")
        print(f"       Reasoning: {alert.reasoning}")
        print(f"       Timestamp: {alert.timestamp}")

    # Filter for critical and high priority alerts
    print("\n4️⃣  Filtered Alerts (Tier 1-2 Only):")
    print("-" * 80)

    filtered = container.alert_service.filter_by_tier(
        alerts,
        tiers=[1, 2],
        min_confidence=60
    )

    if not filtered:
        print("\n   No critical or high-priority alerts at this time")
    else:
        print(f"\n   Found {len(filtered)} actionable alerts:")

        for i, alert in enumerate(filtered, 1):
            # Check if we should send alert (deduplication)
            should_send, reason = container.alert_service.should_alert(
                strategy_name=alert.strategy_name,
                confidence=alert.confidence,
                direction=alert.direction,
                min_confidence_delta=20,
                max_alerts_per_day=3,
                max_alerts_per_hour=10
            )

            status = "✅ SEND" if should_send else "⏸️  SKIP"
            print(f"\n   [{i}] {status} - {alert.strategy_name}")
            print(f"       Confidence: {alert.confidence}% | Direction: {alert.direction}")
            print(f"       Tier: {alert.tier}")

            if should_send:
                print(f"       Action: Alert should be sent")
                # Record the alert
                alert_id = container.alert_service.record_alert(
                    strategy_name=alert.strategy_name,
                    confidence=alert.confidence,
                    direction=alert.direction
                )
                print(f"       Alert ID: {alert_id}")
            else:
                print(f"       Skip Reason: {reason}")
                # Record suppression
                container.alert_repo.record_suppression()

# Get alert statistics
print("\n5️⃣  Alert Statistics (Last 7 Days):")
print("-" * 80)

stats = container.alert_service.get_alert_statistics(days=7)

if not stats:
    print("\n   No alert history yet")
else:
    for date, day_stats in stats.items():
        print(f"\n   {date}:")
        print(f"       Total: {day_stats['total_alerts']}")
        print(f"       Tier 1: {day_stats['tier_1']}")
        print(f"       Tier 2: {day_stats['tier_2']}")
        print(f"       Tier 3: {day_stats['tier_3']}")
        print(f"       Suppressed: {day_stats['suppressed']}")

print("\n" + "="*80)
print("✅ DEMO COMPLETE")
print("="*80)

print("\n💡 Key Features Demonstrated:")
print("   • Strategy detection (trend following, contrarian, arbitrage)")
print("   • Alert filtering by tier and confidence")
print("   • Deduplication with cooldown periods")
print("   • Alert state management via repository")
print("   • Statistics and performance tracking")

print("\n📚 Next Steps:")
print("   • Add more strategy detectors (breakout, momentum, etc.)")
print("   • Integrate Discord notifications")
print("   • Add ML-based scoring (optional)")
print("   • Implement Kalman filtering (optional)")
print()
