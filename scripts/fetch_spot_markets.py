#!/usr/bin/env python3
"""
Spot Market Data Fetcher
Fetches BTC spot prices from major exchanges for basis analysis

Exchanges covered:
- Binance: BTC/USDT spot
- Bybit: BTC/USDT spot
- OKX: BTC/USDT spot
- Bitget: BTC/USDT spot
- Gate.io: BTC/USDT spot
- Coinbase: BTC/USD spot
"""

import requests
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone


def fetch_binance_spot() -> Dict:
    """Fetch Binance BTC/USDT spot market data"""
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        return {
            'exchange': 'Binance',
            'symbol': 'BTC/USDT',
            'price': float(data['lastPrice']),
            'volume_24h': float(data['quoteVolume']),
            'price_change_pct': float(data['priceChangePercent']),
            'bid': float(data['bidPrice']),
            'ask': float(data['askPrice']),
            'spread_pct': (float(data['askPrice']) - float(data['bidPrice'])) / float(data['lastPrice']) * 100,
            'num_trades': int(data['count']),
            'type': 'CEX',
            'market_type': 'SPOT',
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Binance', 'status': 'error', 'error': str(e)}


def fetch_bybit_spot() -> Dict:
    """Fetch Bybit BTC/USDT spot market data"""
    try:
        response = requests.get(
            "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get('retCode') != 0:
            return {'exchange': 'Bybit', 'status': 'error', 'error': data.get('retMsg', 'Unknown error')}

        ticker = data['result']['list'][0]

        return {
            'exchange': 'Bybit',
            'symbol': 'BTC/USDT',
            'price': float(ticker['lastPrice']),
            'volume_24h': float(ticker['turnover24h']),
            'price_change_pct': float(ticker['price24hPcnt']) * 100,
            'bid': float(ticker['bid1Price']),
            'ask': float(ticker['ask1Price']),
            'spread_pct': (float(ticker['ask1Price']) - float(ticker['bid1Price'])) / float(ticker['lastPrice']) * 100,
            'num_trades': None,
            'type': 'CEX',
            'market_type': 'SPOT',
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Bybit', 'status': 'error', 'error': str(e)}


def fetch_okx_spot() -> Dict:
    """Fetch OKX BTC/USDT spot market data"""
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get('code') != '0':
            return {'exchange': 'OKX', 'status': 'error', 'error': data.get('msg', 'Unknown error')}

        ticker = data['data'][0]
        price = float(ticker['last'])
        open_price = float(ticker['open24h'])

        return {
            'exchange': 'OKX',
            'symbol': 'BTC/USDT',
            'price': price,
            'volume_24h': float(ticker['volCcy24h']),
            'price_change_pct': ((price - open_price) / open_price) * 100,
            'bid': float(ticker['bidPx']),
            'ask': float(ticker['askPx']),
            'spread_pct': (float(ticker['askPx']) - float(ticker['bidPx'])) / price * 100,
            'num_trades': None,
            'type': 'CEX',
            'market_type': 'SPOT',
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'OKX', 'status': 'error', 'error': str(e)}


def fetch_bitget_spot() -> Dict:
    """Fetch Bitget BTC/USDT spot market data"""
    try:
        response = requests.get(
            "https://api.bitget.com/api/spot/v1/market/ticker?symbol=BTCUSDT",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get('code') != '00000':
            return {'exchange': 'Bitget', 'status': 'error', 'error': data.get('msg', 'Unknown error')}

        ticker = data['data']
        price = float(ticker['close'])
        open_price = float(ticker['open'])

        return {
            'exchange': 'Bitget',
            'symbol': 'BTC/USDT',
            'price': price,
            'volume_24h': float(ticker['usdtVolume']),
            'price_change_pct': ((price - open_price) / open_price) * 100,
            'bid': float(ticker['bidPr']),
            'ask': float(ticker['askPr']),
            'spread_pct': (float(ticker['askPr']) - float(ticker['bidPr'])) / price * 100,
            'num_trades': None,
            'type': 'CEX',
            'market_type': 'SPOT',
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Bitget', 'status': 'error', 'error': str(e)}


def fetch_gateio_spot() -> Dict:
    """Fetch Gate.io BTC/USDT spot market data"""
    try:
        response = requests.get(
            "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) == 0:
            return {'exchange': 'Gate.io', 'status': 'error', 'error': 'Unexpected API response'}

        ticker = data[0]
        price = float(ticker['last'])

        return {
            'exchange': 'Gate.io',
            'symbol': 'BTC/USDT',
            'price': price,
            'volume_24h': float(ticker['quote_volume']),
            'price_change_pct': float(ticker['change_percentage']),
            'bid': float(ticker['highest_bid']),
            'ask': float(ticker['lowest_ask']),
            'spread_pct': (float(ticker['lowest_ask']) - float(ticker['highest_bid'])) / price * 100,
            'num_trades': None,
            'type': 'CEX',
            'market_type': 'SPOT',
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Gate.io', 'status': 'error', 'error': str(e)}


def fetch_coinbase_spot() -> Dict:
    """Fetch Coinbase BTC/USD spot market data"""
    try:
        # Get ticker data
        ticker_response = requests.get(
            "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
            timeout=10
        )
        ticker_response.raise_for_status()
        ticker = ticker_response.json()

        # Get 24h stats
        stats_response = requests.get(
            "https://api.exchange.coinbase.com/products/BTC-USD/stats",
            timeout=10
        )
        stats_response.raise_for_status()
        stats = stats_response.json()

        price = float(ticker['price'])
        open_price = float(stats['open'])

        return {
            'exchange': 'Coinbase',
            'symbol': 'BTC/USD',
            'price': price,
            'volume_24h': float(stats['volume']) * price,  # Convert BTC volume to USD
            'price_change_pct': ((price - open_price) / open_price) * 100,
            'bid': float(ticker['bid']),
            'ask': float(ticker['ask']),
            'spread_pct': (float(ticker['ask']) - float(ticker['bid'])) / price * 100,
            'num_trades': None,
            'type': 'CEX',
            'market_type': 'SPOT',
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Coinbase', 'status': 'error', 'error': str(e)}


def fetch_all_spot_markets() -> List[Dict]:
    """Fetch all spot markets in parallel"""
    fetchers = [
        fetch_binance_spot,
        fetch_bybit_spot,
        fetch_okx_spot,
        fetch_bitget_spot,
        fetch_gateio_spot,
        fetch_coinbase_spot
    ]

    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_fetcher = {executor.submit(fetcher): fetcher for fetcher in fetchers}

        for future in as_completed(future_to_fetcher):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Fetcher failed: {e}")

    return results


def calculate_spot_summary(results: List[Dict]) -> Dict:
    """Calculate summary statistics across all spot markets"""
    successful = [r for r in results if r.get('status') == 'success']

    if not successful:
        return {}

    prices = [r['price'] for r in successful]
    volumes = [r['volume_24h'] for r in successful]

    return {
        'avg_price': sum(prices) / len(prices),
        'min_price': min(prices),
        'max_price': max(prices),
        'price_spread': max(prices) - min(prices),
        'price_spread_pct': ((max(prices) - min(prices)) / (sum(prices) / len(prices))) * 100,
        'total_volume_24h': sum(volumes),
        'num_exchanges': len(successful),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    print("\n📊 Fetching BTC spot market data from all exchanges...\n")

    results = fetch_all_spot_markets()

    # Display results
    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') == 'error']

    print("="*100)
    print(f"{'BTC SPOT MARKETS':^100}")
    print("="*100)
    print(f"\n{'Exchange':<15}{'Price':<15}{'24h Volume':<18}{'Δ Price':<12}{'Spread':<10}{'Trades'}")
    print("-"*100)

    for r in successful:
        volume_str = f"${r['volume_24h']/1e9:.2f}B" if r['volume_24h'] > 1e9 else f"${r['volume_24h']/1e6:.0f}M"
        trades_str = f"{r['num_trades']:,}" if r['num_trades'] else "N/A"

        print(f"{r['exchange']:<15}"
              f"${r['price']:<14,.2f}"
              f"{volume_str:<18}"
              f"{r['price_change_pct']:>6.2f}%    "
              f"{r['spread_pct']:.4f}%   "
              f"{trades_str}")

    # Summary statistics
    summary = calculate_spot_summary(results)
    if summary:
        print("\n" + "="*100)
        print("📊 MARKET SUMMARY")
        print("="*100)
        print(f"Average BTC Price:     ${summary['avg_price']:,.2f}")
        print(f"Price Range:           ${summary['min_price']:,.2f} - ${summary['max_price']:,.2f}")
        print(f"Exchange Spread:       ${summary['price_spread']:.2f} ({summary['price_spread_pct']:.3f}%)")
        print(f"Total 24h Volume:      ${summary['total_volume_24h']/1e9:.2f}B")
        print(f"Exchanges Reporting:   {summary['num_exchanges']}/6")

    if failed:
        print(f"\n⚠️  Failed Exchanges:")
        for r in failed:
            print(f"   - {r['exchange']}: {r.get('error', 'Unknown error')}")

    print("\n")
