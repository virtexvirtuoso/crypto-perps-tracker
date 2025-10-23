#!/usr/bin/env python3
"""
Per-Coin Analysis Across All Exchanges
Analyzes BTC, ETH, SOL across all 8 exchanges
"""

import requests
from datetime import datetime
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed


# Symbol mappings for each exchange
SYMBOL_MAPS = {
    'Binance': {
        'BTC': 'BTCUSDT',
        'ETH': 'ETHUSDT',
        'SOL': 'SOLUSDT'
    },
    'Bybit': {
        'BTC': 'BTCUSDT',
        'ETH': 'ETHUSDT',
        'SOL': 'SOLUSDT'
    },
    'OKX': {
        'BTC': 'BTC-USDT-SWAP',
        'ETH': 'ETH-USDT-SWAP',
        'SOL': 'SOL-USDT-SWAP'
    },
    'Bitget': {
        'BTC': 'BTCUSDT_UMCBL',
        'ETH': 'ETHUSDT_UMCBL',
        'SOL': 'SOLUSDT_UMCBL'
    },
    'Gate.io': {
        'BTC': 'BTC_USDT',
        'ETH': 'ETH_USDT',
        'SOL': 'SOL_USDT'
    },
    'HyperLiquid': {
        'BTC': 'BTC',
        'ETH': 'ETH',
        'SOL': 'SOL'
    },
    'dYdX': {
        'BTC': 'BTC-USD',
        'ETH': 'ETH-USD',
        'SOL': 'SOL-USD'
    }
}


def fetch_binance_coin(coin: str) -> Dict:
    """Fetch single coin data from Binance"""
    symbol = SYMBOL_MAPS['Binance'][coin]

    try:
        # Get ticker
        ticker_resp = requests.get(
            f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}",
            timeout=5
        ).json()

        # Get OI
        oi_resp = requests.get(
            f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}",
            timeout=5
        ).json()

        # Get funding
        funding_resp = requests.get(
            f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}",
            timeout=5
        ).json()

        return {
            'exchange': 'Binance',
            'coin': coin,
            'price': float(ticker_resp.get('lastPrice', 0)),
            'volume_24h': float(ticker_resp.get('quoteVolume', 0)),
            'price_change_pct': float(ticker_resp.get('priceChangePercent', 0)),
            'open_interest': float(oi_resp.get('openInterest', 0)) * float(ticker_resp.get('lastPrice', 0)),
            'funding_rate': float(funding_resp.get('lastFundingRate', 0)) * 100,
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Binance', 'coin': coin, 'status': 'error', 'error': str(e)}


def fetch_bybit_coin(coin: str) -> Dict:
    """Fetch single coin data from Bybit"""
    symbol = SYMBOL_MAPS['Bybit'][coin]

    try:
        response = requests.get(
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}",
            timeout=5
        ).json()

        ticker = response['result']['list'][0]

        return {
            'exchange': 'Bybit',
            'coin': coin,
            'price': float(ticker.get('lastPrice', 0)),
            'volume_24h': float(ticker.get('turnover24h', 0)),
            'price_change_pct': float(ticker.get('price24hPcnt', 0)) * 100,
            'open_interest': float(ticker.get('openInterestValue', 0)),
            'funding_rate': float(ticker.get('fundingRate', 0)) * 100,
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Bybit', 'coin': coin, 'status': 'error', 'error': str(e)}


def fetch_okx_coin(coin: str) -> Dict:
    """Fetch single coin data from OKX"""
    symbol = SYMBOL_MAPS['OKX'][coin]

    try:
        # Get ticker
        ticker_resp = requests.get(
            f"https://www.okx.com/api/v5/market/ticker?instId={symbol}",
            timeout=5
        ).json()

        ticker = ticker_resp['data'][0]

        # Get OI
        oi_resp = requests.get(
            f"https://www.okx.com/api/v5/public/open-interest?instId={symbol}",
            timeout=5
        ).json()

        oi = float(oi_resp['data'][0].get('oiUsd', 0)) if oi_resp.get('data') else 0

        # Get funding
        funding_resp = requests.get(
            f"https://www.okx.com/api/v5/public/funding-rate?instId={symbol}",
            timeout=5
        ).json()

        funding = float(funding_resp['data'][0].get('fundingRate', 0)) * 100 if funding_resp.get('data') else 0

        # Calculate volume
        vol_base = float(ticker.get('volCcy24h', 0))
        price = float(ticker.get('last', 0))

        return {
            'exchange': 'OKX',
            'coin': coin,
            'price': price,
            'volume_24h': vol_base * price,
            'price_change_pct': ((price - float(ticker.get('open24h', 0))) / float(ticker.get('open24h', 1))) * 100,
            'open_interest': oi,
            'funding_rate': funding,
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'OKX', 'coin': coin, 'status': 'error', 'error': str(e)}


def fetch_hyperliquid_coin(coin: str) -> Dict:
    """Fetch single coin data from HyperLiquid"""
    try:
        response = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            headers={"Content-Type": "application/json"},
            timeout=5
        ).json()

        universe = response[0]["universe"]
        asset_ctxs = response[1]

        # Find our coin
        for i, asset in enumerate(universe):
            if asset["name"] == coin:
                ctx = asset_ctxs[i]

                return {
                    'exchange': 'HyperLiquid',
                    'coin': coin,
                    'price': float(ctx.get('markPx', 0)),
                    'volume_24h': float(ctx.get('dayNtlVlm', 0)),
                    'price_change_pct': ((float(ctx.get('markPx', 0)) - float(ctx.get('prevDayPx', 1))) / float(ctx.get('prevDayPx', 1))) * 100,
                    'open_interest': float(ctx.get('openInterest', 0)) * float(ctx.get('markPx', 0)),
                    'funding_rate': float(ctx.get('funding', 0)) * 100,
                    'status': 'success'
                }

        return {'exchange': 'HyperLiquid', 'coin': coin, 'status': 'error', 'error': 'Coin not found'}
    except Exception as e:
        return {'exchange': 'HyperLiquid', 'coin': coin, 'status': 'error', 'error': str(e)}


