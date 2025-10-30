"""Spot-futures basis analysis

Analyzes the basis (price difference) between spot and futures markets to identify:
- Market structure (contango vs backwardation)
- Arbitrage opportunities
- Leverage activity levels
"""

from typing import Dict, List, Optional
import requests


def fetch_spot_and_futures_basis(exchange: str) -> Optional[Dict]:
    """Fetch both spot and perpetual futures prices to calculate basis

    Note: This uses manual API calls for each exchange since we don't yet have
    unified spot market clients. This will be refactored when spot clients are added.

    Args:
        exchange: Exchange name (e.g., "Binance", "Bybit", "OKX")

    Returns:
        Dictionary with spot price, futures price, and basis metrics,
        or None if data unavailable
    """
    try:
        if exchange == "Binance":
            spot_resp = requests.get(
                "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
                timeout=10
            ).json()

            futures_resp = requests.get(
                "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT",
                timeout=10
            ).json()

            spot_price = float(spot_resp['lastPrice'])
            futures_price = float(futures_resp['lastPrice'])
            spot_volume = float(spot_resp['quoteVolume'])
            futures_volume = float(futures_resp['quoteVolume'])

        elif exchange == "Bybit":
            spot_resp = requests.get(
                "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT",
                timeout=10
            ).json()

            futures_resp = requests.get(
                "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT",
                timeout=10
            ).json()

            spot_price = float(spot_resp['result']['list'][0]['lastPrice'])
            futures_price = float(futures_resp['result']['list'][0]['lastPrice'])
            spot_volume = float(spot_resp['result']['list'][0]['turnover24h'])
            futures_volume = float(futures_resp['result']['list'][0]['turnover24h'])

        elif exchange == "OKX":
            spot_resp = requests.get(
                "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
                timeout=10
            ).json()

            futures_resp = requests.get(
                "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP",
                timeout=10
            ).json()

            spot_price = float(spot_resp['data'][0]['last'])
            futures_price = float(futures_resp['data'][0]['last'])
            spot_volume = float(spot_resp['data'][0]['volCcy24h']) * spot_price
            futures_volume = float(futures_resp['data'][0]['volCcy24h']) * futures_price

        elif exchange == "Gate.io":
            spot_resp = requests.get(
                "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT",
                timeout=10
            ).json()

            futures_resp = requests.get(
                "https://api.gateio.ws/api/v4/futures/usdt/contracts/BTC_USDT",
                timeout=10
            ).json()

            spot_price = float(spot_resp[0]['last'])
            futures_price = float(futures_resp['mark_price'])
            spot_volume = float(spot_resp[0]['quote_volume'])
            futures_volume = None

        elif exchange == "Kraken":
            spot_resp = requests.get(
                "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
                timeout=10
            ).json()

            if spot_resp.get('error') and len(spot_resp['error']) > 0:
                return None

            futures_resp = requests.get(
                "https://futures.kraken.com/derivatives/api/v3/tickers",
                timeout=10
            ).json()

            if futures_resp.get('result') != 'success':
                return None

            spot_data = spot_resp['result']['XXBTZUSD']
            spot_price = float(spot_data['c'][0])
            spot_volume = float(spot_data['v'][1]) * spot_price

            btc_perp = next((t for t in futures_resp['tickers'] if t['symbol'] == 'PI_XBTUSD'), None)
            if not btc_perp:
                return None

            futures_price = float(btc_perp['markPrice'])
            futures_volume = float(btc_perp['volumeQuote'])

        else:
            return None

        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': exchange,
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': spot_volume,
            'futures_volume': futures_volume,
            'status': 'success'
        }

    except Exception as e:
        return None


