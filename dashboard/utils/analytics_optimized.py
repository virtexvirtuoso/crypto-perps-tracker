"""
Optimized Dashboard Analytics with Caching
Provides performance-optimized analytics functions for the dashboard
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Dict, List
import numpy as np

from src.container import Container
from src.models.market import SymbolData
from scripts.generate_symbol_report import (
    normalize_symbol,
    get_exchange_name,
    analyze_symbol,
    fetch_all_symbols_from_exchanges
)
from dashboard.utils.cache import cached, dashboard_cache
from scripts.generate_symbol_report import (
    fetch_historical_data_for_symbols,
    generate_bitcoin_beta_chart_timeseries
)


@cached(ttl_seconds=30)
def get_symbol_analytics_cached(container: Container, top_n: int = 20) -> List[Dict]:
    """
    Get comprehensive symbol analytics with caching

    Cache key: Based on top_n parameter
    Cache TTL: 30 seconds

    Returns list of analyzed symbols sorted by volume
    """
    print(f"🔄 Fetching fresh symbol analytics (top_n={top_n})...")

    # Fetch BTC price change for beta calculation
    btc_price_change = None
    try:
        btc_symbols = container.exchange_service.fetch_symbol_across_exchanges('BTCUSDT', use_cache=True)
        if btc_symbols:
            btc_changes = [s.price_change_24h_pct for s in btc_symbols if s.price_change_24h_pct is not None]
            if btc_changes:
                btc_price_change = sum(btc_changes) / len(btc_changes)
    except:
        pass

    # Fetch all symbols from all exchanges
    symbol_data = fetch_all_symbols_from_exchanges(container)

    # Analyze each symbol
    analyses = []
    for symbol, exchange_data in symbol_data.items():
        analysis = analyze_symbol(symbol, exchange_data, btc_price_change)
        if analysis:
            analyses.append(analysis)

    # Sort by volume
    analyses.sort(key=lambda x: x['total_volume_24h'], reverse=True)

    print(f"✅ Analyzed {len(analyses)} symbols")
    return analyses[:top_n]


def get_symbol_analytics(container: Container, top_n: int = 20) -> List[Dict]:
    """
    Get symbol analytics - uses cached version with 30s TTL
    This is a wrapper to maintain API compatibility
    """
    return get_symbol_analytics_cached(container, top_n)


def get_market_summary(analyses: List[Dict]) -> Dict:
    """Get summary statistics (fast, no API calls)"""
    if not analyses:
        return {}

    total_volume = sum(a['total_volume_24h'] for a in analyses)
    total_oi = sum(a['total_open_interest'] for a in analyses)

    all_exchanges = set()
    for a in analyses:
        all_exchanges.update(a['exchanges'])

    return {
        'total_symbols': len(analyses),
        'total_volume_24h': total_volume,
        'total_open_interest': total_oi,
        'num_exchanges': len(all_exchanges),
        'exchanges': list(all_exchanges)
    }


def get_top_movers(analyses: List[Dict], top_n: int = 10) -> List[Dict]:
    """Get top movers by 24h price change (fast, no API calls)"""
    movers = [a for a in analyses if a.get('avg_price_change_24h') is not None]
    movers.sort(key=lambda x: abs(x['avg_price_change_24h']), reverse=True)
    return movers[:top_n]


def get_arbitrage_opportunities(analyses: List[Dict], min_spread: float = 0.2) -> List[Dict]:
    """Get arbitrage opportunities (fast, no API calls)"""
    opportunities = [
        a for a in analyses
        if a.get('arbitrage_opportunity') and a['price_spread_pct'] > min_spread
    ]
    opportunities.sort(key=lambda x: x['price_spread_pct'], reverse=True)
    return opportunities


def get_funding_extremes(analyses: List[Dict]) -> Dict:
    """Get funding rate extremes (fast, no API calls)"""
    with_funding = [a for a in analyses if a.get('avg_funding_rate') is not None]

    if not with_funding:
        return {'highest': [], 'lowest': []}

    sorted_by_funding = sorted(with_funding, key=lambda x: x['avg_funding_rate'])

    return {
        'lowest': sorted_by_funding[:10],  # Best for longs
        'highest': sorted_by_funding[-10:][::-1]  # Best for shorts
    }


def get_chart_data_optimized(analyses: List[Dict], chart_type: str, limit: int = 10) -> Dict:
    """
    Get optimized chart data without creating Plotly figures
    Returns raw data that can be used to create charts on-demand

    Args:
        analyses: List of analyzed symbols
        chart_type: 'beta', 'volume', 'funding'
        limit: Number of data points

    Returns:
        Dict with x, y, colors, and other chart data
    """
    if chart_type == 'beta':
        data = [(a['symbol'], a['bitcoin_beta'])
                for a in analyses
                if a.get('bitcoin_beta') is not None]
        data.sort(key=lambda x: abs(x[1]), reverse=True)
        data = data[:limit]

        symbols = [d[0] for d in data]
        values = [d[1] for d in data]
        colors = ['#00ff00' if v > 0 else '#ff6b6b' for v in values]

        return {
            'type': 'bar',
            'orientation': 'h',
            'x': values,
            'y': symbols,
            'colors': colors,
            'title': 'Bitcoin Beta Correlation',
            'xaxis_title': 'Beta Coefficient'
        }

    elif chart_type == 'volume':
        data = [(a['symbol'], a['total_volume_24h']) for a in analyses[:limit]]
        return {
            'type': 'bar',
            'x': [d[0] for d in data],
            'y': [d[1]/1e6 for d in data],  # Convert to millions
            'colors': ['#FFA500'] * len(data),
            'title': f'Top {limit} Symbols by Volume',
            'yaxis_title': 'Volume (Millions USD)'
        }

    elif chart_type == 'funding':
        data = [(a['symbol'], a.get('avg_funding_rate', 0) * 100)
                for a in analyses[:limit]
                if a.get('avg_funding_rate') is not None]

        symbols = [d[0] for d in data]
        rates = [d[1] for d in data]
        colors = ['#ff6b6b' if r > 0 else '#00ff00' for r in rates]

        return {
            'type': 'bar',
            'x': symbols,
            'y': rates,
            'colors': colors,
            'title': 'Average Funding Rates',
            'yaxis_title': 'Funding Rate (%)'
        }

    return {}


@cached(ttl_seconds=300)  # 5 minute cache for historical data
def get_performance_chart_data(container: Container, analyses: List[Dict], top_n: int = 30) -> bytes:
    """
    Fetch historical data and generate time-series performance chart

    Cache TTL: 5 minutes (historical data doesn't change that often)
    Returns: PNG chart bytes
    """
    print(f"🔄 Generating 12h performance chart for top {top_n} symbols...")

    # Get top symbols
    top_symbols = [a['symbol'] for a in analyses[:top_n]]

    # Fetch 12h historical data
    historical_data = fetch_historical_data_for_symbols(top_symbols, limit=12)

    if not historical_data:
        print("⚠️  No historical data available")
        return None

    # Generate chart
    chart_bytes = generate_bitcoin_beta_chart_timeseries(analyses, historical_data)
    print(f"✅ Performance chart generated ({len(historical_data)} symbols)")

    return chart_bytes


@cached(ttl_seconds=300)  # 5 minute cache for historical data
def get_performance_chart_plotly(container: Container, analyses: List[Dict], top_n: int = 30) -> Dict:
    """
    Fetch historical data and generate interactive Plotly time-series performance chart

    Cache TTL: 5 minutes (historical data doesn't change that often)
    Returns: Dict with Plotly traces and layout data
    """
    print(f"🔄 Generating interactive 12h performance chart for top {top_n} symbols...")

    # Get top symbols
    top_symbols = [a['symbol'] for a in analyses[:top_n]]

    # Fetch 12h historical data
    historical_data = fetch_historical_data_for_symbols(top_symbols, limit=12)

    if not historical_data:
        print("⚠️  No historical data available")
        return None

    # Create beta lookup
    beta_lookup = {a['symbol']: a.get('btc_beta', 1.0) for a in analyses}

    # Color palette (excluding orange for BTC)
    color_palette = [
        '#00FF7F', '#FF1493', '#00CED1', '#FFD700', '#FF6347',
        '#7B68EE', '#FF69B4', '#20B2AA', '#FF8C00', '#9370DB',
        '#32CD32', '#FF4500', '#00BFFF', '#ADFF2F', '#FF00FF',
        '#00FA9A', '#DC143C', '#00FFFF', '#7FFF00', '#FF6B6B',
        '#4ECDC4', '#95E1D3', '#F38181', '#AA96DA', '#FCBAD3',
        '#A8D8EA', '#FFCFDF', '#FEFDCA', '#E7CBA9', '#EEBEFA'
    ]

    traces = []
    symbol_data = []
    color_index = 0

    # Plot each symbol
    for symbol, candles in historical_data.items():
        if not candles:
            continue

        # Normalize to percentage change from first candle
        initial_price = candles[0]['close']
        from datetime import datetime
        timestamps = [datetime.fromtimestamp(c['timestamp'] / 1000) for c in candles]
        percent_changes = [((c['close'] - initial_price) / initial_price) * 100 for c in candles]

        # Get color
        if symbol == 'BTC':
            color = '#FFA500'
            linewidth = 4
        else:
            color = color_palette[color_index % len(color_palette)]
            color_index += 1
            linewidth = 2

        # Store final performance
        final_perf = percent_changes[-1] if percent_changes else 0
        symbol_data.append({
            'symbol': symbol,
            'final_perf': final_perf,
            'color': color
        })

        # Create trace
        trace = {
            'x': timestamps,
            'y': percent_changes,
            'mode': 'lines',
            'name': f'{symbol} {final_perf:+.1f}%',
            'line': {
                'color': color,
                'width': linewidth
            },
            'hovertemplate': f'<b>{symbol}</b><br>%{{x|%H:%M}}<br>%{{y:.2f}}%<extra></extra>'
        }

        traces.append(trace)

    # Sort traces by final performance (high to low)
    symbol_data.sort(key=lambda d: d['final_perf'], reverse=True)

    # Calculate market summary
    outperformers = len([d for d in symbol_data if d['final_perf'] > 1.0])
    underperformers = len([d for d in symbol_data if d['final_perf'] < -3.0])

    from datetime import datetime, timezone
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    print(f"✅ Interactive performance chart generated ({len(historical_data)} symbols)")

    return {
        'traces': traces,
        'outperformers': outperformers,
        'underperformers': underperformers,
        'current_time': current_time,
        'total_symbols': len(symbol_data)
    }


def clear_analytics_cache():
    """Clear all analytics cache - call this if you need fresh data immediately"""
    if hasattr(get_symbol_analytics_cached, 'cache'):
        get_symbol_analytics_cached.cache.clear()
    if hasattr(get_performance_chart_data, 'cache'):
        get_performance_chart_data.cache.clear()
    dashboard_cache.clear()
    print("🗑️  Analytics cache cleared")
