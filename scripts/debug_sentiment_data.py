#!/usr/bin/env python3
"""
Debug: Sentiment Data Structure
Shows actual data available for strategy detection
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container

print("\n" + "="*80)
print("DEBUG: Sentiment Data Structure")
print("="*80)

# Initialize container
config = Config(
    app_name="Sentiment Debug",
    exchanges={"enabled": ["binance", "bybit", "okx", "gateio", "bitget"]},
    cache={"ttl": 300},
    database={"path": "data/demo_market.db"},
    alert_database={"path": "data/demo_alerts.db"}
)

container = Container(config)

# Fetch market data
print("\n📊 Fetching Market Data...")
markets = container.exchange_service.fetch_all_markets(use_cache=True)
print(f"   Markets fetched: {len(markets)}")

# Get sentiment
print("\n🔍 Calculating Sentiment...")
sentiment = container.analysis_service.calculate_market_sentiment(markets)

print("\n📋 Available Sentiment Fields:")
print("-" * 80)
for key, value in sorted(sentiment.items()):
    if isinstance(value, (int, float)):
        print(f"   {key}: {value:.6f}")
    else:
        print(f"   {key}: {value}")

# Get arbitrage opportunities
print("\n💰 Funding Arbitrage Opportunities:")
print("-" * 80)
arb_opportunities = container.analysis_service.find_funding_arbitrage_opportunities(use_cache=True)
print(f"   Total opportunities: {len(arb_opportunities)}")

if arb_opportunities:
    print("\n   First opportunity structure:")
    print(json.dumps(arb_opportunities[0], indent=4, default=str))

    print("\n   All opportunities:")
    for i, opp in enumerate(arb_opportunities, 1):
        print(f"\n   [{i}] {opp.get('symbol', 'N/A')}")
        for key, value in sorted(opp.items()):
            if isinstance(value, (int, float)):
                print(f"       {key}: {value:.6f}")
            else:
                print(f"       {key}: {value}")

# Calculate total volume
total_volume = sum(m.volume_24h for m in markets if m.volume_24h)
print(f"\n💵 Total Market Volume: ${total_volume:,.0f}")

print("\n" + "="*80)
print("✅ DEBUG COMPLETE")
print("="*80)
print()
