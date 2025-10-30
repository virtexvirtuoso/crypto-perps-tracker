"""
Dashboard Analytics Utilities

Provides analytics functions for the dashboard by wrapping/reusing
functions from generate_symbol_report.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Dict, List
from collections import defaultdict
import numpy as np

from src.container import Container
from src.models.market import SymbolData
from scripts.generate_symbol_report import (
    normalize_symbol,
    get_exchange_name,
    analyze_symbol,
    fetch_all_symbols_from_exchanges
)


def get_symbol_analytics(container: Container, top_n: int = 20) -> List[Dict]:
    """
    Get comprehensive symbol analytics for dashboard display

    Returns list of analyzed symbols sorted by volume, with:
    - Volume, OI, price data
    - Funding rate comparisons
    - Arbitrage opportunities
    - Bitcoin beta
    """
    # Fetch BTC price change for beta calculation
    btc_price_change = None
    try:
        # Try to get BTC from multiple exchanges
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

    return analyses[:top_n]


def get_top_movers(analyses: List[Dict], top_n: int = 10) -> List[Dict]:
    """Get top movers by 24h price change"""
    movers = [a for a in analyses if a.get('avg_price_change_24h') is not None]
    movers.sort(key=lambda x: abs(x['avg_price_change_24h']), reverse=True)
    return movers[:top_n]


def get_arbitrage_opportunities(analyses: List[Dict], min_spread: float = 0.2) -> List[Dict]:
    """Get arbitrage opportunities with spread > min_spread%"""
    opportunities = [
        a for a in analyses
        if a.get('arbitrage_opportunity') and a['price_spread_pct'] > min_spread
    ]
    opportunities.sort(key=lambda x: x['price_spread_pct'], reverse=True)
    return opportunities


def get_funding_extremes(analyses: List[Dict]) -> Dict:
    """Get symbols with extreme funding rates"""
    with_funding = [a for a in analyses if a.get('avg_funding_rate') is not None]

    if not with_funding:
        return {'highest': [], 'lowest': []}

    sorted_by_funding = sorted(with_funding, key=lambda x: x['avg_funding_rate'])

    return {
        'lowest': sorted_by_funding[:10],  # Best for longs
        'highest': sorted_by_funding[-10:][::-1]  # Best for shorts
    }


def get_market_summary(analyses: List[Dict]) -> Dict:
    """Get summary statistics across all analyzed symbols"""
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
