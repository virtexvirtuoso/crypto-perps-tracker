#!/usr/bin/env python3
"""
Discord Market Report Sender
Sends formatted market reports to Discord webhook
"""

import sys
import os
import requests
from datetime import datetime
from typing import Dict, List
import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import market analysis functions
from generate_market_report import (
    fetch_all_enhanced,
    analyze_market_sentiment,
    identify_arbitrage_opportunities,
    analyze_trading_behavior,
    detect_anomalies,
    calculate_market_dominance
)


def load_config() -> Dict:
    """Load configuration from YAML file with environment variable substitution"""
    try:
        with open('config/config.yaml', 'r') as f:
            content = f.read()
            # Substitute environment variables
            content = os.path.expandvars(content)
            return yaml.safe_load(content)
    except FileNotFoundError:
        print("⚠️  Config file not found. Using default settings.")
        return {
            'discord': {
                'enabled': True,
                'webhook_url': '',
                'username': 'Crypto Perps Bot',
                'color_scheme': {
                    'bullish': 0x00FF00,
                    'bearish': 0xFF0000,
                    'neutral': 0xFFFFFF,
                    'alert': 0xFFA500
                },
                'include_sections': {
                    'executive_summary': True,
                    'sentiment_analysis': True,
                    'arbitrage_opportunities': True,
                    'trading_patterns': True,
                    'recommendations': True,
                    'anomalies': True
                }
            }
        }


def get_sentiment_color(sentiment: str, config: Dict) -> int:
    """Get color based on sentiment"""
    colors = config['discord']['color_scheme']

    if '🟢 BULLISH' in sentiment:
        return colors['bullish']
    elif '🔴 BEARISH' in sentiment:
        return colors['bearish']
    else:
        return colors['neutral']


