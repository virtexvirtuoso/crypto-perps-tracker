#!/usr/bin/env python3
"""
Crypto Performance Tracker - Bybit Only

Generates the "CRYPTO PERFORMANCE TRACKER" chart using only Bybit data.
This is a standalone script with no dependencies on src/ modules.

Features:
- Fetches top perpetual symbols from Bybit
- Gets 12h historical hourly candles from Bybit API
- Generates a rebased returns chart (all lines start at 0%)
- Optional Discord webhook integration
"""

import requests
import json
import io
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict

# Chart generation
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def normalize_symbol(symbol: str) -> str:
    """Normalize Bybit symbol names to base asset

    Examples:
        BTCUSDT -> BTC
        ETHUSDT -> ETH
        1000PEPEUSDT -> PEPE
        1000000BABYDOGEUSDT -> BABYDOGE
    """
    symbol = symbol.upper()

    # Remove USDT suffix
    if symbol.endswith('USDT'):
        symbol = symbol[:-4]
    elif symbol.endswith('USD'):
        symbol = symbol[:-3]

    # Handle numeric prefixes for meme coins (Bybit convention)
    # Order matters: check longer prefixes first
    for prefix in ['10000000', '1000000', '100000', '10000', '1000']:
        if symbol.startswith(prefix):
            symbol = symbol[len(prefix):]
            break

    return symbol.strip()


# Mapping of normalized symbols to their Bybit API format
# Some meme coins require the 1000 prefix for the API
BYBIT_SYMBOL_MAP = {
    'PEPE': '1000PEPEUSDT',
    'SHIB': '1000SHIBUSDT',
    'FLOKI': '1000FLOKIUSDT',
    'BONK': '1000BONKUSDT',
    'LUNC': '1000LUNCUSDT',
    'BABYDOGE': '1000000BABYDOGEUSDT',
    'SATS': '1000SATSUSDT',
    'RATS': '1000RATSUSDT',
    'CAT': '10000CATUSDT',
    'LADYS': '1000LADYSUSDT',
    'BTT': '1000000BTTUSDT',
    'XEC': '1000XECUSDT',
    'CHEEMS': '10000CHEEMSUSDT',
    'COQ': '1000000COQUSDT',
    'STARL': '10000STARLUSDT',
}


def fetch_bybit_tickers() -> List[Dict]:
    """Fetch all Bybit linear perpetual tickers

    Returns:
        List of ticker data with symbol, price, volume, price_change_pct
    """
    print("📊 Fetching Bybit perpetual tickers...")

    try:
        response = requests.get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "linear"},
            timeout=15
        )
        data = response.json()

        if data.get('retCode') != 0:
            print(f"   ❌ Bybit API error: {data.get('retMsg')}")
            return []

        results = []
        for ticker in data['result']['list']:
            # Skip non-USDT pairs
            if not ticker['symbol'].endswith('USDT'):
                continue

            # Safe float conversion
            def safe_float(value, default=0.0):
                if value is None or value == '':
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default

            results.append({
                'symbol': ticker['symbol'],
                'normalized': normalize_symbol(ticker['symbol']),
                'price': safe_float(ticker.get('lastPrice')),
                'volume_24h': safe_float(ticker.get('turnover24h')),  # USD volume
                'open_interest': safe_float(ticker.get('openInterestValue')),
                'price_change_pct': safe_float(ticker.get('price24hPcnt')) * 100,  # Convert to %
                'funding_rate': safe_float(ticker.get('fundingRate')) * 100,  # Convert to %
            })

        # Sort by volume
        results.sort(key=lambda x: x['volume_24h'], reverse=True)
        print(f"   ✅ Fetched {len(results)} USDT perpetual pairs")

        return results

    except Exception as e:
        print(f"   ❌ Error fetching Bybit tickers: {e}")
        return []


def fetch_bybit_klines(symbol: str, interval: str = "60", limit: int = 12) -> List[Dict]:
    """Fetch historical kline/candle data from Bybit

    Args:
        symbol: Bybit symbol (e.g., "BTCUSDT")
        interval: Candle interval in minutes ("60" = 1 hour)
        limit: Number of candles to fetch (max 1000)

    Returns:
        List of candle dicts with timestamp, open, high, low, close, volume
    """
    try:
        response = requests.get(
            "https://api.bybit.com/v5/market/kline",
            params={
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            },
            timeout=10
        )
        data = response.json()

        if data.get('retCode') != 0:
            return []

        candles = []
        # Bybit returns newest first, so reverse for chronological order
        for k in reversed(data['result']['list']):
            candles.append({
                'timestamp': int(k[0]),  # Already in ms
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            })

        return candles

    except Exception as e:
        return []


