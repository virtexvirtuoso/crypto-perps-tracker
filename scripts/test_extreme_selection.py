#!/usr/bin/env python3
"""
Test EXTREME Symbol Selection - For Maximum Volatility & Outliers
Focuses on high-beta, extreme movers while maintaining minimum liquidity
"""

import sys
import os

# Add deprecated directory to path
deprecated_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deprecated')
sys.path.insert(0, deprecated_dir)

import requests
from datetime import datetime, timezone
from typing import Dict, List
from collections import defaultdict

# Import from deprecated script
from generate_symbol_report import (
    normalize_symbol,
    analyze_symbol
)


def fetch_bybit_symbols() -> List[Dict]:
    """Fetch all Bybit perpetual symbols"""
    try:
        response = requests.get(
            "https://api.bybit.com/v5/market/tickers?category=linear",
            timeout=10
        )
        data = response.json()

        if data.get('retCode') != 0:
            return []

        results = []
        for ticker in data['result']['list']:
            def safe_float(value, default=0.0):
                if value is None or value == '':
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default

            results.append({
                'exchange': 'Bybit',
                'symbol': ticker['symbol'],
                'price': safe_float(ticker.get('lastPrice'), 0),
                'volume': safe_float(ticker.get('turnover24h'), 0),
                'open_interest': safe_float(ticker.get('openInterestValue'), 0),
                'funding_rate': safe_float(ticker.get('fundingRate'), 0) * 100,
                'price_change_pct': safe_float(ticker.get('price24hPcnt'), 0) * 100,
                'num_trades': None,
                'type': 'CEX'
            })

        return results

    except Exception as e:
        print(f"Bybit error: {e}")
        return []


def fetch_symbol_data():
    """Fetch and analyze all symbols"""
    symbol_data = defaultdict(list)

    print("📊 Fetching data from Bybit...")
    results = fetch_bybit_symbols()
    print(f"   ✓ Fetched {len(results)} symbols\n")

    for item in results:
        symbol = normalize_symbol(item['symbol'])
        if symbol:
            symbol_data[symbol].append(item)

    # Get BTC change for beta calculation
    btc_data = symbol_data.get('BTC', [])
    btc_price_change = None
    if btc_data:
        btc_changes = [d.get('price_change_pct') for d in btc_data if d.get('price_change_pct') is not None]
        if btc_changes:
            btc_price_change = sum(btc_changes) / len(btc_changes)

    # Analyze all symbols
    print("🔍 Analyzing symbols...")
    analyses = []
    for symbol, data in symbol_data.items():
        analysis = analyze_symbol(symbol, data, btc_price_change=btc_price_change)
        if analysis:
            analyses.append(analysis)

    print(f"   ✓ Analyzed {len(analyses)} symbols\n")

    return analyses, btc_price_change


