#!/usr/bin/env python3
"""
Bitcoin Beta HTML Dashboard Generator - BYBIT ONLY VERSION
Creates interactive HTML with 10 different Bitcoin Beta visualizations using only Bybit data
"""

import sys
import os

# Add deprecated directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deprecated'))

import requests
import json
from datetime import datetime, timezone
from typing import Dict, List
from collections import defaultdict
import time


def fetch_symbol_data_from_bybit_only() -> Dict[str, List[Dict]]:
    """
    Fetch data from Bybit only and group by symbol

    Returns:
        Dict mapping symbol -> list of exchange data for that symbol
    """
    symbol_data = defaultdict(list)

    print("   📊 Fetching data from Bybit...")

    # Fetch only from Bybit
    try:
        results = fetch_bybit_symbols()
        print(f"      ✓ Fetched {len(results)} symbols from Bybit")

        # Group by symbol
        for item in results:
            symbol = normalize_symbol(item['symbol'])
            if symbol:  # Skip empty symbols
                symbol_data[symbol].append(item)

    except Exception as e:
        print(f"      ❌ Error fetching Bybit data: {e}")

    return dict(symbol_data)


if __name__ == "__main__":
    print("\n🚀 Generating Bitcoin Beta HTML Dashboard (BYBIT ONLY)...\n")
    print("⏳ Fetching data from Bybit...\n")

    # Fetch Bybit-only data
    symbol_data = fetch_symbol_data_from_bybit_only()

    print(f"\n✅ Collected data for {len(symbol_data)} symbols from Bybit\n")

    # Get BTC price change for beta calculation
    btc_data = symbol_data.get('BTC', [])
    btc_price_change = None
    if btc_data:
        btc_changes = [d.get('price_change_pct') for d in btc_data if d.get('price_change_pct') is not None]
        if btc_changes:
            btc_price_change = sum(btc_changes) / len(btc_changes)
            print(f"📊 BTC 24h change: {btc_price_change:+.2f}% (using for beta calculation)\n")

    # Analyze symbols
    print("🔍 Analyzing symbols...\n")
    analyses = []
    for symbol, data in symbol_data.items():
        analysis = analyze_symbol(symbol, data, btc_price_change=btc_price_change)
        if analysis:
            analyses.append(analysis)

    # Sort by volume
    analyses.sort(key=lambda x: x['total_volume_24h'], reverse=True)

    print(f"✅ Analyzed {len(analyses)} symbols\n")

    # Fetch historical data for top 25 symbols (including BTC)
    print("📈 Fetching historical price data for top 25 symbols...\n")
    top_symbols = ['BTC'] + [a['symbol'] for a in analyses[:24] if a['symbol'] != 'BTC']
    historical_data = fetch_historical_data_for_symbols(top_symbols, limit=24)
    print(f"\n✅ Fetched historical data for {len(historical_data)} symbols\n")

    # Generate HTML
    print("🎨 Generating Bitcoin Beta dashboard (Bybit data)...\n")
    html_content = generate_beta_html_dashboard(analyses, btc_price_change, historical_data)

    # Modify the title to indicate Bybit-only
    html_content = html_content.replace(
        '<h1>₿ BITCOIN BETA ANALYSIS</h1>',
        '<h1>₿ BITCOIN BETA ANALYSIS - BYBIT ONLY</h1>'
    )
    html_content = html_content.replace(
        '<div class="subtitle">Multi-Dimensional Correlation Dashboard</div>',
        '<div class="subtitle">Multi-Dimensional Correlation Dashboard (Bybit Exchange)</div>'
    )

    # Save HTML
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

    # Get project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')

    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)

    filename = os.path.join(data_dir, f"bitcoin_beta_dashboard_bybit_only_{timestamp}.html")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Bitcoin Beta Dashboard (Bybit Only) saved to: {filename}")
        print(f"\n🌐 Open in browser to explore 10 different beta visualizations!")

        # Try to open in browser
        import webbrowser
        filepath = os.path.abspath(filename)
        webbrowser.open('file://' + filepath)
        print(f"🔥 Opening in browser...")

    except Exception as e:
        print(f"⚠️  Could not save HTML: {e}")