def fetch_historical_data_bybit(symbols: List[str], limit: int = 12) -> Dict[str, List[Dict]]:
    """Fetch hourly historical data for multiple symbols from Bybit

    Args:
        symbols: List of normalized symbol names (e.g., ['BTC', 'ETH', 'PEPE'])
        limit: Number of hourly candles (12 = 12 hours)

    Returns:
        Dict mapping symbol -> list of candle data
    """
    historical_data = {}

    print(f"\n📈 Fetching {limit}h historical data for {len(symbols)} symbols from Bybit...")

    for symbol in symbols:
        # Check if symbol needs special mapping (meme coins with 1000 prefix)
        if symbol in BYBIT_SYMBOL_MAP:
            bybit_symbol = BYBIT_SYMBOL_MAP[symbol]
        else:
            bybit_symbol = f"{symbol}USDT"

        candles = fetch_bybit_klines(bybit_symbol, interval="60", limit=limit)

        if candles:
            historical_data[symbol] = candles
            print(f"   ✅ {symbol}: {len(candles)} candles")
        else:
            print(f"   ⚠️  {symbol}: No data (tried {bybit_symbol})")

        # Rate limiting (Bybit allows 120 req/s but be conservative)
        time.sleep(0.1)

    return historical_data


def generate_performance_chart(
    historical_data: Dict[str, List[Dict]],
    ticker_data: List[Dict]
) -> bytes:
    """Generate the CRYPTO PERFORMANCE TRACKER chart

    Args:
        historical_data: Dict of symbol -> candle list
        ticker_data: List of ticker dicts with price_change_pct

    Returns:
        PNG image as bytes
    """
    # Apply dark style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    if not historical_data:
        # Empty chart
        fig, ax = plt.subplots(figsize=(16, 10))
        ax.text(0.5, 0.5, 'No Historical Data Available',
                ha='center', va='center', fontsize=24, color='#FFA500')
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
        buf.seek(0)
        plt.close()
        plt.style.use('default')
        return buf.getvalue()

    # Color palette (20 distinct colors)
    color_palette = [
        '#00FF7F',  # Spring Green
        '#FF1493',  # Deep Pink
        '#00CED1',  # Dark Turquoise
        '#FFD700',  # Gold
        '#FF6347',  # Tomato
        '#7B68EE',  # Medium Slate Blue
        '#FF69B4',  # Hot Pink
        '#20B2AA',  # Light Sea Green
        '#9370DB',  # Medium Purple
        '#32CD32',  # Lime Green
        '#FF4500',  # Orange Red
        '#00BFFF',  # Deep Sky Blue
        '#ADFF2F',  # Green Yellow
        '#FF00FF',  # Magenta
        '#00FA9A',  # Medium Spring Green
        '#DC143C',  # Crimson
        '#00FFFF',  # Cyan
        '#7FFF00',  # Chartreuse
        '#FF8C00',  # Dark Orange
        '#8A2BE2',  # Blue Violet
    ]

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 10))

    # Track symbol data for legend
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

        # BTC gets orange, others get colors from palette
        if symbol == 'BTC':
            color = '#FFA500'
        else:
            color = color_palette[color_index % len(color_palette)]
            color_index += 1

        linewidth = 2.5 if symbol == 'BTC' else 1.2
        alpha = 1.0 if symbol == 'BTC' else 0.75

        # Plot line
        line, = ax.plot(timestamps, percent_changes, color=color,
                       linewidth=linewidth, alpha=alpha, label=symbol)

        # Add endpoint label
        if timestamps and percent_changes:
            final_x = timestamps[-1]
            final_y = percent_changes[-1]
            ax.text(final_x, final_y, f' {symbol}',
                   fontsize=5, color=color, fontweight='normal',
                   ha='left', va='center', alpha=0.85)

            symbol_data.append({
                'symbol': symbol,
                'final_y': final_y,
                'line': line,
                'color': color
            })

    # Zero line
    ax.axhline(y=0, color='#888888', linestyle='-', linewidth=1, alpha=0.5)

    # Calculate outperformers/underperformers
    outperformers = len([d for d in symbol_data if d['final_y'] > 1.0])
    underperformers = len([d for d in symbol_data if d['final_y'] < -3.0])

    # Title with timestamp and counts
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    ax.set_title(
        f'CRYPTO PERFORMANCE TRACKER\n'
        f'12h Returns | {outperformers} Outperformers • {underperformers} Underperformers\n'
        f'Generated: {current_time}',
        fontsize=12, fontweight='bold', color='#FFA500', pad=20
    )

    # Axis labels
    ax.set_xlabel('Time (12h Period)', fontsize=9, fontweight='bold', color='#FFD700')
    ax.set_ylabel('Price Change (%)', fontsize=9, fontweight='bold', color='#FFD700')

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    # Styling
    ax.grid(alpha=0.08, color='#FFD700', linewidth=0.5)
    ax.tick_params(colors='#FFD700', labelsize=7)
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#0a0a0a')

    # Sort legend by performance (best at top)
    symbol_data.sort(key=lambda d: d['final_y'], reverse=True)

    # Create legend
    handles = [d['line'] for d in symbol_data]
    labels = [f"{d['symbol']} {d['final_y']:+.1f}%" for d in symbol_data]

    legend = ax.legend(handles, labels,
                      fontsize=7,
                      framealpha=0.9,
                      loc='center left',
                      bbox_to_anchor=(1.01, 0.5),
                      ncol=1)

    # Color-match legend text (lighter weight)
    for i, text in enumerate(legend.get_texts()):
        if i < len(symbol_data):
            text.set_color(symbol_data[i]['color'])
            text.set_fontweight('normal')

    legend.get_frame().set_facecolor('#1a1a1a')
    legend.get_frame().set_edgecolor('#FFA500')
    legend.get_frame().set_linewidth(1)

    # Watermark
    fig.text(0.98, 0.02, 'Generated by Virtuoso Crypto',
             ha='right', va='bottom', fontsize=8, color='#FFA500',
             alpha=0.6, style='italic', fontweight='bold')

    # Add data source badge (no emoji to avoid font warnings)
    fig.text(0.02, 0.02, 'Data: Bybit',
             ha='left', va='bottom', fontsize=8, color='#FFD700',
             alpha=0.6, fontweight='bold')

    # Save to bytes
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')

    return chart_bytes