def fetch_dydx_coin(coin: str) -> Dict:
    """Fetch single coin data from dYdX"""
    symbol = SYMBOL_MAPS['dYdX'][coin]

    try:
        response = requests.get(
            f"https://indexer.dydx.trade/v4/perpetualMarkets/{symbol}",
            timeout=5
        ).json()

        market = response['markets'][symbol]

        return {
            'exchange': 'dYdX v4',
            'coin': coin,
            'price': float(market.get('oraclePrice', 0)),
            'volume_24h': float(market.get('volume24H', 0)),
            'price_change_pct': float(market.get('priceChange24H', 0)) * 100,
            'open_interest': float(market.get('openInterest', 0)) * float(market.get('oraclePrice', 0)),
            'funding_rate': float(market.get('nextFundingRate', 0)) * 100,
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'dYdX v4', 'coin': coin, 'status': 'error', 'error': str(e)}


def analyze_coin_across_exchanges(coin: str) -> List[Dict]:
    """Fetch coin data from all exchanges in parallel"""
    fetchers = [
        lambda: fetch_binance_coin(coin),
        lambda: fetch_bybit_coin(coin),
        lambda: fetch_okx_coin(coin),
        lambda: fetch_hyperliquid_coin(coin),
        lambda: fetch_dydx_coin(coin)
    ]

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_fetcher = {executor.submit(fetcher): fetcher for fetcher in fetchers}

        for future in as_completed(future_to_fetcher):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error: {e}")

    return results


