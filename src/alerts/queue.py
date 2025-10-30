"""
Alert Queue and Bundling System (Phase 3+)
Decouples alert generation from delivery for better reliability
Bundles similar alerts into digests to reduce fatigue
"""
import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import threading


class AlertQueue:
    """
    Queue system for alert delivery
    Supports bundling, rate limiting, and retry logic
    """

    def __init__(self, queue_file: str = 'data/alert_queue.json',
                 bundle_window_seconds: int = 300):
        """
        Args:
            queue_file: Path to persistent queue storage
            bundle_window_seconds: Time window for bundling similar alerts (default 5 min)
        """
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.bundle_window = timedelta(seconds=bundle_window_seconds)

        self.pending_alerts: List[Dict] = []
        self.sent_alerts: List[Dict] = []
        self.failed_alerts: List[Dict] = []

        self._load_queue()
        self._lock = threading.Lock()

    def _load_queue(self):
        """Load queue from disk"""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                    self.pending_alerts = data.get('pending', [])
                    self.failed_alerts = data.get('failed', [])
            except Exception as e:
                print(f"Error loading queue: {e}")

    def _save_queue(self):
        """Save queue to disk"""
        with self._lock:
            data = {
                'pending': self.pending_alerts,
                'failed': self.failed_alerts[-100:],  # Keep last 100 failed
                'last_updated': datetime.now().isoformat()
            }
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)

    def enqueue(self, alert: Dict):
        """
        Add alert to queue

        Args:
            alert: Alert data dictionary
        """
        with self._lock:
            alert['queued_at'] = datetime.now().isoformat()
            alert['retry_count'] = 0
            self.pending_alerts.append(alert)
        self._save_queue()

    def dequeue(self, max_alerts: int = 10) -> List[Dict]:
        """
        Get next batch of alerts to send

        Args:
            max_alerts: Maximum alerts to retrieve

        Returns:
            List of alerts ready to send
        """
        with self._lock:
            # Get alerts ready to send
            ready = []
            remaining = []

            for alert in self.pending_alerts:
                queued_time = datetime.fromisoformat(alert['queued_at'])
                retry_delay = 60 * (2 ** alert.get('retry_count', 0))  # Exponential backoff

                if datetime.now() >= queued_time + timedelta(seconds=retry_delay):
                    ready.append(alert)
                    if len(ready) >= max_alerts:
                        remaining.extend(self.pending_alerts[self.pending_alerts.index(alert) + 1:])
                        break
                else:
                    remaining.append(alert)

            self.pending_alerts = remaining
            return ready

    def mark_sent(self, alert: Dict):
        """Mark alert as successfully sent"""
        with self._lock:
            alert['sent_at'] = datetime.now().isoformat()
            self.sent_alerts.append(alert)
        self._save_queue()

    def mark_failed(self, alert: Dict, error: str):
        """Mark alert as failed"""
        with self._lock:
            alert['retry_count'] = alert.get('retry_count', 0) + 1
            alert['last_error'] = error
            alert['last_error_time'] = datetime.now().isoformat()

            # Max 3 retries
            if alert['retry_count'] >= 3:
                alert['permanently_failed'] = True
                self.failed_alerts.append(alert)
            else:
                # Requeue for retry
                self.pending_alerts.append(alert)

        self._save_queue()

    def get_pending_count(self) -> int:
        """Get number of pending alerts"""
        return len(self.pending_alerts)

    def get_failed_count(self) -> int:
        """Get number of failed alerts"""
        return len([a for a in self.failed_alerts if a.get('permanently_failed')])

    def clear_old_sent(self, days: int = 7):
        """Remove old sent alerts from memory"""
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            self.sent_alerts = [
                a for a in self.sent_alerts
                if datetime.fromisoformat(a['sent_at']) > cutoff
            ]


