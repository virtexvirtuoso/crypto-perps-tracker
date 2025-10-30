#!/usr/bin/env python3
"""
Trading Strategy Alert System (v2)
Refactored to use new AlertService architecture

This version uses the Container/Service pattern and AlertService
for cleaner, maintainable code.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
import argparse
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from src.models.config import Config
from src.container import Container
from src.services.alert import StrategyAlert


# ========================================
# DISCORD INTEGRATION
# ========================================

def send_to_discord(alerts: List[StrategyAlert], webhook_url: str) -> bool:
    """Send strategy alerts to Discord webhook

    Args:
        alerts: List of strategy alerts to send
        webhook_url: Discord webhook URL

    Returns:
        True if sent successfully, False otherwise
    """
    import requests

    if not alerts or not webhook_url:
        return False

    # Group alerts by tier
    tier_1 = [a for a in alerts if a.tier == 1]
    tier_2 = [a for a in alerts if a.tier == 2]
    tier_3 = [a for a in alerts if a.tier == 3]

    # Build message
    embeds = []

    # Tier 1 - CRITICAL (red)
    if tier_1:
        fields = []
        for alert in tier_1:
            fields.append({
                "name": f"🔴 {alert.strategy_name}",
                "value": (
                    f"**Direction:** {alert.direction}\n"
                    f"**Confidence:** {alert.confidence}%\n"
                    f"**Reasoning:** {alert.reasoning}\n"
                    f"_Detected: {alert.timestamp.strftime('%Y-%m-%d %H:%M UTC')}_"
                ),
                "inline": False
            })

        embeds.append({
            "title": "🚨 CRITICAL ALERTS - Immediate Action Required",
            "color": 15158332,  # Red
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Tier 2 - HIGH PRIORITY (orange)
    if tier_2:
        fields = []
        for alert in tier_2:
            fields.append({
                "name": f"🟠 {alert.strategy_name}",
                "value": (
                    f"**Direction:** {alert.direction}\n"
                    f"**Confidence:** {alert.confidence}%\n"
                    f"**Reasoning:** {alert.reasoning}\n"
                    f"_Detected: {alert.timestamp.strftime('%Y-%m-%d %H:%M UTC')}_"
                ),
                "inline": False
            })

        embeds.append({
            "title": "⚠️ HIGH PRIORITY ALERTS - Act Within Hours",
            "color": 16753920,  # Orange
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Tier 3 - BACKGROUND (gray) - only if specifically requested
    if tier_3:
        fields = []
        for alert in tier_3[:3]:  # Limit to 3
            fields.append({
                "name": f"⚪ {alert.strategy_name}",
                "value": (
                    f"**Direction:** {alert.direction}\n"
                    f"**Confidence:** {alert.confidence}%\n"
                    f"_Background opportunity_"
                ),
                "inline": True
            })

        embeds.append({
            "title": "📊 Background Opportunities",
            "color": 9807270,  # Gray
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Send to Discord
    try:
        payload = {
            "username": "Strategy Alert Bot",
            "embeds": embeds[:10]  # Discord limit: 10 embeds per message
        }

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code in (200, 204):
            return True
        else:
            print(f"Discord webhook failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error sending to Discord: {e}")
        return False


# ========================================
# MAIN EXECUTION
# ========================================

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Trading Strategy Alert System')
    parser.add_argument('--send-discord', action='store_true',
                       help='Send alerts to Discord webhook')
    parser.add_argument('--tiers', nargs='+', type=int, default=[1, 2],
                       help='Alert tiers to process (default: 1 2)')
    parser.add_argument('--min-confidence', type=int, default=60,
                       help='Minimum confidence threshold (default: 60)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Detect strategies but do not send alerts')
    args = parser.parse_args()

    # Initialize container with production config
    config = Config(
        app_name="Strategy Alert System",
        exchanges={"enabled": [
            "binance", "bybit", "okx", "gateio", "bitget",
            "coinbase_intx", "kraken", "kucoin",
            "hyperliquid", "dydx", "asterdex"
        ]},
        cache={"ttl": 300},
        database={"path": "data/market.db"},
        alert_database={"path": "data/alerts.db"}
    )

    container = Container(config)

    # Initialize alert repository
    print("🔧 Initializing Alert Repository...")
    container.alert_repo.initialize_database()

    # Detect all strategies
    print("\n🔍 Detecting Trading Strategies...")
    alerts = container.alert_service.detect_all_strategies()

    print(f"   Found {len(alerts)} potential strategies")

    if not alerts:
        print("   ✅ No strategies detected (market is calm)")
        return

    # Filter by tier and confidence
    filtered = container.alert_service.filter_by_tier(
        alerts,
        tiers=args.tiers,
        min_confidence=args.min_confidence
    )

    print(f"   Filtered to {len(filtered)} actionable alerts (tiers {args.tiers}, confidence >= {args.min_confidence}%)")

    if not filtered:
        print("   ✅ No actionable alerts after filtering")
        return

    # Process alerts with deduplication
    print("\n📊 Processing Alerts...")
    alerts_to_send = []

    for alert in filtered:
        should_send, reason = container.alert_service.should_alert(
            strategy_name=alert.strategy_name,
            confidence=alert.confidence,
            direction=alert.direction,
            min_confidence_delta=20,
            max_alerts_per_day=3,
            max_alerts_per_hour=10
        )

        tier_label = "CRITICAL" if alert.tier == 1 else "HIGH" if alert.tier == 2 else "BACKGROUND"

        if should_send:
            print(f"   ✅ {alert.strategy_name} (Tier {alert.tier} - {tier_label})")
            print(f"      Confidence: {alert.confidence}% | Direction: {alert.direction}")
            print(f"      {alert.reasoning}")

            if not args.dry_run:
                # Record the alert
                alert_id = container.alert_service.record_alert(
                    strategy_name=alert.strategy_name,
                    confidence=alert.confidence,
                    direction=alert.direction
                )
                print(f"      Recorded: Alert ID {alert_id}")

            alerts_to_send.append(alert)
        else:
            print(f"   ⏸️  {alert.strategy_name} - SKIPPED ({reason})")
            # Record suppression
            container.alert_repo.record_suppression()

    # Send to Discord if requested
    if args.send_discord and alerts_to_send and not args.dry_run:
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

        if not webhook_url:
            print("\n❌ Discord webhook URL not found in environment")
            print("   Set DISCORD_WEBHOOK_URL in .env file")
        else:
            print(f"\n📤 Sending {len(alerts_to_send)} alerts to Discord...")
            success = send_to_discord(alerts_to_send, webhook_url)

            if success:
                print("   ✅ Alerts sent successfully")
            else:
                print("   ❌ Failed to send alerts")

    # Show summary statistics
    print("\n📈 Alert Statistics (Last 7 Days):")
    stats = container.alert_service.get_alert_statistics(days=7)

    if stats:
        for date, day_stats in sorted(stats.items())[-7:]:  # Last 7 days
            print(f"   {date}: {day_stats['total_alerts']} alerts "
                  f"(T1: {day_stats['tier_1']}, T2: {day_stats['tier_2']}, T3: {day_stats['tier_3']}, "
                  f"Suppressed: {day_stats['suppressed']})")
    else:
        print("   No historical data yet")

    print("\n✅ Strategy Alert System Complete\n")


if __name__ == "__main__":
    main()