def format_coin_analysis(coin: str, data: List[Dict]) -> str:
    """Format coin analysis output"""
    successful = [d for d in data if d.get('status') == 'success']

    if not successful:
        return f"\n❌ No data available for {coin}\n"

    output = []

    # Header
    output.append("\n" + "="*100)
    output.append(f"{'  ' + coin + ' ANALYSIS ACROSS ALL EXCHANGES':^100}")
    output.append(f"{'Updated: ' + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'):^100}")
    output.append("="*100)

    # Calculate average price
    avg_price = sum(d['price'] for d in successful) / len(successful)
    total_volume = sum(d['volume_24h'] for d in successful)
    total_oi = sum(d['open_interest'] for d in successful)

    # Summary
    output.append(f"\n📊 Market Summary:")
    output.append(f"   Average Price:     ${avg_price:,.2f}")
    output.append(f"   Total Volume:      ${total_volume:,.0f}")
    output.append(f"   Total OI:          ${total_oi:,.0f}")
    output.append(f"   Exchanges Tracked: {len(successful)}")

    # Sort by price
    sorted_by_price = sorted(successful, key=lambda x: x['price'], reverse=True)

    # Table
    output.append(f"\n{'Exchange':<15} {'Price':>12} {'Deviation':>10} {'Volume (24h)':>15} {'OI':>15} {'Funding':>10}")
    output.append("-"*100)

    for d in sorted_by_price:
        deviation = ((d['price'] - avg_price) / avg_price) * 100

        output.append(
            f"{d['exchange']:<15} "
            f"${d['price']:>11,.2f} "
            f"{deviation:>9.3f}% "
            f"${d['volume_24h']:>14,.0f} "
            f"${d['open_interest']:>14,.0f} "
            f"{d['funding_rate']:>9.4f}%"
        )

    # Find best/worst
    highest_price = sorted_by_price[0]
    lowest_price = sorted_by_price[-1]
    spread = highest_price['price'] - lowest_price['price']
    spread_pct = (spread / avg_price) * 100

    output.append(f"\n💰 Price Spread:")
    output.append(f"   Highest: {highest_price['exchange']} ${highest_price['price']:,.2f}")
    output.append(f"   Lowest:  {lowest_price['exchange']} ${lowest_price['price']:,.2f}")
    output.append(f"   Spread:  ${spread:,.2f} ({spread_pct:.3f}%)")

    if spread_pct > 0.1:
        output.append(f"\n   ⚠️  ARBITRAGE OPPORTUNITY: {spread_pct:.3f}% spread detected!")

    # Funding rate analysis
    sorted_by_funding = sorted(successful, key=lambda x: x['funding_rate'], reverse=True)
    highest_funding = sorted_by_funding[0]
    lowest_funding = sorted_by_funding[-1]
    funding_spread = highest_funding['funding_rate'] - lowest_funding['funding_rate']

    output.append(f"\n💸 Funding Rates:")
    output.append(f"   Highest: {highest_funding['exchange']} {highest_funding['funding_rate']:.4f}%")
    output.append(f"   Lowest:  {lowest_funding['exchange']} {lowest_funding['funding_rate']:.4f}%")
    output.append(f"   Spread:  {funding_spread:.4f}% (Annualized: {funding_spread * 3 * 365:.2f}%)")

    if funding_spread > 0.005:
        output.append(f"\n   💡 Funding Arb: Short {highest_funding['exchange']} / Long {lowest_funding['exchange']}")

    # Volume distribution
    output.append(f"\n📊 Volume Distribution:")
    sorted_by_volume = sorted(successful, key=lambda x: x['volume_24h'], reverse=True)
    for d in sorted_by_volume[:3]:
        vol_pct = (d['volume_24h'] / total_volume) * 100
        output.append(f"   {d['exchange']:<15} ${d['volume_24h']:>14,.0f} ({vol_pct:>5.1f}%)")

    # OI distribution
    output.append(f"\n🎯 Open Interest Distribution:")
    sorted_by_oi = sorted(successful, key=lambda x: x['open_interest'], reverse=True)
    for d in sorted_by_oi[:3]:
        oi_pct = (d['open_interest'] / total_oi) * 100
        output.append(f"   {d['exchange']:<15} ${d['open_interest']:>14,.0f} ({oi_pct:>5.1f}%)")

    output.append("\n" + "="*100 + "\n")

    return "\n".join(output)


def main():
    """Main function"""
    print("\n🚀 Fetching BTC, ETH, SOL data from all exchanges...\n")
    print("⏳ This will take 10-15 seconds...\n")

    coins = ['BTC', 'ETH', 'SOL']

    for coin in coins:
        data = analyze_coin_across_exchanges(coin)
        print(format_coin_analysis(coin, data))


if __name__ == "__main__":
    main()
