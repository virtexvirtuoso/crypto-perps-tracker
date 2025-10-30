#!/usr/bin/env python3
"""
Test Different Symbol Selection Methods
Compares 3 different approaches to selecting crypto symbols for analysis
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


def option_a_balanced(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION A: BALANCED APPROACH

    Strategy:
    - Always include BTC (market benchmark)
    - Top 5 by market cap (market leaders)
    - Top 5 by volume (most liquid)
    - Top 5 highest correlation (strong BTC followers)
    - Fill remaining with high volume (>$50M)

    Pros:
    - Balanced representation across metrics
    - Includes both market movers and stable assets
    - Good for general market overview

    Cons:
    - May include some overlap
    - Less focused on specific criteria
    """
    selected = []
    selected_symbols = set()

    # 1. Always BTC first
    btc = [a for a in analyses if a['symbol'] == 'BTC']
    if btc:
        selected.append(btc[0])
        selected_symbols.add('BTC')

    # 2. Top 5 by volume (excluding already selected)
    by_volume = sorted(analyses, key=lambda x: x['total_volume_24h'], reverse=True)
    for a in by_volume:
        if a['symbol'] not in selected_symbols and len(selected) < 6:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 3. Top 5 with highest absolute beta (strong correlators)
    by_beta = sorted([a for a in analyses if a.get('btc_beta') is not None],
                     key=lambda x: abs(x['btc_beta']), reverse=True)
    for a in by_beta:
        if a['symbol'] not in selected_symbols and len(selected) < 11:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 4. Top 5 with high beta (amplifiers >1.5)
    high_beta = sorted([a for a in analyses if a.get('btc_beta', 0) > 1.5],
                       key=lambda x: x['btc_beta'], reverse=True)
    for a in high_beta:
        if a['symbol'] not in selected_symbols and len(selected) < 16:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 5. Fill to limit with high volume (>$50M)
    high_volume = [a for a in by_volume if a['total_volume_24h'] > 50e6]
    for a in high_volume:
        if a['symbol'] not in selected_symbols and len(selected) < limit:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    return selected


