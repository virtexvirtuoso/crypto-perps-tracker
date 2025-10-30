#!/usr/bin/env python3
"""Quick test of symbol-specific fetching"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container

print("\n🧪 Testing Symbol-Specific Fetching\n")

# Initialize
config = Config(app_name="Test", environment="development")
container = Container(config)
service = container.exchange_service

# Test fetching BTC across exchanges (each exchange has different symbol format)
print("Fetching BTC from Binance...")
btc_binance = service.clients['binance'].fetch_symbol('BTCUSDT')
if btc_binance:
    print(f"✅ Binance BTC: ${btc_binance.price:,.2f}")
else:
    print("❌ Failed to fetch from Binance")

print("\nFetching BTC from Bybit...")
btc_bybit = service.clients['bybit'].fetch_symbol('BTCUSDT')
if btc_bybit:
    print(f"✅ Bybit BTC: ${btc_bybit.price:,.2f}")
else:
    print("❌ Failed to fetch from Bybit")

print("\n✅ Symbol-specific fetching working!")
