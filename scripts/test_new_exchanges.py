#!/usr/bin/env python3
"""Quick test of the 3 new exchange clients"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container

print("\n🧪 Testing New Exchange Clients (HyperLiquid, dYdX, Coinbase INTX)\n")

# Initialize
config = Config(app_name="Test", environment="development")
container = Container(config)
service = container.exchange_service

# Test HyperLiquid
print("1. Testing HyperLiquid...")
try:
    hl_btc = service.clients['hyperliquid'].fetch_symbol('BTC')
    if hl_btc:
        print(f"   ✅ HyperLiquid BTC: ${hl_btc.price:,.2f}")
        print(f"      Volume: ${hl_btc.volume_24h/1e6:,.1f}M")
        print(f"      Funding: {hl_btc.funding_rate:.4f}%")
    else:
        print("   ❌ Failed to fetch BTC from HyperLiquid")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test dYdX
print("\n2. Testing dYdX v4...")
try:
    dydx_btc = service.clients['dydx'].fetch_symbol('BTC-USD')
    if dydx_btc:
        print(f"   ✅ dYdX BTC-USD: ${dydx_btc.price:,.2f}")
        print(f"      Volume: ${dydx_btc.volume_24h/1e6:,.1f}M")
        print(f"      Funding: {dydx_btc.funding_rate:.4f}%")
    else:
        print("   ❌ Failed to fetch BTC-USD from dYdX")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test Coinbase INTX
print("\n3. Testing Coinbase INTX...")
try:
    cb_btc = service.clients['coinbase_intx'].fetch_symbol('BTC-PERP')
    if cb_btc:
        print(f"   ✅ Coinbase INTX BTC-PERP: ${cb_btc.price:,.2f}")
        print(f"      Volume: ${cb_btc.volume_24h/1e6:,.1f}M")
        print(f"      Funding: {cb_btc.funding_rate:.4f}%")
    else:
        print("   ❌ Failed to fetch BTC-PERP from Coinbase INTX")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n✅ All new exchange clients tested!\n")
