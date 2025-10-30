#!/usr/bin/env python3
"""
Directional Trading Alerts - Long/Short Opportunity Scanner

Analyzes symbols for directional trading opportunities based on:
1. High-Beta Longs - Amplify Bitcoin momentum
2. Parabolic Reversal Shorts - Fade extreme moves
3. Beta Divergence Plays - Catch lagging high-beta symbols
4. Funding Rate Extremes - Trade sentiment exhaustion

Uses existing infrastructure for data fetching and analysis.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import requests
from dotenv import load_dotenv

from src.models.config import Config
from src.container import Container


@dataclass
class DirectionalAlert:
    """Represents a directional trading opportunity"""
    direction: str  # 'LONG' or 'SHORT'
    symbol: str
    strategy: str
    confidence: float  # 0-100
    reasoning: List[str]
    metrics: Dict
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'


def get_btc_metrics(analyses: List[Dict]) -> Optional[Dict]:
    """Extract Bitcoin metrics for reference"""
    btc = next((a for a in analyses if a['symbol'] == 'BTC'), None)
    if not btc:
        return None

    return {
        'price_change_24h': btc.get('avg_price_change_24h', 0),
        'funding_rate': btc.get('avg_funding_rate', 0),
        'volume': btc.get('total_volume_24h', 0)
    }


def analyze_high_beta_longs(analyses: List[Dict], btc_metrics: Dict) -> List[DirectionalAlert]:
    """
    Strategy 1: High-Beta Long Plays

    Conditions:
    - Bitcoin trending up (24h > +1.5%)
    - Symbol has Beta > 1.5x
    - Symbol has positive 24h momentum
    - Low funding rate (< 0.01%)
    - Good liquidity (> $50M volume)
    """
    alerts = []

    # Only trigger if BTC is trending up
    btc_change = btc_metrics.get('price_change_24h', 0)
    if btc_change < 1.5:
        return alerts

    for analysis in analyses:
        symbol = analysis['symbol']
        if symbol == 'BTC':  # Skip BTC itself
            continue

        beta = analysis.get('btc_beta')
        price_change = analysis.get('avg_price_change_24h')
        funding = analysis.get('avg_funding_rate')
        volume = analysis.get('total_volume_24h', 0)

        if not all([beta is not None, price_change is not None, funding is not None]):
            continue

        # Check conditions
        conditions_met = []
        confidence = 0

        # 1. High beta (30 points)
        if beta > 1.5:
            conditions_met.append(f"✅ High beta: {beta:.2f}x amplifies BTC moves")
            confidence += 30
        else:
            continue  # Critical condition

        # 2. Positive momentum (25 points)
        if price_change > 0:
            conditions_met.append(f"✅ Positive momentum: {price_change:+.1f}%")
            confidence += 25
        else:
            conditions_met.append(f"⚠️ Negative momentum: {price_change:+.1f}% (contrarian entry)")
            confidence += 10  # Lower confidence for contrarian

        # 3. Low funding (20 points)
        if funding < 0.01:
            conditions_met.append(f"✅ Cheap to hold: {funding:.4f}% funding")
            confidence += 20
        elif funding < 0.02:
            conditions_met.append(f"⚠️ Moderate funding: {funding:.4f}%")
            confidence += 10

        # 4. Good liquidity (15 points)
        if volume > 50_000_000:
            conditions_met.append(f"✅ Good liquidity: ${volume/1_000_000:.1f}M")
            confidence += 15
        elif volume > 10_000_000:
            conditions_met.append(f"⚠️ Moderate liquidity: ${volume/1_000_000:.1f}M")
            confidence += 8

        # 5. Beta alignment bonus (10 points) - if symbol is already outperforming expected beta
        expected_move = btc_change * beta
        actual_move = price_change
        if actual_move > expected_move * 0.8:  # Within 80% of expected
            conditions_met.append(f"✅ Moving as expected with BTC momentum")
            confidence += 10

        # Only alert if confidence >= 60%
        if confidence >= 60:
            alerts.append(DirectionalAlert(
                direction='LONG',
                symbol=symbol,
                strategy='High-Beta Amplification',
                confidence=confidence,
                reasoning=conditions_met,
                metrics={
                    'beta': beta,
                    'price_change_24h': price_change,
                    'funding_rate': funding,
                    'volume_24h': volume,
                    'btc_change': btc_change,
                    'expected_move': expected_move
                },
                risk_level='MEDIUM'
            ))

    return alerts


def analyze_parabolic_shorts(analyses: List[Dict]) -> List[DirectionalAlert]:
    """
    Strategy 2: Parabolic Reversal Shorts

    Conditions:
    - Extreme 24h gains (> 50%)
    - Very high beta (> 15x) - signs of mania
    - Low OI/Volume ratio (< 0.3x) - weak hands
    - High funding rate (> 0.02%) - expensive to hold longs
    """
    alerts = []

    for analysis in analyses:
        symbol = analysis['symbol']
        if symbol == 'BTC':  # Skip BTC
            continue

        beta = analysis.get('btc_beta')
        price_change = analysis.get('avg_price_change_24h')
        funding = analysis.get('avg_funding_rate')
        volume = analysis.get('total_volume_24h', 0)
        oi = analysis.get('total_open_interest', 0)

        if not all([beta is not None, price_change is not None]):
            continue

        # Check conditions
        conditions_met = []
        confidence = 0

        # 1. Parabolic move (40 points)
        if price_change > 100:
            conditions_met.append(f"⚠️ EXTREME pump: {price_change:+.1f}% (parabolic)")
            confidence += 40
        elif price_change > 50:
            conditions_met.append(f"⚠️ Strong pump: {price_change:+.1f}%")
            confidence += 30
        elif price_change > 20:
            conditions_met.append(f"⚠️ Notable pump: {price_change:+.1f}%")
            confidence += 20
        else:
            continue  # Not parabolic enough

        # 2. Very high beta (25 points) - mania indicator
        if beta > 30:
            conditions_met.append(f"⚠️ EXTREME beta: {beta:.1f}x (mania territory)")
            confidence += 25
        elif beta > 15:
            conditions_met.append(f"⚠️ Very high beta: {beta:.1f}x")
            confidence += 20
        elif beta > 5:
            conditions_met.append(f"⚠️ High beta: {beta:.1f}x")
            confidence += 10

        # 3. Weak hands indicator - low OI/Vol (20 points)
        oi_vol_ratio = oi / volume if volume > 0 else 0
        if oi_vol_ratio < 0.3 and oi > 0:
            conditions_met.append(f"✅ Weak hands: {oi_vol_ratio:.2f}x OI/Vol (day traders)")
            confidence += 20
        elif oi_vol_ratio < 0.5 and oi > 0:
            conditions_met.append(f"⚠️ Moderate conviction: {oi_vol_ratio:.2f}x OI/Vol")
            confidence += 10

        # 4. Expensive longs - high funding (15 points)
        if funding and funding > 0.05:
            conditions_met.append(f"✅ Expensive longs: {funding:.4f}% funding")
            confidence += 15
        elif funding and funding > 0.02:
            conditions_met.append(f"⚠️ Elevated funding: {funding:.4f}%")
            confidence += 10

        # Only alert if confidence >= 50%
        if confidence >= 50:
            risk = 'VERY_HIGH' if price_change > 100 else 'HIGH'

            alerts.append(DirectionalAlert(
                direction='SHORT',
                symbol=symbol,
                strategy='Parabolic Reversal',
                confidence=confidence,
                reasoning=conditions_met,
                metrics={
                    'beta': beta,
                    'price_change_24h': price_change,
                    'funding_rate': funding,
                    'volume_24h': volume,
                    'oi_vol_ratio': oi_vol_ratio
                },
                risk_level=risk
            ))

    return alerts


def analyze_beta_divergence(analyses: List[Dict], btc_metrics: Dict) -> List[DirectionalAlert]:
    """
    Strategy 3: Beta Divergence Plays

    When high-beta symbols lag Bitcoin's move, they often "catch up"

    Conditions:
    - Symbol has Beta > 1.3x
    - BTC moved significantly (|change| > 2%)
    - Symbol underperformed its expected beta move
    - Good liquidity
    """
    alerts = []

    btc_change = btc_metrics.get('price_change_24h', 0)
    if abs(btc_change) < 2:  # Need significant BTC move
        return alerts

    for analysis in analyses:
        symbol = analysis['symbol']
        if symbol == 'BTC':
            continue

        beta = analysis.get('btc_beta')
        price_change = analysis.get('avg_price_change_24h')
        volume = analysis.get('total_volume_24h', 0)
        funding = analysis.get('avg_funding_rate')

        if not all([beta is not None, price_change is not None]):
            continue

        # Check conditions
        conditions_met = []
        confidence = 0

        # 1. High beta (must have)
        if beta < 1.3:
            continue

        # 2. Calculate expected vs actual move
        expected_move = btc_change * beta
        actual_move = price_change
        divergence_pct = ((actual_move - expected_move) / abs(expected_move) * 100) if expected_move != 0 else 0

        # Only alert if significantly lagging (< 60% of expected)
        if divergence_pct > -40:  # Not lagging enough
            continue

        conditions_met.append(f"✅ Lagging beta: Expected {expected_move:+.1f}%, got {actual_move:+.1f}%")
        conditions_met.append(f"✅ Beta: {beta:.2f}x should amplify BTC's {btc_change:+.1f}%")
        confidence += 40

        # 3. Good liquidity (20 points)
        if volume > 50_000_000:
            conditions_met.append(f"✅ Good liquidity: ${volume/1_000_000:.1f}M")
            confidence += 20
        elif volume > 10_000_000:
            conditions_met.append(f"⚠️ Moderate liquidity: ${volume/1_000_000:.1f}M")
            confidence += 10
        else:
            continue  # Need liquidity

        # 4. Funding not extreme (15 points)
        if funding and abs(funding) < 0.02:
            conditions_met.append(f"✅ Reasonable funding: {funding:.4f}%")
            confidence += 15

        # 5. Divergence magnitude (25 points)
        if divergence_pct < -60:
            conditions_met.append(f"✅ MAJOR lag: {divergence_pct:.0f}% below expected")
            confidence += 25
        elif divergence_pct < -40:
            conditions_met.append(f"✅ Significant lag: {divergence_pct:.0f}% below expected")
            confidence += 20

        if confidence >= 65:
            direction = 'LONG' if btc_change > 0 else 'SHORT'

            alerts.append(DirectionalAlert(
                direction=direction,
                symbol=symbol,
                strategy='Beta Divergence Catch-Up',
                confidence=confidence,
                reasoning=conditions_met,
                metrics={
                    'beta': beta,
                    'expected_move': expected_move,
                    'actual_move': actual_move,
                    'divergence_pct': divergence_pct,
                    'btc_change': btc_change,
                    'volume_24h': volume
                },
                risk_level='MEDIUM'
            ))

    return alerts


def analyze_funding_extremes(analyses: List[Dict]) -> List[DirectionalAlert]:
    """
    Strategy 4: Funding Rate Extremes

    When funding becomes extreme, it signals sentiment exhaustion

    Conditions:
    - Very high funding (> 0.03%) - fade longs
    - Very negative funding (< -0.02%) - fade shorts
    - High OI (conviction behind the move)
    - Good liquidity
    """
    alerts = []

    for analysis in analyses:
        symbol = analysis['symbol']
        funding = analysis.get('avg_funding_rate')
        volume = analysis.get('total_volume_24h', 0)
        oi = analysis.get('total_open_interest', 0)
        price_change = analysis.get('avg_price_change_24h')

        if not all([funding is not None, price_change is not None]):
            continue

        conditions_met = []
        confidence = 0
        direction = None

        # Check for extreme funding
        if funding > 0.03:  # Extreme long funding
            direction = 'SHORT'
            conditions_met.append(f"⚠️ EXTREME long funding: {funding:.4f}% (annualized: {funding*365*3:.1f}%)")
            confidence += 35

            if funding > 0.05:
                conditions_met.append(f"⚠️ CRITICAL: {funding:.4f}% is exceptionally high")
                confidence += 15

        elif funding < -0.02:  # Extreme short funding
            direction = 'LONG'
            conditions_met.append(f"⚠️ EXTREME short funding: {funding:.4f}% (annualized: {funding*365*3:.1f}%)")
            confidence += 35

            if funding < -0.04:
                conditions_met.append(f"⚠️ CRITICAL: {funding:.4f}% is exceptionally negative")
                confidence += 15
        else:
            continue  # Not extreme enough

        # High OI indicates conviction (20 points)
        oi_vol_ratio = oi / volume if volume > 0 else 0
        if oi_vol_ratio > 0.4:
            conditions_met.append(f"✅ High conviction: {oi_vol_ratio:.2f}x OI/Vol")
            confidence += 20

        # Good liquidity (15 points)
        if volume > 50_000_000:
            conditions_met.append(f"✅ Good liquidity: ${volume/1_000_000:.1f}M")
            confidence += 15
        elif volume > 10_000_000:
            conditions_met.append(f"⚠️ Moderate liquidity: ${volume/1_000_000:.1f}M")
            confidence += 8

        # Recent price movement alignment (10 points)
        if direction == 'SHORT' and price_change > 5:
            conditions_met.append(f"✅ Extended move: {price_change:+.1f}% may be exhausted")
            confidence += 10
        elif direction == 'LONG' and price_change < -5:
            conditions_met.append(f"✅ Extended drop: {price_change:+.1f}% may be exhausted")
            confidence += 10

        if confidence >= 60:
            alerts.append(DirectionalAlert(
                direction=direction,
                symbol=symbol,
                strategy='Funding Rate Exhaustion',
                confidence=confidence,
                reasoning=conditions_met,
                metrics={
                    'funding_rate': funding,
                    'annualized_funding': funding * 365 * 3,  # 3 funding periods per day
                    'volume_24h': volume,
                    'oi_vol_ratio': oi_vol_ratio,
                    'price_change_24h': price_change
                },
                risk_level='MEDIUM'
            ))

    return alerts


def format_alert_message(alert: DirectionalAlert) -> str:
    """Format a single alert for display"""

    # Risk emoji
    risk_emoji = {
        'LOW': '🟢',
        'MEDIUM': '🟡',
        'HIGH': '🟠',
        'VERY_HIGH': '🔴'
    }

    # Direction emoji
    direction_emoji = '🟢' if alert.direction == 'LONG' else '🔴'

    msg = []
    msg.append(f"\n{direction_emoji} {alert.direction} {alert.symbol}")
    msg.append(f"{'─' * 80}")
    msg.append(f"Strategy: {alert.strategy}")
    msg.append(f"Confidence: {alert.confidence:.0f}% | Risk: {risk_emoji[alert.risk_level]} {alert.risk_level}")
    msg.append("")
    msg.append("Reasoning:")
    for reason in alert.reasoning:
        msg.append(f"  {reason}")
    msg.append("")
    msg.append("Key Metrics:")
    for key, value in alert.metrics.items():
        if isinstance(value, float):
            if 'pct' in key or 'change' in key:
                msg.append(f"  • {key}: {value:+.2f}%")
            elif 'rate' in key:
                msg.append(f"  • {key}: {value:.4f}%")
            elif 'beta' in key:
                msg.append(f"  • {key}: {value:.2f}x")
            else:
                msg.append(f"  • {key}: {value:,.0f}")
        else:
            msg.append(f"  • {key}: {value}")

    return "\n".join(msg)


def send_discord_alert(alerts: List[DirectionalAlert], config: Config):
    """Send alerts to Discord"""

    webhook_url = os.getenv('DISCORD_DIRECTIONAL_WEBHOOK_URL') or os.getenv('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        print("⚠️  No Discord webhook URL configured")
        return

    # Group by direction
    longs = [a for a in alerts if a.direction == 'LONG']
    shorts = [a for a in alerts if a.direction == 'SHORT']

    # Sort by confidence
    longs.sort(key=lambda x: x.confidence, reverse=True)
    shorts.sort(key=lambda x: x.confidence, reverse=True)

    embeds = []

    # Summary embed
    summary_color = 0x00FF00 if len(longs) > len(shorts) else (0xFF0000 if len(shorts) > len(longs) else 0xFFFFFF)

    embeds.append({
        "title": "🎯 Directional Trading Alerts",
        "description": f"**{len(alerts)} opportunities detected**\n\n🟢 {len(longs)} LONG signals\n🔴 {len(shorts)} SHORT signals",
        "color": summary_color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Crypto Perps Tracker • Directional Alerts"}
    })

    # Long alerts (top 5)
    if longs:
        for alert in longs[:5]:
            embeds.append({
                "title": f"🟢 LONG {alert.symbol}",
                "description": f"**{alert.strategy}**\n\nConfidence: **{alert.confidence:.0f}%** | Risk: **{alert.risk_level}**",
                "color": 0x00FF00,
                "fields": [
                    {
                        "name": "Reasoning",
                        "value": "\n".join(alert.reasoning[:5]),  # Top 5 reasons
                        "inline": False
                    },
                    {
                        "name": "Key Metrics",
                        "value": "\n".join([
                            f"• {k}: {v:.2f}" if isinstance(v, float) else f"• {k}: {v}"
                            for k, v in list(alert.metrics.items())[:5]
                        ]),
                        "inline": False
                    }
                ]
            })

    # Short alerts (top 5)
    if shorts:
        for alert in shorts[:5]:
            embeds.append({
                "title": f"🔴 SHORT {alert.symbol}",
                "description": f"**{alert.strategy}**\n\nConfidence: **{alert.confidence:.0f}%** | Risk: **{alert.risk_level}**",
                "color": 0xFF0000,
                "fields": [
                    {
                        "name": "Reasoning",
                        "value": "\n".join(alert.reasoning[:5]),
                        "inline": False
                    },
                    {
                        "name": "Key Metrics",
                        "value": "\n".join([
                            f"• {k}: {v:.2f}" if isinstance(v, float) else f"• {k}: {v}"
                            for k, v in list(alert.metrics.items())[:5]
                        ]),
                        "inline": False
                    }
                ]
            })

    # Send to Discord
    payload = {
        "embeds": embeds[:10],  # Discord limit
        "username": "Directional Alert Bot"
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 204:
            print(f"✅ Sent {len(embeds)} embeds to Discord")
        else:
            print(f"⚠️  Discord returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("DIRECTIONAL TRADING ALERTS - Long/Short Opportunity Scanner")
    print("="*80 + "\n")

    # Load environment
    load_dotenv()

    # Initialize
    config = Config.from_yaml('config/config.yaml')
    container = Container(config)

    print("📊 Fetching symbol data from all exchanges...")

    # Import analysis functions from generate_symbol_report
    from generate_symbol_report import (
        fetch_all_symbols_from_exchanges,
        analyze_symbol
    )

    # Fetch all symbols
    symbol_data = fetch_all_symbols_from_exchanges(container)

    if not symbol_data:
        print("❌ No symbol data available")
        return

    print(f"✅ Fetched data for {len(symbol_data)} symbols\n")
    print("🔍 Analyzing opportunities...")

    # Analyze each symbol
    analyses = []
    btc_data = None

    for symbol, exchange_data in symbol_data.items():
        analysis = analyze_symbol(symbol, exchange_data)
        if analysis:
            analyses.append(analysis)
            if symbol == 'BTC':
                btc_data = analysis

    if not btc_data:
        print("❌ Bitcoin data not available - cannot calculate beta strategies")
        return

    btc_metrics = get_btc_metrics(analyses)
    print(f"   ₿ BTC 24h: {btc_metrics['price_change_24h']:+.2f}%\n")

    # Run all alert strategies
    all_alerts = []

    print("Strategy 1: High-Beta Longs...")
    high_beta_longs = analyze_high_beta_longs(analyses, btc_metrics)
    all_alerts.extend(high_beta_longs)
    print(f"   Found {len(high_beta_longs)} opportunities")

    print("Strategy 2: Parabolic Shorts...")
    parabolic_shorts = analyze_parabolic_shorts(analyses)
    all_alerts.extend(parabolic_shorts)
    print(f"   Found {len(parabolic_shorts)} opportunities")

    print("Strategy 3: Beta Divergence...")
    beta_divergence = analyze_beta_divergence(analyses, btc_metrics)
    all_alerts.extend(beta_divergence)
    print(f"   Found {len(beta_divergence)} opportunities")

    print("Strategy 4: Funding Extremes...")
    funding_extremes = analyze_funding_extremes(analyses)
    all_alerts.extend(funding_extremes)
    print(f"   Found {len(funding_extremes)} opportunities\n")

    # Display results
    if not all_alerts:
        print("=" * 80)
        print("No alerts detected - no strong opportunities at this time")
        print("=" * 80)
        return

    # Sort by confidence
    all_alerts.sort(key=lambda x: x.confidence, reverse=True)

    # Group by direction
    longs = [a for a in all_alerts if a.direction == 'LONG']
    shorts = [a for a in all_alerts if a.direction == 'SHORT']

    print("=" * 80)
    print(f"🎯 {len(all_alerts)} DIRECTIONAL OPPORTUNITIES DETECTED")
    print("=" * 80)

    if longs:
        print(f"\n🟢 LONG OPPORTUNITIES ({len(longs)} detected)")
        print("=" * 80)
        for alert in longs:
            print(format_alert_message(alert))

    if shorts:
        print(f"\n🔴 SHORT OPPORTUNITIES ({len(shorts)} detected)")
        print("=" * 80)
        for alert in shorts:
            print(format_alert_message(alert))

    print("\n" + "=" * 80)
    print(f"Analysis complete • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 80)

    # Send to Discord if enabled
    if config.discord.enabled:
        print("\n📤 Sending alerts to Discord...")
        send_discord_alert(all_alerts, config)


if __name__ == "__main__":
    main()
