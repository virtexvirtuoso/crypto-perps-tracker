#!/usr/bin/env python3
"""
Spot-Futures Basis Calculator
Combines spot and futures data to calculate basis, arbitrage opportunities,
and market health metrics
"""

import sys
sys.path.append('.')

from scripts.fetch_spot_markets import fetch_all_spot_markets
from scripts.compare_all_exchanges import fetch_all_enhanced
from typing import Dict, List
from datetime import datetime, timezone


def calculate_basis_metrics(spot_price: float, futures_price: float, funding_rate: float = None) -> Dict:
    """
    Calculate comprehensive basis metrics

    Args:
        spot_price: Current spot price
        futures_price: Current perpetual futures price
        funding_rate: Hourly funding rate (optional)

    Returns:
        Dictionary with basis metrics
    """
    basis_absolute = futures_price - spot_price
    basis_pct = (basis_absolute / spot_price) * 100

    # Annualized basis (assuming daily settlement)
    basis_annual = basis_pct * 365

    metrics = {
        'spot_price': spot_price,
        'futures_price': futures_price,
        'basis_absolute': basis_absolute,
        'basis_pct': basis_pct,
        'basis_annual_pct': basis_annual,
        'premium_discount': 'PREMIUM' if basis_absolute > 0 else 'DISCOUNT' if basis_absolute < 0 else 'NEUTRAL',
        'market_structure': 'CONTANGO' if basis_absolute > 0 else 'BACKWARDATION' if basis_absolute < 0 else 'FLAT'
    }

    # Add funding rate comparison if available
    if funding_rate is not None:
        # Convert funding rate to same timeframe as basis for comparison
        funding_hourly_pct = funding_rate
        funding_daily_pct = funding_rate * 24
        funding_annual_pct = funding_rate * 24 * 365

        metrics['funding_rate_hourly'] = funding_hourly_pct
        metrics['funding_rate_annual'] = funding_annual_pct

        # Funding-basis spread (important for arbitrage)
        # If funding > basis, perpetuals are expensive relative to spot
        metrics['funding_basis_spread'] = funding_hourly_pct - basis_pct
        metrics['arbitrage_signal'] = 'BUY_SPOT_SHORT_PERP' if metrics['funding_basis_spread'] > 0.01 else \
                                      'BUY_PERP_SHORT_SPOT' if metrics['funding_basis_spread'] < -0.01 else \
                                      'NEUTRAL'

    return metrics


def analyze_spot_futures_market(spot_results: List[Dict], futures_results: List[Dict]) -> List[Dict]:
    """
    Analyze spot-futures relationships across all exchanges

    Returns list of basis analysis for each exchange
    """
    analysis = []

    # Create lookup dictionaries
    spot_lookup = {r['exchange']: r for r in spot_results if r.get('status') == 'success'}
    futures_lookup = {r['exchange']: r for r in futures_results if r.get('status') == 'success'}

    # Find common exchanges
    common_exchanges = set(spot_lookup.keys()) & set(futures_lookup.keys())

    for exchange in common_exchanges:
        spot_data = spot_lookup[exchange]
        futures_data = futures_lookup[exchange]

        basis_metrics = calculate_basis_metrics(
            spot_price=spot_data['price'],
            futures_price=futures_data.get('funding_rate', 0) * 100 + spot_data['price'],  # Approximate futures price from spot + implied premium
            funding_rate=futures_data.get('funding_rate')
        )

        analysis.append({
            'exchange': exchange,
            **basis_metrics,
            'spot_volume': spot_data['volume_24h'],
            'futures_volume': futures_data.get('volume', 0),
            'volume_ratio': futures_data.get('volume', 0) / spot_data['volume_24h'] if spot_data['volume_24h'] > 0 else None,
            'spot_spread_pct': spot_data.get('spread_pct', 0),
        })

    return analysis