class AlertBundler:
    """
    Bundles similar alerts into digests
    Reduces alert fatigue by grouping related signals
    """

    def __init__(self, bundle_threshold: int = 3):
        """
        Args:
            bundle_threshold: Minimum alerts to trigger bundling
        """
        self.bundle_threshold = bundle_threshold

    def should_bundle(self, alerts: List[Dict]) -> bool:
        """
        Determine if alerts should be bundled

        Args:
            alerts: List of pending alerts

        Returns:
            True if bundling recommended
        """
        if len(alerts) < self.bundle_threshold:
            return False

        # Bundle if multiple alerts for same strategy
        strategy_counts = defaultdict(int)
        for alert in alerts:
            strategy_counts[alert.get('strategy', '')] += 1

        # If any strategy has 3+ alerts, bundle them
        return any(count >= self.bundle_threshold for count in strategy_counts.values())

    def bundle_alerts(self, alerts: List[Dict]) -> List[Dict]:
        """
        Group alerts into bundles

        Args:
            alerts: List of alerts to bundle

        Returns:
            List of bundled alert groups
        """
        # Group by strategy and tier
        groups = defaultdict(list)
        for alert in alerts:
            key = (alert.get('strategy', 'unknown'), alert.get('tier', 3))
            groups[key].append(alert)

        # Create bundle objects
        bundles = []
        for (strategy, tier), group_alerts in groups.items():
            if len(group_alerts) >= self.bundle_threshold:
                # Create digest bundle
                bundle = {
                    'type': 'digest',
                    'strategy': strategy,
                    'tier': tier,
                    'alert_count': len(group_alerts),
                    'time_range': {
                        'start': min(a['queued_at'] for a in group_alerts),
                        'end': max(a['queued_at'] for a in group_alerts)
                    },
                    'alerts': group_alerts,
                    'summary': self._create_summary(group_alerts)
                }
                bundles.append(bundle)
            else:
                # Keep as individual alerts
                bundles.extend(group_alerts)

        return bundles

    def _create_summary(self, alerts: List[Dict]) -> str:
        """Create summary text for bundled alerts"""
        if not alerts:
            return ""

        strategy = alerts[0].get('strategy', 'Unknown')
        count = len(alerts)

        # Get direction distribution
        bullish = sum(1 for a in alerts if a.get('direction') == 'BULLISH')
        bearish = sum(1 for a in alerts if a.get('direction') == 'BEARISH')

        # Get confidence range
        confidences = [a.get('confidence', 0) for a in alerts]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        direction_text = "BULLISH" if bullish > bearish else "BEARISH" if bearish > bullish else "MIXED"

        summary = (
            f"📊 **{strategy} Digest** ({count} alerts)\n"
            f"Direction: {direction_text} ({bullish}↗ {bearish}↘)\n"
            f"Avg Confidence: {avg_conf:.0f}%\n"
            f"Time span: {self._format_timespan(alerts)}"
        )

        return summary

    def _format_timespan(self, alerts: List[Dict]) -> str:
        """Format time span of alerts"""
        try:
            times = [datetime.fromisoformat(a['queued_at']) for a in alerts]
            span = max(times) - min(times)

            if span.total_seconds() < 3600:
                return f"{int(span.total_seconds() / 60)} minutes"
            else:
                return f"{span.total_seconds() / 3600:.1f} hours"
        except Exception:
            return "unknown"

    def format_bundle_message(self, bundle: Dict) -> str:
        """
        Format a bundled alert for Discord

        Args:
            bundle: Bundle dictionary

        Returns:
            Formatted message string
        """
        if bundle.get('type') != 'digest':
            # Not a bundle, format as regular alert
            return self._format_single_alert(bundle)

        # Format digest
        summary = bundle.get('summary', '')
        alerts = bundle.get('alerts', [])

        message = f"{summary}\n\n"
        message += "**Individual Alerts:**\n"

        for i, alert in enumerate(alerts[:5], 1):  # Show first 5
            conf = alert.get('confidence', 0)
            direction = alert.get('direction', '?')
            message += f"{i}. {direction} {conf}% - {alert.get('reason', '')}\n"

        if len(alerts) > 5:
            message += f"...and {len(alerts) - 5} more\n"

        return message

    def _format_single_alert(self, alert: Dict) -> str:
        """Format single alert"""
        strategy = alert.get('strategy', 'Unknown')
        confidence = alert.get('confidence', 0)
        direction = alert.get('direction', '?')
        tier = alert.get('tier', 3)

        tier_emoji = "🚨" if tier == 1 else "⚠️" if tier == 2 else "ℹ️"

        return (
            f"{tier_emoji} **{strategy}**\n"
            f"Direction: {direction}\n"
            f"Confidence: {confidence}%\n"
            f"Reason: {alert.get('reason', 'N/A')}"
        )
