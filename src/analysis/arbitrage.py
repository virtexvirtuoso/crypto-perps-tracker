"""Arbitrage opportunity identification

Identifies potential arbitrage opportunities across exchanges based on:
- Funding rate spreads
- Price discrepancies
- Volume imbalances
"""

from typing import Dict, List


def identify_arbitrage_opportunities(results: List[Dict]) -> List[Dict]:
    """Identify potential arbitrage opportunities based on funding rate spreads

    Analyzes funding rate differences between exchanges to find profitable
    arbitrage opportunities. A profitable arbitrage exists when you can:
    1. Short the exchange with high funding rate (collect funding)
    2. Long the exchange with low funding rate (pay less funding)
    3. Net profit = funding rate spread (collected every 8 hours)

    Args:
        results: List of market data dictionaries from exchanges

    Returns:
        List of arbitrage opportunities, sorted by spread (highest first).
        Each opportunity contains:
        - type: Type of arbitrage
        - action: Description of the trade
        - spread: Funding rate spread (%)
        - annual_yield: Annualized return (%)
        - risk: Risk level assessment
        - details: Additional information
    """
    successful = [r for r in results if r.get('status') == 'success' and r.get('funding_rate') is not None]

    if len(successful) < 2:
        return []

    sorted_by_funding = sorted(successful, key=lambda x: x['funding_rate'])

    opportunities = []

    for i, low_fr in enumerate(sorted_by_funding[:-1]):
        for high_fr in sorted_by_funding[i+1:]:
            spread = high_fr['funding_rate'] - low_fr['funding_rate']

            # Only consider spreads > 0.5% (0.005)
            if spread > 0.005:
                opportunities.append({
                    'type': 'Funding Rate Arbitrage',
                    'action': f"Short {high_fr['exchange']} / Long {low_fr['exchange']}",
                    'spread': spread,
                    'annual_yield': spread * 3 * 365,  # 3 funding payments per day
                    'risk': 'Medium' if spread < 0.02 else 'High',
                    'details': f"Collect {spread:.4f}% every 8 hours"
                })

    return sorted(opportunities, key=lambda x: x['spread'], reverse=True)


def analyze_trading_behavior(results: List[Dict]) -> Dict:
    """Analyze trading behavior patterns across exchanges

    Categorizes exchanges based on their OI/Volume ratio:
    - Day trading heavy: Low OI/Vol (< 0.3) - High turnover, low conviction
    - Balanced: Medium OI/Vol (0.3-0.5) - Mixed trading styles
    - Position holding: High OI/Vol (> 0.5) - Low turnover, high conviction

    Args:
        results: List of market data dictionaries from exchanges

    Returns:
        Dictionary with three categories of exchanges
    """
    successful = [r for r in results if r.get('status') == 'success']

    day_traders = []
    balanced = []
    position_holders = []

    for r in successful:
        oi_vol = r.get('oi_volume_ratio')
        if oi_vol is not None:
            if oi_vol < 0.3:
                day_traders.append(r['exchange'])
            elif oi_vol <= 0.5:
                balanced.append(r['exchange'])
            else:
                position_holders.append(r['exchange'])

    return {
        'day_trading_heavy': day_traders,
        'balanced': balanced,
        'position_holding': position_holders
    }


def detect_anomalies(results: List[Dict]) -> List[Dict]:
    """Detect potential wash trading or market anomalies

    Identifies unusual patterns that may indicate:
    - Wash trading (artificially inflated volume)
    - Extreme market conditions
    - Data quality issues

    Args:
        results: List of market data dictionaries from exchanges

    Returns:
        List of detected anomalies with type, indicator, and severity
    """
    successful = [r for r in results if r.get('status') == 'success']
    anomalies = []

    for r in successful:
        # Check for potential wash trading
        if r.get('oi_volume_ratio') and r['oi_volume_ratio'] < 0.15:
            anomalies.append({
                'exchange': r['exchange'],
                'type': 'Potential Wash Trading',
                'indicator': f"Very low OI/Vol ratio: {r['oi_volume_ratio']:.2f}x",
                'severity': 'Medium'
            })

        # Check for extreme funding rates
        if r.get('funding_rate') and abs(r['funding_rate']) > 0.05:
            anomalies.append({
                'exchange': r['exchange'],
                'type': 'Extreme Funding Rate',
                'indicator': f"Funding rate: {r['funding_rate']:.4f}%",
                'severity': 'High'
            })

    return anomalies