def detect_arbitrage_opportunities(analysis: List[Dict], min_profit_pct: float = 0.05) -> List[Dict]:
    """
    Detect profitable cash-and-carry or reverse cash-and-carry arbitrage

    Args:
        analysis: List of basis analysis results
        min_profit_pct: Minimum profit percentage to flag as opportunity

    Returns:
        List of arbitrage opportunities
    """
    opportunities = []

    for item in analysis:
        # Cash-and-carry: Buy spot, sell futures
        # Profitable when basis + funding > fees
        if item.get('basis_pct', 0) > min_profit_pct:
            expected_return = item['basis_pct'] + (item.get('funding_rate_annual', 0) or 0)
            if expected_return > min_profit_pct:
                opportunities.append({
                    'exchange': item['exchange'],
                    'type': 'CASH_AND_CARRY',
                    'action': f"Buy {item['exchange']} Spot / Sell {item['exchange']} Futures",
                    'spot_price': item['spot_price'],
                    'futures_price': item['futures_price'],
                    'basis_capture': item['basis_pct'],
                    'funding_yield_annual': item.get('funding_rate_annual', 0),
                    'total_expected_return': expected_return,
                    'risk': 'LOW (Hedged position)',
                    'capital_required': '$10,000+',
                })

        # Reverse cash-and-carry: Sell spot (or synthetic), buy futures
        # Profitable when negative basis exceeds costs
        elif item.get('basis_pct', 0) < -min_profit_pct:
            expected_return = abs(item['basis_pct']) - (item.get('funding_rate_annual', 0) or 0)
            if expected_return > min_profit_pct:
                opportunities.append({
                    'exchange': item['exchange'],
                    'type': 'REVERSE_CASH_AND_CARRY',
                    'action': f"Sell {item['exchange']} Spot / Buy {item['exchange']} Futures",
                    'spot_price': item['spot_price'],
                    'futures_price': item['futures_price'],
                    'basis_capture': abs(item['basis_pct']),
                    'funding_cost_annual': item.get('funding_rate_annual', 0),
                    'total_expected_return': expected_return,
                    'risk': 'MEDIUM (Rare condition)',
                    'capital_required': '$10,000+',
                })

    # Sort by expected return
    opportunities.sort(key=lambda x: x['total_expected_return'], reverse=True)

    return opportunities


