#!/usr/bin/env python3
"""
Complete 9-Exchange Perpetual Futures Comparison
CEX: Binance, Bybit, OKX, Bitget, Gate.io, Coinbase INTX (Top 6 globally)
DEX: HyperLiquid, AsterDEX, dYdX v4 (Top 3 DEXs)

Enhanced Metrics:
- 24h Trading Volume
- Open Interest (OI)
- Funding Rate
- OI/Volume Ratio
- 24h Price Change %
- Number of Trades (where available)
"""

import requests
from datetime import datetime, timezone
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_binance_enhanced() -> Dict:
    """Fetch Binance with enhanced metrics"""
    try:
        # Get 24hr ticker data
        ticker_response = requests.get(
            "https://fapi.binance.com/fapi/v1/ticker/24hr",
            timeout=10
        )
        tickers = ticker_response.json()

        if not isinstance(tickers, list):
            return {'exchange': 'Binance', 'status': 'error', 'error': str(tickers)}

        # Calculate totals
        total_volume = sum(float(t.get('quoteVolume', 0)) for t in tickers)
        total_trades = sum(int(t.get('count', 0)) for t in tickers)

        # Get BTC data for reference
        btc_data = next((t for t in tickers if t['symbol'] == 'BTCUSDT'), {})

        # Create price lookup for OI calculation
        price_map = {t['symbol']: float(t.get('lastPrice', 0)) for t in tickers}

        # Fetch OI for ALL pairs using parallel requests
        def fetch_single_oi(symbol):
            """Fetch OI for a single symbol"""
            try:
                oi_resp = requests.get(
                    f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}",
                    timeout=5
                ).json()
                if 'openInterest' in oi_resp:
                    oi_value = float(oi_resp['openInterest']) * price_map.get(symbol, 0)
                    return oi_value
            except Exception:
                pass
            return 0

        # Parallel fetch with ThreadPoolExecutor (max 30 concurrent to respect rate limits)
        total_oi = 0
        oi_samples = 0
        with ThreadPoolExecutor(max_workers=30) as executor:
            symbols = [t['symbol'] for t in tickers]
            future_to_symbol = {executor.submit(fetch_single_oi, symbol): symbol for symbol in symbols}

            for future in as_completed(future_to_symbol):
                oi_value = future.result()
                if oi_value > 0:
                    total_oi += oi_value
                    oi_samples += 1

        # Get funding rate for BTC
        funding_rate = None
        try:
            funding_resp = requests.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",
                timeout=5
            ).json()
            funding_rate = float(funding_resp.get('lastFundingRate', 0)) * 100  # Convert to percentage
        except Exception:
            pass

        # Get top 5 pairs
        top_pairs = sorted(tickers, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)[:5]

        return {
            'exchange': 'Binance',
            'volume': total_volume,
            'open_interest': total_oi if oi_samples > 0 else None,
            'funding_rate': funding_rate,
            'oi_volume_ratio': (total_oi / total_volume) if (total_oi > 0 and total_volume > 0) else None,
            'price_change_pct': float(btc_data.get('priceChangePercent', 0)) if btc_data else None,
            'num_trades': total_trades,
            'markets': len(tickers),
            'type': 'CEX',
            'top_pair': top_pairs[0]['symbol'] if top_pairs else 'N/A',
            'top_volume': float(top_pairs[0].get('quoteVolume', 0)) if top_pairs else 0,
            'status': 'success',
            'oi_coverage': f"{oi_samples}/{len(tickers)}"  # Full coverage tracking
        }

    except Exception as e:
        return {'exchange': 'Binance', 'status': 'error', 'error': str(e)}


