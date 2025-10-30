#!/usr/bin/env python3
"""
Historical Market Data Logger (Refactored)

Stores hourly snapshots to SQLite for trend analysis, backtesting, and ML features.
Refactored to use the new service architecture and repository pattern.

Key improvements:
- Uses ExchangeService for parallel data fetching
- Uses MarketRepository for clean database operations
- Automatic caching (80-90% API call reduction)
- Type-safe models
- Clean separation of concerns

Usage:
    python3 scripts/data_logger_new.py                    # Log current snapshot
    python3 scripts/data_logger_new.py --init             # Initialize database
    python3 scripts/data_logger_new.py --stats            # Show database statistics
    python3 scripts/data_logger_new.py --cleanup DAYS     # Cleanup old data

Add to crontab for automation:
    0 * * * * cd ~/crypto-perps-tracker && python3 scripts/data_logger_new.py >> logs/data_logger.log 2>&1
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import datetime, timezone
from typing import Dict, List

from src.models.config import Config
from src.container import Container
from src.repositories.market import MarketRepository


def fetch_all_markets(container: Container) -> List[Dict]:
    """Fetch market data from all exchanges using ExchangeService

    Returns results in format compatible with sentiment analysis:
    [{
        'exchange': 'Binance',
        'status': 'success',
        'volume': 12345678.90,
        'open_interest': 98765432.10,
        'funding_rate': 0.0001,
        'markets': 150,
        'price_change_pct': None,
        'type': 'CEX',
        'oi_volume_ratio': 0.45
    }, ...]
    """
    results = []

    markets = container.exchange_service.fetch_all_markets(use_cache=True)

    for market in markets:
        exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)

        dex_exchanges = ['HyperLiquid', 'dYdX v4', 'AsterDEX']
        exchange_type = 'DEX' if exchange_name in dex_exchanges else 'CEX'

        oi_vol_ratio = (
            market.open_interest / market.volume_24h
            if market.open_interest is not None and market.volume_24h > 0
            else 0
        )

        results.append({
            'exchange': exchange_name,
            'status': 'success',
            'volume': market.volume_24h,
            'open_interest': market.open_interest,
            'funding_rate': market.funding_rate,
            'markets': market.market_count,
            'price_change_pct': None,
            'type': exchange_type,
            'oi_volume_ratio': oi_vol_ratio
        })

    return results


def analyze_market_sentiment(results: List[Dict]) -> Dict:
    """Simplified sentiment analysis for logging

    Note: This is a subset of the full analysis from generate_market_report_new.py
    Includes only the core factors needed for database logging.
    """
    successful = [r for r in results if r.get('status') == 'success']
    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

    # FACTOR 1: Funding Rate
    weighted_funding = 0
    funding_rates = []

    for r in successful:
        if r.get('funding_rate') is not None:
            weight = r['volume'] / total_volume
            weighted_funding += r['funding_rate'] * weight
            funding_rates.append(r['funding_rate'])

    if weighted_funding > 0.01:
        funding_score = min(weighted_funding / 0.05, 1.0)
        funding_signal = "🟢 BULLISH"
    elif weighted_funding < -0.01:
        funding_score = max(weighted_funding / 0.05, -1.0)
        funding_signal = "🔴 BEARISH"
    else:
        funding_score = weighted_funding / 0.01
        funding_signal = "⚪ NEUTRAL"

    # FACTOR 2: Price Momentum
    weighted_price_change = 0
    price_changes = []

    for r in successful:
        if r.get('price_change_pct') is not None:
            weight = r['volume'] / total_volume
            weighted_price_change += r['price_change_pct'] * weight
            price_changes.append(r['price_change_pct'])

    if weighted_price_change > 2.0:
        price_score = min(weighted_price_change / 10.0, 1.0)
    elif weighted_price_change < -2.0:
        price_score = max(weighted_price_change / 10.0, -1.0)
    else:
        price_score = weighted_price_change / 2.0

    # FACTOR 3: OI/Volume Ratio
    market_oi_vol_ratio = total_oi / total_volume if total_volume > 0 else 0

    if market_oi_vol_ratio > 0.5:
        conviction_score = min((market_oi_vol_ratio - 0.3) / 0.3, 1.0)
    elif market_oi_vol_ratio < 0.25:
        conviction_score = -min((0.25 - market_oi_vol_ratio) / 0.15, 1.0)
    else:
        conviction_score = 0

    # FACTOR 4: Funding Divergence
    if len(funding_rates) > 1:
        funding_std = (sum((x - weighted_funding) ** 2 for x in funding_rates) / len(funding_rates)) ** 0.5
        divergence_score = -min(funding_std / 0.01, 1.0)
    else:
        divergence_score = 0
        funding_std = 0

    # FACTOR 5: OI-Price Correlation
    if weighted_price_change > 0 and market_oi_vol_ratio > 0.35:
        oi_price_score = 0.5
    elif weighted_price_change < 0 and market_oi_vol_ratio > 0.35:
        oi_price_score = -0.5
    else:
        oi_price_score = 0

    # FACTOR 6: Long/Short Bias (from OKX)
    try:
        import requests
        response = requests.get(
            "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
            params={"ccy": "BTC"},
            timeout=5
        ).json()

        if response.get('code') == '0' and response.get('data'):
            latest = response['data'][0]
            ratio = float(latest[1])
            long_pct = ratio / (ratio + 1)

            if ratio > 2.5:
                ls_score = max(-1.0, -0.5 - (ratio - 2.5) * 0.2)
            elif ratio > 1.5:
                ls_score = -0.3 - (ratio - 1.5) * 0.2
            elif ratio < 0.4:
                ls_score = min(1.0, 0.5 + (0.4 - ratio) * 2.0)
            elif ratio < 0.67:
                ls_score = 0.3 + (0.67 - ratio) * 0.74
            else:
                ls_score = (1.0 - ratio) * 0.2
        else:
            ls_score = 0
            long_pct = None
    except Exception:
        ls_score = 0
        long_pct = None

    # COMPOSITE SCORE
    composite_score = (
        funding_score * 0.35 +
        price_score * 0.20 +
        ls_score * 0.15 +
        conviction_score * 0.15 +
        divergence_score * 0.08 +
        oi_price_score * 0.07
    )

    if composite_score > 0.3:
        sentiment = "🟢 BULLISH"
    elif composite_score < -0.3:
        sentiment = "🔴 BEARISH"
    else:
        sentiment = "⚪ NEUTRAL"

    abs_score = abs(composite_score)
    if abs_score > 0.7:
        strength = "STRONG"
    elif abs_score > 0.5:
        strength = "MODERATE"
    elif abs_score > 0.3:
        strength = "WEAK"
    else:
        strength = "NEUTRAL"

    return {
        'weighted_funding': weighted_funding,
        'sentiment': sentiment,
        'avg_price_change': weighted_price_change,
        'composite_score': composite_score,
        'strength': strength,
        'factors': {
            'funding': {'score': funding_score},
            'price_momentum': {'score': price_score},
            'long_short_bias': {'score': ls_score, 'long_pct': long_pct},
            'conviction': {'score': conviction_score},
            'divergence': {'score': divergence_score, 'value': funding_std},
            'oi_price_correlation': {'score': oi_price_score}
        }
    }


def log_market_snapshot(container: Container, repository: MarketRepository) -> bool:
    """Fetch current market data and log to database

    Args:
        container: Dependency injection container
        repository: Market data repository

    Returns:
        True if successful, False otherwise
    """
    timestamp = int(datetime.now(timezone.utc).timestamp())

    print(f"\n📊 Logging market snapshot at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    try:
        # Fetch data from all exchanges
        print("⏳ Fetching data from 8 exchanges using ExchangeService...")
        results = fetch_all_markets(container)

        # Analyze sentiment
        print("🧮 Analyzing market sentiment...")
        sentiment = analyze_market_sentiment(results)

        # Calculate totals
        successful = [r for r in results if r.get('status') == 'success']
        total_volume = sum(r['volume'] for r in successful)
        total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

        # CEX vs DEX
        cex_volume = sum(r['volume'] for r in successful if r.get('type') == 'CEX')
        dex_volume = sum(r['volume'] for r in successful if r.get('type') == 'DEX')

        # Save market snapshot
        repository.save_market_snapshot(
            timestamp=timestamp,
            composite_score=sentiment['composite_score'],
            funding_rate=sentiment['weighted_funding'],
            total_volume=total_volume,
            total_oi=total_oi if total_oi > 0 else None,
            price_change=sentiment['avg_price_change'],
            long_pct=sentiment['factors']['long_short_bias'].get('long_pct'),
            sentiment=sentiment['sentiment'],
            strength=sentiment['strength'],
            oi_vol_ratio=total_oi / total_volume if total_volume > 0 and total_oi > 0 else None,
            funding_divergence=sentiment['factors']['divergence']['value'],
            exchanges_count=len(successful),
            cex_volume=cex_volume,
            dex_volume=dex_volume
        )

        # Save exchange snapshots
        for r in successful:
            repository.save_exchange_snapshot(
                timestamp=timestamp,
                exchange=r['exchange'],
                exchange_type=r.get('type'),
                volume=r['volume'],
                open_interest=r.get('open_interest'),
                funding_rate=r.get('funding_rate'),
                price_change=r.get('price_change_pct'),
                markets=r.get('markets'),
                num_trades=r.get('num_trades')
            )

        # Save sentiment factors
        factors = sentiment['factors']
        repository.save_sentiment_factors(
            timestamp=timestamp,
            funding_score=factors['funding']['score'],
            price_score=factors['price_momentum']['score'],
            ls_bias_score=factors['long_short_bias']['score'],
            conviction_score=factors['conviction']['score'],
            divergence_score=factors['divergence']['score'],
            oi_price_score=factors['oi_price_correlation']['score']
        )

        print(f"✅ Snapshot logged successfully")
        print(f"   • Exchanges: {len(successful)}")
        print(f"   • Total Volume: ${total_volume/1e9:.2f}B")
        print(f"   • Total OI: ${total_oi/1e9:.2f}B" if total_oi > 0 else "   • Total OI: N/A")
        print(f"   • Composite Score: {sentiment['composite_score']:.3f}")
        print(f"   • Sentiment: {sentiment['sentiment']}")

        return True

    except Exception as e:
        print(f"❌ Error logging snapshot: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_database_stats(repository: MarketRepository):
    """Display database statistics"""
    stats = repository.get_statistics()

    if not stats.get('exists'):
        print(f"❌ Database not found at: {repository.db_path}")
        print("   Run with --init to initialize")
        return

    print("\n" + "="*80)
    print("📊 MARKET HISTORY DATABASE STATISTICS")
    print("="*80)

    # Market snapshots
    ms_stats = stats['market_snapshots']
    count = ms_stats['count']

    if count > 0:
        first_snapshot = datetime.fromtimestamp(ms_stats['first_timestamp'], tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        last_snapshot = datetime.fromtimestamp(ms_stats['last_timestamp'], tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        hours = (ms_stats['last_timestamp'] - ms_stats['first_timestamp']) / 3600

        print(f"\n📈 Market Snapshots:")
        print(f"   • Total Records: {count:,}")
        print(f"   • First Snapshot: {first_snapshot}")
        print(f"   • Last Snapshot: {last_snapshot}")
        print(f"   • Time Span: {hours:.1f} hours ({hours/24:.1f} days)")

        # Average metrics
        avgs = stats['averages']
        print(f"\n📊 Average Metrics:")
        print(f"   • Composite Score: {avgs['composite_score']:.3f}")
        print(f"   • Volume: ${avgs['volume']/1e9:.2f}B")
        if avgs['open_interest']:
            print(f"   • Open Interest: ${avgs['open_interest']/1e9:.2f}B")
        if avgs['oi_vol_ratio']:
            print(f"   • OI/Vol Ratio: {avgs['oi_vol_ratio']:.2f}x")

        # Sentiment distribution
        print(f"\n💭 Sentiment Distribution:")
        sent_dist = stats['sentiment_distribution']
        total_sent = sum(sent_dist.values())
        for sentiment, count in sent_dist.items():
            pct = (count / total_sent) * 100
            print(f"   • {sentiment}: {count} ({pct:.1f}%)")
    else:
        print("\n⚠️  No market snapshots recorded yet")

    # Exchange snapshots
    print(f"\n🏢 Exchange Data:")
    print(f"   • Unique Exchanges: {stats['unique_exchanges']}")
    print(f"   • Total Records: {stats['exchange_snapshot_count']:,}")

    # Database size
    print(f"\n💾 Database:")
    print(f"   • File Size: {stats['db_size_bytes']/1024:.1f} KB")
    print(f"   • Location: {repository.db_path}")

    print("\n" + "="*80)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Market Data Logger (Refactored)')
    parser.add_argument('--init', action='store_true', help='Initialize database')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Remove data older than DAYS')

    args = parser.parse_args()

    # Initialize repository
    repository = MarketRepository('data/market_history.db')

    if args.init:
        repository.initialize_database()
        print(f"✅ Database initialized at: {repository.db_path}")
    elif args.stats:
        show_database_stats(repository)
    elif args.cleanup:
        deleted = repository.cleanup_old_data(args.cleanup)
        if deleted > 0:
            print(f"🗑️  Deleted {deleted} records older than {args.cleanup} days")
            print(f"✅ Cleanup complete")
        else:
            print(f"✓ No records older than {args.cleanup} days")
    else:
        # Default: log current snapshot
        try:
            config = Config.from_yaml('config/config.yaml')
        except (FileNotFoundError, ValueError) as e:
            print(f"⚠️  Config error ({e}), using default configuration")
            config = Config(app_name="Crypto Perps Tracker", environment="development")

        container = Container(config)
        log_market_snapshot(container, repository)


if __name__ == "__main__":
    main()