def format_basis_report(spot_results: List[Dict], futures_results: List[Dict]) -> str:
    """Format comprehensive spot-futures basis report"""
    analysis = analyze_spot_futures_market(spot_results, futures_results)
    opportunities = detect_arbitrage_opportunities(analysis)

    output = []
    output.append("\n" + "="*120)
    output.append(f"{'SPOT-FUTURES BASIS ANALYSIS':^120}")
    output.append(f"{'Updated: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'):^120}")
    output.append("="*120)

    if not analysis:
        output.append("\n⚠️  No common exchanges between spot and futures data")
        return "\n".join(output)

    # Basis metrics table
    output.append(f"\n{'Exchange':<15}{'Spot':<12}{'Futures':<12}{'Basis':<10}{'Annual':<10}{'Structure':<15}{'Signal'}")
    output.append("-"*120)

    for item in analysis:
        spot_str = f"${item['spot_price']:,.2f}"
        futures_str = f"${item['futures_price']:,.2f}"
        basis_str = f"{item['basis_pct']:>+6.3f}%"
        annual_str = f"{item.get('basis_annual_pct', 0):>+6.2f}%"
        structure = item['market_structure']

        # Color coding for basis
        if item['basis_pct'] > 0.15:
            signal = "🟢 LONG BIAS"
        elif item['basis_pct'] < -0.15:
            signal = "🔴 SHORT BIAS"
        else:
            signal = "⚪ NEUTRAL"

        output.append(f"{item['exchange']:<15}{spot_str:<12}{futures_str:<12}{basis_str:<10}{annual_str:<10}{structure:<15}{signal}")

    # Market summary
    avg_basis = sum(item['basis_pct'] for item in analysis) / len(analysis)
    max_basis = max(item['basis_pct'] for item in analysis)
    min_basis = min(item['basis_pct'] for item in analysis)

    output.append("\n" + "="*120)
    output.append("📊 MARKET SUMMARY")
    output.append("="*120)
    output.append(f"Average Basis:         {avg_basis:+.4f}% ({'CONTANGO' if avg_basis > 0 else 'BACKWARDATION'})")
    output.append(f"Basis Range:           {min_basis:+.4f}% to {max_basis:+.4f}%")
    output.append(f"Market Structure:      {'HEALTHY' if abs(avg_basis) < 0.2 else 'SPECULATIVE' if avg_basis > 0.5 else 'UNUSUAL'}")
    output.append(f"Exchanges Analyzed:    {len(analysis)}")

    # Arbitrage opportunities
    if opportunities:
        output.append("\n" + "="*120)
        output.append("💰 ARBITRAGE OPPORTUNITIES")
        output.append("="*120)

        for i, opp in enumerate(opportunities[:3], 1):  # Show top 3
            output.append(f"\n{i}. {opp['type']} - {opp['exchange']}")
            output.append(f"   Action: {opp['action']}")
            output.append(f"   Basis Capture: {opp['basis_capture']:.3f}%")
            if 'funding_yield_annual' in opp:
                output.append(f"   Funding Yield: {opp['funding_yield_annual']:.2f}% annual")
            output.append(f"   Total Expected Return: {opp['total_expected_return']:.2f}% annual")
            output.append(f"   Risk: {opp['risk']}")
    else:
        output.append("\n✅ No significant arbitrage opportunities (basis < 0.05% threshold)")

    # Volume ratio analysis
    output.append("\n" + "="*120)
    output.append("📈 SPOT VS FUTURES VOLUME")
    output.append("="*120)
    output.append(f"{'Exchange':<15}{'Spot Vol':<18}{'Futures Vol':<18}{'Ratio':<12}{'Interpretation'}")
    output.append("-"*120)

    for item in analysis:
        if item['volume_ratio']:
            spot_vol_str = f"${item['spot_volume']/1e9:.2f}B" if item['spot_volume'] > 1e9 else f"${item['spot_volume']/1e6:.0f}M"
            futures_vol_str = f"${item['futures_volume']/1e9:.2f}B" if item['futures_volume'] > 1e9 else f"${item['futures_volume']/1e6:.0f}M"
            ratio_str = f"{item['volume_ratio']:.2f}x"

            if item['volume_ratio'] > 3.0:
                interpretation = "🔴 HIGH LEVERAGE (Speculative)"
            elif item['volume_ratio'] < 1.5:
                interpretation = "🟢 SPOT DOMINANT (Institutional)"
            else:
                interpretation = "⚪ BALANCED (Healthy)"

            output.append(f"{item['exchange']:<15}{spot_vol_str:<18}{futures_vol_str:<18}{ratio_str:<12}{interpretation}")

    output.append("\n" + "="*120)
    output.append("\nKEY INSIGHTS:")
    output.append("• Basis = Futures Price - Spot Price (shows market premium/discount)")
    output.append("• Contango (positive basis) = Market expects higher prices")
    output.append("• Backwardation (negative basis) = Market expects lower prices")
    output.append("• High volume ratio (>3x) = Speculation dominant, liquidation risk")
    output.append("• Low volume ratio (<1.5x) = Real demand, institutional buying")
    output.append("\n")

    return "\n".join(output)


if __name__ == "__main__":
    print("\n🔍 Analyzing spot-futures basis across all exchanges...\n")
    print("⏳ Fetching data (10-15 seconds)...\n")

    # Fetch both spot and futures data
    spot_results = fetch_all_spot_markets()
    futures_results = fetch_all_enhanced()

    # Generate basis report
    report = format_basis_report(spot_results, futures_results)
    print(report)