def fetch_bybit_enhanced() -> Dict:
    """Fetch Bybit with enhanced metrics"""
    try:
        response = requests.get(
            "https://api.bybit.com/v5/market/tickers?category=linear",
            timeout=10
        )
        data = response.json()

        if data.get('retCode') != 0:
            return {'exchange': 'Bybit', 'status': 'error', 'error': data.get('msg')}

        tickers = data['result']['list']

        # Calculate metrics
        total_volume = sum(float(t.get('turnover24h', 0)) for t in tickers)
        total_oi = sum(float(t.get('openInterestValue', 0)) for t in tickers)

        # Get BTC data
        btc_data = next((t for t in tickers if t['symbol'] == 'BTCUSDT'), {})
        funding_rate = float(btc_data.get('fundingRate', 0)) * 100 if btc_data else None
        price_change = float(btc_data.get('price24hPcnt', 0)) * 100 if btc_data else None

        # Top pairs
        top_pairs = sorted(tickers, key=lambda x: float(x.get('turnover24h', 0)), reverse=True)[:5]

        return {
            'exchange': 'Bybit',
            'volume': total_volume,
            'open_interest': total_oi,
            'funding_rate': funding_rate,
            'oi_volume_ratio': total_oi / total_volume if total_volume > 0 else None,
            'price_change_pct': price_change,
            'num_trades': None,  # Not available in ticker
            'markets': len(tickers),
            'type': 'CEX',
            'top_pair': top_pairs[0]['symbol'] if top_pairs else 'N/A',
            'top_volume': float(top_pairs[0].get('turnover24h', 0)) if top_pairs else 0,
            'status': 'success'
        }

    except Exception as e:
        return {'exchange': 'Bybit', 'status': 'error', 'error': str(e)}


def fetch_okx_enhanced() -> Dict:
    """Fetch OKX with enhanced metrics"""
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
            timeout=10
        )
        data = response.json()

        if data.get('code') != '0':
            return {'exchange': 'OKX', 'status': 'error', 'error': data.get('msg')}

        tickers = data['data']

        # Calculate USD volumes
        volumes = []
        for t in tickers:
            try:
                vol_usd = float(t.get('volCcy24h', 0)) * float(t.get('last', 0))
                volumes.append({'symbol': t['instId'], 'volume': vol_usd})
            except Exception:
                continue

        total_volume = sum(v['volume'] for v in volumes)

        # Get OI from separate endpoint (one call for all instruments)
        total_oi = 0
        try:
            oi_resp = requests.get(
                "https://www.okx.com/api/v5/public/open-interest?instType=SWAP",
                timeout=10
            ).json()
            if oi_resp.get('code') == '0' and oi_resp.get('data'):
                total_oi = sum(float(item.get('oiUsd', 0)) for item in oi_resp['data'])
        except Exception:
            pass

        # Get BTC funding rate
        funding_rate = None
        try:
            funding_resp = requests.get(
                "https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP",
                timeout=5
            ).json()
            if funding_resp.get('code') == '0' and funding_resp.get('data'):
                funding_rate = float(funding_resp['data'][0].get('fundingRate', 0)) * 100
        except Exception:
            pass

        # Get BTC price change
        btc_ticker = next((t for t in tickers if t['instId'] == 'BTC-USDT-SWAP'), {})
        price_change = None
        if btc_ticker:
            last = float(btc_ticker.get('last', 0))
            open_24h = float(btc_ticker.get('open24h', 0))
            if open_24h > 0:
                price_change = ((last - open_24h) / open_24h) * 100

        top_pairs = sorted(volumes, key=lambda x: x['volume'], reverse=True)[:5]

        return {
            'exchange': 'OKX',
            'volume': total_volume,
            'open_interest': total_oi if total_oi > 0 else None,
            'funding_rate': funding_rate,
            'oi_volume_ratio': (total_oi / total_volume) if (total_oi > 0 and total_volume > 0) else None,
            'price_change_pct': price_change,
            'num_trades': None,
            'markets': len(tickers),
            'type': 'CEX',
            'top_pair': top_pairs[0]['symbol'] if top_pairs else 'N/A',
            'top_volume': top_pairs[0]['volume'] if top_pairs else 0,
            'status': 'success'
        }

    except Exception as e:
        return {'exchange': 'OKX', 'status': 'error', 'error': str(e)}


