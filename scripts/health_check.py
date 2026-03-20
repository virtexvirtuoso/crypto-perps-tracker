#!/usr/bin/env python3
"""
Health check script for crypto-perps-tracker

Runs health checks on:
- Database connectivity and freshness
- Exchange API connectivity
- Disk space
- Sends alerts to Discord if any checks fail
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import argparse
from src.models.config import Config
from src.container import Container
from src.utils.monitoring import HealthMonitor
from src.utils.logging_config import setup_logging, get_logger


def main():
    """Run health checks and report results"""
    parser = argparse.ArgumentParser(description='Run health checks')
    parser.add_argument('--config', default='config/config.yaml', help='Path to config file')
    parser.add_argument('--db', default='data/market_history.db', help='Path to database file')
    parser.add_argument('--alert', action='store_true', help='Send Discord alerts on failures')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    # Setup logging
    setup_logging(log_level='DEBUG' if args.verbose else 'INFO')
    logger = get_logger(__name__)

    logger.info("Starting health checks...")

    # Load config and create container
    try:
        config = Config.from_yaml(args.config)
        container = Container(config)
    except Exception as e:
        logger.error(f"Failed to initialize container: {e}")
        print(f"❌ Initialization failed: {e}")
        sys.exit(1)

    # Run health checks
    monitor = HealthMonitor()
    checks = monitor.check_all(container, db_path=args.db)

    # Print results
    print("\n" + "=" * 60)
    print("HEALTH CHECK RESULTS")
    print("=" * 60 + "\n")

    for check in checks:
        emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌'
        }[check.status]

        print(f"{emoji} {check.name.upper()}: {check.message}")

        if args.verbose and check.details:
            for key, value in check.details.items():
                print(f"   {key}: {value}")

    # Overall status
    overall_status = monitor.get_status_summary(checks)
    print("\n" + "=" * 60)

    if overall_status == 'healthy':
        print("✅ OVERALL STATUS: HEALTHY")
        exit_code = 0
    elif overall_status == 'degraded':
        print("⚠️  OVERALL STATUS: DEGRADED")
        exit_code = 1
    else:
        print("❌ OVERALL STATUS: UNHEALTHY")
        exit_code = 2

    print("=" * 60 + "\n")

    # Send alerts if requested
    if args.alert:
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if webhook_url:
            logger.info("Sending Discord alert...")
            monitor.send_alert_if_unhealthy(checks, webhook_url)
        else:
            logger.warning("DISCORD_WEBHOOK_URL not set, skipping alerts")

    # Cleanup
    container.cleanup()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