def option_b_liquidity(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION B: PURE LIQUIDITY FOCUS

    Strategy:
    - Minimum $100M daily volume
    - Minimum $1B market cap equivalent (via volume proxy)
    - Sort by volume descending
    - Take top N

    Pros:
    - Safest for actual trading
    - Best execution and lowest slippage
    - Most institutional quality

    Cons:
    - May miss interesting smaller caps
    - Limited diversity in beta ranges
    """
    MIN_VOLUME = 100e6  # $100M daily

    # Filter by minimum volume
    filtered = [a for a in analyses if a['total_volume_24h'] >= MIN_VOLUME]

    # Sort by volume
    filtered.sort(key=lambda x: x['total_volume_24h'], reverse=True)

    return filtered[:limit]


def option_c_beta_spectrum(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION C: BETA SIGNIFICANCE / SPECTRUM

    Strategy:
    - Always include BTC (benchmark)
    - High beta (>1.5): 8 symbols - amplifiers
    - Medium beta (0.8-1.2): 10 symbols - trackers
    - Low beta (0.3-0.8): 6 symbols - weak correlators
    - Inverse (<0): 3 symbols - contrarians
    - Uncorrelated/neutral: 2 symbols

    Pros:
    - Best for correlation studies
    - Shows full spectrum of BTC relationships
    - Educational/analytical value

    Cons:
    - May include low liquidity symbols
    - Less practical for trading
    """
    selected = []

    # 1. BTC (benchmark)
    btc = [a for a in analyses if a['symbol'] == 'BTC']
    if btc:
        selected.extend(btc)

    # 2. High beta (>1.5) - 8 symbols
    high_beta = sorted([a for a in analyses if a.get('btc_beta', 0) > 1.5],
                       key=lambda x: x['btc_beta'], reverse=True)
    selected.extend(high_beta[:8])

    # 3. Medium beta (0.8-1.2) - 10 symbols
    medium_beta = sorted([a for a in analyses if 0.8 <= a.get('btc_beta', 0) <= 1.2],
                         key=lambda x: x['total_volume_24h'], reverse=True)
    selected.extend(medium_beta[:10])

    # 4. Low beta (0.3-0.8) - 6 symbols
    low_beta = sorted([a for a in analyses if 0.3 <= a.get('btc_beta', 0) < 0.8],
                      key=lambda x: x['total_volume_24h'], reverse=True)
    selected.extend(low_beta[:6])

    # 5. Inverse (<0) - 3 symbols
    inverse = sorted([a for a in analyses if a.get('btc_beta', 0) < 0],
                     key=lambda x: x['total_volume_24h'], reverse=True)
    selected.extend(inverse[:3])

    # 6. Near zero/uncorrelated (0-0.3) - 2 symbols
    near_zero = sorted([a for a in analyses if 0 <= a.get('btc_beta', 0) < 0.3],
                       key=lambda x: x['total_volume_24h'], reverse=True)
    selected.extend(near_zero[:2])

    # Remove duplicates and limit
    seen = set()
    unique_selected = []
    for a in selected:
        if a['symbol'] not in seen:
            unique_selected.append(a)
            seen.add(a['symbol'])

    return unique_selected[:limit]


def print_selection_summary(name: str, selected: List[Dict], btc_change: float):
    """Print detailed summary of a selection"""
    print(f"\n{'='*100}")
    print(f"{name:^100}")
    print(f"{'='*100}\n")

    # Overall stats
    total_volume = sum(a['total_volume_24h'] for a in selected) / 1e9
    avg_volume = total_volume / len(selected) if selected else 0
    total_oi = sum(a['total_open_interest'] for a in selected) / 1e9

    print(f"📊 SUMMARY STATISTICS")
    print(f"   Total Symbols:       {len(selected)}")
    print(f"   Total Volume:        ${total_volume:.2f}B")
    print(f"   Avg Volume/Symbol:   ${avg_volume:.2f}B")
    print(f"   Total Open Interest: ${total_oi:.2f}B")

    # Beta distribution
    with_beta = [a for a in selected if a.get('btc_beta') is not None]
    if with_beta:
        betas = [a['btc_beta'] for a in with_beta]
        avg_beta = sum(betas) / len(betas)

        high_beta = len([b for b in betas if b > 1.5])
        medium_high = len([b for b in betas if 1.0 < b <= 1.5])
        medium = len([b for b in betas if 0.5 < b <= 1.0])
        low = len([b for b in betas if 0 < b <= 0.5])
        inverse = len([b for b in betas if b < 0])

        print(f"\n📈 BETA DISTRIBUTION")
        print(f"   Average Beta:     {avg_beta:.2f}x")
        print(f"   High (>1.5x):     {high_beta} symbols ({high_beta/len(selected)*100:.1f}%)")
        print(f"   Med-High (1-1.5): {medium_high} symbols ({medium_high/len(selected)*100:.1f}%)")
        print(f"   Medium (0.5-1):   {medium} symbols ({medium/len(selected)*100:.1f}%)")
        print(f"   Low (0-0.5):      {low} symbols ({low/len(selected)*100:.1f}%)")
        print(f"   Inverse (<0):     {inverse} symbols ({inverse/len(selected)*100:.1f}%)")

    # Volume distribution
    volumes = [a['total_volume_24h'] / 1e6 for a in selected]
    over_1b = len([v for v in volumes if v >= 1000])
    over_500m = len([v for v in volumes if 500 <= v < 1000])
    over_100m = len([v for v in volumes if 100 <= v < 500])
    under_100m = len([v for v in volumes if v < 100])

    print(f"\n💰 VOLUME DISTRIBUTION")
    print(f"   >$1B:      {over_1b} symbols ({over_1b/len(selected)*100:.1f}%)")
    print(f"   $500M-$1B: {over_500m} symbols ({over_500m/len(selected)*100:.1f}%)")
    print(f"   $100M-500M: {over_100m} symbols ({over_100m/len(selected)*100:.1f}%)")
    print(f"   <$100M:    {under_100m} symbols ({under_100m/len(selected)*100:.1f}%)")

    # Top 10 symbols
    print(f"\n🏆 TOP 10 SYMBOLS (by volume)")
    print(f"{'Rank':<6}{'Symbol':<10}{'Volume':<15}{'Beta':<12}{'24h Change':<12}{'OI'}")
    print("-" * 100)

    sorted_by_vol = sorted(selected, key=lambda x: x['total_volume_24h'], reverse=True)[:10]
    for i, a in enumerate(sorted_by_vol, 1):
        vol_str = f"${a['total_volume_24h']/1e9:.2f}B" if a['total_volume_24h'] > 1e9 else f"${a['total_volume_24h']/1e6:.0f}M"
        beta_str = f"{a['btc_beta']:.2f}x" if a.get('btc_beta') is not None else "N/A"
        change_str = f"{a.get('avg_price_change_24h', 0):+.1f}%" if a.get('avg_price_change_24h') is not None else "N/A"
        oi_str = f"${a['total_open_interest']/1e9:.2f}B" if a['total_open_interest'] > 1e9 else f"${a['total_open_interest']/1e6:.0f}M"

        print(f"{i:<6}{a['symbol']:<10}{vol_str:<15}{beta_str:<12}{change_str:<12}{oi_str}")

    # Performance stats
    changes = [a.get('avg_price_change_24h', 0) for a in selected if a.get('avg_price_change_24h') is not None]
    if changes:
        positive = len([c for c in changes if c > 0])
        negative = len([c for c in changes if c < 0])

        print(f"\n📈 PERFORMANCE (24h)")
        print(f"   Positive: {positive} symbols ({positive/len(changes)*100:.1f}%)")
        print(f"   Negative: {negative} symbols ({negative/len(changes)*100:.1f}%)")
        print(f"   Best:     {max(changes):+.2f}%")
        print(f"   Worst:    {min(changes):+.2f}%")


def compare_selections(option_a: List[Dict], option_b: List[Dict], option_c: List[Dict]):
    """Compare the three options side by side"""
    print(f"\n{'='*100}")
    print(f"{'COMPARISON MATRIX':^100}")
    print(f"{'='*100}\n")

    print(f"{'Metric':<30}{'Option A (Balanced)':<25}{'Option B (Liquidity)':<25}{'Option C (Beta)':<25}")
    print("-" * 100)

    # Count
    print(f"{'Total Symbols':<30}{len(option_a):<25}{len(option_b):<25}{len(option_c):<25}")

    # Average volume
    avg_vol_a = sum(a['total_volume_24h'] for a in option_a) / len(option_a) / 1e9 if option_a else 0
    avg_vol_b = sum(a['total_volume_24h'] for a in option_b) / len(option_b) / 1e9 if option_b else 0
    avg_vol_c = sum(a['total_volume_24h'] for a in option_c) / len(option_c) / 1e9 if option_c else 0
    print(f"{'Avg Volume (per symbol)':<30}${avg_vol_a:.2f}B{' '*15}${avg_vol_b:.2f}B{' '*15}${avg_vol_c:.2f}B")

    # Min volume
    min_vol_a = min(a['total_volume_24h'] for a in option_a) / 1e6 if option_a else 0
    min_vol_b = min(a['total_volume_24h'] for a in option_b) / 1e6 if option_b else 0
    min_vol_c = min(a['total_volume_24h'] for a in option_c) / 1e6 if option_c else 0
    print(f"{'Min Volume':<30}${min_vol_a:.0f}M{' '*17}${min_vol_b:.0f}M{' '*17}${min_vol_c:.0f}M")

    # Beta range
    betas_a = [a['btc_beta'] for a in option_a if a.get('btc_beta') is not None]
    betas_b = [a['btc_beta'] for a in option_b if a.get('btc_beta') is not None]
    betas_c = [a['btc_beta'] for a in option_c if a.get('btc_beta') is not None]

    if betas_a and betas_b and betas_c:
        beta_range_a = f"{min(betas_a):.2f} to {max(betas_a):.2f}"
        beta_range_b = f"{min(betas_b):.2f} to {max(betas_b):.2f}"
        beta_range_c = f"{min(betas_c):.2f} to {max(betas_c):.2f}"
        print(f"{'Beta Range':<30}{beta_range_a:<25}{beta_range_b:<25}{beta_range_c:<25}")

        avg_beta_a = sum(betas_a) / len(betas_a)
        avg_beta_b = sum(betas_b) / len(betas_b)
        avg_beta_c = sum(betas_c) / len(betas_c)
        print(f"{'Avg Beta':<30}{avg_beta_a:.2f}x{' '*20}{avg_beta_b:.2f}x{' '*20}{avg_beta_c:.2f}x")

    # High beta count
    high_a = len([b for b in betas_a if b > 1.5]) if betas_a else 0
    high_b = len([b for b in betas_b if b > 1.5]) if betas_b else 0
    high_c = len([b for b in betas_c if b > 1.5]) if betas_c else 0
    print(f"{'High Beta (>1.5) Count':<30}{high_a:<25}{high_b:<25}{high_c:<25}")

    # Inverse count
    inv_a = len([b for b in betas_a if b < 0]) if betas_a else 0
    inv_b = len([b for b in betas_b if b < 0]) if betas_b else 0
    inv_c = len([b for b in betas_c if b < 0]) if betas_c else 0
    print(f"{'Inverse Beta (<0) Count':<30}{inv_a:<25}{inv_b:<25}{inv_c:<25}")

    print("\n" + "="*100)

    # Recommendations
    print(f"\n💡 RECOMMENDATIONS\n")
    print(f"🏆 OPTION A (Balanced):")
    print(f"   ✓ Best for: General market analysis, diverse portfolios")
    print(f"   ✓ Strengths: Good mix of volume + beta diversity")
    print(f"   ✓ Use when: You want comprehensive market coverage")

    print(f"\n💰 OPTION B (Liquidity):")
    print(f"   ✓ Best for: Active trading, institutional use")
    print(f"   ✓ Strengths: Highest liquidity, lowest slippage")
    print(f"   ✓ Use when: You need maximum tradability")

    print(f"\n📊 OPTION C (Beta Spectrum):")
    print(f"   ✓ Best for: Correlation studies, academic analysis")
    print(f"   ✓ Strengths: Full beta spectrum, educational value")
    print(f"   ✓ Use when: You're studying BTC relationships")

    print("\n" + "="*100 + "\n")


if __name__ == "__main__":
    print("\n" + "="*100)
    print(f"{'SYMBOL SELECTION METHOD TESTING':^100}")
    print(f"{'Comparing 3 Different Selection Approaches':^100}")
    print("="*100 + "\n")

    # Fetch data
    analyses, btc_change = fetch_symbol_data()

    if not analyses:
        print("❌ No data available for testing")
        exit(1)

    print(f"✅ Ready to test with {len(analyses)} analyzed symbols\n")
    print(f"📊 BTC 24h change: {btc_change:+.2f}%\n")

    # Run all three selection methods
    print("🔬 Running selection methods...\n")

    option_a = option_a_balanced(analyses, limit=30)
    print("   ✓ Option A: Balanced")

    option_b = option_b_liquidity(analyses, limit=30)
    print("   ✓ Option B: Liquidity Focus")

    option_c = option_c_beta_spectrum(analyses, limit=30)
    print("   ✓ Option C: Beta Spectrum")

    # Print detailed summaries
    print_selection_summary("OPTION A: BALANCED APPROACH", option_a, btc_change)
    print_selection_summary("OPTION B: PURE LIQUIDITY FOCUS", option_b, btc_change)
    print_selection_summary("OPTION C: BETA SIGNIFICANCE SPECTRUM", option_c, btc_change)

    # Comparison matrix
    compare_selections(option_a, option_b, option_c)

    print(f"✅ Test completed! Review the results above to choose the best option.\n")
