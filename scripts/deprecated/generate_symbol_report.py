#!/usr/bin/env python3
"""
Symbol-Specific Market Report Generator
Analyzes individual trading pairs across all exchanges for actionable trading insights

For each symbol (e.g., BTC, ETH, SOL), provides:
- Cross-exchange price comparison
- Liquidity analysis (volume, OI by exchange)
- Funding rate comparison
- Arbitrage opportunities
- Best execution venues
- Trading recommendations
"""

import requests
import json
import io
import yaml
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Chart generation
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap
import numpy as np


def normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol names across exchanges

    Examples:
        BTCUSDT -> BTC
        BTC-USDT-SWAP -> BTC
        BTC-PERP -> BTC
        BTC_USDT -> BTC
    """
    # Remove common suffixes
    symbol = symbol.upper()
    symbol = symbol.replace('USDT', '').replace('USDC', '').replace('USD', '')
    symbol = symbol.replace('-PERP', '').replace('-SWAP', '').replace('_UMCBL', '')
    symbol = symbol.replace('-', '').replace('_', '').replace('PERPETUAL', '')
    symbol = symbol.strip()

    return symbol


def fetch_symbol_data_from_exchanges() -> Dict[str, List[Dict]]:
    """
    Fetch data for all symbols from all exchanges and group by symbol

    Returns:
        Dict mapping symbol -> list of exchange data for that symbol
    """
    symbol_data = defaultdict(list)

    # Fetch from each exchange with symbol-level detail
    exchanges = [
        fetch_binance_symbols,
        fetch_bybit_symbols,
        fetch_okx_symbols,
        fetch_bitget_symbols,
        fetch_gateio_symbols,
        fetch_hyperliquid_symbols,
        fetch_dydx_symbols,
        fetch_coinbase_symbols
    ]

    all_results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_exchange = {executor.submit(fetch): fetch for fetch in exchanges}

        for future in as_completed(future_to_exchange):
            try:
                result = future.result()
                if result:
                    all_results.extend(result)
            except Exception as e:
                print(f"Error fetching exchange data: {e}")

    # Group by symbol
    for item in all_results:
        symbol = normalize_symbol(item['symbol'])
        if symbol:  # Skip empty symbols
            symbol_data[symbol].append(item)

    return dict(symbol_data)


def fetch_binance_symbols() -> List[Dict]:
    """Fetch all Binance perpetual symbols with metrics"""
    try:
        response = requests.get(
            "https://fapi.binance.com/fapi/v1/ticker/24hr",
            timeout=10
        )
        tickers = response.json()

        if not isinstance(tickers, list):
            return []

        results = []
        for ticker in tickers:
            symbol = ticker['symbol']

            # Get funding rate
            funding_rate = None
            try:
                funding_resp = requests.get(
                    f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}",
                    timeout=5
                ).json()
                funding_rate = float(funding_resp.get('lastFundingRate', 0)) * 100
            except Exception:
                pass

            # Get OI
            oi_value = None
            try:
                oi_resp = requests.get(
                    f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}",
                    timeout=5
                ).json()
                if 'openInterest' in oi_resp:
                    oi_value = float(oi_resp['openInterest']) * float(ticker.get('lastPrice', 0))
            except Exception:
                pass

            results.append({
                'exchange': 'Binance',
                'symbol': symbol,
                'price': float(ticker.get('lastPrice', 0)),
                'volume': float(ticker.get('quoteVolume', 0)),
                'open_interest': oi_value,
                'funding_rate': funding_rate,
                'price_change_pct': float(ticker.get('priceChangePercent', 0)),
                'num_trades': int(ticker.get('count', 0)),
                'type': 'CEX'
            })

        return results

    except Exception as e:
        print(f"Binance error: {e}")
        return []


def fetch_bybit_symbols() -> List[Dict]:
    """Fetch all Bybit perpetual symbols"""
    try:
        response = requests.get(
            "https://api.bybit.com/v5/market/tickers?category=linear",
            timeout=10
        )
        data = response.json()

        if data.get('retCode') != 0:
            return []

        results = []
        for ticker in data['result']['list']:
            results.append({
                'exchange': 'Bybit',
                'symbol': ticker['symbol'],
                'price': float(ticker.get('lastPrice', 0)),
                'volume': float(ticker.get('turnover24h', 0)),
                'open_interest': float(ticker.get('openInterestValue', 0)),
                'funding_rate': float(ticker.get('fundingRate', 0)) * 100,
                'price_change_pct': float(ticker.get('price24hPcnt', 0)) * 100,
                'num_trades': None,
                'type': 'CEX'
            })

        return results

    except Exception as e:
        print(f"Bybit error: {e}")
        return []


def fetch_okx_symbols() -> List[Dict]:
    """Fetch all OKX perpetual symbols"""
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
            timeout=10
        )
        data = response.json()

        if data.get('code') != '0':
            return []

        # Get OI data
        oi_map = {}
        try:
            oi_resp = requests.get(
                "https://www.okx.com/api/v5/public/open-interest?instType=SWAP",
                timeout=10
            ).json()
            if oi_resp.get('code') == '0' and oi_resp.get('data'):
                oi_map = {item['instId']: float(item.get('oiUsd', 0)) for item in oi_resp['data']}
        except Exception:
            pass

        # Get funding rates (batch)
        funding_map = {}
        try:
            funding_resp = requests.get(
                "https://www.okx.com/api/v5/public/funding-rate?instType=SWAP",
                timeout=10
            ).json()
            if funding_resp.get('code') == '0' and funding_resp.get('data'):
                funding_map = {item['instId']: float(item.get('fundingRate', 0)) * 100 for item in funding_resp['data']}
        except Exception:
            pass

        results = []
        for ticker in data['data']:
            inst_id = ticker['instId']
            last_price = float(ticker.get('last', 0))
            vol_ccy = float(ticker.get('volCcy24h', 0))

            # Calculate price change
            price_change = None
            open_24h = float(ticker.get('open24h', 0))
            if open_24h > 0:
                price_change = ((last_price - open_24h) / open_24h) * 100

            results.append({
                'exchange': 'OKX',
                'symbol': inst_id,
                'price': last_price,
                'volume': vol_ccy * last_price,
                'open_interest': oi_map.get(inst_id),
                'funding_rate': funding_map.get(inst_id),
                'price_change_pct': price_change,
                'num_trades': None,
                'type': 'CEX'
            })

        return results

    except Exception as e:
        print(f"OKX error: {e}")
        return []


def fetch_bitget_symbols() -> List[Dict]:
    """Fetch all Bitget perpetual symbols"""
    try:
        response = requests.get(
            "https://api.bitget.com/api/mix/v1/market/tickers?productType=umcbl",
            timeout=10
        )
        data = response.json()

        if data.get('code') != '00000':
            return []

        results = []
        for ticker in data['data']:
            results.append({
                'exchange': 'Bitget',
                'symbol': ticker['symbol'],
                'price': float(ticker.get('last', 0)),
                'volume': float(ticker.get('usdtVolume', 0)),
                'open_interest': float(ticker.get('holdingAmount', 0)) * float(ticker.get('last', 0)),
                'funding_rate': float(ticker.get('fundingRate', 0)) * 100,
                'price_change_pct': float(ticker.get('priceChangePercent', 0)) * 100,
                'num_trades': None,
                'type': 'CEX'
            })

        return results

    except Exception as e:
        print(f"Bitget error: {e}")
        return []


def fetch_gateio_symbols() -> List[Dict]:
    """Fetch all Gate.io perpetual symbols"""
    try:
        response = requests.get(
            "https://api.gateio.ws/api/v4/futures/usdt/tickers",
            timeout=10
        )
        tickers = response.json()

        if not isinstance(tickers, list):
            return []

        results = []
        for ticker in tickers:
            results.append({
                'exchange': 'Gate.io',
                'symbol': ticker['contract'],
                'price': float(ticker.get('last', 0)),
                'volume': float(ticker.get('volume_24h_settle', 0)),
                'open_interest': float(ticker.get('total_size', 0)) * float(ticker.get('mark_price', 0)) * float(ticker.get('quanto_multiplier', 0.0001)),
                'funding_rate': float(ticker.get('funding_rate', 0)) * 100,
                'price_change_pct': float(ticker.get('change_percentage', 0)),
                'num_trades': None,
                'type': 'CEX'
            })

        return results

    except Exception as e:
        print(f"Gate.io error: {e}")
        return []


def fetch_hyperliquid_symbols() -> List[Dict]:
    """Fetch all HyperLiquid symbols"""
    try:
        response = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        data = response.json()

        if not isinstance(data, list) or len(data) < 2:
            return []

        universe = data[0]["universe"]
        asset_ctxs = data[1]

        results = []
        for i, ctx in enumerate(asset_ctxs):
            if i < len(universe):
                symbol = universe[i]["name"]

                # Calculate OI
                oi_value = None
                if 'openInterest' in ctx and 'markPx' in ctx:
                    oi_value = float(ctx['openInterest']) * float(ctx['markPx'])

                # Price change
                price_change = None
                prev_price = float(ctx.get('prevDayPx', 0))
                mark_price = float(ctx.get('markPx', 0))
                if prev_price > 0:
                    price_change = ((mark_price - prev_price) / prev_price) * 100

                results.append({
                    'exchange': 'HyperLiquid',
                    'symbol': symbol,
                    'price': mark_price,
                    'volume': float(ctx.get('dayNtlVlm', 0)),
                    'open_interest': oi_value,
                    'funding_rate': float(ctx.get('funding', 0)) * 100,
                    'price_change_pct': price_change,
                    'num_trades': None,
                    'type': 'DEX'
                })

        return results

    except Exception as e:
        print(f"HyperLiquid error: {e}")
        return []


def fetch_dydx_symbols() -> List[Dict]:
    """Fetch all dYdX v4 symbols"""
    try:
        response = requests.get(
            "https://indexer.dydx.trade/v4/perpetualMarkets",
            timeout=10
        )
        data = response.json()

        if 'markets' not in data:
            return []

        results = []
        for ticker, market in data['markets'].items():
            oracle_price = float(market.get('oraclePrice', 0))

            # Price change
            price_change = None
            price_change_24h = float(market.get('priceChange24H', 0))
            if oracle_price > 0:
                price_change = (price_change_24h / oracle_price) * 100

            results.append({
                'exchange': 'dYdX v4',
                'symbol': ticker,
                'price': oracle_price,
                'volume': float(market.get('volume24H', 0)),
                'open_interest': float(market.get('openInterest', 0)) * oracle_price,
                'funding_rate': float(market.get('nextFundingRate', 0)) * 100,
                'price_change_pct': price_change,
                'num_trades': int(market.get('trades24H', 0)),
                'type': 'DEX'
            })

        return results

    except Exception as e:
        print(f"dYdX error: {e}")
        return []


def fetch_coinbase_symbols() -> List[Dict]:
    """Fetch all Coinbase INTX perpetual symbols"""
    try:
        response = requests.get(
            "https://api.international.coinbase.com/api/v1/instruments",
            timeout=10
        )
        instruments = response.json()

        if not isinstance(instruments, list):
            return []

        results = []
        for inst in instruments:
            if inst.get('type') == 'PERP' and inst.get('trading_state') == 'TRADING':
                quote = inst.get('quote', {})

                # Price change
                price_change = None
                settlement_price = float(quote.get('settlement_price', 0))
                mark_price = float(quote.get('mark_price', 0))
                if settlement_price > 0:
                    price_change = ((mark_price - settlement_price) / settlement_price) * 100

                results.append({
                    'exchange': 'Coinbase INTX',
                    'symbol': inst.get('symbol', ''),
                    'price': mark_price,
                    'volume': float(inst.get('notional_24hr', 0)),
                    'open_interest': float(inst.get('open_interest', 0)) * mark_price,
                    'funding_rate': float(quote.get('predicted_funding', 0)) * 100,
                    'price_change_pct': price_change,
                    'num_trades': int(float(inst.get('qty_24hr', 0))),
                    'type': 'CEX'
                })

        return results

    except Exception as e:
        print(f"Coinbase INTX error: {e}")
        return []


def fetch_historical_data_for_symbols(symbols: List[str], limit: int = 24) -> Dict[str, List[Dict]]:
    """
    Fetch hourly historical OHLCV data for specified symbols from OKX

    Args:
        symbols: List of symbol names (e.g., ['BTC', 'ETH', 'SOL'])
        limit: Number of hourly candles to fetch (default 24 for 24 hours)

    Returns:
        Dict mapping symbol -> list of {timestamp, open, high, low, close, volume}
    """
    historical_data = {}

    print(f"   📊 Fetching {limit}h historical data for {len(symbols)} symbols...")

    for symbol in symbols:
        try:
            # OKX uses -USDT-SWAP pairs
            okx_symbol = f"{symbol}-USDT-SWAP"

            url = "https://www.okx.com/api/v5/market/candles"
            params = {
                'instId': okx_symbol,
                'bar': '1H',
                'limit': limit
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == '0' and data.get('data'):
                    klines = data['data']

                    # Parse klines data (OKX format: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm])
                    candles = []
                    for k in reversed(klines):  # OKX returns newest first, reverse to get oldest first
                        candles.append({
                            'timestamp': int(k[0]),  # Timestamp in ms
                            'open': float(k[1]),
                            'high': float(k[2]),
                            'low': float(k[3]),
                            'close': float(k[4]),
                            'volume': float(k[5])
                        })

                    historical_data[symbol] = candles
                    print(f"      ✓ {symbol}: {len(candles)} candles")
                else:
                    print(f"      ⚠️  {symbol}: API returned error")
            else:
                print(f"      ⚠️  {symbol}: Failed to fetch (status {response.status_code})")

            # Rate limiting
            time.sleep(0.15)

        except Exception as e:
            print(f"      ❌ {symbol}: {e}")

    return historical_data


def generate_time_series_chart(analyses: List[Dict], historical_data: Dict[str, List[Dict]], filename: str) -> bool:
    """Generate time-series chart showing individual symbol movements vs Bitcoin"""

    # Apply style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    if not historical_data:
        print("      ⚠️  No historical data available for chart")
        return False

    # Helper function to get color based on beta
    def get_beta_color(beta):
        if beta > 1.5:
            return '#FF6B35'
        elif beta > 1.0:
            return '#FFA500'
        elif beta > 0.5:
            return '#FDB44B'
        elif beta > 0:
            return '#FFD700'
        else:
            return '#00FF7F'

    # Create beta lookup
    beta_lookup = {a['symbol']: a.get('btc_beta', 1.0) for a in analyses}

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 10))

    # Plot each symbol
    for symbol, candles in historical_data.items():
        if not candles:
            continue

        # Normalize to percentage change from first candle
        initial_price = candles[0]['close']
        timestamps = [datetime.fromtimestamp(c['timestamp'] / 1000) for c in candles]
        percent_changes = [((c['close'] - initial_price) / initial_price) * 100 for c in candles]

        # Get beta and color
        beta = beta_lookup.get(symbol, 1.0)
        color = get_beta_color(beta)
        linewidth = 4 if symbol == 'BTC' else 2
        alpha = 1.0 if symbol == 'BTC' else 0.7

        # Plot line
        ax.plot(timestamps, percent_changes, color=color, linewidth=linewidth,
                alpha=alpha, label=symbol if symbol == 'BTC' else None)

        # Add label at the end
        if timestamps and percent_changes:
            ax.text(timestamps[-1], percent_changes[-1], f'  {symbol}',
                   va='center', ha='left', color=color, fontsize=10,
                   fontweight='bold' if symbol == 'BTC' else 'normal',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='#0a0a0a',
                            edgecolor=color, alpha=0.8, linewidth=1))

    # Zero line
    ax.axhline(y=0, color='#888888', linestyle='-', linewidth=2, alpha=0.6)

    # Formatting
    ax.set_xlabel('Time (12h Period)', fontsize=14, fontweight='bold', color='#FFD700')
    ax.set_ylabel('Price Change (%)', fontsize=14, fontweight='bold', color='#FFD700')
    ax.set_title('BITCOIN BETA ANALYSIS\nIndividual Symbol Movements vs Bitcoin (12h)',
                fontsize=18, fontweight='bold', color='#FFA500', pad=20)

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    fig.autofmt_xdate()

    # Grid and styling
    ax.grid(alpha=0.2, color='#FFD700', linewidth=0.8)
    ax.tick_params(colors='#FFD700', labelsize=11)
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#0a0a0a')

    # Legend
    if ax.get_legend_handles_labels()[0]:
        legend = ax.legend(fontsize=12, framealpha=0.9, loc='upper left')
        plt.setp(legend.get_texts(), color='#FFD700')
        legend.get_frame().set_facecolor('#1a1a1a')
        legend.get_frame().set_edgecolor('#FFA500')
        legend.get_frame().set_linewidth(2)

    # Add glow effects if available
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Save to file
    try:
        plt.tight_layout()
        plt.savefig(filename, dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
        plt.close()
        plt.style.use('default')
        return True
    except Exception as e:
        print(f"      ❌ Error saving chart: {e}")
        plt.close()
        plt.style.use('default')
        return False


def analyze_symbol(symbol: str, exchange_data: List[Dict], btc_price_change: float = None) -> Dict:
    """
    Analyze a single symbol across all exchanges

    Args:
        symbol: Symbol name
        exchange_data: List of exchange data for this symbol
        btc_price_change: BTC 24h price change for beta calculation

    Returns comprehensive trading insights for the symbol
    """
    if not exchange_data:
        return None

    # Filter out invalid data
    valid_data = [d for d in exchange_data if d.get('price', 0) > 0]

    if not valid_data:
        return None

    # Calculate aggregated metrics
    total_volume = sum(d.get('volume', 0) for d in valid_data)
    total_oi = sum(d.get('open_interest', 0) or 0 for d in valid_data)

    # Price analysis
    prices = [d['price'] for d in valid_data]
    avg_price = sum(prices) / len(prices)
    max_price = max(prices)
    min_price = min(prices)
    price_spread_pct = ((max_price - min_price) / min_price) * 100 if min_price > 0 else 0

    # Find best execution venues
    best_liquidity = max(valid_data, key=lambda x: x.get('volume', 0))

    # Funding rate analysis
    funding_rates = [(d['exchange'], d['funding_rate']) for d in valid_data if d.get('funding_rate') is not None]

    best_long = None  # Lowest funding (cheapest to be long)
    best_short = None  # Highest funding (most profitable to be short)
    avg_funding = None

    if funding_rates:
        funding_rates.sort(key=lambda x: x[1])
        best_long = funding_rates[0]  # Lowest
        best_short = funding_rates[-1]  # Highest
        avg_funding = sum(fr[1] for fr in funding_rates) / len(funding_rates)

    # Price change momentum
    price_changes = [d['price_change_pct'] for d in valid_data if d.get('price_change_pct') is not None]
    avg_price_change = sum(price_changes) / len(price_changes) if price_changes else None

    # Bitcoin Beta calculation (correlation to BTC moves)
    btc_beta = None
    beta_interpretation = None
    if avg_price_change is not None and btc_price_change is not None and btc_price_change != 0:
        btc_beta = avg_price_change / btc_price_change

        # Interpret beta
        if btc_beta > 1.5:
            beta_interpretation = "High Beta (Very volatile)"
        elif btc_beta > 1.0:
            beta_interpretation = "High Beta (Amplifies BTC)"
        elif btc_beta > 0.5:
            beta_interpretation = "Medium Beta (Follows BTC)"
        elif btc_beta > 0:
            beta_interpretation = "Low Beta (Weak correlation)"
        elif btc_beta > -0.5:
            beta_interpretation = "Negative Beta (Inverse)"
        else:
            beta_interpretation = "Strong Inverse (Opposite BTC)"

    # Arbitrage opportunity
    arb_opportunity = None
    if price_spread_pct > 0.2:  # >0.2% spread
        high_exchange = max(valid_data, key=lambda x: x['price'])
        low_exchange = min(valid_data, key=lambda x: x['price'])

        arb_opportunity = {
            'type': 'CROSS_EXCHANGE_ARB',
            'buy': low_exchange['exchange'],
            'buy_price': low_exchange['price'],
            'sell': high_exchange['exchange'],
            'sell_price': high_exchange['price'],
            'spread_pct': price_spread_pct,
            'profit_per_unit': max_price - min_price
        }

    # Trading recommendation
    recommendation = generate_symbol_recommendation(
        symbol=symbol,
        avg_funding=avg_funding,
        avg_price_change=avg_price_change,
        total_volume=total_volume,
        total_oi=total_oi,
        price_spread=price_spread_pct
    )

    return {
        'symbol': symbol,
        'num_exchanges': len(valid_data),
        'exchanges': [d['exchange'] for d in valid_data],
        'total_volume_24h': total_volume,
        'total_open_interest': total_oi,
        'avg_price': avg_price,
        'price_range': (min_price, max_price),
        'price_spread_pct': price_spread_pct,
        'avg_funding_rate': avg_funding,
        'best_long_venue': best_long,
        'best_short_venue': best_short,
        'best_liquidity_venue': best_liquidity['exchange'],
        'liquidity_volume': best_liquidity['volume'],
        'avg_price_change_24h': avg_price_change,
        'btc_beta': btc_beta,
        'beta_interpretation': beta_interpretation,
        'arbitrage_opportunity': arb_opportunity,
        'recommendation': recommendation,
        'exchange_details': valid_data
    }


def generate_symbol_recommendation(
    symbol: str,
    avg_funding: Optional[float],
    avg_price_change: Optional[float],
    total_volume: float,
    total_oi: float,
    price_spread: float
) -> str:
    """Generate actionable trading recommendation for a symbol"""

    recommendations = []

    # Volume/liquidity check
    if total_volume < 1e6:  # < $1M daily volume
        return f"⚠️ LOW LIQUIDITY - Avoid trading {symbol} (only ${total_volume/1e6:.2f}M daily volume)"

    # Funding rate signal
    if avg_funding is not None:
        if avg_funding > 0.03:  # >0.03% per 8h
            recommendations.append(f"🔴 EXPENSIVE LONGS - Funding at {avg_funding:.3f}% (avoid long positions)")
        elif avg_funding < -0.03:
            recommendations.append(f"🟢 PROFITABLE LONGS - Negative funding at {avg_funding:.3f}% (collect fees as long)")
        else:
            recommendations.append(f"⚪ NEUTRAL FUNDING - {avg_funding:.3f}% (no directional bias)")

    # Price momentum
    if avg_price_change is not None:
        if avg_price_change > 5:
            recommendations.append(f"📈 STRONG UPTREND - {avg_price_change:+.2f}% (consider trend following)")
        elif avg_price_change < -5:
            recommendations.append(f"📉 STRONG DOWNTREND - {avg_price_change:+.2f}% (caution on longs)")

    # Arbitrage
    if price_spread > 0.3:
        recommendations.append(f"💰 ARBITRAGE AVAILABLE - {price_spread:.2f}% spread between exchanges")

    # OI/Volume ratio
    if total_volume > 0:
        oi_vol_ratio = total_oi / total_volume
        if oi_vol_ratio > 0.5:
            recommendations.append(f"🎯 HIGH CONVICTION - OI/Vol {oi_vol_ratio:.2f}x (position holders)")
        elif oi_vol_ratio < 0.25:
            recommendations.append(f"⚡ DAY-TRADER HEAVY - OI/Vol {oi_vol_ratio:.2f}x (quick flips)")

    if not recommendations:
        return f"✅ TRADEABLE - Standard conditions for {symbol}"

    return " | ".join(recommendations)


def format_symbol_report(symbol_data: Dict[str, List[Dict]], top_n: int = 20) -> str:
    """
    Format comprehensive symbol report

    Args:
        symbol_data: Dict mapping symbol -> list of exchange data
        top_n: Number of top symbols to include in detailed report
    """
    # Analyze each symbol
    analyses = []
    for symbol, data in symbol_data.items():
        analysis = analyze_symbol(symbol, data)
        if analysis:
            analyses.append(analysis)

    # Sort by total volume
    analyses.sort(key=lambda x: x['total_volume_24h'], reverse=True)

    output = []
    output.append("\n" + "="*150)
    output.append(f"{'TOKEN ANALYTICS INTEL':^150}")
    output.append(f"{'Cross-Exchange Analysis • Generated: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'):^150}")
    output.append(f"{'Powered by Virtuoso Crypto [virtuosocrypto.com]':^150}")
    output.append("="*150)

    # Executive summary
    output.append("\n📊 EXECUTIVE SUMMARY")
    output.append("="*150)
    output.append(f"Total Symbols Tracked:     {len(analyses)}")
    output.append(f"Total Market Volume:       ${sum(a['total_volume_24h'] for a in analyses)/1e9:.2f}B")
    output.append(f"Total Open Interest:       ${sum(a['total_open_interest'] for a in analyses)/1e9:.2f}B")
    output.append(f"Exchanges Analyzed:        {len(set(ex for a in analyses for ex in a['exchanges']))}")

    # Top symbols overview table
    output.append("\n" + "="*150)
    output.append(f"TOP {top_n} SYMBOLS BY VOLUME")
    output.append("="*150)
    output.append(f"{'Rank':<5}{'Symbol':<8}{'Volume (12h)':<15}{'OI':<15}{'Exchanges':<12}{'Avg Price':<14}{'Spread':<10}{'Funding':<10}{'24h Δ':<10}{'Beta'}")
    output.append("-"*150)

    for i, analysis in enumerate(analyses[:top_n], 1):
        symbol_str = analysis['symbol'][:7]
        volume_str = f"${analysis['total_volume_24h']/1e9:.2f}B" if analysis['total_volume_24h'] > 1e9 else f"${analysis['total_volume_24h']/1e6:.0f}M"
        oi_str = f"${analysis['total_open_interest']/1e9:.2f}B" if analysis['total_open_interest'] > 1e9 else f"${analysis['total_open_interest']/1e6:.0f}M"
        exchanges_str = f"{analysis['num_exchanges']}x"
        price_str = f"${analysis['avg_price']:,.2f}"
        spread_str = f"{analysis['price_spread_pct']:.2f}%"
        funding_str = f"{analysis['avg_funding_rate']:.3f}%" if analysis['avg_funding_rate'] is not None else "N/A"
        change_str = (f"{analysis['avg_price_change_24h']:+.1f}%" if analysis['avg_price_change_24h'] is not None else "N/A")
        beta_str = (f"{analysis['btc_beta']:.2f}x" if analysis.get('btc_beta') is not None else "N/A")

        output.append(
            f"{i:<5}{symbol_str:<8}{volume_str:<15}{oi_str:<15}{exchanges_str:<12}"
            f"{price_str:<14}{spread_str:<10}{funding_str:<10}{change_str:<10}{beta_str:<10}"
        )

    # Detailed analysis for top symbols
    output.append("\n" + "="*150)
    output.append("DETAILED SYMBOL ANALYSIS (TOP 10)")
    output.append("="*150)

    for i, analysis in enumerate(analyses[:10], 1):
        output.append(f"\n{i}. {analysis['symbol']} - ${analysis['total_volume_24h']/1e9:.2f}B Daily Volume")
        output.append("-"*150)

        # Exchange breakdown
        output.append(f"   Available on {analysis['num_exchanges']} exchanges: {', '.join(analysis['exchanges'])}")

        # Price analysis
        min_p, max_p = analysis['price_range']
        output.append(f"   Price Range: ${min_p:,.2f} - ${max_p:,.2f} (Spread: {analysis['price_spread_pct']:.2f}%)")

        # Best venues
        output.append(f"   Best Liquidity: {analysis['best_liquidity_venue']} (${analysis['liquidity_volume']/1e9:.2f}B)")

        if analysis['best_long_venue']:
            output.append(f"   Best for LONGS: {analysis['best_long_venue'][0]} (funding: {analysis['best_long_venue'][1]:.3f}%)")

        if analysis['best_short_venue']:
            output.append(f"   Best for SHORTS: {analysis['best_short_venue'][0]} (funding: {analysis['best_short_venue'][1]:.3f}%)")

        # Arbitrage
        if analysis['arbitrage_opportunity']:
            arb = analysis['arbitrage_opportunity']
            output.append(f"   💰 ARBITRAGE: Buy on {arb['buy']} @ ${arb['buy_price']:,.2f}, Sell on {arb['sell']} @ ${arb['sell_price']:,.2f}")
            output.append(f"      Spread: {arb['spread_pct']:.2f}% (${arb['profit_per_unit']:.2f} per unit)")

        # Bitcoin Beta
        if analysis.get('btc_beta') is not None:
            output.append(f"   ₿ Bitcoin Beta: {analysis['btc_beta']:.2f}x ({analysis['beta_interpretation']})")

        # Recommendation
        output.append(f"   📋 TRADING INSIGHT: {analysis['recommendation']}")

    # Bitcoin Beta analysis section
    output.append("\n" + "="*150)
    output.append("₿ BITCOIN BETA ANALYSIS (Correlation to BTC Moves)")
    output.append("="*150)
    output.append("📊 Time-Series Chart: See bitcoin_beta_chart_[timestamp].png for visual representation")
    output.append("")

    symbols_with_beta = [a for a in analyses if a.get('btc_beta') is not None and a['symbol'] != 'BTC']

    # Sort by interesting betas (furthest from 1.0)
    symbols_with_beta.sort(key=lambda x: abs(x['btc_beta'] - 1.0), reverse=True)

    output.append(f"{'Symbol':<10}{'Beta':<10}{'24h Δ':<12}{'Interpretation':<30}{'Trading Implication'}")
    output.append("-"*150)

    for a in symbols_with_beta[:15]:
        beta = a['btc_beta']
        change = a.get('avg_price_change_24h', 0)
        interpretation = a.get('beta_interpretation', 'N/A')

        # Trading implication
        if beta > 1.5:
            implication = "⚡ Extreme volatility - Use tight stops"
        elif beta > 1.0:
            implication = "📈 Amplifies BTC moves - High risk/reward"
        elif beta > 0.5:
            implication = "✅ Follows BTC trend - Standard risk"
        elif beta > 0:
            implication = "🔄 Weak BTC correlation - Independent"
        elif beta > -0.5:
            implication = "↔️ Slight hedge - Diversification"
        else:
            implication = "🛡️ Inverse correlation - Portfolio hedge"

        output.append(
            f"{a['symbol']:<10}{beta:<9.2f}x {change:>+6.1f}%     {interpretation:<30}{implication}"
        )

    output.append("\n💡 Beta Interpretation:")
    output.append("   • Beta > 1.5x: Symbol moves much more than BTC (high volatility)")
    output.append("   • Beta ≈ 1.0x: Symbol moves in sync with BTC")
    output.append("   • Beta < 0.5x: Symbol has weak correlation to BTC (more independent)")
    output.append("   • Negative Beta: Symbol moves opposite to BTC (rare, potential hedge)")
    output.append("   • Use high-beta symbols for leveraged BTC exposure")
    output.append("   • Use low/negative-beta symbols for portfolio diversification")

    # Arbitrage opportunities across all symbols
    arb_opportunities = [a for a in analyses if a['arbitrage_opportunity'] is not None]
    arb_opportunities.sort(key=lambda x: x['arbitrage_opportunity']['spread_pct'], reverse=True)

    if arb_opportunities:
        output.append("\n" + "="*150)
        output.append(f"CROSS-EXCHANGE ARBITRAGE OPPORTUNITIES (Top 10)")
        output.append("="*150)
        output.append(f"{'Symbol':<10}{'Buy From':<16}{'Buy Price':<14}{'Sell To':<16}{'Sell Price':<14}{'Spread':<10}{'Profit/Unit'}")
        output.append("-"*150)

        for a in arb_opportunities[:10]:
            arb = a['arbitrage_opportunity']
            output.append(
                f"{a['symbol']:<10}{arb['buy']:<16}${arb['buy_price']:<13,.2f}"
                f"{arb['sell']:<16}${arb['sell_price']:<13,.2f}"
                f"{arb['spread_pct']:<9.2f}% ${arb['profit_per_unit']:.2f}"
            )

    # Funding rate comparison
    output.append("\n" + "="*150)
    output.append("FUNDING RATE HOTSPOTS (Highest Cost to Hold)")
    output.append("="*150)

    # Get symbols with funding data
    with_funding = [a for a in analyses if a['avg_funding_rate'] is not None]
    with_funding.sort(key=lambda x: abs(x['avg_funding_rate']), reverse=True)

    output.append(f"{'Symbol':<10}{'Avg Funding':<15}{'Annual Cost':<15}{'Best Long':<20}{'Best Short':<20}{'Interpretation'}")
    output.append("-"*150)

    for a in with_funding[:15]:
        funding = a['avg_funding_rate']
        annual = funding * 3 * 365  # 3 periods per day

        best_long_str = f"{a['best_long_venue'][0]}: {a['best_long_venue'][1]:.3f}%" if a['best_long_venue'] else "N/A"
        best_short_str = f"{a['best_short_venue'][0]}: {a['best_short_venue'][1]:.3f}%" if a['best_short_venue'] else "N/A"

        if funding > 0.03:
            interpretation = "🔴 Very expensive longs"
        elif funding < -0.03:
            interpretation = "🟢 Longs get paid"
        else:
            interpretation = "⚪ Neutral"

        output.append(
            f"{a['symbol']:<10}{funding:<14.3f}% {annual:<14.1f}% "
            f"{best_long_str:<20}{best_short_str:<20}{interpretation}"
        )

    # Footer
    output.append("\n" + "="*150)
    output.append("📝 NOTES")
    output.append("="*150)
    output.append("• Spread = Price difference between highest and lowest exchange")
    output.append("• Funding Rate = Cost/profit to hold position (positive = longs pay shorts)")
    output.append("• Best Long Venue = Exchange with lowest funding rate (cheapest to be long)")
    output.append("• Best Short Venue = Exchange with highest funding rate (most profitable to be short)")
    output.append("• OI/Vol Ratio: >0.5x = conviction trades, <0.25x = day trading")
    output.append("• Arbitrage opportunities require fast execution and account balancing across exchanges")
    output.append("\n")

    return "\n".join(output)


def generate_top_symbols_volume_chart(analyses: List[Dict], top_n: int = 15) -> bytes:
    """Generate top symbols by volume bar chart with Cyberpunk Amber styling"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    # Get top symbols
    top_symbols = analyses[:top_n]
    symbols = [a['symbol'][:6] for a in top_symbols]  # Truncate long symbols
    volumes = [a['total_volume_24h'] / 1e9 for a in top_symbols]  # Convert to billions

    # Create color gradient (amber)
    colors = []
    for i, vol in enumerate(volumes):
        if i == 0:
            colors.append('#FF6B35')  # Brightest for #1
        elif i < 3:
            colors.append('#FFA500')  # Medium for top 3
        else:
            colors.append('#FDB44B')  # Warm amber for rest

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create bars
    bars = ax.barh(symbols, volumes, color=colors, alpha=0.9, edgecolor='#FFA500', linewidth=2)

    # Add glow effect
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Add value labels
    for i, (bar, vol) in enumerate(zip(bars, volumes)):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height() / 2,
                f'${vol:.2f}B',
                ha='left', va='center',
                fontsize=10, fontweight='bold', color='#FFD700',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='#FFA500', alpha=0.8, linewidth=1))

    # Styling
    ax.set_xlabel('24h Volume (Billions USD)', fontsize=13, fontweight='bold', color='#FFD700', labelpad=10)
    ax.set_title(f'⚡ Top {top_n} Symbols by Trading Volume', fontsize=15, fontweight='bold', pad=20, color='#FFA500')

    ax.grid(axis='x', alpha=0.2, color='#FFD700', linewidth=0.5)
    ax.tick_params(axis='both', colors='#FFD700', labelsize=10)

    # Dark background styling
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#0a0a0a')

    # Invert y-axis so #1 is at top
    ax.invert_yaxis()

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')

    return chart_bytes


