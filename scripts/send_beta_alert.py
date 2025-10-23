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


def generate_beta_champions_chart(analyses: List[Dict], top_n: int = 15) -> bytes:
    """Generate single Beta Champions chart with Cyberpunk Amber styling"""

    # Apply style
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
    ax.set_title('₿ BITCOIN BETA CHAMPIONS\nTop Symbols by Beta Category (Sorted by Volume)',
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


def send_beta_alert_to_discord(analyses: List[Dict], btc_price_change: float, webhook_url: str) -> bool:
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
                "text": "Beta = Symbol 24h Change / BTC 24h Change • Higher volume = more liquid"
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
        print("   • Generating Beta Champions chart...")
        beta_chart = generate_beta_champions_chart(analyses, top_n=15)
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

    # Send to Discord
    webhook_url = "https://discord.com/api/webhooks/1430641654846459964/QQj9KDof3UNhDj-p3GyrVDDAX1rWjja6D8VfQ92wSaxdsqEot8VD2S_W8J9uQdLT-oR7"

    print("📤 Sending Bitcoin Beta alert to Discord...\n")
    send_beta_alert_to_discord(analyses, btc_price_change if btc_price_change else 0, webhook_url)
