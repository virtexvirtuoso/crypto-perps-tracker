"""Market dominance and concentration analysis

Analyzes market structure including:
- Exchange market share
- Market concentration (HHI index)
- CEX vs DEX distribution
"""

from typing import Dict, List


def calculate_market_dominance(results: List[Dict]) -> Dict:
    """Calculate market dominance and concentration metrics

    Analyzes the market structure to identify:
    1. Top 3 exchange concentration
    2. Herfindahl-Hirschman Index (HHI) for market concentration
    3. CEX vs DEX market share

    The HHI measures market concentration:
    - HHI < 1500: Low concentration (competitive market)
    - HHI 1500-2500: Moderate concentration
    - HHI > 2500: High concentration (oligopoly)

    Args:
        results: List of market data dictionaries from exchanges

    Returns:
        Dictionary containing:
        - top3_concentration: % of volume in top 3 exchanges
        - hhi: Herfindahl-Hirschman Index
        - concentration_level: "High", "Moderate", or "Low"
        - cex_dominance: % of volume on CEX platforms
        - dex_share: % of volume on DEX platforms
        - leaders: Top exchanges by volume with their shares
    """
    successful = [r for r in results if r.get('status') == 'success']
    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

    sorted_by_volume = sorted(successful, key=lambda x: x['volume'], reverse=True)

    # Calculate top 3 concentration
    top3_volume = sum(r['volume'] for r in sorted_by_volume[:3])
    top3_concentration = (top3_volume / total_volume) * 100

    # Calculate Herfindahl-Hirschman Index (HHI)
    # HHI = sum of squared market shares
    hhi = sum((r['volume'] / total_volume * 100) ** 2 for r in successful)

    # Calculate CEX vs DEX distribution
    cex_volume = sum(r['volume'] for r in successful if r['type'] == 'CEX')
    dex_volume = sum(r['volume'] for r in successful if r['type'] == 'DEX')

    return {
        'top3_concentration': top3_concentration,
        'hhi': hhi,
        'concentration_level': 'High' if hhi > 2500 else 'Moderate' if hhi > 1500 else 'Low',
        'cex_dominance': (cex_volume / total_volume) * 100,
        'dex_share': (dex_volume / total_volume) * 100,
        'leaders': [
            {
                'exchange': r['exchange'],
                'volume': r['volume'],
                'share': (r['volume'] / total_volume) * 100
            }
            for r in sorted_by_volume[:3]
        ]
    }