def create_executive_summary_embed(results: List[Dict], sentiment: Dict, config: Dict) -> Dict:
    """Create executive summary embed"""
    successful = [r for r in results if r.get('status') == 'success']
    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)
    total_markets = sum(r['markets'] for r in successful)

    color = get_sentiment_color(sentiment['sentiment'], config)

    embed = {
        "title": "📊 Crypto Perpetual Futures Market Report",
        "description": f"**Market Snapshot** • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "color": color,
        "fields": [
            {
                "name": "💰 Total Volume (24h)",
                "value": f"**${total_volume/1e9:.2f}B**",
                "inline": True
            },
            {
                "name": "📈 Open Interest",
                "value": f"**${total_oi/1e9:.2f}B**",
                "inline": True
            },
            {
                "name": "📊 Markets Tracked",
                "value": f"**{total_markets:,}**",
                "inline": True
            },
            {
                "name": "🎯 Market Sentiment",
                "value": f"**{sentiment['sentiment']}**\n{sentiment['interpretation']}",
                "inline": False
            },
            {
                "name": "📉 Avg Price Change",
                "value": f"**{sentiment['avg_price_change']:.2f}%**",
                "inline": True
            },
            {
                "name": "💸 Weighted Funding",
                "value": f"**{sentiment['weighted_funding']:.4f}%**",
                "inline": True
            }
        ],
        "footer": {
            "text": f"Data from {len(successful)} exchanges • OI Coverage: 7/8 (87.5%)"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    return embed


def create_sentiment_embed(sentiment: Dict, config: Dict) -> Dict:
    """Create sentiment analysis embed"""

    # Build funding rates table
    funding_text = "```\n"
    funding_text += "Exchange     Rate    Annualized\n"
    funding_text += "─" * 35 + "\n"

    for fe in sentiment['funding_exchanges'][:7]:  # Top 7 to fit in Discord
        annual = fe['rate'] * 3 * 365
        funding_text += f"{fe['exchange']:<12} {fe['rate']:>6.4f}%  {annual:>8.2f}%\n"

    funding_text += "```"

    embed = {
        "title": "💭 Market Sentiment Analysis",
        "color": get_sentiment_color(sentiment['sentiment'], config),
        "fields": [
            {
                "name": "🎯 Overall Sentiment",
                "value": f"**{sentiment['sentiment']}**",
                "inline": False
            },
            {
                "name": "📊 Funding Rates (BTC)",
                "value": funding_text,
                "inline": False
            }
        ]
    }

    return embed


def create_arbitrage_embed(arb_opportunities: List[Dict], config: Dict) -> Dict:
    """Create arbitrage opportunities embed"""

    if not arb_opportunities:
        return {
            "title": "💰 Arbitrage Opportunities",
            "description": "No significant arbitrage opportunities detected at this time.",
            "color": config['discord']['color_scheme']['neutral']
        }

    # Top 5 opportunities
    fields = []
    for i, opp in enumerate(arb_opportunities[:5], 1):
        fields.append({
            "name": f"#{i} • {opp['annual_yield']:.2f}% Annual Yield",
            "value": (
                f"**Strategy:** {opp['action']}\n"
                f"**Spread:** {opp['spread']:.4f}% per 8h\n"
                f"**Risk:** {opp['risk']}"
            ),
            "inline": False
        })

    embed = {
        "title": f"💰 Arbitrage Opportunities ({len(arb_opportunities)} found)",
        "description": "**Funding Rate Arbitrage** opportunities with risk-neutral returns",
        "color": config['discord']['color_scheme']['alert'],
        "fields": fields
    }

    return embed


def create_trading_patterns_embed(behavior: Dict, dominance: Dict, config: Dict) -> Dict:
    """Create trading patterns embed"""

    embed = {
        "title": "📈 Trading Patterns & Market Structure",
        "color": config['discord']['color_scheme']['neutral'],
        "fields": [
            {
                "name": "🎯 Market Dominance",
                "value": (
                    f"**Top 3 Control:** {dominance['top3_concentration']:.1f}%\n"
                    f"**CEX Share:** {dominance['cex_dominance']:.1f}%\n"
                    f"**DEX Share:** {dominance['dex_share']:.1f}%\n"
                    f"**Concentration:** {dominance['concentration_level']} (HHI: {dominance['hhi']:.0f})"
                ),
                "inline": False
            }
        ]
    }

    # Market leaders
    leaders_text = ""
    for i, leader in enumerate(dominance['leaders'], 1):
        leaders_text += f"{i}. **{leader['exchange']}** - ${leader['volume']/1e9:.2f}B ({leader['share']:.1f}%)\n"

    embed['fields'].append({
        "name": "🏆 Market Leaders",
        "value": leaders_text,
        "inline": False
    })

    # Trading behavior
    behavior_text = ""
    if behavior['day_trading_heavy']:
        behavior_text += f"**Day Trading:** {', '.join(behavior['day_trading_heavy'])}\n"
    if behavior['balanced']:
        behavior_text += f"**Balanced:** {', '.join(behavior['balanced'])}\n"
    if behavior['position_holding']:
        behavior_text += f"**Position Holding:** {', '.join(behavior['position_holding'])}\n"

    if behavior_text:
        embed['fields'].append({
            "name": "📊 Trading Style (by OI/Vol ratio)",
            "value": behavior_text,
            "inline": False
        })

    return embed


def create_recommendations_embed(recommendations: List[str], config: Dict) -> Dict:
    """Create recommendations embed"""

    rec_text = ""
    for rec in recommendations[:10]:  # Limit to 10 to fit in Discord
        rec_text += f"• {rec}\n"

    embed = {
        "title": "🎯 Trading Recommendations",
        "description": rec_text,
        "color": config['discord']['color_scheme']['alert'],
        "footer": {
            "text": "⚠️ Trading involves risk. Always use proper risk management."
        }
    }

    return embed


def create_anomalies_embed(anomalies: List[Dict], config: Dict) -> Dict:
    """Create anomalies embed"""

    if not anomalies:
        return None  # Don't send embed if no anomalies

    fields = []
    for anomaly in anomalies[:10]:  # Limit to 10
        severity_emoji = "🔴" if anomaly['severity'] == 'High' else "🟡"
        fields.append({
            "name": f"{severity_emoji} {anomaly['exchange']} - {anomaly['type']}",
            "value": anomaly['indicator'],
            "inline": False
        })

    embed = {
        "title": f"⚠️ Market Anomalies Detected ({len(anomalies)})",
        "color": config['discord']['color_scheme']['alert'],
        "fields": fields
    }

    return embed


def send_to_discord(webhook_url: str, embeds: List[Dict], username: str = "Crypto Perps Bot") -> bool:
    """Send embeds to Discord webhook"""

    # Discord allows max 10 embeds per message
    if len(embeds) > 10:
        embeds = embeds[:10]

    payload = {
        "username": username,
        "embeds": embeds
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if response.status_code == 204:
            print("✅ Successfully sent report to Discord!")
            return True
        else:
            print(f"❌ Discord webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")
        return False


def generate_and_send_discord_report(webhook_url: str = None) -> bool:
    """Main function to generate and send Discord report"""

    print("\n🚀 Generating Discord Market Report...\n")

    # Load config
    config = load_config()

    # Use provided webhook URL or get from config
    if webhook_url:
        config['discord']['webhook_url'] = webhook_url

    if not config['discord']['webhook_url']:
        print("❌ No Discord webhook URL configured!")
        print("   Please set webhook_url in config/config.yaml or pass as argument")
        return False

    if not config['discord']['enabled']:
        print("⚠️  Discord integration is disabled in config")
        return False

    print("⏳ Fetching data from 8 exchanges (20-30 seconds)...\n")

    # Fetch data
    results = fetch_all_enhanced()

    # Analyze
    sentiment = analyze_market_sentiment(results)
    arb_opportunities = identify_arbitrage_opportunities(results)
    trading_behavior = analyze_trading_behavior(results)
    anomalies = detect_anomalies(results)
    dominance = calculate_market_dominance(results)

    # Generate recommendations
    from generate_market_report import generate_recommendations
    recommendations = generate_recommendations(sentiment, arb_opportunities, trading_behavior, anomalies)

    # Build embeds based on config
    embeds = []
    sections = config['discord']['include_sections']

    if sections.get('executive_summary', True):
        embeds.append(create_executive_summary_embed(results, sentiment, config))

    if sections.get('sentiment_analysis', True):
        embeds.append(create_sentiment_embed(sentiment, config))

    if sections.get('arbitrage_opportunities', True) and arb_opportunities:
        embeds.append(create_arbitrage_embed(arb_opportunities, config))

    if sections.get('trading_patterns', True):
        embeds.append(create_trading_patterns_embed(trading_behavior, dominance, config))

    if sections.get('recommendations', True):
        embeds.append(create_recommendations_embed(recommendations, config))

    if sections.get('anomalies', True) and anomalies:
        anomaly_embed = create_anomalies_embed(anomalies, config)
        if anomaly_embed:
            embeds.append(anomaly_embed)

    # Send to Discord
    username = config['discord'].get('username', 'Crypto Perps Bot')
    return send_to_discord(config['discord']['webhook_url'], embeds, username)


if __name__ == "__main__":
    # Allow webhook URL as command line argument
    webhook_url = sys.argv[1] if len(sys.argv) > 1 else None

    success = generate_and_send_discord_report(webhook_url)

    sys.exit(0 if success else 1)