def option_d_extreme_hunters(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION D: EXTREME OUTLIER HUNTERS

    Strategy:
    - Always include BTC (benchmark)
    - Top 5 by absolute beta (biggest movers vs BTC)
    - Top 5 extreme high beta (>3x amplifiers)
    - Top 5 extreme inverse beta (<-2x contrarians)
    - Top 5 highest 24h volatility
    - Top 5 biggest gainers (24h change)
    - Top 5 biggest losers (24h change)
    - Minimum $10M volume (tradable but allows smaller caps)

    Pros:
    - Maximum volatility and action
    - Best for spotting extreme correlations
    - Most interesting visual patterns
    - Great for finding alpha opportunities

    Cons:
    - Higher risk from lower liquidity
    - May include unstable correlations
    - More noise in the data
    """
    MIN_VOLUME = 10e6  # $10M minimum (allows smaller volatile coins)

    selected = []
    selected_symbols = set()

    # Filter to minimum volume first
    filtered = [a for a in analyses if a['total_volume_24h'] >= MIN_VOLUME]

    # 1. Always BTC first
    btc = [a for a in filtered if a['symbol'] == 'BTC']
    if btc:
        selected.append(btc[0])
        selected_symbols.add('BTC')

    # 2. Top 5 by ABSOLUTE beta (biggest movers regardless of direction)
    by_abs_beta = sorted([a for a in filtered if a.get('btc_beta') is not None],
                         key=lambda x: abs(x['btc_beta']), reverse=True)
    for a in by_abs_beta:
        if a['symbol'] not in selected_symbols and len([s for s in selected if 'abs_beta' in s.get('category', '')]) < 5:
            a['category'] = 'abs_beta'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 3. Top 5 extreme HIGH beta (>3x)
    extreme_high = sorted([a for a in filtered if a.get('btc_beta', 0) > 3.0],
                          key=lambda x: x['btc_beta'], reverse=True)
    for a in extreme_high:
        if a['symbol'] not in selected_symbols and len([s for s in selected if 'extreme_high' in s.get('category', '')]) < 5:
            a['category'] = 'extreme_high'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 4. Top 5 extreme INVERSE beta (<-2x)
    extreme_inverse = sorted([a for a in filtered if a.get('btc_beta', 0) < -2.0],
                             key=lambda x: x['btc_beta'])
    for a in extreme_inverse:
        if a['symbol'] not in selected_symbols and len([s for s in selected if 'extreme_inverse' in s.get('category', '')]) < 5:
            a['category'] = 'extreme_inverse'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 5. Top 5 biggest GAINERS (24h change)
    biggest_gainers = sorted([a for a in filtered if a.get('avg_price_change_24h') is not None],
                             key=lambda x: x['avg_price_change_24h'], reverse=True)
    for a in biggest_gainers:
        if a['symbol'] not in selected_symbols and len([s for s in selected if 'gainer' in s.get('category', '')]) < 5:
            a['category'] = 'gainer'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 6. Top 5 biggest LOSERS (24h change)
    biggest_losers = sorted([a for a in filtered if a.get('avg_price_change_24h') is not None],
                            key=lambda x: x['avg_price_change_24h'])
    for a in biggest_losers:
        if a['symbol'] not in selected_symbols and len([s for s in selected if 'loser' in s.get('category', '')]) < 5:
            a['category'] = 'loser'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 7. Fill remaining with high volume extremes
    remaining_by_volume = sorted([a for a in filtered if a['symbol'] not in selected_symbols],
                                 key=lambda x: x['total_volume_24h'], reverse=True)
    for a in remaining_by_volume:
        if len(selected) < limit:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    return selected


def option_e_volatility_focus(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION E: PURE VOLATILITY FOCUS

    Strategy:
    - Prioritize symbols with extreme price swings
    - Include both high and low volume (volatility matters more)
    - Focus on beta extremes (>2x or <-1x)
    - Include recent extreme movers
    - Minimum $5M volume (very permissive)

    Pros:
    - Maximum chart excitement
    - Best for spotting pattern divergence
    - Most educational for correlation behavior

    Cons:
    - Highest risk
    - May include illiquid/unreliable data
    """
    MIN_VOLUME = 5e6  # $5M minimum (very permissive)

    selected = []
    selected_symbols = set()

    # Filter to minimum volume
    filtered = [a for a in analyses if a['total_volume_24h'] >= MIN_VOLUME]

    # 1. BTC always included
    btc = [a for a in filtered if a['symbol'] == 'BTC']
    if btc:
        selected.append(btc[0])
        selected_symbols.add('BTC')

    # 2. All symbols with beta > 2.0 or < -1.0
    extreme_betas = sorted([a for a in filtered
                           if a.get('btc_beta') is not None
                           and (abs(a['btc_beta']) > 2.0)],
                          key=lambda x: abs(x['btc_beta']), reverse=True)

    for a in extreme_betas:
        if a['symbol'] not in selected_symbols and len(selected) < limit:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 3. Fill with highest absolute price change
    by_change = sorted([a for a in filtered if a.get('avg_price_change_24h') is not None],
                       key=lambda x: abs(x['avg_price_change_24h']), reverse=True)

    for a in by_change:
        if a['symbol'] not in selected_symbols and len(selected) < limit:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    return selected


def print_selection_summary(name: str, selected: List[Dict]):
    """Print detailed summary of a selection"""
    print(f"\n{'='*100}")
    print(f"{name:^100}")
    print(f"{'='*100}\n")

    # Overall stats
    total_volume = sum(a['total_volume_24h'] for a in selected) / 1e9
    avg_volume = total_volume / len(selected) if selected else 0

    print(f"📊 SUMMARY")
    print(f"   Total Symbols:     {len(selected)}")
    print(f"   Avg Volume:        ${avg_volume:.2f}B")
    print(f"   Min Volume:        ${min(a['total_volume_24h'] for a in selected)/1e6:.0f}M")
    print(f"   Max Volume:        ${max(a['total_volume_24h'] for a in selected)/1e9:.2f}B")

    # Beta stats
    with_beta = [a for a in selected if a.get('btc_beta') is not None]
    if with_beta:
        betas = [a['btc_beta'] for a in with_beta]
        print(f"\n📈 BETA EXTREMES")
        print(f"   Range:          {min(betas):.2f}x to {max(betas):.2f}x")
        print(f"   Avg:            {sum(betas)/len(betas):.2f}x")
        print(f"   >3x:            {len([b for b in betas if b > 3.0])} symbols")
        print(f"   >5x:            {len([b for b in betas if b > 5.0])} symbols")
        print(f"   >10x:           {len([b for b in betas if b > 10.0])} symbols")
        print(f"   <-1x:           {len([b for b in betas if b < -1.0])} symbols")
        print(f"   <-2x:           {len([b for b in betas if b < -2.0])} symbols")

    # Performance extremes
    changes = [a.get('avg_price_change_24h', 0) for a in selected if a.get('avg_price_change_24h') is not None]
    if changes:
        print(f"\n📊 24H PERFORMANCE")
        print(f"   Best Gainer:    {max(changes):+.2f}%")
        print(f"   Worst Loser:    {min(changes):+.2f}%")
        print(f"   >+10%:          {len([c for c in changes if c > 10])} symbols")
        print(f"   <-10%:          {len([c for c in changes if c < -10])} symbols")

    # Top 10
    print(f"\n🏆 TOP 10 EXTREME MOVERS")
    print(f"{'Symbol':<12}{'Beta':<12}{'24h Δ':<12}{'Volume':<15}{'Category'}")
    print("-" * 100)

    sorted_by_beta = sorted([a for a in selected if a.get('btc_beta') is not None],
                           key=lambda x: abs(x['btc_beta']), reverse=True)[:10]

    for a in sorted_by_beta:
        beta_str = f"{a['btc_beta']:+.2f}x"
        change_str = f"{a.get('avg_price_change_24h', 0):+.1f}%"
        vol_str = f"${a['total_volume_24h']/1e6:.0f}M"
        cat = a.get('category', 'N/A')
        print(f"{a['symbol']:<12}{beta_str:<12}{change_str:<12}{vol_str:<15}{cat}")


if __name__ == "__main__":
    print("\n" + "="*100)
    print(f"{'EXTREME OUTLIER SELECTION TESTING':^100}")
    print(f"{'For Maximum Volatility & Interesting Patterns':^100}")
    print("="*100 + "\n")

    # Fetch data
    analyses, btc_change = fetch_symbol_data()

    if not analyses:
        print("❌ No data available")
        exit(1)

    print(f"✅ Ready with {len(analyses)} symbols\n")
    print(f"📊 BTC 24h change: {btc_change:+.2f}%\n")

    # Run extreme selection methods
    print("🔬 Running extreme selection methods...\n")

    option_d = option_d_extreme_hunters(analyses, limit=30)
    print("   ✓ Option D: Extreme Hunters")

    option_e = option_e_volatility_focus(analyses, limit=30)
    print("   ✓ Option E: Pure Volatility")

    # Print summaries
    print_selection_summary("OPTION D: EXTREME OUTLIER HUNTERS", option_d)
    print_selection_summary("OPTION E: PURE VOLATILITY FOCUS", option_e)

    # Comparison
    print(f"\n{'='*100}")
    print(f"{'RECOMMENDATION':^100}")
    print(f"{'='*100}\n")

    print("🔥 OPTION D (Extreme Hunters) - RECOMMENDED FOR YOUR USE CASE")
    print("   ✓ Balanced extreme selection across categories")
    print("   ✓ Includes biggest movers, gainers, losers")
    print("   ✓ Maintains $10M minimum volume (tradable)")
    print("   ✓ Best mix of excitement + reliability")
    print("   ✓ Great visual patterns on chart")

    print("\n💥 OPTION E (Pure Volatility)")
    print("   ✓ Maximum volatility at all costs")
    print("   ✓ Only $5M volume minimum (more risky)")
    print("   ✓ Best for pure correlation research")
    print("   ✓ Most extreme patterns")

    print("\n" + "="*100 + "\n")
