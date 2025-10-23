#!/usr/bin/env python3
"""
OKX Perpetual Futures Volume Tracker
Fetches real-time trading volume data from OKX API
"""

import requests
from datetime import datetime
from typing import Dict


def fetch_okx_volume() -> Dict:
    """
    Fetch 24h trading volume from OKX perpetual futures (SWAP)

    Returns:
        Dict containing volume data, market count, and top pairs
    """
    try:
        # Fetch all tickers
        response = requests.get(
            "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get('code') != '0':
            raise ValueError(f"API error: {data.get('msg', 'Unknown error')}")

        tickers = data['data']

        # Calculate total volume (volCcy24h * last price for USD value)
        total_volume = 0
        pairs_with_volume = []

        for ticker in tickers:
            try:
                # volCcy24h is in base currency, need to convert to USD
                volume_base = float(ticker.get('volCcy24h', 0))
                last_price = float(ticker.get('last', 0))
                volume_usd = volume_base * last_price
                total_volume += volume_usd

                pairs_with_volume.append({
                    'symbol': ticker['instId'],
                    'volume_24h': volume_usd,
                    'price_change_pct': float(ticker.get('changeUtc24h', 0)) * 100,  # Convert to percentage
                    'last_price': last_price,
                    'open_interest': 0  # Will be filled from separate API call
                })
            except (ValueError, KeyError):
                continue

        # Get OI from separate endpoint (one call for all instruments)
        try:
            oi_resp = requests.get(
                "https://www.okx.com/api/v5/public/open-interest?instType=SWAP",
                timeout=10
            ).json()

            if oi_resp.get('code') == '0' and oi_resp.get('data'):
                # Create a mapping of instId to oiUsd
                oi_map = {item['instId']: float(item.get('oiUsd', 0)) for item in oi_resp['data']}

                # Update OI for each pair
                for pair in pairs_with_volume:
                    pair['open_interest'] = oi_map.get(pair['symbol'], 0)
        except Exception:
            pass

        # Sort by volume and get top 10
        sorted_pairs = sorted(
            pairs_with_volume,
            key=lambda x: x['volume_24h'],
            reverse=True
        )

        return {
            'exchange': 'OKX',
            'total_volume_24h': total_volume,
            'num_markets': len(tickers),
            'top_pairs': sorted_pairs[:10],
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'CEX'
        }

    except requests.RequestException as e:
        return {
            'exchange': 'OKX',
            'error': f"Request failed: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'exchange': 'OKX',
            'error': f"Error: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }


def format_volume_output(data: Dict) -> str:
    """Format volume data for console output"""
    if 'error' in data:
        return f"❌ {data['exchange']}: {data['error']}"

    output = []
    output.append(f"\n{'='*85}")
    output.append(f"{'OKX PERPETUAL FUTURES (SWAP)':^85}")
    output.append(f"{'='*85}")
    output.append(f"\n📊 Market Overview:")
    output.append(f"   Total 24h Volume: ${data['total_volume_24h']:,.2f}")
    output.append(f"   Active Markets: {data['num_markets']}")
    output.append(f"   Exchange Type: {data['type']} (Centralized)")
    output.append(f"   Updated: {data['timestamp']}")

    output.append(f"\n🔥 Top 10 Trading Pairs:")
    output.append(f"{'   Rank':<8}{'Symbol':<20}{'24h Volume':<20}{'Price Change':<15}{'Open Interest'}")
    output.append(f"   {'-'*85}")

    for i, pair in enumerate(data['top_pairs'], 1):
        change_indicator = "🟢" if pair['price_change_pct'] >= 0 else "🔴"
        output.append(
            f"   {i:<8}{pair['symbol']:<20}"
            f"${pair['volume_24h']:>15,.2f}   "
            f"{change_indicator} {pair['price_change_pct']:>6.2f}%   "
            f"${pair['open_interest']:>15,.2f}"
        )

    output.append(f"\n{'='*85}\n")
    return "\n".join(output)


if __name__ == "__main__":
    print("\n🚀 Fetching OKX volume data...\n")

    data = fetch_okx_volume()
    print(format_volume_output(data))

    # Optionally save to JSON
    # with open('okx_volume.json', 'w') as f:
    #     json.dump(data, f, indent=2)
