#!/usr/bin/env python3
"""Comprehensive test of all 12 exchange clients through the Container

Tests the full integration of all exchange clients with the DI container
and ExchangeService to ensure everything works end-to-end.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container

print("\n" + "="*80)
print("TESTING ALL 12 EXCHANGE CLIENTS VIA CONTAINER")
print("="*80)

# Initialize container with default config
print("\n📦 Initializing Container...")
config = Config(
    app_name="Exchange Test",
    exchanges={
        "enabled": [
            "binance", "bybit", "okx", "gateio", "bitget",
            "coinbase_intx", "kraken", "kucoin", "coinbase",
            "hyperliquid", "dydx", "asterdex"
        ],
        "timeout": 15,
        "retry_attempts": 2
    },
    cache={"ttl": 300},
    database={"path": "data/test.db"},
    alert_database={"path": "data/test_alerts.db"}
)

container = Container(config)
print(f"✅ Container initialized with {len(config.exchanges.enabled)} exchanges")

# Fetch market data from all exchanges
print("\n🌐 Fetching market data from all exchanges...")
print("-" * 80)

try:
    markets = container.exchange_service.fetch_all_markets(use_cache=False)

    # Group by exchange
    exchange_data = {}
    for market in markets:
        exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)
        if exchange_name not in exchange_data:
            exchange_data[exchange_name] = market

    # Display results
    print(f"\n✅ Successfully fetched data from {len(exchange_data)} exchanges\n")

    total_volume = 0
    total_oi = 0
    cex_count = 0
    dex_count = 0

    # Sort by volume
    sorted_exchanges = sorted(
        exchange_data.items(),
        key=lambda x: x[1].volume_24h,
        reverse=True
    )

    print(f"{'#':<4}{'Exchange':<20}{'Type':<6}{'24h Volume':<18}{'Markets':<10}{'OI':<18}{'Funding'}")
    print("-" * 80)

    for i, (name, market) in enumerate(sorted_exchanges, 1):
        # Determine type
        dex_exchanges = ['HyperLiquid', 'dYdX v4', 'AsterDEX']
        exchange_type = 'DEX' if name in dex_exchanges else 'CEX'

        if exchange_type == 'CEX':
            cex_count += 1
        else:
            dex_count += 1

        # Format volume
        vol_str = f"${market.volume_24h/1e9:>6.2f}B" if market.volume_24h else "N/A"

        # Format OI
        if market.open_interest and market.open_interest > 0:
            oi_str = f"${market.open_interest/1e9:>6.2f}B"
            total_oi += market.open_interest
        else:
            oi_str = "N/A"

        # Format funding
        funding_str = f"{market.funding_rate:>6.4f}%" if market.funding_rate is not None else "N/A"

        # Track total volume
        if market.volume_24h:
            total_volume += market.volume_24h

        print(
            f"{i:<4}"
            f"{name:<20}"
            f"{exchange_type:<6}"
            f"{vol_str:<18}"
            f"{market.market_count:<10}"
            f"{oi_str:<18}"
            f"{funding_str}"
        )

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\n📊 Exchange Coverage:")
    print(f"   Total Exchanges: {len(exchange_data)}")
    print(f"   CEX: {cex_count}")
    print(f"   DEX: {dex_count}")

    print(f"\n💰 Market Metrics:")
    print(f"   Total 24h Volume: ${total_volume:,.0f} (${total_volume/1e9:.2f}B)")
    print(f"   Total Open Interest: ${total_oi:,.0f} (${total_oi/1e9:.2f}B)")

    if total_volume > 0:
        print(f"   CEX vs DEX Split:")
        cex_vol = sum(m.volume_24h for n, m in exchange_data.items() if n not in dex_exchanges)
        dex_vol = sum(m.volume_24h for n, m in exchange_data.items() if n in dex_exchanges)
        print(f"     CEX: ${cex_vol/1e9:.2f}B ({cex_vol/total_volume*100:.1f}%)")
        print(f"     DEX: ${dex_vol/1e9:.2f}B ({dex_vol/total_volume*100:.1f}%)")

    print(f"\n🎯 Service Performance:")
    print(f"   Successfully integrated with ExchangeService")

    # List any missing exchanges
    enabled = set(config.exchanges.enabled)
    fetched = set(e.lower().replace(' ', '_').replace('.', '') for e in exchange_data.keys())

    # Normalize exchange names for comparison
    enabled_normalized = set()
    for e in enabled:
        if e == 'coinbase_intx':
            enabled_normalized.add('coinbaseintx')
        elif e == 'gateio':
            enabled_normalized.add('gateio')
        elif e == 'dydx':
            enabled_normalized.add('dydxv4')
        else:
            enabled_normalized.add(e)

    fetched_normalized = set()
    for e in fetched:
        if 'coinbase' in e and 'intx' in e:
            fetched_normalized.add('coinbaseintx')
        elif 'dydx' in e:
            fetched_normalized.add('dydxv4')
        else:
            fetched_normalized.add(e.replace('_', '').replace('.', ''))

    missing = enabled_normalized - fetched_normalized

    if missing:
        print(f"\n⚠️  Note: Some exchanges may require authentication or had errors:")
        for ex in missing:
            if ex == 'coinbase':
                print(f"   • Coinbase: Requires API keys (Advanced Trade API)")
            else:
                print(f"   • {ex}: Check logs for details")

except Exception as e:
    print(f"\n❌ Error fetching market data: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("🎉 INTEGRATION TEST COMPLETE")
print("="*80)
print()
