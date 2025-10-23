#!/usr/bin/env python3
"""
Simple Spot vs Futures Comparison
Fetches both spot and perpetual prices from working exchanges to calculate basis
"""

import requests
from typing import Dict, List
from datetime import datetime, timezone


def fetch_okx_spot_and_futures() -> Dict:
    """Fetch both OKX spot and perpetual futures data"""
    try:
        # Spot
        spot_resp = requests.get(
            "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
            timeout=10
        ).json()

        # Futures (perpetual swap)
        futures_resp = requests.get(
            "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP",
            timeout=10
        ).json()

        if spot_resp.get('code') != '0' or futures_resp.get('code') != '0':
            return {'exchange': 'OKX', 'status': 'error'}

        spot_data = spot_resp['data'][0]
        futures_data = futures_resp['data'][0]

        spot_price = float(spot_data['last'])
        futures_price = float(futures_data['last'])
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': 'OKX',
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': float(spot_data['volCcy24h']),
            'futures_volume': float(futures_data['volCcy24h']),
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'OKX', 'status': 'error', 'error': str(e)}


def fetch_gateio_spot_and_futures() -> Dict:
    """Fetch both Gate.io spot and perpetual futures data"""
    try:
        # Spot
        spot_resp = requests.get(
            "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT",
            timeout=10
        ).json()

        # Futures
        futures_resp = requests.get(
            "https://api.gateio.ws/api/v4/futures/usdt/contracts/BTC_USDT",
            timeout=10
        ).json()

        if not spot_resp or not futures_resp:
            return {'exchange': 'Gate.io', 'status': 'error'}

        spot_price = float(spot_resp[0]['last'])
        futures_price = float(futures_resp['mark_price'])
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': 'Gate.io',
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': float(spot_resp[0]['quote_volume']),
            'futures_volume': None,  # Would need separate API call
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Gate.io', 'status': 'error', 'error': str(e)}


def fetch_coinbase_intx_spot_and_futures() -> Dict:
    """Fetch Coinbase spot and INTX perpetual"""
    try:
        # Spot from regular Coinbase
        spot_resp = requests.get(
            "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
            timeout=10
        ).json()

        # Futures from INTX
        futures_resp = requests.get(
            "https://api.international.coinbase.com/api/v1/instruments",
            timeout=10
        ).json()

        btc_perp = next((p for p in futures_resp if p.get('symbol') == 'BTC-PERP'), None)
        if not btc_perp:
            return {'exchange': 'Coinbase', 'status': 'error', 'error': 'BTC-PERP not found'}

        spot_price = float(spot_resp['price'])
        futures_price = float(btc_perp['quote']['mark_price'])
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': 'Coinbase',
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': None,  # Would need separate API call
            'futures_volume': float(btc_perp['notional_24hr']),
            'funding_rate': float(btc_perp['quote'].get('predicted_funding', 0)) * 100,
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Coinbase', 'status': 'error', 'error': str(e)}


def fetch_binance_spot_and_futures() -> Dict:
    """Fetch both Binance spot and perpetual futures data"""
    try:
        # Spot
        spot_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            timeout=10
        ).json()

        # Futures (perpetual)
        futures_resp = requests.get(
            "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT",
            timeout=10
        ).json()

        spot_price = float(spot_resp['lastPrice'])
        futures_price = float(futures_resp['lastPrice'])
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': 'Binance',
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': float(spot_resp['quoteVolume']),
            'futures_volume': float(futures_resp['quoteVolume']),
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Binance', 'status': 'error', 'error': str(e)}


def fetch_bybit_spot_and_futures() -> Dict:
    """Fetch both Bybit spot and perpetual futures data"""
    try:
        # Spot
        spot_resp = requests.get(
            "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT",
            timeout=10
        ).json()

        # Futures (linear perpetual)
        futures_resp = requests.get(
            "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT",
            timeout=10
        ).json()

        if spot_resp.get('retCode') != 0 or futures_resp.get('retCode') != 0:
            return {'exchange': 'Bybit', 'status': 'error', 'error': 'API error'}

        spot_data = spot_resp['result']['list'][0]
        futures_data = futures_resp['result']['list'][0]

        spot_price = float(spot_data['lastPrice'])
        futures_price = float(futures_data['lastPrice'])
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': 'Bybit',
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': float(spot_data['turnover24h']),
            'futures_volume': float(futures_data['turnover24h']),
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Bybit', 'status': 'error', 'error': str(e)}


def fetch_kraken_spot_and_futures() -> Dict:
    """Fetch both Kraken spot and perpetual futures data"""
    try:
        # Spot
        spot_resp = requests.get(
            "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
            timeout=10
        ).json()

        if spot_resp.get('error') and len(spot_resp['error']) > 0:
            return {'exchange': 'Kraken', 'status': 'error', 'error': spot_resp['error']}

        # Futures (perpetual)
        futures_resp = requests.get(
            "https://futures.kraken.com/derivatives/api/v3/tickers",
            timeout=10
        ).json()

        if futures_resp.get('result') != 'success':
            return {'exchange': 'Kraken', 'status': 'error', 'error': 'Futures API error'}

        # Extract BTC spot data (pair name is XXBTZUSD)
        spot_data = spot_resp['result']['XXBTZUSD']
        spot_price = float(spot_data['c'][0])  # Last trade price
        spot_volume = float(spot_data['v'][1])  # 24h volume in BTC

        # Convert BTC volume to USD volume using current price
        spot_volume_usd = spot_volume * spot_price

        # Extract BTC perpetual futures data (symbol is PI_XBTUSD)
        btc_perp = next((t for t in futures_resp['tickers'] if t['symbol'] == 'PI_XBTUSD'), None)
        if not btc_perp:
            return {'exchange': 'Kraken', 'status': 'error', 'error': 'PI_XBTUSD not found'}

        futures_price = float(btc_perp['markPrice'])  # Mark price
        futures_volume = float(btc_perp['volumeQuote'])  # 24h volume in USD

        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': 'Kraken',
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': spot_volume_usd,
            'futures_volume': futures_volume,
            'funding_rate': float(btc_perp['fundingRate']) * 100,  # Convert to percentage
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Kraken', 'status': 'error', 'error': str(e)}