def generate_funding_comparison_chart(analyses: List[Dict], top_n: int = 15) -> bytes:
    """Generate funding rate comparison chart for top symbols with Cyberpunk Amber styling"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    # Get top symbols by volume that have funding data
    symbols_with_funding = [a for a in analyses if a.get('avg_funding_rate') is not None]
    top_symbols = symbols_with_funding[:top_n]

    symbols = [a['symbol'][:6] for a in top_symbols]
    funding_rates = [a['avg_funding_rate'] for a in top_symbols]

    # Color based on funding rate
    colors = []
    for rate in funding_rates:
        if rate > 0.03:
            colors.append('#FF6B35')  # Red - expensive longs
        elif rate < -0.03:
            colors.append('#00FF7F')  # Green - profitable longs
        else:
            colors.append('#FDB44B')  # Amber - neutral

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create bars
    bars = ax.barh(symbols, funding_rates, color=colors, alpha=0.9, edgecolor='#FFA500', linewidth=2)

    # Add glow effect
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Add value labels
    for bar, rate in zip(bars, funding_rates):
        width = bar.get_width()
        x_pos = width if width >= 0 else 0
        ha = 'left' if width >= 0 else 'right'

        # Calculate annual rate
        annual = rate * 3 * 365

        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f' {rate:.3f}% ({annual:+.1f}% annual)',
                ha=ha, va='center',
                fontsize=9, fontweight='bold', color='#FFD700',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='#FFA500', alpha=0.8, linewidth=1))

    # Styling
    ax.set_xlabel('Funding Rate (% per 8h)', fontsize=13, fontweight='bold', color='#FFD700', labelpad=10)
    ax.set_title(f'💰 Funding Rates - Top {top_n} Symbols by Volume', fontsize=15, fontweight='bold', pad=20, color='#FFA500')

    # Reference line at zero
    ax.axvline(x=0, color='#888888', linestyle='-', linewidth=1.5, alpha=0.8)
    ax.grid(axis='x', alpha=0.2, color='#FFD700', linewidth=0.5)
    ax.tick_params(axis='both', colors='#FFD700', labelsize=10)

    # Dark background styling
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#0a0a0a')

    # Invert y-axis
    ax.invert_yaxis()

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')

    return chart_bytes


def generate_arbitrage_opportunities_chart(analyses: List[Dict], top_n: int = 12) -> bytes:
    """Generate arbitrage opportunities chart with Cyberpunk Amber styling"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    # Get arbitrage opportunities
    arb_opportunities = [a for a in analyses if a['arbitrage_opportunity'] is not None]
    arb_opportunities.sort(key=lambda x: x['arbitrage_opportunity']['spread_pct'], reverse=True)

    # Filter out extreme outliers (>100% spread) for better visualization
    filtered_arbs = [a for a in arb_opportunities if a['arbitrage_opportunity']['spread_pct'] <= 100]

    if not filtered_arbs:
        # If all are >100%, just take top reasonable ones
        filtered_arbs = arb_opportunities[:top_n]

    top_arbs = filtered_arbs[:top_n]

    symbols = [a['symbol'][:6] for a in top_arbs]
    spreads = [a['arbitrage_opportunity']['spread_pct'] for a in top_arbs]

    # Color gradient based on spread magnitude
    colors = []
    for spread in spreads:
        if spread > 10:
            colors.append('#FF6B35')  # Bright red - huge opportunity
        elif spread > 2:
            colors.append('#FFA500')  # Orange - good opportunity
        else:
            colors.append('#FDB44B')  # Amber - moderate

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create bars
    bars = ax.barh(symbols, spreads, color=colors, alpha=0.9, edgecolor='#FFA500', linewidth=2)

    # Add glow effect
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Add value labels with exchange info
    for a, bar, spread in zip(top_arbs, bars, spreads):
        width = bar.get_width()
        arb = a['arbitrage_opportunity']

        label = f"{spread:.2f}% ({arb['buy'][:3]}→{arb['sell'][:3]})"

        ax.text(width, bar.get_y() + bar.get_height() / 2,
                f' {label}',
                ha='left', va='center',
                fontsize=9, fontweight='bold', color='#FFD700',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='#FFA500', alpha=0.8, linewidth=1))

    # Styling
    ax.set_xlabel('Price Spread (%)', fontsize=13, fontweight='bold', color='#FFD700', labelpad=10)
    ax.set_title(f'🎯 Cross-Exchange Arbitrage Opportunities (Top {top_n})', fontsize=15, fontweight='bold', pad=20, color='#FFA500')

    ax.grid(axis='x', alpha=0.2, color='#FFD700', linewidth=0.5)
    ax.tick_params(axis='both', colors='#FFD700', labelsize=10)

    # Dark background styling
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#0a0a0a')

    # Invert y-axis
    ax.invert_yaxis()

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')

    return chart_bytes