def fetch_hyperliquid_enhanced() -> Dict:
    """Fetch HyperLiquid with enhanced metrics"""
    try:
        response = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        data = response.json()

        if not isinstance(data, list) or len(data) < 2:
            return {'exchange': 'HyperLiquid', 'status': 'error', 'error': 'Invalid response'}

        universe = data[0]["universe"]
        asset_ctxs = data[1]

        volumes = []
        total_oi = 0
        btc_funding = None
        btc_price_change = None

        for i, ctx in enumerate(asset_ctxs):
            if i < len(universe) and "dayNtlVlm" in ctx:
                symbol = universe[i]["name"]
                vol = float(ctx["dayNtlVlm"])
                volumes.append({'symbol': symbol, 'volume': vol})

                # Add open interest (in USD)
                if 'openInterest' in ctx and 'markPx' in ctx:
                    oi_value = float(ctx['openInterest']) * float(ctx['markPx'])
                    total_oi += oi_value

                # Get BTC metrics
                if symbol == 'BTC':
                    btc_funding = float(ctx.get('funding', 0)) * 100
                    prev_price = float(ctx.get('prevDayPx', 0))
                    mark_price = float(ctx.get('markPx', 0))
                    if prev_price > 0:
                        btc_price_change = ((mark_price - prev_price) / prev_price) * 100

        total_volume = sum(v['volume'] for v in volumes)
        top_pairs = sorted(volumes, key=lambda x: x['volume'], reverse=True)[:5]

        return {
            'exchange': 'HyperLiquid',
            'volume': total_volume,
            'open_interest': total_oi,
            'funding_rate': btc_funding,
            'oi_volume_ratio': total_oi / total_volume if total_volume > 0 else None,
            'price_change_pct': btc_price_change,
            'num_trades': None,
            'markets': len(volumes),
            'type': 'DEX',
            'top_pair': top_pairs[0]['symbol'] if top_pairs else 'N/A',
            'top_volume': top_pairs[0]['volume'] if top_pairs else 0,
            'status': 'success'
        }

    except Exception as e:
        return {'exchange': 'HyperLiquid', 'status': 'error', 'error': str(e)}


def fetch_asterdex_enhanced() -> Dict:
    """Fetch AsterDEX with enhanced metrics"""
    try:
        response = requests.get(
            "https://fapi.asterdex.com/fapi/v1/ticker/24hr",
            timeout=10
        )
        tickers = response.json()

        if not isinstance(tickers, list):
            return {'exchange': 'AsterDEX', 'status': 'error', 'error': 'Invalid response'}

        total_volume = sum(float(t.get('quoteVolume', 0)) for t in tickers)
        total_trades = sum(int(t.get('count', 0)) for t in tickers)

        # Get BTC data
        btc_data = next((t for t in tickers if t['symbol'] == 'BTCUSDT'), {})
        price_change = float(btc_data.get('priceChangePercent', 0)) if btc_data else None

        top_pairs = sorted(tickers, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)[:5]

        return {
            'exchange': 'AsterDEX',
            'volume': total_volume,
            'open_interest': None,  # Not available
            'funding_rate': None,  # Not available in this endpoint
            'oi_volume_ratio': None,
            'price_change_pct': price_change,
            'num_trades': total_trades,
            'markets': len(tickers),
            'type': 'DEX',
            'top_pair': top_pairs[0]['symbol'] if top_pairs else 'N/A',
            'top_volume': float(top_pairs[0].get('quoteVolume', 0)) if top_pairs else 0,
            'status': 'success'
        }

    except Exception as e:
        return {'exchange': 'AsterDEX', 'status': 'error', 'error': str(e)}


def fetch_dydx_enhanced() -> Dict:
    """Fetch dYdX v4 with enhanced metrics"""
    try:
        response = requests.get(
            "https://indexer.dydx.trade/v4/perpetualMarkets",
            timeout=10
        )
        data = response.json()

        if 'markets' not in data:
            return {'exchange': 'dYdX v4', 'status': 'error', 'error': 'Invalid response'}

        volumes = []
        total_oi = 0
        total_trades = 0
        btc_funding = None
        btc_price_change = None

        for ticker, market in data['markets'].items():
            vol = float(market.get('volume24H', 0))
            volumes.append({'symbol': ticker, 'volume': vol})

            # Open interest (base asset * oracle price)
            oi_base = float(market.get('openInterest', 0))
            oracle_price = float(market.get('oraclePrice', 0))
            total_oi += oi_base * oracle_price

            # Trades
            total_trades += int(market.get('trades24H', 0))

            # BTC metrics
            if ticker == 'BTC-USD':
                btc_funding = float(market.get('nextFundingRate', 0)) * 100
                btc_price_change = float(market.get('priceChange24H', 0)) / oracle_price * 100 if oracle_price > 0 else None

        total_volume = sum(v['volume'] for v in volumes)
        top_pairs = sorted(volumes, key=lambda x: x['volume'], reverse=True)[:5]

        return {
            'exchange': 'dYdX v4',
            'volume': total_volume,
            'open_interest': total_oi,
            'funding_rate': btc_funding,
            'oi_volume_ratio': total_oi / total_volume if total_volume > 0 else None,
            'price_change_pct': btc_price_change,
            'num_trades': total_trades,
            'markets': len(data['markets']),
            'type': 'DEX',
            'top_pair': top_pairs[0]['symbol'] if top_pairs else 'N/A',
            'top_volume': top_pairs[0]['volume'] if top_pairs else 0,
            'status': 'success'
        }

    except Exception as e:
        return {'exchange': 'dYdX v4', 'status': 'error', 'error': str(e)}


