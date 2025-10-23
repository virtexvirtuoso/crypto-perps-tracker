#!/usr/bin/env python3
"""
Bitcoin Beta Alert - Send Beta Champions chart to Discord
Simple alert showing top symbols by beta category
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_symbol_report import (
    fetch_symbol_data_from_exchanges,
    analyze_symbol
)
import requests
import json
import io
from datetime import datetime, timezone
from typing import List, Dict
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import time


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


def generate_time_series_chart(analyses: List[Dict], historical_data: Dict[str, List[Dict]]) -> bytes:
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
    ax.set_xlabel('Time (24h Period)', fontsize=14, fontweight='bold', color='#FFD700')
    ax.set_ylabel('Price Change (%)', fontsize=14, fontweight='bold', color='#FFD700')
    ax.set_title('₿ BITCOIN BETA ANALYSIS\nIndividual Symbol Movements vs Bitcoin (24h)',
                fontsize=18, fontweight='bold', color='#FFA500', pad=20)

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
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

    # Save to bytes
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')

    return chart_bytes


def send_beta_alert_to_discord(analyses: List[Dict], btc_price_change: float, historical_data: Dict[str, List[Dict]], webhook_url: str) -> bool:
    """Send Bitcoin Beta alert to Discord"""

    try:
        # Calculate metrics
        symbols_with_beta = [a for a in analyses if a.get('btc_beta') is not None and a['symbol'] != 'BTC']

        if not symbols_with_beta:
            print("⚠️  No symbols with beta data found")
            return False

        # Get top betas
        high_volatility = [a for a in symbols_with_beta if a['btc_beta'] > 1.5]
        amplifiers = [a for a in symbols_with_beta if 1.0 < a['btc_beta'] <= 1.5]
        inverse_beta = [a for a in symbols_with_beta if a['btc_beta'] < 0]

        # Sort by volume and get top 3 from each category
        high_volatility.sort(key=lambda x: x['total_volume_24h'], reverse=True)
        amplifiers.sort(key=lambda x: x['total_volume_24h'], reverse=True)
        inverse_beta.sort(key=lambda x: x['total_volume_24h'], reverse=True)

        # Create embed
        embed = {
            "title": f"₿ Bitcoin Beta Alert - {datetime.now(timezone.utc).strftime('%b %d, %H:%M UTC')}",
            "description": (
                f"**BTC 24h Change:** {btc_price_change:+.2f}%\n"
                f"**Symbols Tracked:** {len(symbols_with_beta)}\n"
                f"**High Volatility (>1.5x):** {len(high_volatility)} symbols\n"
                f"**Amplifies BTC (1.0-1.5x):** {len(amplifiers)} symbols\n"
                f"**Inverse (<0):** {len(inverse_beta)} symbols"
            ),
            "color": 0xFFA500,  # Amber
            "fields": [],
            "footer": {
                "text": "Beta = Symbol 24h Change / BTC 24h Change • Time-series shows 24h price movements"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Add top symbols from each category
        if high_volatility:
            top_high = [f"**{a['symbol']}** ({a['btc_beta']:.2f}x)" for a in high_volatility[:3]]
            embed["fields"].append({
                "name": "🔴 High Volatility (>1.5x)",
                "value": "\n".join(top_high) if top_high else "None",
                "inline": True
            })

        if amplifiers:
            top_amp = [f"**{a['symbol']}** ({a['btc_beta']:.2f}x)" for a in amplifiers[:3]]
            embed["fields"].append({
                "name": "🟠 Amplifies BTC (1.0-1.5x)",
                "value": "\n".join(top_amp) if top_amp else "None",
                "inline": True
            })

        if inverse_beta:
            top_inv = [f"**{a['symbol']}** ({a['btc_beta']:.2f}x)" for a in inverse_beta[:3]]
            embed["fields"].append({
                "name": "🟢 Inverse (<0)",
                "value": "\n".join(top_inv) if top_inv else "None",
                "inline": True
            })

        # Generate chart
        print("   • Generating time-series chart...")
        beta_chart = generate_time_series_chart(analyses, historical_data)
        print("      ✓ Chart generated")

        # Prepare files
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
        files = {
            'file1': (f"bitcoin_beta_{timestamp}.png", beta_chart, 'image/png')
        }

        payload = {
            'username': 'Bitcoin Beta Alert',
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
            print(f"\n✅ Bitcoin Beta alert sent to Discord!")
            print(f"   • BTC 24h Change: {btc_price_change:+.2f}%")
            print(f"   • {len(symbols_with_beta)} symbols analyzed")
            print(f"   • High Volatility: {len(high_volatility)} symbols")
            print(f"   • Amplifies BTC: {len(amplifiers)} symbols")
            print(f"   • Inverse: {len(inverse_beta)} symbols")
            return True
        else:
            print(f"\n❌ Discord webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Error sending Beta alert: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🚀 Bitcoin Beta Alert Generator\n")
    print("⏳ Fetching data from 8 exchanges (30-40 seconds)...\n")

    # Fetch data
    symbol_data = fetch_symbol_data_from_exchanges()
    print(f"✅ Collected data for {len(symbol_data)} symbols\n")

    # Get BTC price change
    btc_data = symbol_data.get('BTC', [])
    btc_price_change = None
    if btc_data:
        btc_changes = [d.get('price_change_pct') for d in btc_data if d.get('price_change_pct') is not None]
        if btc_changes:
            btc_price_change = sum(btc_changes) / len(btc_changes)
            print(f"📊 BTC 24h change: {btc_price_change:+.2f}%\n")

    # Analyze symbols
    print("🔍 Analyzing symbols and calculating betas...\n")
    analyses = []
    for symbol, data in symbol_data.items():
        analysis = analyze_symbol(symbol, data, btc_price_change=btc_price_change)
        if analysis:
            analyses.append(analysis)

    # Sort by volume
    analyses.sort(key=lambda x: x['total_volume_24h'], reverse=True)
    print(f"✅ Analyzed {len(analyses)} symbols\n")

    # Fetch historical data for top 25 symbols (including BTC)
    print("📈 Fetching historical price data for top 25 symbols...\n")
    top_symbols = ['BTC'] + [a['symbol'] for a in analyses[:24] if a['symbol'] != 'BTC']
    historical_data = fetch_historical_data_for_symbols(top_symbols, limit=24)
    print(f"\n✅ Fetched historical data for {len(historical_data)} symbols\n")

    # Send to Discord
    webhook_url = "https://discord.com/api/webhooks/1430641654846459964/QQj9KDof3UNhDj-p3GyrVDDAX1rWjja6D8VfQ92wSaxdsqEot8VD2S_W8J9uQdLT-oR7"

    print("📤 Sending Bitcoin Beta alert to Discord...\n")
    send_beta_alert_to_discord(analyses, btc_price_change if btc_price_change else 0, historical_data, webhook_url)
