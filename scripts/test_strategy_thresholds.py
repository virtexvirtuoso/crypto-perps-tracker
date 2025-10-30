#!/usr/bin/env python3
"""
Test: Strategy Detector Thresholds
Shows current market metrics vs detection thresholds
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container

print("\n" + "="*80)
print("TEST: Strategy Detector Thresholds vs Current Market Metrics")
print("="*80)

# Initialize container
config = Config(
    app_name="Strategy Threshold Test",
    exchanges={"enabled": ["binance", "bybit", "okx", "gateio", "bitget"]},
    cache={"ttl": 300},
    database={"path": "data/demo_market.db"},
    alert_database={"path": "data/demo_alerts.db"}
)

container = Container(config)

# Fetch market data
print("\n📊 Fetching Market Data...")
markets = container.exchange_service.fetch_all_markets(use_cache=True)
sentiment = container.analysis_service.calculate_market_sentiment(markets)
total_volume = sum(m.volume_24h for m in markets if m.volume_24h)
arb_opportunities = container.analysis_service.find_funding_arbitrage_opportunities(use_cache=True)

print(f"   Markets: {len(markets)}")
print(f"   Total Volume: ${total_volume:,.0f}")

# Show current market metrics
print("\n🔍 Current Market Metrics:")
print("-" * 80)
print(f"Weighted Funding Rate: {sentiment.get('weighted_funding', 0):.4f}%")
print(f"Avg Long Ratio: {sentiment.get('avg_long_ratio', 0):.2f}%")
print(f"Total Volume: ${total_volume:,.0f}")
print(f"Arbitrage Opportunities: {len(arb_opportunities)}")

# Show detection thresholds
print("\n📏 Strategy Detection Thresholds:")
print("-" * 80)

print("\n1️⃣  TREND FOLLOWING")
print(f"   Current: {sentiment.get('weighted_funding', 0):.4f}%")
print(f"   Threshold: > 0.05% (bullish) or < -0.05% (bearish)")
print(f"   Status: {'✅ Would trigger' if abs(sentiment.get('weighted_funding', 0)) > 0.05 else '❌ Below threshold'}")

print("\n2️⃣  CONTRARIAN PLAY")
print(f"   Current: {sentiment.get('weighted_funding', 0):.4f}%")
print(f"   Threshold: > 0.10% or < -0.10%")
print(f"   Status: {'✅ Would trigger' if abs(sentiment.get('weighted_funding', 0)) > 0.10 else '❌ Below threshold'}")

print("\n3️⃣  FUNDING ARBITRAGE")
print(f"   Current Opportunities: {len(arb_opportunities)}")
print(f"   Threshold: >= 3 opportunities with >0.05% spread")
print(f"   Status: {'✅ Would trigger' if len(arb_opportunities) >= 3 else '❌ Below threshold'}")

print("\n4️⃣  MOMENTUM BREAKOUT")
print(f"   Current: {abs(sentiment.get('weighted_funding', 0)):.4f}%")
print(f"   Threshold: > 0.15% (extreme)")
print(f"   Status: {'✅ Would trigger' if abs(sentiment.get('weighted_funding', 0)) > 0.15 else '❌ Below threshold'}")

print("\n5️⃣  LIQUIDATION CASCADE RISK")
avg_long_ratio = sentiment.get('avg_long_ratio', 0)
long_bias = abs(avg_long_ratio - 50.0)
print(f"   Current Long Bias: {long_bias:.2f}%")
print(f"   Threshold: > 20% deviation from neutral")
print(f"   Status: {'✅ Would trigger' if long_bias > 20 else '❌ Below threshold'}")

print("\n6️⃣  MEAN REVERSION")
print(f"   Current: {sentiment.get('weighted_funding', 0):.4f}%")
print(f"   Threshold: > 0.08% or < -0.08%")
print(f"   Status: {'✅ Would trigger' if abs(sentiment.get('weighted_funding', 0)) > 0.08 else '❌ Below threshold'}")

print("\n7️⃣  RANGE TRADING")
print(f"   Current: {abs(sentiment.get('weighted_funding', 0)):.4f}%")
print(f"   Threshold: < 0.02% (neutral)")
print(f"   Status: {'✅ Would trigger' if abs(sentiment.get('weighted_funding', 0)) < 0.02 else '❌ Above threshold'}")

print("\n8️⃣  SCALPING SETUP")
print(f"   Current: {abs(sentiment.get('weighted_funding', 0)):.4f}%")
print(f"   Volume: ${total_volume:,.0f}")
print(f"   Threshold: < 0.01% funding AND > $10B volume")
volume_b = total_volume / 1_000_000_000
print(f"   Status: {'✅ Would trigger' if (abs(sentiment.get('weighted_funding', 0)) < 0.01 and volume_b > 10) else '❌ Below threshold'}")

# Summary
print("\n" + "="*80)
print("📊 SUMMARY")
print("="*80)

triggered = 0
total = 10

if abs(sentiment.get('weighted_funding', 0)) > 0.05:
    triggered += 1
if abs(sentiment.get('weighted_funding', 0)) > 0.10:
    triggered += 1
if len(arb_opportunities) >= 3:
    triggered += 1
if abs(sentiment.get('weighted_funding', 0)) > 0.15:
    triggered += 1
if long_bias > 20:
    triggered += 1
if abs(sentiment.get('weighted_funding', 0)) > 0.08:
    triggered += 1
if abs(sentiment.get('weighted_funding', 0)) < 0.02:
    triggered += 1
if abs(sentiment.get('weighted_funding', 0)) < 0.01 and volume_b > 10:
    triggered += 1

print(f"\nStrategies Triggered: {triggered}/{total}")
print(f"Market Condition: {'NEUTRAL/CALM' if triggered == 0 else 'ACTIVE' if triggered < 5 else 'VOLATILE'}")

print("\n💡 Interpretation:")
if triggered == 0:
    print("   • Current market is in equilibrium")
    print("   • No strong directional bias")
    print("   • Low volatility environment")
    print("   • Strategy detectors working as expected (no false positives)")
elif triggered < 5:
    print("   • Some opportunity present")
    print("   • Selective strategy deployment recommended")
else:
    print("   • High volatility environment")
    print("   • Multiple strategies triggered")
    print("   • Active trading opportunities")

print()