def analyze_basis_metrics() -> Dict:
    """Analyze spot-futures basis across available exchanges

    Fetches spot and futures prices from multiple exchanges and analyzes:
    1. Average basis (is market in contango or backwardation?)
    2. Market structure interpretation
    3. Arbitrage opportunities (cash-and-carry or reverse)
    4. Volume analysis (spot vs futures activity)

    Returns:
        Dictionary containing:
        - status: 'success' or 'unavailable'
        - exchanges_analyzed: Number of exchanges with data
        - basis_data: Raw basis data from each exchange
        - avg_basis: Average basis across exchanges (%)
        - market_structure: "CONTANGO" or "BACKWARDATION" with strength
        - interpretation: What the basis means for market sentiment
        - arbitrage_opportunities: List of potential arb trades
        - volume_analysis: Spot vs futures volume ratios
    """
    exchanges = ["Binance", "Bybit", "OKX", "Gate.io", "Kraken"]
    basis_data = []

    for exchange in exchanges:
        result = fetch_spot_and_futures_basis(exchange)
        if result:
            basis_data.append(result)

    if not basis_data:
        return {'status': 'unavailable', 'exchanges_analyzed': 0}

    avg_basis = sum(d['basis_pct'] for d in basis_data) / len(basis_data)
    max_basis = max(d['basis_pct'] for d in basis_data)
    min_basis = min(d['basis_pct'] for d in basis_data)

    # Interpret market structure
    if avg_basis > 0.15:
        market_structure = "CONTANGO (Strong)"
        structure_signal = "🟢"
        interpretation = "Futures trading at significant premium - bullish market expectations"
    elif avg_basis > 0.05:
        market_structure = "CONTANGO (Mild)"
        structure_signal = "🟢"
        interpretation = "Futures slightly above spot - neutral to bullish"
    elif avg_basis < -0.15:
        market_structure = "BACKWARDATION (Strong)"
        structure_signal = "🔴"
        interpretation = "Futures at significant discount - bearish market expectations"
    elif avg_basis < -0.05:
        market_structure = "BACKWARDATION (Mild)"
        structure_signal = "🔴"
        interpretation = "Futures slightly below spot - neutral to bearish"
    else:
        market_structure = "NEUTRAL (Tight Basis)"
        structure_signal = "⚪"
        interpretation = "Extremely efficient market - spot and futures well aligned"

    # Identify arbitrage opportunities
    arbitrage_opportunities = []
    for d in basis_data:
        if abs(d['basis_pct']) > 0.1:  # 0.1% threshold
            arb_type = "Cash-and-Carry" if d['basis_pct'] > 0 else "Reverse Cash-and-Carry"
            arbitrage_opportunities.append({
                'exchange': d['exchange'],
                'type': arb_type,
                'basis_capture': abs(d['basis_pct']),
                'action': f"Buy {d['exchange']} Spot / Sell Futures" if d['basis_pct'] > 0 else
                         f"Short {d['exchange']} Spot / Buy Futures"
            })

    # Analyze spot vs futures volume
    volume_analysis = []
    for d in basis_data:
        if d.get('spot_volume') and d.get('futures_volume'):
            ratio = d['futures_volume'] / d['spot_volume']
            if ratio > 3.0:
                signal = "🔴 HIGH LEVERAGE"
                meaning = "Speculative activity dominant"
            elif ratio < 1.5:
                signal = "🟢 SPOT DOMINANT"
                meaning = "Institutional buying likely"
            else:
                signal = "⚪ BALANCED"
                meaning = "Healthy market structure"

            volume_analysis.append({
                'exchange': d['exchange'],
                'ratio': ratio,
                'signal': signal,
                'meaning': meaning
            })

    return {
        'status': 'success',
        'exchanges_analyzed': len(basis_data),
        'basis_data': basis_data,
        'avg_basis': avg_basis,
        'max_basis': max_basis,
        'min_basis': min_basis,
        'market_structure': market_structure,
        'structure_signal': structure_signal,
        'interpretation': interpretation,
        'arbitrage_opportunities': arbitrage_opportunities,
        'volume_analysis': volume_analysis
    }
