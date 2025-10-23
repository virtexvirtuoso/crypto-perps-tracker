#!/usr/bin/env python3
"""
Liquidation Data Fetcher
Fetches recent liquidation data from exchanges to detect cascade risks

Supports:
- Binance (via forceOrders endpoint)
- More exchanges can be added as APIs become available

Usage:
    python3 scripts/fetch_liquidations.py                    # Fetch and display
    python3 scripts/fetch_liquidations.py --exchange binance # Specific exchange
    python3 scripts/fetch_liquidations.py --hours 24         # Last 24 hours

Returns liquidation metrics for integration with strategy alerts
"""

import requests
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


def fetch_binance_liquidations(hours: int = 1, limit: int = 1000) -> Dict:
    """
    Fetch recent liquidations from Binance Futures

    Args:
        hours: Number of hours to look back
        limit: Maximum number of liquidations to fetch (max 1000 per request)

    Returns:
        {
            'exchange': 'Binance',
            'total_liquidations_usd': float,
            'long_liquidations': float,
            'short_liquidations': float,
            'liquidation_count': int,
            'long_short_liq_ratio': float,
            'status': 'success'|'error'
        }
    """
    try:
        # Binance Force Orders (Liquidations) endpoint
        url = "https://fapi.binance.com/fapi/v1/allForceOrders"

        # Calculate start time (milliseconds)
        start_time = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)

        params = {
            'startTime': start_time,
            'limit': limit
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return {
                'exchange': 'Binance',
                'status': 'error',
                'error': f"HTTP {response.status_code}: {response.text}"
            }

        liquidations = response.json()

        if not isinstance(liquidations, list):
            return {
                'exchange': 'Binance',
                'status': 'error',
                'error': f"Unexpected response: {liquidations}"
            }

        # Parse and aggregate liquidations
        total_liq_usd = 0
        long_liq_usd = 0
        short_liq_usd = 0
        long_count = 0
        short_count = 0

        for liq in liquidations:
            # Extract values
            qty = float(liq.get('origQty', 0))
            price = float(liq.get('price', 0))
            value_usd = qty * price
            side = liq.get('side', '')

            total_liq_usd += value_usd

            # SELL = Long position liquidated (forced to sell)
            # BUY = Short position liquidated (forced to buy)
            if side == 'SELL':
                long_liq_usd += value_usd
                long_count += 1
            elif side == 'BUY':
                short_liq_usd += value_usd
                short_count += 1

        # Calculate ratio (handle division by zero)
        if short_liq_usd > 0:
            liq_ratio = long_liq_usd / short_liq_usd
        elif long_liq_usd > 0:
            liq_ratio = float('inf')  # Only longs liquidated
        else:
            liq_ratio = 1.0  # No liquidations

        return {
            'exchange': 'Binance',
            'total_liquidations_usd': total_liq_usd,
            'long_liquidations': long_liq_usd,
            'short_liquidations': short_liq_usd,
            'liquidation_count': len(liquidations),
            'long_count': long_count,
            'short_count': short_count,
            'long_short_liq_ratio': liq_ratio,
            'time_period_hours': hours,
            'status': 'success'
        }

    except requests.exceptions.Timeout:
        return {
            'exchange': 'Binance',
            'status': 'error',
            'error': 'Request timeout'
        }
    except requests.exceptions.RequestException as e:
        return {
            'exchange': 'Binance',
            'status': 'error',
            'error': f'Request failed: {str(e)}'
        }
    except Exception as e:
        return {
            'exchange': 'Binance',
            'status': 'error',
            'error': f'Unexpected error: {str(e)}'
        }


def fetch_bybit_liquidations(hours: int = 1) -> Dict:
    """
    Fetch Bybit liquidations

    Note: Bybit v5 API doesn't have a public liquidation endpoint
    Alternative: Use trade history with large quantities as proxy

    Returns:
        Dict with status='not_available' until API access is added
    """
    # TODO: Implement when Bybit provides public liquidation data
    # Current v5 API limitations:
    # - executions endpoint requires authentication
    # - No public liquidation feed

    return {
        'exchange': 'Bybit',
        'status': 'not_available',
        'error': 'Bybit public liquidation API not available'
    }


def fetch_okx_liquidations(hours: int = 1) -> Dict:
    """
    Fetch OKX liquidations

    Note: OKX has liquidation history but may require authentication

    Returns:
        Dict with liquidation data or error status
    """
    # TODO: Implement OKX liquidation fetching
    # Endpoint: /api/v5/public/liquidation-orders

    return {
        'exchange': 'OKX',
        'status': 'not_available',
        'error': 'OKX liquidation fetching not yet implemented'
    }


def fetch_all_liquidations(hours: int = 1) -> List[Dict]:
    """
    Fetch liquidations from all supported exchanges

    Args:
        hours: Number of hours to look back

    Returns:
        List of liquidation dicts from each exchange
    """
    return [
        fetch_binance_liquidations(hours=hours),
        fetch_bybit_liquidations(hours=hours),
        fetch_okx_liquidations(hours=hours)
    ]


def calculate_liquidation_metrics(liquidation_data: List[Dict], market_volume: float) -> Dict:
    """
    Calculate aggregate liquidation metrics and cascade risk score

    Args:
        liquidation_data: List of liquidation dicts from exchanges
        market_volume: Total 24h market volume for ratio calculation

    Returns:
        {
            'total_liquidations': float,
            'long_liquidations': float,
            'short_liquidations': float,
            'liquidation_volume_ratio': float,
            'long_liquidation_bias': bool,
            'cascade_risk_score': float (0-1),
            'risk_level': str
        }
    """
    # Aggregate successful fetches
    successful = [d for d in liquidation_data if d.get('status') == 'success']

    total_liq = sum(d.get('total_liquidations_usd', 0) for d in successful)
    total_long_liq = sum(d.get('long_liquidations', 0) for d in successful)
    total_short_liq = sum(d.get('short_liquidations', 0) for d in successful)
    total_count = sum(d.get('liquidation_count', 0) for d in successful)

    # Calculate liquidation/volume ratio
    liq_vol_ratio = total_liq / market_volume if market_volume > 0 else 0

    # Determine long/short bias
    long_bias = total_long_liq > total_short_liq

    # ========================================
    # CASCADE RISK SCORE CALCULATION (0-1)
    # ========================================
    # Higher score = higher risk of liquidation cascade

    cascade_score = 0.0

    # Factor 1: Liquidation Volume Ratio (0-0.4 weight)
    # High liquidations relative to volume = elevated risk
    if liq_vol_ratio > 0.05:  # >5% liquidations
        cascade_score += 0.4
    elif liq_vol_ratio > 0.03:  # 3-5%
        cascade_score += 0.3
    elif liq_vol_ratio > 0.01:  # 1-3%
        cascade_score += 0.2
    elif liq_vol_ratio > 0.005:  # 0.5-1%
        cascade_score += 0.1

    # Factor 2: Directional Imbalance (0-0.3 weight)
    # Extreme one-sided liquidations = higher cascade risk
    if total_liq > 0:
        long_pct = total_long_liq / total_liq
        imbalance = abs(long_pct - 0.5)  # Deviation from balanced (0.5 = balanced)

        if imbalance > 0.40:  # >90% one-sided
            cascade_score += 0.3
        elif imbalance > 0.30:  # 80-90% one-sided
            cascade_score += 0.25
        elif imbalance > 0.20:  # 70-80% one-sided
            cascade_score += 0.2
        elif imbalance > 0.10:  # 60-70% one-sided
            cascade_score += 0.1

    # Factor 3: Absolute Liquidation Size (0-0.3 weight)
    # Large absolute liquidation amounts = systemic risk
    if total_liq > 1e9:  # >$1B
        cascade_score += 0.3
    elif total_liq > 500e6:  # $500M-$1B
        cascade_score += 0.25
    elif total_liq > 100e6:  # $100M-$500M
        cascade_score += 0.2
    elif total_liq > 50e6:  # $50M-$100M
        cascade_score += 0.15
    elif total_liq > 10e6:  # $10M-$50M
        cascade_score += 0.1

    # Cap at 1.0
    cascade_score = min(cascade_score, 1.0)

    # Determine risk level
    if cascade_score > 0.7:
        risk_level = 'CRITICAL'
    elif cascade_score > 0.5:
        risk_level = 'HIGH'
    elif cascade_score > 0.3:
        risk_level = 'MODERATE'
    else:
        risk_level = 'LOW'

    return {
        'total_liquidations': total_liq,
        'long_liquidations': total_long_liq,
        'short_liquidations': total_short_liq,
        'liquidation_count': total_count,
        'liquidation_volume_ratio': liq_vol_ratio,
        'long_liquidation_bias': long_bias,
        'cascade_risk_score': cascade_score,
        'risk_level': risk_level,
        'exchanges_reporting': len(successful)
    }


def display_liquidation_report(liquidation_data: List[Dict], market_volume: float = None):
    """Display formatted liquidation report"""
    print("\n" + "="*80)
    print("⚠️  LIQUIDATION REPORT")
    print("="*80)

    for liq in liquidation_data:
        exchange = liq.get('exchange', 'Unknown')
        status = liq.get('status', 'unknown')

        print(f"\n{'─'*80}")
        print(f"Exchange: {exchange}")
        print(f"{'─'*80}")

        if status == 'success':
            total = liq.get('total_liquidations_usd', 0)
            long_liq = liq.get('long_liquidations', 0)
            short_liq = liq.get('short_liquidations', 0)
            count = liq.get('liquidation_count', 0)
            ratio = liq.get('long_short_liq_ratio', 0)

            print(f"Status:              ✅ Success")
            print(f"Time Period:         {liq.get('time_period_hours', 1)} hour(s)")
            print(f"Total Liquidations:  ${total/1e6:.2f}M")
            print(f"  • Long Liq:        ${long_liq/1e6:.2f}M ({liq.get('long_count', 0)} trades)")
            print(f"  • Short Liq:       ${short_liq/1e6:.2f}M ({liq.get('short_count', 0)} trades)")
            print(f"Liquidation Count:   {count:,}")

            if ratio != float('inf'):
                print(f"Long/Short Ratio:    {ratio:.2f}x")
            else:
                print(f"Long/Short Ratio:    ∞ (only longs liquidated)")

            # Bias indicator
            if long_liq > short_liq * 2:
                print(f"Bias:                🔴 LONGS GETTING REKT")
            elif short_liq > long_liq * 2:
                print(f"Bias:                🟢 SHORTS GETTING REKT")
            else:
                print(f"Bias:                ⚪ BALANCED")

        elif status == 'not_available':
            print(f"Status:              ⚠️  Not Available")
            print(f"Reason:              {liq.get('error', 'Unknown')}")

        else:
            print(f"Status:              ❌ Error")
            print(f"Error:               {liq.get('error', 'Unknown error')}")

    # Aggregate metrics
    if market_volume:
        print(f"\n{'='*80}")
        print("📊 AGGREGATE METRICS")
        print(f"{'='*80}")

        metrics = calculate_liquidation_metrics(liquidation_data, market_volume)

        print(f"Total Liquidations:        ${metrics['total_liquidations']/1e6:.2f}M")
        print(f"  • Longs:                 ${metrics['long_liquidations']/1e6:.2f}M")
        print(f"  • Shorts:                ${metrics['short_liquidations']/1e6:.2f}M")
        print(f"Liquidation/Volume Ratio:  {metrics['liquidation_volume_ratio']*100:.3f}%")
        print(f"Cascade Risk Score:        {metrics['cascade_risk_score']:.2f}/1.0 ({metrics['risk_level']})")

        # Risk interpretation
        print(f"\n🎯 Risk Interpretation:")
        if metrics['risk_level'] == 'CRITICAL':
            print("   ⚠️  CRITICAL: Liquidation cascade in progress or imminent")
            print("   → Reduce leverage immediately, expect high volatility")
        elif metrics['risk_level'] == 'HIGH':
            print("   🔴 HIGH: Significant liquidation activity detected")
            print("   → Use caution, tighten stops, reduce position sizes")
        elif metrics['risk_level'] == 'MODERATE':
            print("   🟡 MODERATE: Elevated liquidations, monitor closely")
            print("   → Normal market stress, standard risk management")
        else:
            print("   🟢 LOW: Liquidations within normal range")
            print("   → No immediate cascade risk")

    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description='Liquidation Data Fetcher')
    parser.add_argument('--hours', type=int, default=1, help='Hours to look back (default: 1)')
    parser.add_argument('--exchange', type=str, help='Specific exchange (binance|bybit|okx)')
    parser.add_argument('--volume', type=float, help='Market volume for ratio calculation (optional)')

    args = parser.parse_args()

    # Fetch liquidations
    if args.exchange:
        if args.exchange.lower() == 'binance':
            liq_data = [fetch_binance_liquidations(hours=args.hours)]
        elif args.exchange.lower() == 'bybit':
            liq_data = [fetch_bybit_liquidations(hours=args.hours)]
        elif args.exchange.lower() == 'okx':
            liq_data = [fetch_okx_liquidations(hours=args.hours)]
        else:
            print(f"❌ Unknown exchange: {args.exchange}")
            print("   Supported: binance, bybit, okx")
            return
    else:
        liq_data = fetch_all_liquidations(hours=args.hours)

    # Display report
    display_liquidation_report(liq_data, args.volume)


if __name__ == "__main__":
    main()
