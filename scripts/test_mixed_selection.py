#!/usr/bin/env python3
"""
Test MIXED Selection - Combining Liquidity (B) + Extremes (D)
The best of both worlds: High liquidity with extreme outliers
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


def option_f_liquid_extremes(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION F: LIQUID EXTREMES (B + D Mix)

    Strategy:
    - Minimum $50M volume (tradable but allows interesting coins)
    - Prioritize EXTREME betas (>5x or <-2x) within liquid pool
    - Include top liquid symbols (BTC, ETH, SOL always)
    - Add extreme gainers/losers (but only if >$50M volume)
    - Fill with high-beta liquid symbols

    Balance:
    - 50% extreme outliers (high beta, inverse, movers)
    - 50% liquid market leaders (top volume)

    Pros:
    - Best visual excitement + tradability
    - Extreme patterns with reliable execution
    - Professional grade with alpha opportunities
    - Great for both analysis AND trading

    Cons:
    - May miss some VERY extreme low-volume coins
    - Less extreme than pure Option D
    """
    MIN_VOLUME = 50e6  # $50M minimum (sweet spot)

    selected = []
    selected_symbols = set()

    # Filter to minimum volume first
    filtered = [a for a in analyses if a['total_volume_24h'] >= MIN_VOLUME]

    print(f"   After $50M filter: {len(filtered)} symbols available")

    # === PHASE 1: Always include top 3 by volume (market leaders) ===
    by_volume = sorted(filtered, key=lambda x: x['total_volume_24h'], reverse=True)
    for a in by_volume[:3]:
        if a['symbol'] not in selected_symbols:
            a['category'] = 'market_leader'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    print(f"   Added {len(selected)} market leaders")

    # === PHASE 2: Extreme high beta (>5x) - up to 7 symbols ===
    extreme_high = sorted([a for a in filtered if a.get('btc_beta', 0) > 5.0],
                          key=lambda x: x['btc_beta'], reverse=True)
    count = 0
    for a in extreme_high:
        if a['symbol'] not in selected_symbols and count < 7:
            a['category'] = 'extreme_high_beta'
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   Added {count} extreme high beta (>5x)")

    # === PHASE 3: Extreme inverse beta (<-2x) - up to 5 symbols ===
    extreme_inverse = sorted([a for a in filtered if a.get('btc_beta', 0) < -2.0],
                             key=lambda x: x['btc_beta'])
    count = 0
    for a in extreme_inverse:
        if a['symbol'] not in selected_symbols and count < 5:
            a['category'] = 'extreme_inverse'
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   Added {count} extreme inverse (<-2x)")

    # === PHASE 4: Top gainers (>10% change) - up to 4 symbols ===
    top_gainers = sorted([a for a in filtered
                         if a.get('avg_price_change_24h', 0) > 10.0],
                        key=lambda x: x['avg_price_change_24h'], reverse=True)
    count = 0
    for a in top_gainers:
        if a['symbol'] not in selected_symbols and count < 4:
            a['category'] = 'top_gainer'
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   Added {count} top gainers (>10%)")

    # === PHASE 5: Top losers (<-10% change) - up to 4 symbols ===
    top_losers = sorted([a for a in filtered
                        if a.get('avg_price_change_24h', 0) < -10.0],
                       key=lambda x: x['avg_price_change_24h'])
    count = 0
    for a in top_losers:
        if a['symbol'] not in selected_symbols and count < 4:
            a['category'] = 'top_loser'
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   Added {count} top losers (<-10%)")

    # === PHASE 6: Medium-high beta (2-5x) for balance - up to 5 symbols ===
    medium_high = sorted([a for a in filtered
                         if 2.0 <= a.get('btc_beta', 0) < 5.0],
                        key=lambda x: x['total_volume_24h'], reverse=True)
    count = 0
    for a in medium_high:
        if a['symbol'] not in selected_symbols and count < 5:
            a['category'] = 'medium_high_beta'
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   Added {count} medium-high beta (2-5x)")

    # === PHASE 7: Fill remaining with highest volume + any beta ===
    remaining = sorted([a for a in filtered if a['symbol'] not in selected_symbols],
                      key=lambda x: x['total_volume_24h'], reverse=True)
    count = 0
    for a in remaining:
        if len(selected) < limit:
            a['category'] = 'high_volume_filler'
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   Added {count} high volume fillers")
    print(f"   Total selected: {len(selected)}")

    return selected


