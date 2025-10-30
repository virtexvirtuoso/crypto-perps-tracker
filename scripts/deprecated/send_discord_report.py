#!/usr/bin/env python3
"""
Discord Market Report Sender
Sends formatted market reports to Discord webhook with charts and text file
"""

import sys
import os
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import market report functions
from generate_market_report import (
    fetch_all_enhanced,
    format_market_report,
    send_market_report_to_discord
)


def load_config():
    """Load configuration from YAML file with environment variable substitution"""
    try:
        with open('config/config.yaml', 'r') as f:
            content = f.read()
            # Substitute environment variables
            content = os.path.expandvars(content)
            return yaml.safe_load(content)
    except FileNotFoundError:
        print("⚠️  Config file not found.")
        return {'discord': {'enabled': True, 'webhook_url': ''}}


def generate_and_send_discord_report(webhook_url: str = None) -> bool:
    """Main function to generate and send Discord report with charts"""

    print("\n🚀 Generating Discord Market Report...\n")

    # Load config
    config = load_config()

    # Use provided webhook URL or get from config
    if not webhook_url:
        webhook_url = config.get('discord', {}).get('webhook_url')

    if not webhook_url:
        print("❌ No Discord webhook URL configured!")
        print("   Please set webhook_url in config/config.yaml or pass as argument")
        return False

    if not config.get('discord', {}).get('enabled', True):
        print("⚠️  Discord integration is disabled in config")
        return False

    print("⏳ Fetching data from 9 exchanges + spot markets (25-35 seconds)...\n")

    # Fetch data
    results = fetch_all_enhanced()

    # Generate full text report
    report_text = format_market_report(results)

    # Save report to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"data/market_report_{timestamp}.txt"

    try:
        with open(filename, 'w') as f:
            f.write(report_text)
        print(f"✅ Report saved to: {filename}\n")
    except Exception as e:
        print(f"⚠️  Could not save report to file: {e}\n")

    # Send to Discord with charts
    print("📤 Sending to Discord webhook...")
    print("   • Generating charts...")

    success = send_market_report_to_discord(report_text, results, webhook_url)

    if success:
        print(f"\n✅ Market Report sent successfully")

    return success


if __name__ == "__main__":
    # Allow webhook URL as command line argument
    webhook_url = sys.argv[1] if len(sys.argv) > 1 else None

    success = generate_and_send_discord_report(webhook_url)

    sys.exit(0 if success else 1)