def generate_bitcoin_beta_chart_timeseries(analyses: List[Dict], historical_data: Dict[str, List[Dict]]) -> bytes:
    """Generate time-series chart showing individual symbol movements vs Bitcoin"""

    # Apply style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    if not historical_data:
        # Return empty chart if no data
        fig, ax = plt.subplots(figsize=(16, 10))
        ax.text(0.5, 0.5, 'No Historical Data Available', ha='center', va='center', fontsize=24, color='#FFA500')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
        buf.seek(0)
        chart_bytes = buf.getvalue()
        plt.close()
        plt.style.use('default')
        return chart_bytes

    # Create a diverse color palette (excluding orange for BTC)
    color_palette = [
        '#00FF7F',  # Spring Green
        '#FF1493',  # Deep Pink
        '#00CED1',  # Dark Turquoise
        '#FFD700',  # Gold
        '#FF6347',  # Tomato
        '#7B68EE',  # Medium Slate Blue
        '#FF69B4',  # Hot Pink
        '#20B2AA',  # Light Sea Green
        '#FF8C00',  # Dark Orange
        '#9370DB',  # Medium Purple
        '#32CD32',  # Lime Green
        '#FF4500',  # Orange Red
        '#00BFFF',  # Deep Sky Blue
        '#ADFF2F',  # Green Yellow
        '#FF00FF',  # Magenta
        '#00FA9A',  # Medium Spring Green
        '#DC143C',  # Crimson
        '#00FFFF',  # Cyan
        '#FF1493',  # Deep Pink
        '#7FFF00',  # Chartreuse
    ]

    # Create beta lookup
    beta_lookup = {a['symbol']: a.get('btc_beta', 1.0) for a in analyses}

    # Create figure with extra space for legend
    fig, ax = plt.subplots(figsize=(16, 10))

    # Collect symbol data for legend ordering
    symbol_data = []
    color_index = 0

    # Plot each symbol
    for symbol, candles in historical_data.items():
        if not candles:
            continue

        # Normalize to percentage change from first candle
        initial_price = candles[0]['close']
        timestamps = [datetime.fromtimestamp(c['timestamp'] / 1000) for c in candles]
        percent_changes = [((c['close'] - initial_price) / initial_price) * 100 for c in candles]

        # Get beta and color
        beta = beta_lookup.get(symbol, 1.0)

        # BTC gets orange, all others get unique colors from palette
        if symbol == 'BTC':
            color = '#FFA500'
        else:
            color = color_palette[color_index % len(color_palette)]
            color_index += 1

        linewidth = 4 if symbol == 'BTC' else 2
        alpha = 1.0 if symbol == 'BTC' else 0.8

        # Plot line with label for legend
        line, = ax.plot(timestamps, percent_changes, color=color, linewidth=linewidth,
                       alpha=alpha, label=symbol)

        # Add inline label at end of line
        if timestamps and percent_changes:
            final_x = timestamps[-1]
            final_y = percent_changes[-1]
            ax.text(final_x, final_y, f' {symbol}',
                   fontsize=6, color=color, fontweight='bold',
                   ha='left', va='center', alpha=0.9)

            symbol_data.append({
                'symbol': symbol,
                'final_y': final_y,
                'beta': beta,
                'line': line,
                'color': color
            })

    # Zero line
    ax.axhline(y=0, color='#888888', linestyle='-', linewidth=2, alpha=0.6)

    # Formatting
    ax.set_xlabel('Time (12h Period)', fontsize=9, fontweight='bold', color='#FFD700')
    ax.set_ylabel('Price Change (%)', fontsize=9, fontweight='bold', color='#FFD700')

    # Calculate market summary
    outperformers = len([d for d in symbol_data if d['final_y'] > 1.0])
    underperformers = len([d for d in symbol_data if d['final_y'] < -3.0])

    # Add timestamp and market summary to title
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    ax.set_title(f'CRYPTO PERFORMANCE TRACKER\n12h Returns | {outperformers} Outperformers • {underperformers} Underperformers\nGenerated: {current_time}',
                fontsize=12, fontweight='bold', color='#FFA500', pad=20)

    # Format x-axis with proper date handling
    if symbol_data and len(symbol_data) > 0:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()

    # Styling (very subtle grid)
    ax.grid(alpha=0.08, color='#FFD700', linewidth=0.5)
    ax.tick_params(colors='#FFD700', labelsize=7)
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#0a0a0a')

    # Sort symbols by final y-position (top to bottom) for ordered legend
    symbol_data.sort(key=lambda d: d['final_y'], reverse=True)

    # Create ordered legend handles and labels with matching colors
    handles = [d['line'] for d in symbol_data]
    # Show raw returns (final_y) instead of beta
    labels = [f"{d['symbol']} {d['final_y']:+.1f}%" for d in symbol_data]

    # Add legend on the right side in a single column
    legend = ax.legend(handles, labels,
                      fontsize=8,
                      framealpha=0.95,
                      loc='center left',
                      bbox_to_anchor=(1.01, 0.5),
                      ncol=1)

    # Match text colors to line colors
    for i, text in enumerate(legend.get_texts()):
        if i < len(symbol_data):
            text.set_color(symbol_data[i]['color'])
            text.set_fontweight('bold')

    legend.get_frame().set_facecolor('#1a1a1a')
    legend.get_frame().set_edgecolor('#FFA500')
    legend.get_frame().set_linewidth(2)

    # Skip glow effects to prevent rendering issues
    # try:
    #     import mplcyberpunk
    #     mplcyberpunk.add_glow_effects(ax=ax)
    # except (ImportError, TypeError):
    #     pass

    # Add watermark at bottom right
    fig.text(0.98, 0.02, 'Generated by Virtuoso Crypto',
             ha='right', va='bottom', fontsize=8, color='#FFA500',
             alpha=0.6, style='italic', fontweight='bold')

    # Save to bytes
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')

    return chart_bytes


