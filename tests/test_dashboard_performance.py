"""
Dashboard Performance and Accuracy Testing
Tests the Symbol Analysis tab for performance, data accuracy, and chart rendering
"""

import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.container import Container
from src.models.config import Config
from dashboard.utils.analytics import (
    get_symbol_analytics,
    get_market_summary,
    get_arbitrage_opportunities,
    get_funding_extremes
)

# Load config
config = Config.from_yaml('config/config.yaml')

def test_data_fetching_performance():
    """Test how long it takes to fetch and analyze symbol data"""
    print("\n" + "="*80)
    print("🔍 TESTING DATA FETCHING PERFORMANCE")
    print("="*80)

    container = Container(config)

    # Test different top_n values
    for top_n in [5, 10, 15, 20]:
        start = time.time()
        analyses = get_symbol_analytics(container, top_n=top_n)
        elapsed = time.time() - start

        print(f"\n📊 Top {top_n} symbols:")
        print(f"   ⏱️  Fetch time: {elapsed:.2f}s")
        print(f"   📈 Symbols returned: {len(analyses)}")
        if analyses:
            print(f"   💰 Total volume: ${sum(a['total_volume_24h'] for a in analyses)/1e9:.2f}B")

def test_data_accuracy():
    """Verify the data returned is accurate and complete"""
    print("\n" + "="*80)
    print("✅ TESTING DATA ACCURACY")
    print("="*80)

    container = Container(config)
    analyses = get_symbol_analytics(container, top_n=10)

    if not analyses:
        print("❌ No data returned!")
        return False

    print(f"\n✅ Got {len(analyses)} symbols")

    # Check each analysis has required fields
    required_fields = [
        'symbol', 'total_volume_24h', 'total_open_interest',
        'exchanges', 'avg_price', 'arbitrage_opportunity'
    ]

    for i, analysis in enumerate(analyses[:3], 1):
        print(f"\n📊 Symbol {i}: {analysis['symbol']}")
        missing_fields = [f for f in required_fields if f not in analysis]

        if missing_fields:
            print(f"   ❌ Missing fields: {missing_fields}")
        else:
            print(f"   ✅ All required fields present")
            print(f"   💰 Volume: ${analysis['total_volume_24h']/1e6:.1f}M")
            print(f"   📊 OI: ${analysis['total_open_interest']/1e6:.1f}M")
            print(f"   🏦 Exchanges: {len(analysis['exchanges'])}")

            # Check optional fields
            if analysis.get('avg_funding_rate') is not None:
                print(f"   📈 Funding: {analysis['avg_funding_rate']*100:.4f}%")
            if analysis.get('bitcoin_beta') is not None:
                print(f"   β  Beta: {analysis['bitcoin_beta']:.2f}")

    return True

def test_chart_data():
    """Test that chart data is properly formatted"""
    print("\n" + "="*80)
    print("📊 TESTING CHART DATA")
    print("="*80)

    container = Container(config)
    analyses = get_symbol_analytics(container, top_n=10)

    # Test Bitcoin Beta chart data
    beta_data = [(a['symbol'], a['bitcoin_beta'])
                 for a in analyses
                 if a.get('bitcoin_beta') is not None]
    print(f"\n📈 Bitcoin Beta Chart:")
    print(f"   Points: {len(beta_data)}")
    if beta_data:
        print(f"   Range: {min(b for _, b in beta_data):.2f} to {max(b for _, b in beta_data):.2f}")

    # Test Volume chart data
    vol_data = [(a['symbol'], a['total_volume_24h']) for a in analyses[:10]]
    print(f"\n💰 Volume Chart:")
    print(f"   Points: {len(vol_data)}")
    if vol_data:
        print(f"   Range: ${min(v for _, v in vol_data)/1e6:.1f}M to ${max(v for _, v in vol_data)/1e6:.1f}M")

    # Test Funding Rate chart data
    funding_data = [(a['symbol'], a.get('avg_funding_rate', 0) * 100)
                    for a in analyses[:10]
                    if a.get('avg_funding_rate') is not None]
    print(f"\n📊 Funding Rate Chart:")
    print(f"   Points: {len(funding_data)}")
    if funding_data:
        print(f"   Range: {min(f for _, f in funding_data):.4f}% to {max(f for _, f in funding_data):.4f}%")

def test_arbitrage_opportunities():
    """Test arbitrage opportunity detection"""
    print("\n" + "="*80)
    print("💎 TESTING ARBITRAGE OPPORTUNITIES")
    print("="*80)

    container = Container(config)
    analyses = get_symbol_analytics(container, top_n=20)

    for min_spread in [0.1, 0.2, 0.5]:
        arb_opps = get_arbitrage_opportunities(analyses, min_spread=min_spread)
        print(f"\n💰 Min spread {min_spread}%:")
        print(f"   Opportunities: {len(arb_opps)}")

        if arb_opps:
            top_opp = arb_opps[0]
            print(f"   Top opportunity: {top_opp['symbol']}")
            print(f"   Spread: {top_opp['price_spread_pct']:.2f}%")
            if 'best_buy' in top_opp:
                print(f"   Buy: {top_opp['best_buy']['exchange']} @ ${top_opp['best_buy']['price']:.2f}")
            if 'best_sell' in top_opp:
                print(f"   Sell: {top_opp['best_sell']['exchange']} @ ${top_opp['best_sell']['price']:.2f}")

def test_funding_extremes():
    """Test funding rate extreme detection"""
    print("\n" + "="*80)
    print("⚡ TESTING FUNDING EXTREMES")
    print("="*80)

    container = Container(config)
    analyses = get_symbol_analytics(container, top_n=20)
    extremes = get_funding_extremes(analyses)

    print(f"\n🔴 Highest Funding (best for shorts):")
    for i, a in enumerate(extremes['highest'][:5], 1):
        print(f"   {i}. {a['symbol']}: {a['avg_funding_rate']*100:.4f}%")

    print(f"\n🟢 Lowest Funding (best for longs):")
    for i, a in enumerate(extremes['lowest'][:5], 1):
        print(f"   {i}. {a['symbol']}: {a['avg_funding_rate']*100:.4f}%")

def test_market_summary():
    """Test market summary calculations"""
    print("\n" + "="*80)
    print("📈 TESTING MARKET SUMMARY")
    print("="*80)

    container = Container(config)
    analyses = get_symbol_analytics(container, top_n=15)
    summary = get_market_summary(analyses)

    print(f"\n📊 Market Summary:")
    print(f"   Symbols Tracked: {summary.get('total_symbols', 0)}")
    print(f"   Total Volume: ${summary.get('total_volume_24h', 0)/1e9:.2f}B")
    print(f"   Total OI: ${summary.get('total_open_interest', 0)/1e9:.2f}B")
    print(f"   Exchanges: {summary.get('num_exchanges', 0)}")
    if summary.get('exchanges'):
        print(f"   Exchange list: {', '.join(summary['exchanges'][:5])}")

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 DASHBOARD SYMBOL ANALYSIS TESTING SUITE")
    print("="*80)

    start_time = time.time()

    try:
        test_data_fetching_performance()
        test_data_accuracy()
        test_chart_data()
        test_arbitrage_opportunities()
        test_funding_extremes()
        test_market_summary()

        total_time = time.time() - start_time

        print("\n" + "="*80)
        print(f"✅ ALL TESTS COMPLETED in {total_time:.2f}s")
        print("="*80)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