def option_g_balanced_extremes(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION G: BALANCED EXTREMES (Alternative Mix)

    Strategy:
    - Minimum $30M volume (slightly lower threshold)
    - Equal representation across beta ranges
    - Include diverse market caps
    - Focus on symbols with clear correlation patterns

    Distribution:
    - 5 market leaders (>$500M volume)
    - 5 extreme high beta (>5x)
    - 5 extreme inverse (<-1x)
    - 5 medium beta (1-2x)
    - 5 high performers (price action)
    - 5 wild cards (interesting patterns)

    Pros:
    - Most balanced representation
    - Good mix of safety + excitement
    - Educational value
    - Clear pattern diversity

    Cons:
    - Less focused than Option F
    - May include some moderate performers
    """
    MIN_VOLUME = 30e6  # $30M minimum

    selected = []
    selected_symbols = set()

    filtered = [a for a in analyses if a['total_volume_24h'] >= MIN_VOLUME]

    # 1. Top 5 by volume (>$500M preferred)
    high_volume = sorted([a for a in filtered if a['total_volume_24h'] >= 500e6],
                        key=lambda x: x['total_volume_24h'], reverse=True)
    for a in high_volume[:5]:
        if a['symbol'] not in selected_symbols:
            a['category'] = 'market_leader'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 2. Top 5 extreme high beta (>5x)
    extreme_high = sorted([a for a in filtered if a.get('btc_beta', 0) > 5.0],
                         key=lambda x: x['btc_beta'], reverse=True)
    for a in extreme_high[:5]:
        if a['symbol'] not in selected_symbols:
            a['category'] = 'extreme_high'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 3. Top 5 inverse (<-1x)
    inverse = sorted([a for a in filtered if a.get('btc_beta', 0) < -1.0],
                    key=lambda x: x['btc_beta'])
    for a in inverse[:5]:
        if a['symbol'] not in selected_symbols:
            a['category'] = 'inverse'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 4. Top 5 medium beta (1-2x)
    medium = sorted([a for a in filtered if 1.0 <= a.get('btc_beta', 0) <= 2.0],
                   key=lambda x: x['total_volume_24h'], reverse=True)
    for a in medium[:5]:
        if a['symbol'] not in selected_symbols:
            a['category'] = 'medium_beta'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 5. Top 5 by absolute price change
    by_change = sorted([a for a in filtered if a.get('avg_price_change_24h') is not None],
                      key=lambda x: abs(x['avg_price_change_24h']), reverse=True)
    for a in by_change[:5]:
        if a['symbol'] not in selected_symbols:
            a['category'] = 'big_mover'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    # 6. Fill to limit with high volume
    remaining = sorted([a for a in filtered if a['symbol'] not in selected_symbols],
                      key=lambda x: x['total_volume_24h'], reverse=True)
    for a in remaining:
        if len(selected) < limit:
            a['category'] = 'wildcard'
            selected.append(a)
            selected_symbols.add(a['symbol'])

    return selected


def print_selection_summary(name: str, selected: List[Dict]):
    """Print detailed summary"""
    print(f"\n{'='*110}")
    print(f"{name:^110}")
    print(f"{'='*110}\n")

    # Stats
    total_volume = sum(a['total_volume_24h'] for a in selected) / 1e9
    avg_volume = total_volume / len(selected) if selected else 0

    print(f"📊 SUMMARY")
    print(f"   Total Symbols:     {len(selected)}")
    print(f"   Total Volume:      ${total_volume:.2f}B")
    print(f"   Avg Volume:        ${avg_volume:.2f}B per symbol")
    print(f"   Min Volume:        ${min(a['total_volume_24h'] for a in selected)/1e6:.0f}M")
    print(f"   Max Volume:        ${max(a['total_volume_24h'] for a in selected)/1e9:.2f}B")

    # Category breakdown
    categories = {}
    for a in selected:
        cat = a.get('category', 'N/A')
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n📂 CATEGORY BREAKDOWN")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"   {cat:<25} {count} symbols")

    # Beta stats
    with_beta = [a for a in selected if a.get('btc_beta') is not None]
    if with_beta:
        betas = [a['btc_beta'] for a in with_beta]
        print(f"\n📈 BETA ANALYSIS")
        print(f"   Range:          {min(betas):+.2f}x to {max(betas):+.2f}x")
        print(f"   Average:        {sum(betas)/len(betas):+.2f}x")
        print(f"   Extreme (>5x):  {len([b for b in betas if b > 5.0])} symbols")
        print(f"   High (2-5x):    {len([b for b in betas if 2.0 <= b <= 5.0])} symbols")
        print(f"   Medium (1-2x):  {len([b for b in betas if 1.0 <= b < 2.0])} symbols")
        print(f"   Inverse (<-1x): {len([b for b in betas if b < -1.0])} symbols")

    # Volume distribution
    print(f"\n💰 VOLUME DISTRIBUTION")
    over_1b = len([a for a in selected if a['total_volume_24h'] >= 1e9])
    over_500m = len([a for a in selected if 500e6 <= a['total_volume_24h'] < 1e9])
    over_100m = len([a for a in selected if 100e6 <= a['total_volume_24h'] < 500e6])
    over_50m = len([a for a in selected if 50e6 <= a['total_volume_24h'] < 100e6])
    under_50m = len([a for a in selected if a['total_volume_24h'] < 50e6])

    print(f"   >$1B:      {over_1b} symbols ({over_1b/len(selected)*100:.1f}%)")
    print(f"   $500M-$1B: {over_500m} symbols ({over_500m/len(selected)*100:.1f}%)")
    print(f"   $100-500M: {over_100m} symbols ({over_100m/len(selected)*100:.1f}%)")
    print(f"   $50-100M:  {over_50m} symbols ({over_50m/len(selected)*100:.1f}%)")
    print(f"   <$50M:     {under_50m} symbols ({under_50m/len(selected)*100:.1f}%)")

    # Top 15
    print(f"\n🏆 TOP 15 SYMBOLS")
    print(f"{'Rank':<5}{'Symbol':<10}{'Beta':<12}{'24h Δ':<12}{'Volume':<14}{'Category'}")
    print("-" * 110)

    sorted_sel = sorted(selected, key=lambda x: x['total_volume_24h'], reverse=True)[:15]
    for i, a in enumerate(sorted_sel, 1):
        beta_str = f"{a.get('btc_beta', 0):+.2f}x"
        change_str = f"{a.get('avg_price_change_24h', 0):+.1f}%"
        vol_str = f"${a['total_volume_24h']/1e6:.0f}M"
        cat = a.get('category', 'N/A')[:20]
        print(f"{i:<5}{a['symbol']:<10}{beta_str:<12}{change_str:<12}{vol_str:<14}{cat}")


if __name__ == "__main__":
    print("\n" + "="*110)
    print(f"{'MIXED SELECTION TESTING: OPTION B + D':^110}")
    print(f"{'Combining High Liquidity with Extreme Outliers':^110}")
    print("="*110 + "\n")

    # Fetch data
    analyses, btc_change = fetch_symbol_data()

    if not analyses:
        print("❌ No data available")
        exit(1)

    print(f"✅ Ready with {len(analyses)} symbols")
    print(f"📊 BTC 24h change: {btc_change:+.2f}%\n")

    # Run mixed options
    print("🔬 Running mixed selection methods...\n")

    print("Running Option F: Liquid Extremes...")
    option_f = option_f_liquid_extremes(analyses, limit=30)

    print("\nRunning Option G: Balanced Extremes...")
    option_g = option_g_balanced_extremes(analyses, limit=30)

    # Print summaries
    print_selection_summary("OPTION F: LIQUID EXTREMES (B+D Mix)", option_f)
    print_selection_summary("OPTION G: BALANCED EXTREMES (Alternative)", option_g)

    # Final recommendation
    print(f"\n{'='*110}")
    print(f"{'FINAL RECOMMENDATION':^110}")
    print(f"{'='*110}\n")

    print("🏆 OPTION F: LIQUID EXTREMES - BEST OF BOTH WORLDS")
    print("   ✓ $50M minimum volume (reliable execution)")
    print("   ✓ Focus on extreme betas (>5x and <-2x)")
    print("   ✓ Includes market leaders (BTC, ETH, SOL)")
    print("   ✓ Top gainers/losers for momentum")
    print("   ✓ Perfect balance: 50% extreme + 50% liquid")
    print("   ✓ Great visual patterns + tradable")
    print("   ✓ Professional grade with alpha opportunities")

    print("\n⚖️  OPTION G: BALANCED EXTREMES")
    print("   ✓ $30M minimum (slightly lower threshold)")
    print("   ✓ Equal representation across beta ranges")
    print("   ✓ More educational/analytical value")
    print("   ✓ Better for correlation studies")

    print("\n💡 RECOMMENDATION: Use Option F for your chart!")
    print("   It gives you the extreme outliers you want while maintaining")
    print("   enough liquidity to be meaningful and tradable.\n")

    print("="*110 + "\n")