def generate_bitcoin_beta_chart(analyses: List[Dict], top_n: int = 15) -> bytes:
    """Generate Beta Champions chart showing top symbols by beta category (DEPRECATED - use timeseries version)"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    # Get symbols with beta data
    symbols_with_beta = [a for a in analyses if a.get('btc_beta') is not None and a['symbol'] != 'BTC']

    if not symbols_with_beta:
        # Return empty chart if no data
        fig, ax = plt.subplots(figsize=(14, 10))
        ax.text(0.5, 0.5, 'No Beta Data Available', ha='center', va='center', fontsize=24, color='#FFA500')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
        buf.seek(0)
        chart_bytes = buf.getvalue()
        plt.close()
        plt.style.use('default')
        return chart_bytes

    # Sort by volume for each category
    high_beta = sorted([a for a in symbols_with_beta if a['btc_beta'] > 1.5],
                      key=lambda x: x['total_volume_24h'], reverse=True)[:top_n//3]
    amplifies_btc = sorted([a for a in symbols_with_beta if 1.0 < a['btc_beta'] <= 1.5],
                           key=lambda x: x['total_volume_24h'], reverse=True)[:top_n//3]
    inverse = sorted([a for a in symbols_with_beta if a['btc_beta'] < 0],
                    key=lambda x: x['total_volume_24h'], reverse=True)[:top_n//3]

    # Prepare data
    categories = []
    symbols_list = []
    betas_list = []
    colors_list = []
    volumes_list = []

    for a in high_beta:
        categories.append('High Volatility (>1.5x)')
        symbols_list.append(a['symbol'][:10])
        betas_list.append(a['btc_beta'])
        colors_list.append('#FF6B35')
        volumes_list.append(a['total_volume_24h'] / 1e9)

    for a in amplifies_btc:
        categories.append('Amplifies BTC (1.0-1.5x)')
        symbols_list.append(a['symbol'][:10])
        betas_list.append(a['btc_beta'])
        colors_list.append('#FFA500')
        volumes_list.append(a['total_volume_24h'] / 1e9)

    for a in inverse:
        categories.append('Inverse (<0)')
        symbols_list.append(a['symbol'][:10])
        betas_list.append(a['btc_beta'])
        colors_list.append('#00FF7F')
        volumes_list.append(a['total_volume_24h'] / 1e9)

    if not symbols_list:
        # Return empty chart
        fig, ax = plt.subplots(figsize=(14, 10))
        ax.text(0.5, 0.5, 'No Beta Champions Found', ha='center', va='center', fontsize=24, color='#FFA500')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
        buf.seek(0)
        chart_bytes = buf.getvalue()
        plt.close()
        plt.style.use('default')
        return chart_bytes

    # Create chart
    fig, ax = plt.subplots(figsize=(14, 10))

    y_positions = range(len(symbols_list))
    bars = ax.barh(y_positions, betas_list, color=colors_list,
                   alpha=0.8, edgecolor='#FFA500', linewidth=2.5)

    # Add labels with symbol name, beta, and volume
    for i, (sym, beta, vol) in enumerate(zip(symbols_list, betas_list, volumes_list)):
        label_text = f'{sym} ({beta:.2f}x) • ${vol:.1f}B'
        ax.text(beta if beta > 0 else 0, i, f'  {label_text}',
                ha='left' if beta > 0 else 'right', va='center',
                fontsize=11, fontweight='bold', color='#FFD700',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a1a1a',
                         edgecolor=colors_list[i], alpha=0.8, linewidth=1.5))

    # Category dividers
    category_positions = {}
    for i, cat in enumerate(categories):
        if cat not in category_positions:
            category_positions[cat] = i

    for cat, pos in category_positions.items():
        if pos > 0:
            ax.axhline(y=pos - 0.5, color='#FFD700', linestyle='--',
                      linewidth=1, alpha=0.3)

    ax.set_yticks(y_positions)
    ax.set_yticklabels([])

    # Reference lines
    ax.axvline(x=1.0, color='#FFA500', linestyle='--', linewidth=3, alpha=0.8, label='1.0x (Matches BTC)')
    ax.axvline(x=0, color='#888888', linestyle='-', linewidth=2, alpha=0.6)

    ax.set_xlabel('Bitcoin Beta', fontsize=14, fontweight='bold', color='#FFD700')
    ax.set_title('BITCOIN BETA CHAMPIONS\nTop Symbols by Beta Category (Sorted by Volume)',
                fontsize=18, fontweight='bold', color='#FFA500', pad=20)
    ax.grid(axis='x', alpha=0.2, color='#FFD700', linewidth=0.8)
    ax.tick_params(colors='#FFD700', labelsize=11)

    # Legend
    legend = ax.legend(fontsize=11, framealpha=0.9, loc='lower right')
    plt.setp(legend.get_texts(), color='#FFD700')
    legend.get_frame().set_facecolor('#1a1a1a')
    legend.get_frame().set_edgecolor('#FFA500')
    legend.get_frame().set_linewidth(2)

    # Add glow effects if available
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')

    return chart_bytes


def send_symbol_report_to_discord(report_text: str, analyses: List[Dict], historical_data: Dict[str, List[Dict]], webhook_url: str) -> bool:
    """Send Token Analytics Intel to Discord as summary embed + file attachment"""

    try:
        # Calculate summary metrics
        total_symbols = len(analyses)
        total_volume = sum(a['total_volume_24h'] for a in analyses)
        total_oi = sum(a['total_open_interest'] for a in analyses)

        # Get top 3 by volume
        top_3 = analyses[:3]

        # Count arbitrage opportunities
        arb_count = sum(1 for a in analyses if a['arbitrage_opportunity'] is not None)

        # Get top arbitrage if exists
        arb_opportunities = [a for a in analyses if a['arbitrage_opportunity'] is not None]
        arb_opportunities.sort(key=lambda x: x['arbitrage_opportunity']['spread_pct'], reverse=True)

        top_arb_str = "None"
        if arb_opportunities:
            top = arb_opportunities[0]
            arb = top['arbitrage_opportunity']
            top_arb_str = f"{top['symbol']}: {arb['spread_pct']:.1f}% spread"

        # Get extreme funding rates
        with_funding = [a for a in analyses if a['avg_funding_rate'] is not None]
        with_funding.sort(key=lambda x: abs(x['avg_funding_rate']), reverse=True)

        extreme_funding_str = "Normal"
        if with_funding and abs(with_funding[0]['avg_funding_rate']) > 0.1:
            top_funding = with_funding[0]
            extreme_funding_str = f"{top_funding['symbol']}: {top_funding['avg_funding_rate']:.2f}%"

        # Create summary embed
        embed = {
            "title": f"📈 Token Analytics Intel - {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}",
            "description": (
                f"**Symbols Tracked:** {total_symbols}\n"
                f"**Total Volume:** ${total_volume/1e9:.2f}B\n"
                f"**Total Open Interest:** ${total_oi/1e9:.2f}B"
            ),
            "color": 0x00FF7F,  # Spring green
            "fields": [
                {
                    "name": "🥇 Top 3 Symbols (by Volume)",
                    "value": "\n".join([
                        f"**{i+1}. {a['symbol']}** - ${a['total_volume_24h']/1e9:.2f}B ({a['num_exchanges']} exchanges)"
                        for i, a in enumerate(top_3)
                    ]),
                    "inline": False
                },
                {
                    "name": "💰 Cross-Exchange Arbitrage",
                    "value": f"{arb_count} opportunities\nTop: {top_arb_str}",
                    "inline": True
                },
                {
                    "name": "⚡ Extreme Funding",
                    "value": extreme_funding_str,
                    "inline": True
                },
                {
                    "name": "📊 Market Diversity",
                    "value": f"{len(set(ex for a in analyses for ex in a['exchanges']))} exchanges analyzed",
                    "inline": True
                }
            ],
            "footer": {
                "text": "Full symbol analysis attached • Cross-exchange comparison"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Add top symbols with recommendations
        if len(analyses) > 0:
            top_insights = []
            for a in analyses[:5]:
                # Shorten recommendation for embed
                rec = a['recommendation']
                if len(rec) > 80:
                    rec = rec[:77] + "..."

                # Get key metric
                metric = ""
                if a['avg_funding_rate'] is not None:
                    if abs(a['avg_funding_rate']) > 0.05:
                        metric = f"Funding: {a['avg_funding_rate']:.2f}%"

                top_insights.append(f"**{a['symbol']}**: {metric if metric else rec}")

            embed["fields"].append({
                "name": "🎯 Top Symbol Insights",
                "value": "\n".join(top_insights[:3]),  # Top 3 only to save space
                "inline": False
            })

        # Create filename
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
        filename = f"symbol_report_{timestamp}.txt"

        # Generate charts
        print("   • Generating charts...")

        volume_chart = None
        funding_chart = None
        arbitrage_chart = None
        beta_chart = None

        try:
            volume_chart = generate_top_symbols_volume_chart(analyses, top_n=15)
            print("      ✓ Volume chart generated")
        except Exception as e:
            print(f"      ⚠️  Could not generate volume chart: {e}")

        try:
            funding_chart = generate_funding_comparison_chart(analyses, top_n=15)
            print("      ✓ Funding chart generated")
        except Exception as e:
            print(f"      ⚠️  Could not generate funding chart: {e}")

        try:
            arbitrage_chart = generate_arbitrage_opportunities_chart(analyses, top_n=12)
            print("      ✓ Arbitrage chart generated")
        except Exception as e:
            print(f"      ⚠️  Could not generate arbitrage chart: {e}")

        try:
            beta_chart = generate_bitcoin_beta_chart_timeseries(analyses, historical_data)
            print("      ✓ Bitcoin Beta chart generated")
        except Exception as e:
            print(f"      ⚠️  Could not generate Bitcoin Beta chart: {e}")

        # Prepare multipart form data
        files = {
            'file1': (filename, report_text.encode('utf-8'), 'text/plain')
        }

        # Add charts if generated successfully
        file_counter = 2

        if volume_chart:
            files[f'file{file_counter}'] = (f"top_symbols_volume_{timestamp}.png", volume_chart, 'image/png')
            file_counter += 1

        if funding_chart:
            files[f'file{file_counter}'] = (f"funding_rates_{timestamp}.png", funding_chart, 'image/png')
            file_counter += 1

        if arbitrage_chart:
            files[f'file{file_counter}'] = (f"arbitrage_opportunities_{timestamp}.png", arbitrage_chart, 'image/png')
            file_counter += 1

        if beta_chart:
            files[f'file{file_counter}'] = (f"bitcoin_beta_{timestamp}.png", beta_chart, 'image/png')
            file_counter += 1

        payload = {
            'username': 'Symbol Analysis Bot',
            'embeds': [embed]
        }

        # Send to Discord
        response = requests.post(
            webhook_url,
            files=files,
            data={'payload_json': json.dumps(payload)},
            timeout=10
        )

        if response.status_code == 200:
            chart_count = sum([bool(volume_chart), bool(funding_chart), bool(arbitrage_chart), bool(beta_chart)])
            print(f"\n✅ Token Analytics Intel sent to Discord!")
            print(f"   • Summary embed posted")
            print(f"   • Full report attached: {filename}")
            print(f"   • {chart_count}/4 charts attached")
            if volume_chart:
                print(f"     ✓ Top symbols volume chart")
            if funding_chart:
                print(f"     ✓ Funding rates comparison chart")
            if arbitrage_chart:
                print(f"     ✓ Arbitrage opportunities chart")
            if beta_chart:
                print(f"     ✓ Bitcoin Beta chart")
            print(f"   • {total_symbols} symbols analyzed")
            print(f"   • {arb_count} arbitrage opportunities found")
            return True
        else:
            print(f"\n❌ Discord webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Error sending to Discord: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 Generating Token Analytics Intel...\n")
    print("⏳ Fetching data from 8 exchanges (30-40 seconds)...\n")

    # Fetch and group data
    symbol_data = fetch_symbol_data_from_exchanges()

    print(f"✅ Collected data for {len(symbol_data)} symbols\n")

    # Get BTC price change for beta calculation
    btc_data = symbol_data.get('BTC', [])
    btc_price_change = None
    if btc_data:
        btc_changes = [d.get('price_change_pct') for d in btc_data if d.get('price_change_pct') is not None]
        if btc_changes:
            btc_price_change = sum(btc_changes) / len(btc_changes)
            print(f"📊 BTC 24h change: {btc_price_change:+.2f}% (using for beta calculation)\n")

    # Analyze symbols
    analyses = []
    for symbol, data in symbol_data.items():
        analysis = analyze_symbol(symbol, data, btc_price_change=btc_price_change)
        if analysis:
            analyses.append(analysis)

    # Sort by volume
    analyses.sort(key=lambda x: x['total_volume_24h'], reverse=True)

    # Fetch historical data for top 25 symbols (including BTC)
    print("📈 Fetching historical price data for top 25 symbols...\n")
    top_symbols = ['BTC'] + [a['symbol'] for a in analyses[:24] if a['symbol'] != 'BTC']
    historical_data = fetch_historical_data_for_symbols(top_symbols, limit=12)
    print(f"\n✅ Fetched historical data for {len(historical_data)} symbols\n")

    # Generate time-series chart
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

    # Get project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)

    chart_filename = os.path.join(data_dir, f"bitcoin_beta_chart_{timestamp}.png")

    print("🎨 Generating Bitcoin Beta time-series chart...")
    try:
        chart_bytes = generate_bitcoin_beta_chart_timeseries(analyses, historical_data)
        with open(chart_filename, 'wb') as f:
            f.write(chart_bytes)
        print(f"   ✓ Chart saved to: {chart_filename}\n")
    except Exception as e:
        print(f"   ⚠️  Chart generation failed: {e}\n")

    # Generate report
    report = format_symbol_report(symbol_data, top_n=20)

    # Update chart filename in report
    chart_basename = os.path.basename(chart_filename)
    report = report.replace("bitcoin_beta_chart_[timestamp].png", chart_basename)

    # Display
    print(report)

    # Save to file
    txt_filename = os.path.join(data_dir, f"symbol_report_{timestamp}.txt")

    try:
        with open(txt_filename, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to: {txt_filename}")
    except Exception as e:
        print(f"⚠️  Could not save report: {e}")

    # Send to Discord if configured
    try:
        with open('config/config.yaml', 'r') as f:
            content = f.read()
            # Substitute environment variables
            from os.path import expandvars
            content = expandvars(content)
            config = yaml.safe_load(content)

        discord_config = config.get('discord', {})
        webhook_url = discord_config.get('webhook_url')

        if webhook_url and discord_config.get('enabled', False):
            print(f"\n📤 Sending to Discord webhook...")
            send_symbol_report_to_discord(report, analyses, historical_data, webhook_url)
        else:
            print("\n⚠️  Discord integration not enabled in config/config.yaml")
    except FileNotFoundError:
        print("\n⚠️  Config file not found: config/config.yaml")
    except Exception as e:
        print(f"\n⚠️  Could not load Discord config: {e}")