def send_to_discord(chart_bytes: bytes, webhook_url: str, tickers: List[Dict]) -> bool:
    """Send chart to Discord webhook

    Args:
        chart_bytes: PNG image bytes
        webhook_url: Discord webhook URL
        tickers: List of ticker data for embed summary

    Returns:
        True if successful
    """
    try:
        # Get BTC price change
        btc_data = next((t for t in tickers if t['normalized'] == 'BTC'), None)
        btc_change = btc_data['price_change_pct'] if btc_data else 0

        # Top performers
        sorted_tickers = sorted(tickers[:50], key=lambda x: x['price_change_pct'], reverse=True)
        top_gainers = sorted_tickers[:5]
        top_losers = sorted_tickers[-5:]

        embed = {
            "title": f"📈 Crypto Performance Tracker - {datetime.now(timezone.utc).strftime('%b %d, %H:%M UTC')}",
            "description": (
                f"**Data Source:** Bybit Linear Perpetuals\n"
                f"**BTC 12h Change:** {btc_change:+.2f}%\n"
                f"**Symbols Tracked:** {len(tickers)}"
            ),
            "color": 0xFFA500,
            "fields": [
                {
                    "name": "🚀 Top Gainers (12h)",
                    "value": "\n".join([
                        f"**{t['normalized']}** {t['price_change_pct']:+.1f}%"
                        for t in top_gainers
                    ]),
                    "inline": True
                },
                {
                    "name": "📉 Top Losers (12h)",
                    "value": "\n".join([
                        f"**{t['normalized']}** {t['price_change_pct']:+.1f}%"
                        for t in top_losers
                    ]),
                    "inline": True
                }
            ],
            "footer": {
                "text": "12h rebased returns chart • Lines start at 0%"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
        files = {
            'file1': (f"crypto_performance_bybit_{timestamp}.png", chart_bytes, 'image/png')
        }

        payload = {
            'username': 'Crypto Performance Tracker',
            'embeds': [embed]
        }

        response = requests.post(
            webhook_url,
            files=files,
            data={'payload_json': json.dumps(payload)},
            timeout=15
        )

        if response.status_code == 200:
            print("\n✅ Chart sent to Discord!")
            return True
        else:
            print(f"\n❌ Discord webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Error sending to Discord: {e}")
        return False


def main():
    """Main execution"""
    print("\n" + "="*60)
    print("🚀 CRYPTO PERFORMANCE TRACKER - BYBIT EDITION")
    print("="*60 + "\n")

    # 1. Fetch tickers
    tickers = fetch_bybit_tickers()

    if not tickers:
        print("❌ No data fetched. Exiting.")
        return

    # 2. Get top 25 symbols for historical data
    top_symbols = ['BTC']  # Always include BTC first
    for t in tickers[:30]:
        if t['normalized'] != 'BTC' and t['normalized'] not in top_symbols:
            top_symbols.append(t['normalized'])
        if len(top_symbols) >= 25:
            break

    # 3. Fetch historical data (12 hourly candles)
    historical_data = fetch_historical_data_bybit(top_symbols, limit=12)

    print(f"\n✅ Got historical data for {len(historical_data)} symbols")

    # 4. Generate chart
    print("\n🎨 Generating performance chart...")
    chart_bytes = generate_performance_chart(historical_data, tickers)
    print("   ✅ Chart generated")

    # 5. Save locally
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(data_dir, f"crypto_performance_bybit_{timestamp}.png")

    with open(filename, 'wb') as f:
        f.write(chart_bytes)
    print(f"\n📁 Chart saved: {filename}")

    # 6. Send to Discord if webhook is configured
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not installed, rely on environment variables

    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if webhook_url:
        print("\n📤 Sending to Discord...")
        send_to_discord(chart_bytes, webhook_url, tickers)
    else:
        print("\n⚠️  Discord webhook not configured (set DISCORD_WEBHOOK_URL env var)")

    # 7. Try to open in browser
    try:
        import webbrowser
        webbrowser.open('file://' + os.path.abspath(filename))
        print("🌐 Opening in browser...")
    except Exception:
        pass

    print("\n" + "="*60)
    print("✅ DONE!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
