#!/usr/bin/env python3
"""
AsterDEX Perpetual Futures Volume Tracker
Fetches real-time trading volume data from AsterDEX API
"""

import requests
from datetime import datetime
from typing import Dict


def fetch_asterdex_volume() -> Dict:
    """
    Fetch 24h trading volume from AsterDEX perpetual futures

    Returns:
        Dict containing volume data, market count, and top pairs
    """
    try:
        response = requests.get(
            "https://fapi.asterdex.com/fapi/v1/ticker/24hr",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            raise ValueError(f"Unexpected response format: {type(data)}")

        # Calculate total volume
        total_volume = sum(float(ticker.get('quoteVolume', 0)) for ticker in data)

        # Get top 10 pairs by volume
        sorted_tickers = sorted(
            data,
            key=lambda x: float(x.get('quoteVolume', 0)),
            reverse=True
        )

        top_pairs = [
            {
                'symbol': ticker['symbol'],
                'volume_24h': float(ticker.get('quoteVolume', 0)),
                'price_change_pct': float(ticker.get('priceChangePercent', 0)),
                'last_price': float(ticker.get('lastPrice', 0))
            }
            for ticker in sorted_tickers[:10]
        ]

        return {
            'exchange': 'AsterDEX',
            'total_volume_24h': total_volume,
            'num_markets': len(data),
            'top_pairs': top_pairs,
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'DEX'
        }

    except requests.RequestException as e:
        return {
            'exchange': 'AsterDEX',
            'error': f"Request failed: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'exchange': 'AsterDEX',
            'error': f"Error: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }


def format_volume_output(data: Dict) -> str:
    """Format volume data for console output"""
    if 'error' in data:
        return f"❌ {data['exchange']}: {data['error']}"

    output = []
    output.append(f"\n{'='*70}")
    output.append(f"{'AsterDEX PERPETUAL FUTURES':^70}")
    output.append(f"{'='*70}")
    output.append(f"\n📊 Market Overview:")
    output.append(f"   Total 24h Volume: ${data['total_volume_24h']:,.2f}")
    output.append(f"   Active Markets: {data['num_markets']}")
    output.append(f"   Exchange Type: {data['type']} (Decentralized)")
    output.append(f"   Updated: {data['timestamp']}")

    output.append(f"\n🔥 Top 10 Trading Pairs:")
    output.append(f"{'   Rank':<8}{'Symbol':<18}{'24h Volume':<20}{'Price Change':<15}{'Last Price'}")
    output.append(f"   {'-'*75}")

    for i, pair in enumerate(data['top_pairs'], 1):
        change_indicator = "🟢" if pair['price_change_pct'] >= 0 else "🔴"
        output.append(
            f"   {i:<8}{pair['symbol']:<18}"
            f"${pair['volume_24h']:>15,.2f}   "
            f"{change_indicator} {pair['price_change_pct']:>6.2f}%   "
            f"${pair['last_price']:,.4f}"
        )

    output.append(f"\n{'='*70}\n")
    return "\n".join(output)


if __name__ == "__main__":
    print("\n🚀 Fetching AsterDEX volume data...\n")

    data = fetch_asterdex_volume()
    print(format_volume_output(data))

    # Optionally save to JSON
    # with open('asterdex_volume.json', 'w') as f:
    #     json.dump(data, f, indent=2)
