#!/usr/bin/env python3
"""
Discord Market Report Sender (v3)
Refactored to use Container/Service architecture

Sends comprehensive market reports to Discord webhook with:
- 4 charts (funding rates, market dominance, basis, leverage)
- Full sentiment analysis
- Arbitrage opportunities
- Market health indicators
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict
import requests
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from src.models.config import Config
from src.container import Container
from src.services.report import ReportFormat

# Import chart generation functions from generate_market_report
from scripts.generate_market_report import (
    fetch_all_markets,
    generate_funding_rate_chart,
    generate_market_dominance_chart,
    generate_basis_chart,
    generate_leverage_chart,
    analyze_market_sentiment,
    analyze_basis_metrics,
    identify_arbitrage_opportunities,
    calculate_market_dominance,
    detect_anomalies
)


def send_comprehensive_report_to_discord(
    results: List[Dict],
    sentiment: Dict,
    basis_metrics: Dict,
    dominance: Dict,
    arb_opportunities: List[Dict],
    webhook_url: str,
    full_report_text: Optional[str] = None
) -> bool:
    """Send comprehensive market report with charts to Discord

    Args:
        results: Market data from all exchanges
        sentiment: Sentiment analysis results
        basis_metrics: Spot-futures basis analysis
        dominance: Market dominance metrics
        arb_opportunities: Arbitrage opportunities
        webhook_url: Discord webhook URL
        full_report_text: Full text report to attach as .txt file (optional)

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Calculate totals
        successful = [r for r in results if r.get('status') == 'success']
        total_volume = sum(r['volume'] for r in successful)
        total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

        # Create comprehensive embed
        embed = {
            "title": "📊 Perpetual Futures Market Report",
            "description": f"**Cross-Exchange Analysis • {datetime.now(timezone.utc).strftime('%b %d, %H:%M UTC')}**",
            "color": 0x3498db,  # Blue
            "fields": [],
            "footer": {
                "text": "Powered by Virtuoso Crypto • virtuosocrypto.com"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Market Overview
        embed["fields"].append({
            "name": "📈 Market Overview",
            "value": (
                f"**Total Volume:** ${total_volume/1e9:.2f}B\n"
                f"**Total OI:** ${total_oi/1e9:.2f}B\n"
                f"**Exchanges:** {len(successful)}"
            ),
            "inline": True
        })

        # Sentiment
        embed["fields"].append({
            "name": "🎯 Market Sentiment",
            "value": (
                f"**Direction:** {sentiment['sentiment']}\n"
                f"**Score:** {sentiment['composite_score']:.3f}\n"
                f"**Strength:** {sentiment['strength']}"
            ),
            "inline": True
        })

        # Funding
        embed["fields"].append({
            "name": "💰 Funding Rate",
            "value": (
                f"**Avg:** {sentiment['weighted_funding']:.4f}%\n"
                f"**Annual:** {sentiment['weighted_funding']*3*365:.1f}%\n"
                f"**Signal:** {sentiment['factors']['funding']['signal']}"
            ),
            "inline": True
        })

        # Market Structure
        if basis_metrics.get('status') == 'success':
            embed["fields"].append({
                "name": "📊 Market Structure",
                "value": (
                    f"**Basis:** {basis_metrics['market_structure']}\n"
                    f"**Avg:** {basis_metrics['avg_basis']:.4f}%\n"
                    f"{basis_metrics['structure_signal']} {basis_metrics['interpretation'][:50]}..."
                ),
                "inline": False
            })

        # Top Arbitrage Opportunity
        if arb_opportunities:
            top_arb = arb_opportunities[0]
            embed["fields"].append({
                "name": "💎 Top Arbitrage Opportunity",
                "value": (
                    f"**Type:** {top_arb['type']}\n"
                    f"**Action:** {top_arb['action']}\n"
                    f"**Yield:** {top_arb['annual_yield']:.1f}% annual"
                ),
                "inline": False
            })

        # Market Dominance
        embed["fields"].append({
            "name": "🏆 Market Leaders",
            "value": "\n".join([
                f"**{i+1}. {l['exchange']}** ${l['volume']/1e9:.1f}B ({l['share']:.1f}%)"
                for i, l in enumerate(dominance['leaders'][:3])
            ]),
            "inline": False
        })

        # Generate charts
        print("   • Generating funding rate chart...")
        funding_chart = generate_funding_rate_chart(results)

        print("   • Generating market dominance chart...")
        dominance_chart = generate_market_dominance_chart(dominance)

        print("   • Generating basis chart...")
        basis_chart = None
        if basis_metrics.get('status') == 'success' and basis_metrics.get('basis_data'):
            basis_chart = generate_basis_chart(basis_metrics['basis_data'])

        print("   • Generating leverage chart...")
        leverage_chart = None
        if basis_metrics.get('status') == 'success':
            leverage_chart = generate_leverage_chart(basis_metrics)

        # Prepare files
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
        files = {
            'file1': (f"funding_rates_{timestamp}.png", funding_chart, 'image/png'),
            'file2': (f"market_dominance_{timestamp}.png", dominance_chart, 'image/png')
        }

        file_idx = 3
        if basis_chart:
            files[f'file{file_idx}'] = (f"basis_{timestamp}.png", basis_chart, 'image/png')
            file_idx += 1

        if leverage_chart:
            files[f'file{file_idx}'] = (f"leverage_{timestamp}.png", leverage_chart, 'image/png')
            file_idx += 1

        # Add full text report as attachment
        if full_report_text:
            files[f'file{file_idx}'] = (f"market_report_{timestamp}.txt", full_report_text.encode('utf-8'), 'text/plain')

        payload = {
            'username': 'Market Intelligence',
            'embeds': [embed]
        }

        # Send to Discord
        response = requests.post(
            webhook_url,
            files=files,
            data={'payload_json': json.dumps(payload)},
            timeout=15
        )

        if response.status_code == 200:
            print(f"\n✅ Comprehensive Market Report sent to Discord!")
            return True
        else:
            print(f"\n❌ Discord webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Error sending comprehensive report: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_to_discord(report_text: str, webhook_url: str) -> bool:
    """Send market report to Discord webhook

    Args:
        report_text: Formatted report text
        webhook_url: Discord webhook URL

    Returns:
        True if sent successfully, False otherwise
    """
    if not webhook_url:
        print("❌ No Discord webhook URL provided")
        return False

    try:
        # Split report into chunks (Discord has 2000 char limit per message)
        max_length = 1900  # Leave room for code block markers
        chunks = []

        if len(report_text) <= max_length:
            chunks = [report_text]
        else:
            # Split by sections or lines
            lines = report_text.split('\n')
            current_chunk = ""

            for line in lines:
                if len(current_chunk) + len(line) + 1 > max_length:
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'

            if current_chunk:
                chunks.append(current_chunk)

        # Send chunks
        for i, chunk in enumerate(chunks):
            if i == 0:
                # First message with header
                payload = {
                    "username": "Market Report Bot",
                    "embeds": [{
                        "title": "📊 Perpetual Futures Market Report",
                        "description": f"```\n{chunk}\n```",
                        "color": 3447003,  # Blue
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "footer": {
                            "text": f"Part {i+1}/{len(chunks)} • Generated with Container Architecture"
                        }
                    }]
                }
            else:
                # Continuation messages
                payload = {
                    "username": "Market Report Bot",
                    "content": f"```\n{chunk}\n```"
                }

            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code not in (200, 204):
                print(f"❌ Discord webhook failed (chunk {i+1}): {response.status_code} - {response.text}")
                return False

            # Rate limit: Discord allows ~5 messages per 5 seconds
            if i < len(chunks) - 1:
                import time
                time.sleep(1.5)

        return True

    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")
        return False


def generate_and_send_comprehensive_report(
    webhook_url: Optional[str] = None
) -> bool:
    """Generate comprehensive market report with charts and send to Discord

    Args:
        webhook_url: Discord webhook URL (or use DISCORD_WEBHOOK_URL env var)

    Returns:
        True if successful, False otherwise
    """
    print("\n🚀 Generating Comprehensive Discord Market Report (v3 - With Charts)...\n")

    # Get webhook URL from env if not provided
    if not webhook_url:
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        print("❌ No Discord webhook URL configured!")
        print("   Set DISCORD_WEBHOOK_URL environment variable or pass as argument")
        return False

    # Initialize container
    print("🔧 Initializing Container...")
    config = Config.from_yaml('config/config.yaml')
    container = Container(config)

    # Fetch market data
    print("📊 Fetching market data from all exchanges...")
    results = fetch_all_markets(container)
    print(f"   ✅ Fetched data from {len(results)} exchanges\n")

    # Run analyses
    print("🔍 Running market analyses...")

    print("   • Analyzing sentiment...")
    sentiment = analyze_market_sentiment(results)

    print("   • Analyzing spot-futures basis...")
    basis_metrics = analyze_basis_metrics()

    print("   • Calculating market dominance...")
    dominance = calculate_market_dominance(results)

    print("   • Identifying arbitrage opportunities...")
    arb_opportunities = identify_arbitrage_opportunities(results)

    print("   ✅ All analyses complete\n")

    # Generate full text report
    print("📝 Generating comprehensive text report...")
    from scripts.generate_market_report import format_market_report
    full_report_text = format_market_report(results)

    # Save to file
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"data/market_report_{timestamp}.txt"

    try:
        with open(filename, 'w') as f:
            f.write(full_report_text)
        print(f"   ✅ Full report saved to: {filename}\n")
    except Exception as e:
        print(f"   ⚠️  Could not save report to file: {e}\n")

    # Send to Discord
    print("📤 Generating charts and sending to Discord webhook...")

    success = send_comprehensive_report_to_discord(
        results=results,
        sentiment=sentiment,
        basis_metrics=basis_metrics,
        dominance=dominance,
        arb_opportunities=arb_opportunities,
        webhook_url=webhook_url,
        full_report_text=full_report_text
    )

    return success


def generate_and_send_report(
    webhook_url: Optional[str] = None,
    format: ReportFormat = ReportFormat.TEXT,
    save_file: bool = True
) -> bool:
    """Generate simple text market report and send to Discord

    Args:
        webhook_url: Discord webhook URL (or use DISCORD_WEBHOOK_URL env var)
        format: Report format (TEXT, MARKDOWN, HTML)
        save_file: Whether to save report to file

    Returns:
        True if successful, False otherwise
    """
    print("\n🚀 Generating Discord Market Report (v2 - Text Only)...\n")

    # Get webhook URL from env if not provided
    if not webhook_url:
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        print("❌ No Discord webhook URL configured!")
        print("   Set DISCORD_WEBHOOK_URL environment variable or pass as argument")
        return False

    # Initialize container
    print("🔧 Initializing Container...")
    config = Config(
        app_name="Discord Market Report",
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

    # Generate report
    print("📊 Generating market summary...")
    print("   Fetching data from all exchanges...")

    report_text = container.report_service.generate_market_summary(
        format=format,
        use_cache=True  # Use cache for faster generation
    )

    print(f"   ✅ Report generated ({len(report_text):,} characters)")

    # Save to file if requested
    if save_file:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"data/market_report_{timestamp}.txt"

        try:
            with open(filename, 'w') as f:
                f.write(report_text)
            print(f"   ✅ Report saved to: {filename}")
        except Exception as e:
            print(f"   ⚠️  Could not save report to file: {e}")

    # Send to Discord
    print("\n📤 Sending to Discord webhook...")

    success = send_to_discord(report_text, webhook_url)

    if success:
        print("\n✅ Market Report sent successfully to Discord!")
    else:
        print("\n❌ Failed to send report to Discord")

    return success


def main():
    """Main execution function"""
    # Parse command line arguments
    webhook_url = None
    comprehensive = True  # Default to comprehensive report with charts

    if len(sys.argv) > 1:
        if sys.argv[1] == '--simple':
            comprehensive = False
        else:
            webhook_url = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[1] != '--simple':
        webhook_url = sys.argv[2]

    # Generate and send
    if comprehensive:
        success = generate_and_send_comprehensive_report(
            webhook_url=webhook_url
        )
    else:
        success = generate_and_send_report(
            webhook_url=webhook_url,
            format=ReportFormat.TEXT,
            save_file=True
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