def fetch_bitget_enhanced() -> Dict:
    """Fetch Bitget with enhanced metrics"""
    try:
        response = requests.get(
            "https://api.bitget.com/api/mix/v1/market/tickers?productType=umcbl",
            timeout=10
        )
        data = response.json()

        if data.get('code') != '00000':
            return {'exchange': 'Bitget', 'status': 'error', 'error': data.get('msg')}

        tickers = data['data']
        total_volume = sum(float(t.get('usdtVolume', 0)) for t in tickers)
        total_oi = sum(
            float(t.get('holdingAmount', 0)) * float(t.get('last', 0))
            for t in tickers
        )

        btc_ticker = next((t for t in tickers if t['symbol'] == 'BTCUSDT_UMCBL'), {})
        funding_rate = float(btc_ticker.get('fundingRate', 0)) * 100 if btc_ticker else None
        price_change = float(btc_ticker.get('priceChangePercent', 0)) * 100 if btc_ticker else None

        top_pairs = sorted(tickers, key=lambda x: float(x.get('usdtVolume', 0)), reverse=True)[:5]

        return {
            'exchange': 'Bitget',
            'volume': total_volume,
            'open_interest': total_oi,
            'funding_rate': funding_rate,
            'oi_volume_ratio': total_oi / total_volume if total_volume > 0 else None,
            'price_change_pct': price_change,
            'num_trades': None,
            'markets': len(tickers),
            'type': 'CEX',
            'top_pair': top_pairs[0]['symbol'].replace('_UMCBL', '') if top_pairs else 'N/A',
            'top_volume': float(top_pairs[0].get('usdtVolume', 0)) if top_pairs else 0,
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Bitget', 'status': 'error', 'error': str(e)}


def fetch_gateio_enhanced() -> Dict:
    """Fetch Gate.io with enhanced metrics"""
    try:
        response = requests.get(
            "https://api.gateio.ws/api/v4/futures/usdt/tickers",
            timeout=10
        )
        tickers = response.json()

        if not isinstance(tickers, list):
            return {'exchange': 'Gate.io', 'status': 'error', 'error': 'Invalid response'}

        total_volume = sum(float(t.get('volume_24h_settle', 0)) for t in tickers)
        total_oi = sum(
            float(t.get('total_size', 0)) * float(t.get('mark_price', 0)) * float(t.get('quanto_multiplier', 0.0001))
            for t in tickers
        )

        btc_ticker = next((t for t in tickers if t['contract'] == 'BTC_USDT'), {})
        funding_rate = float(btc_ticker.get('funding_rate', 0)) * 100 if btc_ticker else None
        price_change = float(btc_ticker.get('change_percentage', 0)) if btc_ticker else None

        top_pairs = sorted(tickers, key=lambda x: float(x.get('volume_24h_settle', 0)), reverse=True)[:5]

        return {
            'exchange': 'Gate.io',
            'volume': total_volume,
            'open_interest': total_oi,
            'funding_rate': funding_rate,
            'oi_volume_ratio': total_oi / total_volume if total_volume > 0 else None,
            'price_change_pct': price_change,
            'num_trades': None,
            'markets': len(tickers),
            'type': 'CEX',
            'top_pair': top_pairs[0]['contract'] if top_pairs else 'N/A',
            'top_volume': float(top_pairs[0].get('volume_24h_settle', 0)) if top_pairs else 0,
            'status': 'success'
        }
    except Exception as e:
        return {'exchange': 'Gate.io', 'status': 'error', 'error': str(e)}


def fetch_coinbase_intx_enhanced() -> Dict:
    """Fetch Coinbase International Exchange (INTX) perpetual futures data"""
    try:
        # Get all instruments (perpetual futures)
        response = requests.get(
            "https://api.international.coinbase.com/api/v1/instruments",
            timeout=10
        )
        response.raise_for_status()
        instruments = response.json()

        if not isinstance(instruments, list):
            return {'exchange': 'Coinbase INTX', 'status': 'error', 'error': 'Unexpected API response'}

        # Filter for perpetual futures only (type = "PERP")
        perps = [inst for inst in instruments if inst.get('type') == 'PERP' and inst.get('trading_state') == 'TRADING']

        # Calculate totals
        total_volume = sum(float(p.get('notional_24hr', 0)) for p in perps)
        total_oi = sum(
            float(p.get('open_interest', 0)) * float(p.get('quote', {}).get('mark_price', 0))
            for p in perps
        )
        total_trades = sum(float(p.get('qty_24hr', 0)) for p in perps)

        # Get BTC-PERP data for reference
        btc_perp = next((p for p in perps if p.get('symbol') == 'BTC-PERP'), {})

        if btc_perp:
            quote = btc_perp.get('quote', {})
            # Funding rate is per hour, convert to percentage
            funding_rate = float(quote.get('predicted_funding', 0)) * 100

            # Calculate 24h price change from settlement and mark prices
            settlement_price = float(quote.get('settlement_price', 0))
            mark_price = float(quote.get('mark_price', 0))
            price_change = ((mark_price - settlement_price) / settlement_price * 100) if settlement_price > 0 else None
        else:
            funding_rate = None
            price_change = None

        # Get top 5 pairs by volume
        top_pairs = sorted(perps, key=lambda x: float(x.get('notional_24hr', 0)), reverse=True)[:5]

        return {
            'exchange': 'Coinbase INTX',
            'volume': total_volume,
            'open_interest': total_oi,
            'funding_rate': funding_rate,
            'oi_volume_ratio': (total_oi / total_volume) if total_volume > 0 else None,
            'price_change_pct': price_change,
            'num_trades': int(total_trades) if total_trades > 0 else None,
            'markets': len(perps),
            'type': 'CEX',
            'top_pair': top_pairs[0].get('symbol', 'N/A') if top_pairs else 'N/A',
            'top_volume': float(top_pairs[0].get('notional_24hr', 0)) if top_pairs else 0,
            'status': 'success'
        }

    except Exception as e:
        return {'exchange': 'Coinbase INTX', 'status': 'error', 'error': str(e)}


def fetch_all_enhanced() -> List[Dict]:
    """Fetch all 9 exchanges with enhanced metrics in parallel"""
    fetchers = [
        fetch_binance_enhanced,
        fetch_bybit_enhanced,
        fetch_okx_enhanced,
        fetch_bitget_enhanced,
        fetch_gateio_enhanced,
        fetch_coinbase_intx_enhanced,
        fetch_hyperliquid_enhanced,
        fetch_asterdex_enhanced,
        fetch_dydx_enhanced
    ]

    results = []
    with ThreadPoolExecutor(max_workers=9) as executor:
        future_to_fetcher = {executor.submit(fetcher): fetcher for fetcher in fetchers}

        for future in as_completed(future_to_fetcher):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error in fetcher: {e}")

    return results


def format_enhanced_table(results: List[Dict]) -> str:
    """Format enhanced comparison table"""
    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') == 'error']

    successful.sort(key=lambda x: x['volume'], reverse=True)

    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)
    cex_volume = sum(r['volume'] for r in successful if r['type'] == 'CEX')
    dex_volume = sum(r['volume'] for r in successful if r['type'] == 'DEX')

    output = []
    output.append("\n" + "="*130)
    output.append(f"{'ENHANCED PERPETUAL FUTURES EXCHANGE COMPARISON':^130}")
    output.append(f"{'Updated: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'):^130}")
    output.append("="*130)

    # Enhanced table with all Priority 1 metrics
    output.append(f"\n{'#':<3}{'Exchange':<14}{'Type':<5}{'24h Volume':<16}{'Open Interest':<16}{'Funding':<9}{'OI/Vol':<8}{'Δ Price':<9}{'Trades':<12}{'Markets'}")
    output.append("-"*130)

    for i, r in enumerate(successful, 1):
        # Format values with proper handling of None
        volume_str = f"${r['volume']/1e9:>6.2f}B"

        oi_str = f"${r['open_interest']/1e9:>5.2f}B" if r.get('open_interest') else "N/A".rjust(9)

        funding_str = f"{r['funding_rate']:>6.4f}%" if r.get('funding_rate') is not None else "N/A".rjust(8)

        oi_vol_str = f"{r['oi_volume_ratio']:>6.2f}x" if r.get('oi_volume_ratio') else "N/A".rjust(7)

        price_str = f"{r['price_change_pct']:>6.2f}%" if r.get('price_change_pct') is not None else "N/A".rjust(8)

        trades_str = f"{r['num_trades']/1e6:>5.1f}M" if r.get('num_trades') else "N/A".rjust(11)

        output.append(
            f"{i:<3}"
            f"{r['exchange']:<14}"
            f"{r['type']:<5}"
            f"{volume_str:<16}"
            f"{oi_str:<16}"
            f"{funding_str:<9}"
            f"{oi_vol_str:<8}"
            f"{price_str:<9}"
            f"{trades_str:<12}"
            f"{r['markets']}"
        )

    # Enhanced summary
    output.append("\n" + "="*130)
    output.append(f"{'MARKET ANALYTICS':^130}")
    output.append("="*130)

    output.append(f"\n📊 Volume Statistics:")
    output.append(f"   Total 24h Volume: ${total_volume:,.0f}")
    output.append(f"   CEX Volume: ${cex_volume:,.0f} ({cex_volume/total_volume*100:.1f}%)")
    output.append(f"   DEX Volume: ${dex_volume:,.0f} ({dex_volume/total_volume*100:.1f}%)")

    output.append(f"\n💰 Open Interest:")
    output.append(f"   Total OI: ${total_oi:,.0f}")
    if total_volume > 0:
        output.append(f"   Market OI/Volume Ratio: {total_oi/total_volume:.2f}x")

    output.append(f"\n📈 Funding Rate Analysis (BTC reference):")
    for r in successful:
        if r.get('funding_rate') is not None:
            sentiment = "🟢 Bullish" if r['funding_rate'] > 0.01 else "🔴 Bearish" if r['funding_rate'] < -0.01 else "⚪ Neutral"
            output.append(f"   {r['exchange']:<14} {r['funding_rate']:>7.4f}%  {sentiment}")

    output.append(f"\n🎯 Trading Activity:")
    total_trades = sum(r.get('num_trades', 0) or 0 for r in successful)
    if total_trades > 0:
        output.append(f"   Total Trades (24h): {total_trades:,}")
    total_markets = sum(r['markets'] for r in successful)
    output.append(f"   Total Markets Tracked: {total_markets}")

    if failed:
        output.append(f"\n⚠️  Failed Exchanges:")
        for r in failed:
            output.append(f"   - {r['exchange']}: {r.get('error', 'Unknown error')}")

    output.append("\n" + "="*130)

    # Add notes
    output.append("\nNOTES:")
    output.append("• Funding Rate: Hourly rate traders pay/receive for holding positions (positive = longs pay shorts)")
    output.append("• OI/Vol Ratio: Open Interest ÷ Volume. Higher = more position holding, Lower = more day trading")
    output.append("• Δ Price: 24h price change % (BTC reference for market sentiment)")
    output.append("• Trades: Number of executed trades in 24h period")

    # Add coverage information for Binance
    binance_data = next((r for r in successful if r['exchange'] == 'Binance'), None)
    if binance_data and binance_data.get('oi_coverage'):
        output.append(f"• Binance OI Coverage: {binance_data['oi_coverage']} pairs (Full coverage)")

    output.append("\n")

    return "\n".join(output)


if __name__ == "__main__":
    print("\n🚀 Fetching enhanced data from all exchanges...\n")
    print("⏳ This may take 20-30 seconds due to full OI coverage (615 Binance pairs)...\n")

    results = fetch_all_enhanced()
    print(format_enhanced_table(results))

    # Optionally save to JSON
    # import json
    # with open('exchange_comparison_enhanced.json', 'w') as f:
    #     json.dump(results, f, indent=2)
