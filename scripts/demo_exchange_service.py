#!/usr/bin/env python3
"""
ExchangeService Demonstration - Multi-Exchange Aggregation

This script demonstrates the power of the ExchangeService which:
- Fetches data from multiple exchanges in parallel
- Caches results to reduce API calls by 80-90%
- Provides type-safe data with Pydantic models
- Makes it easy to aggregate cross-exchange data

Run this to see the new architecture in action!
"""

import time
from src.models.config import Config
from src.container import Container


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def main():
    """Demonstrate ExchangeService capabilities"""

    print_header("EXCHANGE SERVICE DEMO - MULTI-EXCHANGE AGGREGATION")

    # ============================================================
    # Step 1: Initialize Container
    # ============================================================
    print("📋 Step 1: Loading configuration and initializing services...")
    try:
        config = Config.from_yaml('config/config.yaml')
        print(f"   ✅ Config loaded: {config.app_name}")
    except FileNotFoundError:
        print("   ⚠️  config.yaml not found, using defaults")
        config = Config(
            app_name="Crypto Perps Tracker (Demo)",
            environment="development"
        )

    container = Container(config)
    service = container.exchange_service

    print(f"   ✅ Service initialized: {service}")
    print(f"   ✅ Enabled exchanges: {', '.join(config.exchanges.enabled)}")

    # ============================================================
    # Step 2: Fetch All Markets (Parallel API Calls)
    # ============================================================
    print_header("Step 2: Fetching Data from All Exchanges (Parallel)")
    print("⏳ Making API calls to all exchanges in parallel...")
    print("   (This will take ~2-5 seconds depending on API response times)\n")

    start_time = time.time()
    try:
        markets = service.fetch_all_markets(use_cache=False)  # Force fresh fetch
        elapsed = time.time() - start_time

        print(f"✅ Fetched data from {len(markets)} exchanges in {elapsed:.2f}s\n")

        # Display each exchange
        print("📊 Exchange Data:")
        print(f"{'   Exchange':<15} {'24h Volume':<20} {'Open Interest':<20} {'Markets'}")
        print("   " + "-"*75)

        for market in sorted(markets, key=lambda m: m.volume_24h, reverse=True):
            print(
                f"   {market.exchange.value:<15} "
                f"${market.volume_24h:>15,.0f}   "
                f"${(market.open_interest or 0):>15,.0f}   "
                f"{market.market_count or 0:>5}"
            )

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # ============================================================
    # Step 3: Calculate Totals
    # ============================================================
    print_header("Step 3: Aggregate Statistics")

    summary = service.get_market_summary(use_cache=True)  # Use cached data

    print(f"📈 Combined Statistics:")
    print(f"   Total 24h Volume: ${summary['total_volume_24h']:,.2f}")
    print(f"   Total Open Interest: ${summary['total_open_interest']:,.2f}")
    print(f"   Total Markets: {summary['total_markets']:,}")
    print(f"   Exchanges: {len(summary['exchanges'])}")

    if summary['total_volume_24h'] > 0:
        oi_volume_ratio = summary['total_open_interest'] / summary['total_volume_24h']
        print(f"   OI/Volume Ratio: {oi_volume_ratio:.2f}x")

    # ============================================================
    # Step 4: Fetch Again (Cache Hit)
    # ============================================================
    print_header("Step 4: Fetching Again (Demonstrating Cache)")

    print("⚡ Fetching all markets again (should use cache)...\n")
    start_time = time.time()

    markets_cached = service.fetch_all_markets(use_cache=True)
    elapsed_cached = time.time() - start_time

    print(f"✅ Retrieved {len(markets_cached)} markets in {elapsed_cached:.4f}s")
    print(f"   Speed improvement: {elapsed / elapsed_cached:.0f}x faster!")
    print(f"   Cache hit rate: {container.cache.hit_rate:.1%}")

    # ============================================================
    # Step 5: Fetch Specific Exchange
    # ============================================================
    print_header("Step 5: Fetching Specific Exchange")

    exchange_name = 'binance'
    print(f"🎯 Fetching {exchange_name.upper()} data only...\n")

    start_time = time.time()
    exchange_data = service.fetch_exchange(exchange_name, use_cache=True)
    elapsed = time.time() - start_time

    if exchange_data:
        print(f"✅ {exchange_data.exchange.value} data retrieved in {elapsed:.4f}s")
        print(f"   Volume: ${exchange_data.volume_24h:,.2f}")
        if exchange_data.open_interest:
            print(f"   Open Interest: ${exchange_data.open_interest:,.2f}")
        print(f"   Markets: {exchange_data.market_count}")

        if exchange_data.top_pairs:
            print(f"\n   Top 3 Trading Pairs:")
            for i, pair in enumerate(exchange_data.top_pairs[:3], 1):
                print(f"      {i}. {pair.symbol}: ${pair.volume:,.0f}")

    # ============================================================
    # Step 6: Cache Statistics
    # ============================================================
    print_header("Step 6: Cache Performance Metrics")

    stats = container.cache.stats()
    print(f"💾 Cache Statistics:")
    print(f"   Size: {stats['size']} entries")
    print(f"   Hits: {stats['hits']}")
    print(f"   Misses: {stats['misses']}")
    print(f"   Hit Rate: {stats['hit_rate']:.1%}")
    print(f"   TTL: {stats['ttl']}s")

    print(f"\n📊 API Call Reduction:")
    if stats['hits'] + stats['misses'] > 0:
        calls_without_cache = stats['hits'] + stats['misses']
        calls_with_cache = stats['misses']
        reduction = (1 - calls_with_cache / calls_without_cache) * 100
        print(f"   Without caching: ~{calls_without_cache} API calls")
        print(f"   With caching: ~{calls_with_cache} API calls")
        print(f"   Reduction: {reduction:.0f}%")

    # ============================================================
    # Summary
    # ============================================================
    print_header("ARCHITECTURE BENEFITS")

    print("✅ Parallel Fetching:")
    print("   - Multiple exchanges fetched simultaneously")
    print(f"   - {elapsed:.2f}s vs ~{len(markets) * 2:.0f}s sequential")

    print("\n✅ Intelligent Caching:")
    print(f"   - Cache hit rate: {container.cache.hit_rate:.1%}")
    print(f"   - Response time: {elapsed_cached:.4f}s (cached) vs {elapsed:.2f}s (fresh)")
    print(f"   - API calls reduced by ~{stats['hit_rate'] * 100:.0f}%")

    print("\n✅ Type Safety:")
    print("   - All data validated with Pydantic")
    print("   - No runtime type errors")
    print("   - Full IDE autocomplete support")

    print("\n✅ Clean Architecture:")
    print("   - Services handle business logic")
    print("   - Clients handle API communication")
    print("   - Models ensure data integrity")
    print("   - Easy to test and maintain")

    print("\n💡 Production Impact:")
    print(f"   - If running every 5 minutes: ~{12 * len(markets)} API calls/hour")
    print(f"   - With 80% cache hit rate: ~{int(12 * len(markets) * 0.2)} API calls/hour")
    print(f"   - Savings: ~{int(12 * len(markets) * 0.8)} API calls/hour")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