def analyze_basis_opportunities(results: List[Dict]) -> None:
    """Analyze and display basis opportunities"""
    successful = [r for r in results if r.get('status') == 'success']

    if not successful:
        print("❌ No successful data fetches")
        return

    print("\n" + "="*110)
    print(f"{'SPOT VS FUTURES BASIS ANALYSIS':^110}")
    print(f"{'Updated: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'):^110}")
    print("="*110)

    print(f"\n{'Exchange':<15}{'Spot Price':<15}{'Futures Price':<15}{'Basis ($)':<15}{'Basis (%)':<15}{'Signal'}")
    print("-"*110)

    for r in successful:
        spot_str = f"${r['spot_price']:,.2f}"
        futures_str = f"${r['futures_price']:,.2f}"
        basis_str = f"${r['basis']:>+8.2f}"
        basis_pct_str = f"{r['basis_pct']:>+7.4f}%"

        # Interpret basis
        if r['basis_pct'] > 0.15:
            signal = "🟢 CONTANGO (Long bias)"
        elif r['basis_pct'] < -0.15:
            signal = "🔴 BACKWARDATION (Short bias)"
        else:
            signal = "⚪ NEUTRAL (Tight)"

        print(f"{r['exchange']:<15}{spot_str:<15}{futures_str:<15}{basis_str:<15}{basis_pct_str:<15}{signal}")

    # Calculate average basis
    avg_basis = sum(r['basis_pct'] for r in successful) / len(successful)

    print("\n" + "="*110)
    print("📊 MARKET INSIGHTS")
    print("="*110)
    print(f"Average Basis:        {avg_basis:+.4f}%")
    print(f"Market Structure:     {'CONTANGO' if avg_basis > 0 else 'BACKWARDATION' if avg_basis < 0 else 'NEUTRAL'}")
    print(f"Exchanges Analyzed:   {len(successful)}")

    # Arbitrage opportunities
    print("\n💰 ARBITRAGE ANALYSIS:")
    for r in successful:
        if abs(r['basis_pct']) > 0.1:  # > 0.1% basis
            arb_type = "Cash-and-Carry" if r['basis_pct'] > 0 else "Reverse"
            action = f"Buy {r['exchange']} Spot + Short {r['exchange']} Futures" if r['basis_pct'] > 0 else \
                     f"Short {r['exchange']} Spot + Buy {r['exchange']} Futures"

            print(f"\n   {r['exchange']} {arb_type}:")
            print(f"   • Action: {action}")
            print(f"   • Basis Capture: {abs(r['basis_pct']):.4f}%")

            if 'funding_rate' in r:
                annual_funding = r['funding_rate'] * 24 * 365
                total_yield = abs(r['basis_pct']) + (annual_funding if r['basis_pct'] > 0 else -annual_funding)
                print(f"   • Funding Rate: {r['funding_rate']:.4f}% per hour ({annual_funding:.2f}% annual)")
                print(f"   • Estimated Total Yield: {total_yield:.2f}% annual")
        else:
            print(f"   {r['exchange']}: ✅ Tight basis ({r['basis_pct']:+.4f}%) - Efficient market")

    # Volume analysis
    print("\n📈 SPOT VS FUTURES VOLUME:")
    for r in successful:
        if r.get('spot_volume') and r.get('futures_volume'):
            ratio = r['futures_volume'] / r['spot_volume']
            spot_vol_str = f"${r['spot_volume']/1e9:.2f}B"
            futures_vol_str = f"${r['futures_volume']/1e9:.2f}B"

            if ratio > 3.0:
                interpretation = "🔴 HIGH LEVERAGE (Speculative)"
            elif ratio < 1.5:
                interpretation = "🟢 SPOT DOMINANT (Institutional)"
            else:
                interpretation = "⚪ BALANCED"

            print(f"   {r['exchange']}: Spot {spot_vol_str} / Futures {futures_vol_str} = {ratio:.2f}x - {interpretation}")

    print("\n" + "="*110)
    print("\n💡 KEY CONCEPTS:")
    print("   • Basis = Futures Price - Spot Price")
    print("   • Positive Basis (Contango) = Market expects higher prices, futures trade at premium")
    print("   • Negative Basis (Backwardation) = Market expects lower prices, futures at discount")
    print("   • Cash-and-Carry: Buy spot + Sell futures to capture basis + funding")
    print("   • Tight basis (< 0.1%) = Efficient market, no arbitrage")
    print("\n")


if __name__ == "__main__":
    print("\n🔍 Fetching spot and futures data for basis analysis...")

    results = [
        fetch_okx_spot_and_futures(),
        fetch_gateio_spot_and_futures(),
        fetch_coinbase_intx_spot_and_futures(),
        fetch_binance_spot_and_futures(),
        fetch_bybit_spot_and_futures(),
        fetch_kraken_spot_and_futures()
    ]

    analyze_basis_opportunities(results)
