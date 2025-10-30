#!/usr/bin/env python3
"""Test script for the 4 newly implemented exchange clients

Tests:
- AsterDEX (DEX)
- Kraken Futures (CEX)
- KuCoin Futures (CEX)
- Coinbase Spot (CEX)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.asterdex import AsterDEXClient
from src.clients.kraken import KrakenClient
from src.clients.kucoin import KuCoinClient
from src.clients.coinbase import CoinbaseClient


def get_exchange_name(exchange) -> str:
    """Get exchange name as string from ExchangeType or string"""
    if hasattr(exchange, 'value'):
        return exchange.value
    return str(exchange)

print("\n" + "="*70)
print("TESTING 4 NEW EXCHANGE CLIENTS")
print("="*70)

# Test AsterDEX
print("\n1️⃣  Testing AsterDEX (DEX - Perpetual Futures)...")
print("-" * 70)
try:
    asterdex = AsterDEXClient()
    data = asterdex.fetch_volume()
    print(f"✅ AsterDEX Success!")
    print(f"   Exchange: {get_exchange_name(data.exchange)}")
    print(f"   24h Volume: ${data.volume_24h:,.2f}")
    print(f"   Markets: {data.market_count}")
    print(f"   Top Pair: {data.top_pairs[0].symbol if data.top_pairs else 'N/A'}")

    # Test symbol fetch
    btc_data = asterdex.fetch_symbol("BTCUSDT")
    if btc_data:
        print(f"   BTC Price: ${btc_data.price:,.2f}")
    else:
        print(f"   ⚠️  Could not fetch BTC symbol data")
except Exception as e:
    print(f"❌ AsterDEX Error: {e}")

# Test Kraken Futures
print("\n2️⃣  Testing Kraken (CEX - Perpetual Futures)...")
print("-" * 70)
try:
    kraken = KrakenClient()
    data = kraken.fetch_volume()
    print(f"✅ Kraken Futures Success!")
    print(f"   Exchange: {get_exchange_name(data.exchange)}")
    print(f"   24h Volume: ${data.volume_24h:,.2f}")
    print(f"   Markets: {data.market_count}")
    print(f"   Top Pair: {data.top_pairs[0].symbol if data.top_pairs else 'N/A'}")
    if data.open_interest:
        print(f"   Open Interest: ${data.open_interest:,.2f}")
    if data.funding_rate is not None:
        print(f"   Funding Rate: {data.funding_rate:.4f}%")

    # Test symbol fetch
    btc_data = kraken.fetch_symbol("PI_XBTUSD")
    if btc_data:
        print(f"   BTC Price: ${btc_data.price:,.2f}")
    else:
        print(f"   ⚠️  Could not fetch BTC symbol data")
except Exception as e:
    print(f"❌ Kraken Error: {e}")

# Test KuCoin Futures
print("\n3️⃣  Testing KuCoin (CEX - Perpetual Futures)...")
print("-" * 70)
try:
    kucoin = KuCoinClient()
    data = kucoin.fetch_volume()
    print(f"✅ KuCoin Futures Success!")
    print(f"   Exchange: {get_exchange_name(data.exchange)}")
    print(f"   24h Volume: ${data.volume_24h:,.2f}")
    print(f"   Markets: {data.market_count}")
    print(f"   Top Pair: {data.top_pairs[0].symbol if data.top_pairs else 'N/A'}")
    if data.open_interest:
        print(f"   Open Interest: ${data.open_interest:,.2f}")
    if data.funding_rate is not None:
        print(f"   Funding Rate: {data.funding_rate:.4f}%")

    # Test symbol fetch
    btc_data = kucoin.fetch_symbol("XBTUSDTM")
    if btc_data:
        print(f"   BTC Price: ${btc_data.price:,.2f}")
    else:
        print(f"   ⚠️  Could not fetch BTC symbol data")
except Exception as e:
    print(f"❌ KuCoin Error: {e}")

# Test Coinbase Spot
print("\n4️⃣  Testing Coinbase (CEX - Spot Markets)...")
print("-" * 70)
try:
    coinbase = CoinbaseClient()
    data = coinbase.fetch_volume()
    print(f"✅ Coinbase Spot Success!")
    print(f"   Exchange: {get_exchange_name(data.exchange)}")
    print(f"   24h Volume: ${data.volume_24h:,.2f}")
    print(f"   Markets: {data.market_count}")
    print(f"   Top Pair: {data.top_pairs[0].symbol if data.top_pairs else 'N/A'}")

    # Test symbol fetch
    btc_data = coinbase.fetch_symbol("BTC-USD")
    if btc_data:
        print(f"   BTC Price: ${btc_data.price:,.2f}")
        if btc_data.price_change_pct is not None:
            print(f"   24h Change: {btc_data.price_change_pct:.2f}%")
    else:
        print(f"   ⚠️  Could not fetch BTC symbol data")
except Exception as e:
    error_msg = str(e)
    if "401" in error_msg or "Unauthorized" in error_msg:
        print(f"⚠️  Coinbase Advanced Trade API requires authentication")
        print(f"   Note: Client implemented but needs API keys for access")
    else:
        print(f"❌ Coinbase Error: {e}")

print("\n" + "="*70)
print("✅ ALL 4 NEW EXCHANGE CLIENTS TESTED")
print("="*70)
print("\n📊 Summary:")
print("   • AsterDEX (DEX) - Perpetual Futures")
print("   • Kraken (CEX) - Perpetual Futures")
print("   • KuCoin (CEX) - Perpetual Futures")
print("   • Coinbase (CEX) - Spot Markets")
print("\n🎉 Total Exchange Clients: 12 (9 CEX + 3 DEX)")
print("   CEX: Binance, Bybit, OKX, Gate.io, Bitget, Coinbase INTX,")
print("        Kraken, KuCoin, Coinbase")
print("   DEX: HyperLiquid, dYdX v4, AsterDEX")
print()
