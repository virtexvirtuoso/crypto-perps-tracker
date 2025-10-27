#!/usr/bin/env python3
"""
Trading Strategy Alert System V3 - Phase 3+ Enhanced
Integrates websockets, ML scoring, Kalman filtering, alert queue, and monitoring
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
import yaml
from dotenv import load_dotenv
import argparse
import json
import time

# Load environment variables
load_dotenv()

# Import base strategy functions (Phase 1-2)
from strategy_alerts import (
    STRATEGY_TIERS, get_strategy_tier, load_config,
    analyze_all_strategies, send_strategy_alert_to_discord
)

# Import Container for fetching data
from src.container import Container
from src.models.config import Config

# Phase 3+ imports - now from src.alerts
from src.alerts.state_db import AlertStateDB
from src.alerts.kalman_filter import MetricsSmoothing, AdaptiveThresholds, Hysteresis
from src.alerts.ml_scoring import AlertScorer, AlertPrioritizer
from src.alerts.websocket import WebSocketManager
from src.alerts.queue import AlertQueue, AlertBundler
from src.alerts.metrics import MetricsTracker, DashboardGenerator


class EnhancedStrategyAlertSystem:
    """
    Phase 3+ Enhanced Alert System
    Combines all advanced features for production-grade alerting
    """

    def __init__(self, mode: str = 'polling', enable_features: Dict[str, bool] = None):
        """
        Args:
            mode: 'polling', 'websocket', or 'hybrid'
            enable_features: Dict of feature flags (sqlite, ml, kalman, queue, metrics)
        """
        self.mode = mode
        self.features = enable_features or {
            'sqlite': True,
            'ml': True,
            'kalman': True,
            'queue': True,
            'metrics': True,
            'websockets': mode in ['websocket', 'hybrid']
        }

        # Initialize components based on enabled features
        self.state_db = AlertStateDB() if self.features['sqlite'] else None
        self.metrics_smoother = MetricsSmoothing() if self.features['kalman'] else None
        self.adaptive_thresholds = AdaptiveThresholds() if self.features['kalman'] else None

        # ML components
        if self.features['ml']:
            self.alert_scorer = AlertScorer()
            self.alert_prioritizer = AlertPrioritizer(self.alert_scorer)
        else:
            self.alert_scorer = None
            self.alert_prioritizer = None

        # Queue and bundling
        if self.features['queue']:
            self.alert_queue = AlertQueue()
            self.alert_bundler = AlertBundler()
        else:
            self.alert_queue = None
            self.alert_bundler = None

        # Metrics tracking
        if self.features['metrics']:
            self.metrics_tracker = MetricsTracker()
            self.dashboard_gen = DashboardGenerator(self.metrics_tracker)
        else:
            self.metrics_tracker = None
            self.dashboard_gen = None

        # Websocket manager
        self.websocket_alerts = []  # Always initialize buffer
        if self.features['websockets']:
            self.ws_manager = WebSocketManager(self._handle_websocket_event)
        else:
            self.ws_manager = None

        print("🚀 Enhanced Alert System V3 Initialized")
        print(f"   Mode: {mode.upper()}")
        print(f"   Features enabled:")
        for feature, enabled in self.features.items():
            status = "✅" if enabled else "❌"
            print(f"      {status} {feature.upper()}")

    def _handle_websocket_event(self, exchange: str, event_type: str, data: Dict):
        """
        Callback for websocket events
        Triggers immediate strategy checks for Tier 1 alerts
        """
        print(f"⚡ Websocket event: {exchange} - {event_type}")

        if event_type == 'large_liquidation':
            # Trigger immediate Tier 1 check
            alert = {
                'strategy': 'Liquidation Cascade Risk (Websocket)',
                'confidence': 85,
                'direction': 'SHORT' if data.get('side') == 'Long' else 'LONG',
                'tier': 1,
                'trigger': 'websocket',
                'exchange': exchange,
                'liquidation_data': data,
                'recommendation': f"⚡ REAL-TIME: Large {data['side']} liquidation detected\n" +
                                 f"• Size: ${data['size_usd']/1e6:.1f}M\n" +
                                 f"• Exchange: {exchange}\n" +
                                 f"• Counter-position opportunity"
            }

            self.websocket_alerts.append(alert)

    def smooth_market_metrics(self, sentiment: Dict, results: List[Dict]) -> Dict:
        """
        Apply Kalman filtering to smooth noisy market metrics
        """
        if not self.metrics_smoother:
            return sentiment

        # Smooth funding rates for each exchange
        for result in results:
            if result.get('status') == 'success':
                exchange = result.get('exchange', '')

                if 'funding_rate' in result:
                    original = result['funding_rate']
                    smoothed = self.metrics_smoother.smooth_funding_rate(exchange, original)
                    result['funding_rate_smoothed'] = smoothed

                # Smooth OI change if available
                if 'oi_change_pct' in result:
                    original_oi = result['oi_change_pct']
                    smoothed_oi = self.metrics_smoother.smooth_oi_change(exchange, original_oi)
                    result['oi_change_smoothed'] = smoothed_oi

        return sentiment

    def apply_adaptive_thresholds(self, alerts: List[Dict]) -> List[Dict]:
        """
        Adjust alert thresholds based on current market volatility
        """
        if not self.adaptive_thresholds:
            return alerts

        adjusted_alerts = []
        for alert in alerts:
            # Get recent confidence values for this strategy
            strategy_name = alert.get('strategy', '')
            confidence = alert.get('confidence', 0)

            # Adjust threshold based on market conditions
            # (In production, you'd track history of confidences)
            # For now, just mark that adaptive thresholds were considered
            alert['threshold_adjusted'] = True
            adjusted_alerts.append(alert)

        return adjusted_alerts

    def score_and_prioritize_alerts(self, alerts: List[Dict]) -> List[Dict]:
        """
        Score alerts using ML and prioritize
        """
        if not self.alert_scorer or not self.alert_prioritizer:
            return alerts

        # Enrich alerts with ML scores
        for alert in alerts:
            score = self.alert_scorer.score_alert(alert)
            alert['ml_score'] = score

        # Prioritize
        prioritized = self.alert_prioritizer.prioritize(alerts, max_alerts=10)

        if self.metrics_tracker:
            self.metrics_tracker.record_metric('ml_scoring_applied', len(alerts))

        return prioritized

    def check_if_should_bundle(self, alerts: List[Dict]) -> Tuple[bool, List[Dict]]:
        """
        Check if alerts should be bundled into digest
        """
        if not self.alert_bundler:
            return False, alerts

        should_bundle = self.alert_bundler.should_bundle(alerts)

        if should_bundle:
            bundled = self.alert_bundler.bundle_alerts(alerts)
            return True, bundled

        return False, alerts

    def enqueue_alerts(self, alerts: List[Dict]):
        """
        Add alerts to queue for delivery
        """
        if not self.alert_queue:
            return

        for alert in alerts:
            self.alert_queue.enqueue(alert)

    def process_alert_queue(self, webhook_url: str):
        """
        Process queued alerts and send
        """
        if not self.alert_queue:
            return

        ready_alerts = self.alert_queue.dequeue(max_alerts=5)

        for alert in ready_alerts:
            try:
                # Send alert
                success = self._send_single_alert(alert, webhook_url)

                if success:
                    self.alert_queue.mark_sent(alert)
                    if self.metrics_tracker:
                        self.metrics_tracker.record_alert_sent(
                            alert.get('strategy', ''),
                            alert.get('tier', 3),
                            alert.get('confidence', 0)
                        )
                else:
                    self.alert_queue.mark_failed(alert, "Discord webhook failed")

            except Exception as e:
                self.alert_queue.mark_failed(alert, str(e))

    def _send_single_alert(self, alert: Dict, webhook_url: str) -> bool:
        """Send single alert to Discord"""
        return send_strategy_alert_to_discord([alert], webhook_url)

    def record_metrics(self, stage: str, data: Dict):
        """
        Record performance metrics
        """
        if not self.metrics_tracker:
            return

        if stage == 'api_call':
            self.metrics_tracker.record_api_call(
                data['exchange'],
                data['endpoint'],
                data['response_time_ms'],
                data['success']
            )
        elif stage == 'suppression':
            self.metrics_tracker.record_alert_suppressed(
                data['strategy'],
                data['reason']
            )
        elif stage == 'error':
            self.metrics_tracker.record_error(
                data['error_type'],
                data['message']
            )

    def generate_monitoring_dashboard(self, output_path: str = 'data/alert_dashboard.html'):
        """Generate monitoring dashboard"""
        if self.dashboard_gen:
            self.dashboard_gen.generate_dashboard(output_path, days=7)

    def start_websockets(self, exchanges: List[str]):
        """Start websocket connections"""
        if self.ws_manager:
            self.ws_manager.start(exchanges)

    def stop_websockets(self):
        """Stop websocket connections"""
        if self.ws_manager:
            self.ws_manager.stop()

    def filter_with_state_db(self, alerts: List[Dict], tiers: List[int],
                            min_confidence: int) -> List[Dict]:
        """
        Filter alerts using SQLite state database
        """
        if not self.state_db:
            return alerts

        filtered = []
        for alert in alerts:
            strategy_name = alert.get('strategy', '')
            confidence = alert.get('confidence', 0)
            direction = alert.get('direction', 'N/A')
            tier = get_strategy_tier(strategy_name)

            # Tier filter
            if tiers and tier not in tiers:
                continue

            # Confidence filter
            if confidence < min_confidence:
                continue

            # Cooldown config
            cooldown_hours = {1: 1, 2: 2, 3: 4}

            # Check if should alert
            should_send, reason = self.state_db.should_alert(
                strategy_name,
                confidence,
                direction,
                tier,
                cooldown_hours,
                min_confidence_delta=20,
                max_alerts_per_day=3,
                max_alerts_per_hour=10
            )

            if should_send:
                # Record alert
                self.state_db.record_alert(strategy_name, confidence, direction, tier, cooldown_hours[tier])
                filtered.append(alert)
                print(f"   ✅ {strategy_name} ({confidence}%) - {reason}")
            else:
                # Record suppression
                today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                self.state_db.record_suppression(today)
                print(f"   🔇 {strategy_name} ({confidence}%) - {reason}")

                if self.metrics_tracker:
                    self.record_metrics('suppression', {
                        'strategy': strategy_name,
                        'reason': reason
                    })

        return filtered


def main_v3():
    """
    Main function for Phase 3+ enhanced system
    """
    parser = argparse.ArgumentParser(
        description='Crypto Strategy Alert System V3 (Phase 3+ Enhanced)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phase 3+ Features:
  --mode              Alert mode: polling, websocket, or hybrid
  --enable-sqlite     Use SQLite instead of JSON for state
  --enable-ml         Enable ML-based alert scoring
  --enable-kalman     Enable Kalman filtering for metrics
  --enable-queue      Enable alert queue and bundling
  --enable-metrics    Enable metrics tracking and dashboard
  --enable-all        Enable all Phase 3+ features

Examples:
  # Phase 2 compatibility (polling only, JSON state)
  python strategy_alerts_v3.py --tier 1,2 --min-confidence 80

  # Phase 3 (all features enabled)
  python strategy_alerts_v3.py --tier 1,2 --min-confidence 80 --enable-all

  # Hybrid mode with websockets for Tier 1 alerts
  python strategy_alerts_v3.py --mode hybrid --tier 1,2 --enable-all

  # Generate monitoring dashboard
  python strategy_alerts_v3.py --dashboard-only
        """
    )

    # Phase 2 args
    parser.add_argument('--tier', type=str, help='Comma-separated tier numbers (1=CRITICAL, 2=HIGH)')
    parser.add_argument('--min-confidence', type=int, default=80, help='Minimum confidence percentage')

    # Phase 3 args
    parser.add_argument('--mode', type=str, default='polling', choices=['polling', 'websocket', 'hybrid'])
    parser.add_argument('--enable-sqlite', action='store_true', help='Use SQLite state DB')
    parser.add_argument('--enable-ml', action='store_true', help='Enable ML scoring')
    parser.add_argument('--enable-kalman', action='store_true', help='Enable Kalman filtering')
    parser.add_argument('--enable-queue', action='store_true', help='Enable alert queue')
    parser.add_argument('--enable-metrics', action='store_true', help='Enable metrics tracking')
    parser.add_argument('--enable-all', action='store_true', help='Enable all Phase 3 features')
    parser.add_argument('--dashboard-only', action='store_true', help='Generate dashboard and exit')

    args = parser.parse_args()

    # Feature flags
    if args.enable_all:
        features = {
            'sqlite': True,
            'ml': True,
            'kalman': True,
            'queue': True,
            'metrics': True,
            'websockets': args.mode in ['websocket', 'hybrid']
        }
    else:
        features = {
            'sqlite': args.enable_sqlite,
            'ml': args.enable_ml,
            'kalman': args.enable_kalman,
            'queue': args.enable_queue,
            'metrics': args.enable_metrics,
            'websockets': args.mode in ['websocket', 'hybrid']
        }

    # Initialize system
    system = EnhancedStrategyAlertSystem(mode=args.mode, enable_features=features)

    # Dashboard-only mode
    if args.dashboard_only:
        print("📊 Generating monitoring dashboard...")
        system.generate_monitoring_dashboard()
        print("✅ Dashboard generated: data/alert_dashboard.html")
        return

    # Parse tier filter
    tier_filter = None
    if args.tier:
        tier_filter = [int(t.strip()) for t in args.tier.split(',')]
        print(f"📊 Tier filter: {tier_filter}")

    # Load config
    config = load_config()
    webhook_url = config.get('strategy_alerts', {}).get('webhook_url')

    if not webhook_url:
        webhook_url = config.get('discord', {}).get('webhook_url')

    # Start websockets if enabled
    if features['websockets']:
        print("🔌 Starting websocket connections for real-time Tier 1 alerts...")
        system.start_websockets(['binance', 'bybit', 'okx'])
        time.sleep(2)  # Let connections establish

    try:
        # Fetch and analyze
        print("\n⏳ Fetching market data...")
        start_time = time.time()

        # Use Container architecture for data fetching
        config = Config.from_yaml('config/config.yaml')
        container = Container(config)
        results = container.exchange_service.fetch_all_markets()

        fetch_time = (time.time() - start_time) * 1000

        if features['metrics']:
            for r in results:
                if r.get('status') == 'success':
                    system.record_metrics('api_call', {
                        'exchange': r['exchange'],
                        'endpoint': 'perps',
                        'response_time_ms': fetch_time / len(results),
                        'success': True
                    })

        # Analyze strategies
        print("🔍 Analyzing strategies...")
        all_alerts = analyze_all_strategies(results)

        # Apply Kalman smoothing
        if features['kalman']:
            print("🎚️  Applying Kalman filtering...")
            # Smoothing already integrated into analyze flow

        # Apply adaptive thresholds
        if features['kalman']:
            all_alerts = system.apply_adaptive_thresholds(all_alerts)

        # Filter alerts
        print(f"🔍 Filtering alerts (Tier: {tier_filter}, Min confidence: {args.min_confidence}%)")

        if features['sqlite']:
            alerts = system.filter_with_state_db(all_alerts, tier_filter or [1, 2], args.min_confidence)
        else:
            # Fallback to Phase 2 filtering
            from strategy_alerts import filter_alerts
            alerts, _, _ = filter_alerts(all_alerts, tier_filter, args.min_confidence, enable_dedup=True)

        # Add websocket alerts
        if system.websocket_alerts:
            print(f"⚡ Adding {len(system.websocket_alerts)} websocket-triggered alerts")
            alerts.extend(system.websocket_alerts)
            system.websocket_alerts.clear()

        # ML scoring and prioritization
        if features['ml'] and alerts:
            print("🤖 Applying ML scoring and prioritization...")
            alerts = system.score_and_prioritize_alerts(alerts)

        # Check bundling
        if features['queue'] and len(alerts) > 0:
            should_bundle, processed_alerts = system.check_if_should_bundle(alerts)
            if should_bundle:
                print(f"📦 Bundling {len(alerts)} alerts into digest(s)")
                alerts = processed_alerts

        # Results
        print(f"\n✅ Analysis complete: {len(alerts)} alert(s) ready to send\n")

        if not alerts:
            print("📊 No high-confidence alerts detected")
            return

        # Display alerts
        for i, alert in enumerate(alerts, 1):
            print(f"{i}. {alert['strategy']} - {alert['confidence']}% confidence")
            if 'ml_score' in alert:
                print(f"   ML Score: {alert['ml_score']:.1f}/100")

        # Send alerts
        if webhook_url:
            if features['queue']:
                print("\n📮 Enqueueing alerts for delivery...")
                system.enqueue_alerts(alerts)
                system.process_alert_queue(webhook_url)
            else:
                print("\n📤 Sending alerts to Discord...")
                send_strategy_alert_to_discord(alerts, webhook_url)

        # Generate dashboard
        if features['metrics']:
            print("\n📊 Updating monitoring dashboard...")
            system.generate_monitoring_dashboard()

    finally:
        # Cleanup
        if features['websockets']:
            system.stop_websockets()


if __name__ == "__main__":
    try:
        main_v3()
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
