#!/usr/bin/env python3
"""
Bitget Perpetual Futures Volume Tracker
Fetches real-time trading volume data from Bitget API
"""

import requests
from datetime import datetime
from typing import Dict


def fetch_bitget_volume() -> Dict:
    """
    Fetch 24h trading volume from Bitget USDT-M perpetual futures

    Returns:
        Dict containing volume data, market count, and top pairs
    """
    try:
        # Fetch all USDT-margined perpetual tickers
        response = requests.get(
            "https://api.bitget.com/api/mix/v1/market/tickers?productType=umcbl",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get('code') != '00000':
            raise ValueError(f"API error: {data.get('msg', 'Unknown error')}")

        tickers = data['data']

        # Calculate total volume
        total_volume = sum(float(ticker.get('usdtVolume', 0)) for ticker in tickers)

        # Calculate total open interest (in USD)
        total_oi = sum(
            float(ticker.get('holdingAmount', 0)) * float(ticker.get('last', 0))
            for ticker in tickers
        )

        # Get top 10 pairs by volume
        sorted_tickers = sorted(
            tickers,
            key=lambda x: float(x.get('usdtVolume', 0)),
            reverse=True
        )

        top_pairs = [
            {
                'symbol': ticker['symbol'].replace('_UMCBL', ''),
                'volume_24h': float(ticker.get('usdtVolume', 0)),
                'price_change_pct': float(ticker.get('priceChangePercent', 0)) * 100,
                'last_price': float(ticker.get('last', 0)),
                'open_interest': float(ticker.get('holdingAmount', 0)) * float(ticker.get('last', 0)),
                'funding_rate': float(ticker.get('fundingRate', 0)) * 100
            }
            for ticker in sorted_tickers[:10]
        ]

        # Get BTC metrics for reference
        btc_ticker = next((t for t in tickers if t['symbol'] == 'BTCUSDT_UMCBL'), {})
        btc_funding = float(btc_ticker.get('fundingRate', 0)) * 100 if btc_ticker else None
        btc_price_change = float(btc_ticker.get('priceChangePercent', 0)) * 100 if btc_ticker else None

        return {
            'exchange': 'Bitget',
            'total_volume_24h': total_volume,
            'total_open_interest': total_oi,
            'oi_volume_ratio': total_oi / total_volume if total_volume > 0 else 0,
            'btc_funding_rate': btc_funding,
            'btc_price_change': btc_price_change,
            'num_markets': len(tickers),
            'top_pairs': top_pairs,
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'CEX'
        }

    except requests.RequestException as e:
        return {
            'exchange': 'Bitget',
            'error': f"Request failed: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'exchange': 'Bitget',
            'error': f"Error: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }


def format_volume_output(data: Dict) -> str:
    """Format volume data for console output"""
    if 'error' in data:
        return f"❌ {data['exchange']}: {data['error']}"

    output = []
    output.append(f"\n{'='*90}")
    output.append(f"{'BITGET PERPETUAL FUTURES (USDT-M)':^90}")
    output.append(f"{'='*90}")
    output.append(f"\n📊 Market Overview:")
    output.append(f"   Total 24h Volume: ${data['total_volume_24h']:,.2f}")
    output.append(f"   Total Open Interest: ${data['total_open_interest']:,.2f}")
    output.append(f"   OI/Volume Ratio: {data['oi_volume_ratio']:.2f}x")
    output.append(f"   Active Markets: {data['num_markets']}")
    output.append(f"   Exchange Type: {data['type']} (Centralized)")
    output.append(f"   Updated: {data['timestamp']}")

    output.append(f"\n🔍 BTC Reference Metrics:")
    if data['btc_funding_rate'] is not None:
        sentiment = "🟢 Bullish" if data['btc_funding_rate'] > 0.01 else "🔴 Bearish" if data['btc_funding_rate'] < -0.01 else "⚪ Neutral"
        output.append(f"   Funding Rate: {data['btc_funding_rate']:.4f}% {sentiment}")
    if data['btc_price_change'] is not None:
        output.append(f"   24h Price Change: {data['btc_price_change']:.2f}%")

    output.append(f"\n🔥 Top 10 Trading Pairs:")
    output.append(f"{'   Rank':<8}{'Symbol':<20}{'24h Volume':<20}{'OI':<18}{'Funding':<12}{'Δ Price'}")
    output.append(f"   {'-'*85}")

    for i, pair in enumerate(data['top_pairs'], 1):
        change_indicator = "🟢" if pair['price_change_pct'] >= 0 else "🔴"
        output.append(
            f"   {i:<8}{pair['symbol']:<20}"
            f"${pair['volume_24h']:>15,.0f}   "
            f"${pair['open_interest']:>13,.0f}   "
            f"{pair['funding_rate']:>6.4f}%   "
            f"{change_indicator} {pair['price_change_pct']:>6.2f}%"
        )

    output.append(f"\n{'='*90}\n")
    return "\n".join(output)


if __name__ == "__main__":
    print("\n🚀 Fetching Bitget volume data...\n")

    data = fetch_bitget_volume()
    print(format_volume_output(data))

    # Optionally save to JSON
    # with open('bitget_volume.json', 'w') as f:
    #     json.dump(data, f, indent=2)
