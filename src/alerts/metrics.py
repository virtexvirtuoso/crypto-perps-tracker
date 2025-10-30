"""
Metrics Tracking and Monitoring Dashboard (Phase 3+)
Tracks alert effectiveness, system performance, and generates dashboards
"""
import json
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import defaultdict


class MetricsTracker:
    """
    Tracks and analyzes alert system performance metrics
    """

    def __init__(self, metrics_file: str = 'data/metrics.json'):
        self.metrics_file = Path(metrics_file)
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        self.metrics: Dict = {
            'alerts_sent': [],
            'alerts_suppressed': [],
            'api_calls': [],
            'response_times': [],
            'errors': [],
            'alert_effectiveness': []
        }

        self._load_metrics()

    def _load_metrics(self):
        """Load historical metrics"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    self.metrics = json.load(f)
            except Exception as e:
                print(f"Error loading metrics: {e}")

    def _save_metrics(self):
        """Save metrics to disk"""
        # Keep last 10,000 entries per metric to prevent file bloat
        for key in self.metrics:
            if isinstance(self.metrics[key], list) and len(self.metrics[key]) > 10000:
                self.metrics[key] = self.metrics[key][-10000:]

        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

    def record_alert_sent(self, strategy: str, tier: int, confidence: int):
        """Record an alert that was sent"""
        self.metrics['alerts_sent'].append({
            'timestamp': datetime.now().isoformat(),
            'strategy': strategy,
            'tier': tier,
            'confidence': confidence
        })
        self._save_metrics()

    def record_alert_suppressed(self, strategy: str, reason: str):
        """Record an alert that was suppressed"""
        self.metrics['alerts_suppressed'].append({
            'timestamp': datetime.now().isoformat(),
            'strategy': strategy,
            'reason': reason
        })
        self._save_metrics()

    def record_api_call(self, exchange: str, endpoint: str, response_time_ms: float,
                       success: bool):
        """Record API call metrics"""
        self.metrics['api_calls'].append({
            'timestamp': datetime.now().isoformat(),
            'exchange': exchange,
            'endpoint': endpoint,
            'response_time_ms': response_time_ms,
            'success': success
        })
        self._save_metrics()

    def record_error(self, error_type: str, message: str):
        """Record system error"""
        self.metrics['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': message
        })
        self._save_metrics()

    def record_alert_effectiveness(self, strategy: str, was_actionable: bool,
                                  confidence: int):
        """Record whether alert was actionable"""
        self.metrics['alert_effectiveness'].append({
            'timestamp': datetime.now().isoformat(),
            'strategy': strategy,
            'was_actionable': was_actionable,
            'confidence': confidence
        })
        self._save_metrics()

    def get_daily_stats(self, days: int = 7) -> Dict:
        """
        Get statistics for last N days

        Returns:
            Dict with metrics summary
        """
        cutoff = datetime.now() - timedelta(days=days)

        # Filter recent data
        recent_sent = [
            a for a in self.metrics['alerts_sent']
            if datetime.fromisoformat(a['timestamp']) > cutoff
        ]

        recent_suppressed = [
            a for a in self.metrics['alerts_suppressed']
            if datetime.fromisoformat(a['timestamp']) > cutoff
        ]

        recent_api = [
            a for a in self.metrics['api_calls']
            if datetime.fromisoformat(a['timestamp']) > cutoff
        ]

        recent_errors = [
            e for e in self.metrics['errors']
            if datetime.fromisoformat(e['timestamp']) > cutoff
        ]

        # Calculate stats
        total_sent = len(recent_sent)
        total_suppressed = len(recent_suppressed)
        suppression_rate = (
            total_suppressed / (total_sent + total_suppressed)
            if (total_sent + total_suppressed) > 0 else 0
        )

        # API success rate
        total_api = len(recent_api)
        successful_api = sum(1 for a in recent_api if a['success'])
        api_success_rate = successful_api / total_api if total_api > 0 else 0

        # Average response time
        response_times = [a['response_time_ms'] for a in recent_api if 'response_time_ms' in a]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # Alerts by tier
        tier_breakdown = defaultdict(int)
        for alert in recent_sent:
            tier_breakdown[f"tier_{alert.get('tier', 3)}"] += 1

        return {
            'period_days': days,
            'alerts_sent_total': total_sent,
            'alerts_per_day': total_sent / days,
            'alerts_suppressed': total_suppressed,
            'suppression_rate': suppression_rate,
            'alerts_by_tier': dict(tier_breakdown),
            'api_calls': total_api,
            'api_success_rate': api_success_rate,
            'avg_response_time_ms': avg_response_time,
            'errors': len(recent_errors),
            'thresholds': {
                'alerts_per_day': {'target': '5-10', 'status': self._check_threshold(total_sent / days, 5, 10)},
                'suppression_rate': {'target': '>80%', 'status': self._check_threshold(suppression_rate * 100, 80, 100)},
                'api_success_rate': {'target': '>90%', 'status': self._check_threshold(api_success_rate * 100, 90, 100)},
                'response_time': {'target': '<2000ms', 'status': 'GOOD' if avg_response_time < 2000 else 'WARNING'}
            }
        }

    def _check_threshold(self, value: float, min_good: float, max_good: float) -> str:
        """Check if value is within good range"""
        if min_good <= value <= max_good:
            return 'GOOD'
        elif value < min_good * 0.8 or value > max_good * 1.2:
            return 'CRITICAL'
        else:
            return 'WARNING'

    def calculate_alert_quality_score(self, days: int = 7) -> float:
        """
        Calculate overall alert quality score (0-100)

        Formula: Quality = (Actionable Rate * 60) + (1 - Fatigue Factor) * 40
        Where Fatigue Factor = max(0, (Alerts/Day - 10) / 10)
        """
        stats = self.get_daily_stats(days)

        # Get effectiveness data
        cutoff = datetime.now() - timedelta(days=days)
        recent_effectiveness = [
            e for e in self.metrics['alert_effectiveness']
            if datetime.fromisoformat(e['timestamp']) > cutoff
        ]

        if not recent_effectiveness:
            actionable_rate = 0.5  # Default assume 50% if no data
        else:
            actionable_count = sum(1 for e in recent_effectiveness if e['was_actionable'])
            actionable_rate = actionable_count / len(recent_effectiveness)

        # Calculate fatigue factor
        alerts_per_day = stats['alerts_per_day']
        fatigue_factor = max(0, min(1, (alerts_per_day - 10) / 10))

        # Calculate quality score
        quality_score = (actionable_rate * 60) + ((1 - fatigue_factor) * 40)

        return min(100, max(0, quality_score))

    def get_strategy_performance(self, days: int = 7) -> Dict:
        """Get performance breakdown by strategy"""
        cutoff = datetime.now() - timedelta(days=days)

        # Group alerts by strategy
        strategy_stats = defaultdict(lambda: {
            'sent': 0,
            'suppressed': 0,
            'actionable': 0,
            'total_effectiveness_checks': 0
        })

        for alert in self.metrics['alerts_sent']:
            if datetime.fromisoformat(alert['timestamp']) > cutoff:
                strategy = alert['strategy']
                strategy_stats[strategy]['sent'] += 1

        for alert in self.metrics['alerts_suppressed']:
            if datetime.fromisoformat(alert['timestamp']) > cutoff:
                strategy = alert['strategy']
                strategy_stats[strategy]['suppressed'] += 1

        for check in self.metrics['alert_effectiveness']:
            if datetime.fromisoformat(check['timestamp']) > cutoff:
                strategy = check['strategy']
                strategy_stats[strategy]['total_effectiveness_checks'] += 1
                if check['was_actionable']:
                    strategy_stats[strategy]['actionable'] += 1

        # Calculate rates
        result = {}
        for strategy, stats in strategy_stats.items():
            total = stats['sent'] + stats['suppressed']
            result[strategy] = {
                'alerts_sent': stats['sent'],
                'alerts_suppressed': stats['suppressed'],
                'suppression_rate': stats['suppressed'] / total if total > 0 else 0,
                'actionable_rate': (
                    stats['actionable'] / stats['total_effectiveness_checks']
                    if stats['total_effectiveness_checks'] > 0 else None
                )
            }

        return result


class DashboardGenerator:
    """
    Generates monitoring dashboards and visualizations
    """

    def __init__(self, metrics_tracker: MetricsTracker):
        self.tracker = metrics_tracker

    def generate_dashboard(self, output_path: str, days: int = 7):
        """
        Generate comprehensive dashboard as HTML

        Args:
            output_path: Where to save dashboard
            days: Days of data to include
        """
        stats = self.tracker.get_daily_stats(days)
        quality_score = self.tracker.calculate_alert_quality_score(days)
        strategy_perf = self.tracker.get_strategy_performance(days)

        # Generate charts
        charts = {
            'alerts_timeline': self._create_alerts_timeline_chart(days),
            'tier_distribution': self._create_tier_pie_chart(stats),
            'api_performance': self._create_api_performance_chart(days)
        }

        # Generate HTML
        html = self._generate_html(stats, quality_score, strategy_perf, charts)

        # Save
        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Dashboard saved to {output_path}")

    def _create_alerts_timeline_chart(self, days: int) -> str:
        """Create timeline chart of alerts"""
        cutoff = datetime.now() - timedelta(days=days)

        # Get alert timestamps
        timestamps = []
        for alert in self.tracker.metrics['alerts_sent']:
            ts = datetime.fromisoformat(alert['timestamp'])
            if ts > cutoff:
                timestamps.append(ts)

        if not timestamps:
            return "data/no_data.png"

        # Group by day
        daily_counts = defaultdict(int)
        for ts in timestamps:
            day = ts.date()
            daily_counts[day] += 1

        # Plot
        fig, ax = plt.subplots(figsize=(10, 4))
        days_list = sorted(daily_counts.keys())
        counts = [daily_counts[d] for d in days_list]

        ax.plot(days_list, counts, marker='o', linewidth=2, markersize=6)
        ax.axhline(y=10, color='r', linestyle='--', label='Target Max (10/day)')
        ax.axhline(y=5, color='g', linestyle='--', label='Target Min (5/day)')

        ax.set_xlabel('Date')
        ax.set_ylabel('Alerts Per Day')
        ax.set_title('Alert Volume Over Time')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        output_file = f'data/alerts_timeline_{datetime.now().strftime("%Y%m%d")}.png'
        plt.savefig(output_file, dpi=100, bbox_inches='tight')
        plt.close()

        return output_file

    def _create_tier_pie_chart(self, stats: Dict) -> str:
        """Create pie chart of alerts by tier"""
        tier_data = stats.get('alerts_by_tier', {})

        if not tier_data:
            return "data/no_data.png"

        fig, ax = plt.subplots(figsize=(6, 6))

        labels = [f"Tier {t.split('_')[1]}" for t in tier_data.keys()]
        sizes = list(tier_data.values())
        colors = ['#ff4444', '#ffaa00', '#4444ff']

        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.set_title('Alerts by Tier Distribution')

        output_file = f'data/tier_distribution_{datetime.now().strftime("%Y%m%d")}.png'
        plt.savefig(output_file, dpi=100, bbox_inches='tight')
        plt.close()

        return output_file

    def _create_api_performance_chart(self, days: int) -> str:
        """Create API performance chart"""
        cutoff = datetime.now() - timedelta(days=days)

        # Get API call data
        api_calls = [
            c for c in self.tracker.metrics['api_calls']
            if datetime.fromisoformat(c['timestamp']) > cutoff
        ]

        if not api_calls:
            return "data/no_data.png"

        # Group by exchange
        exchange_times = defaultdict(list)
        for call in api_calls:
            if 'response_time_ms' in call:
                exchange_times[call['exchange']].append(call['response_time_ms'])

        fig, ax = plt.subplots(figsize=(10, 4))

        exchanges = list(exchange_times.keys())
        avg_times = [sum(times) / len(times) for times in exchange_times.values()]

        ax.bar(exchanges, avg_times, color='skyblue')
        ax.axhline(y=2000, color='r', linestyle='--', label='Target (2000ms)')
        ax.set_ylabel('Avg Response Time (ms)')
        ax.set_title('API Response Time by Exchange')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        output_file = f'data/api_performance_{datetime.now().strftime("%Y%m%d")}.png'
        plt.savefig(output_file, dpi=100, bbox_inches='tight')
        plt.close()

        return output_file

    def _generate_html(self, stats: Dict, quality_score: float,
                      strategy_perf: Dict, charts: Dict) -> str:
        """Generate HTML dashboard"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Alert System Monitoring Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }}
        .header {{ background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .metric-card {{ background: #2a2a2a; padding: 20px; border-radius: 8px; }}
        .metric-value {{ font-size: 36px; font-weight: bold; margin: 10px 0; }}
        .metric-label {{ color: #888; font-size: 14px; }}
        .status-good {{ color: #00ff00; }}
        .status-warning {{ color: #ffaa00; }}
        .status-critical {{ color: #ff4444; }}
        .chart {{ background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Alert System Monitoring Dashboard</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Period: Last {stats['period_days']} days</p>
    </div>

    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-label">Alert Quality Score</div>
            <div class="metric-value status-{self._get_status_class(quality_score, 70, 85)}">{quality_score:.1f}/100</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Alerts Per Day</div>
            <div class="metric-value">{stats['alerts_per_day']:.1f}</div>
            <div class="metric-label">Target: 5-10</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Suppression Rate</div>
            <div class="metric-value">{stats['suppression_rate']*100:.1f}%</div>
            <div class="metric-label">Target: >80%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">API Success Rate</div>
            <div class="metric-value status-{self._get_status_class(stats['api_success_rate']*100, 90, 95)}">{stats['api_success_rate']*100:.1f}%</div>
            <div class="metric-label">Target: >90%</div>
        </div>
    </div>

    <div class="chart">
        <h2>Alert Volume Timeline</h2>
        <img src="{charts['alerts_timeline']}" alt="Alerts Timeline">
    </div>

    <div class="chart">
        <h2>Tier Distribution</h2>
        <img src="{charts['tier_distribution']}" alt="Tier Distribution">
    </div>

    <div class="chart">
        <h2>API Performance</h2>
        <img src="{charts['api_performance']}" alt="API Performance">
    </div>

    <div class="metric-card">
        <h2>Strategy Performance</h2>
        <table style="width:100%; border-collapse: collapse;">
            <tr style="background: #333;">
                <th style="padding: 10px; text-align: left;">Strategy</th>
                <th style="padding: 10px;">Sent</th>
                <th style="padding: 10px;">Suppressed</th>
                <th style="padding: 10px;">Suppression Rate</th>
            </tr>
            {"".join(self._format_strategy_row(name, perf) for name, perf in sorted(strategy_perf.items(), key=lambda x: x[1]['alerts_sent'], reverse=True))}
        </table>
    </div>
</body>
</html>
"""
        return html

    def _get_status_class(self, value: float, warning_threshold: float, good_threshold: float) -> str:
        """Get CSS class for status"""
        if value >= good_threshold:
            return 'good'
        elif value >= warning_threshold:
            return 'warning'
        else:
            return 'critical'

    def _format_strategy_row(self, name: str, perf: Dict) -> str:
        """Format strategy performance row"""
        return f"""
            <tr style="border-bottom: 1px solid #444;">
                <td style="padding: 10px;">{name}</td>
                <td style="padding: 10px; text-align: center;">{perf['alerts_sent']}</td>
                <td style="padding: 10px; text-align: center;">{perf['alerts_suppressed']}</td>
                <td style="padding: 10px; text-align: center;">{perf['suppression_rate']*100:.1f}%</td>
            </tr>
        """
