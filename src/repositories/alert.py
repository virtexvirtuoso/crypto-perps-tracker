"""Alert repository for SQLite persistence

Manages alert state, deduplication, statistics, and metrics tracking.
"""

import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class AlertRepository:
    """Repository for storing and retrieving alert data

    Handles all database operations for the alert system, including:
    - Alert history tracking
    - Deduplication logic
    - Daily and hourly statistics
    - Performance metrics
    - Cooldown management
    """

    SCHEMA = {
        'strategy_alerts': '''
            CREATE TABLE IF NOT EXISTS strategy_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence INTEGER NOT NULL,
                direction TEXT NOT NULL,
                tier INTEGER NOT NULL,
                cooldown_until TIMESTAMP,
                alert_count_today INTEGER DEFAULT 1,
                exchange TEXT,
                symbol TEXT,
                price REAL,
                metadata TEXT
            )
        ''',

        'daily_stats': '''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_alerts INTEGER DEFAULT 0,
                tier_1_alerts INTEGER DEFAULT 0,
                tier_2_alerts INTEGER DEFAULT 0,
                tier_3_alerts INTEGER DEFAULT 0,
                suppressed_alerts INTEGER DEFAULT 0
            )
        ''',

        'hourly_counts': '''
            CREATE TABLE IF NOT EXISTS hourly_counts (
                hour_key TEXT PRIMARY KEY,
                alert_count INTEGER DEFAULT 0
            )
        ''',

        'metrics': '''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata TEXT
            )
        ''',

        'alert_performance': '''
            CREATE TABLE IF NOT EXISTS alert_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                evaluation_time TIMESTAMP NOT NULL,
                outcome TEXT NOT NULL,
                profit_loss REAL,
                notes TEXT,
                FOREIGN KEY (alert_id) REFERENCES strategy_alerts(id)
            )
        ''',

        'indices': [
            'CREATE INDEX IF NOT EXISTS idx_strategy_time ON strategy_alerts(strategy_name, alert_time DESC)',
            'CREATE INDEX IF NOT EXISTS idx_alert_tier ON strategy_alerts(tier, alert_time DESC)',
            'CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name, timestamp DESC)',
            'CREATE INDEX IF NOT EXISTS idx_performance_alert ON alert_performance(alert_id)'
        ]
    }

    def __init__(self, db_path: str = 'data/alert_state.db'):
        """Initialize repository with database path

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def initialize_database(self) -> None:
        """Initialize database with schema

        Creates all tables and indices if they don't exist.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create tables
        for table_name, schema_sql in self.SCHEMA.items():
            if table_name != 'indices':
                cursor.execute(schema_sql)

        # Create indices
        for index_sql in self.SCHEMA['indices']:
            cursor.execute(index_sql)

        conn.commit()
        conn.close()

    def get_last_alert(self, strategy_name: str) -> Optional[Dict]:
        """Get the last alert for a strategy

        Args:
            strategy_name: Name of the strategy

        Returns:
            Dict with last alert data or None if no alerts exist
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT alert_time, confidence, direction, tier, cooldown_until,
                   alert_count_today, exchange, symbol, price
            FROM strategy_alerts
            WHERE strategy_name = ?
            ORDER BY alert_time DESC
            LIMIT 1
        ''', (strategy_name,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'last_alert_time': row[0],
            'last_confidence': row[1],
            'last_direction': row[2],
            'tier': row[3],
            'cooldown_until': row[4],
            'alert_count_today': row[5],
            'exchange': row[6],
            'symbol': row[7],
            'price': row[8]
        }

    def should_alert(
        self,
        strategy_name: str,
        confidence: int,
        direction: str,
        tier: int,
        cooldown_hours: Dict[int, int],
        min_confidence_delta: int = 20,
        max_alerts_per_day: int = 3,
        max_alerts_per_hour: int = 10
    ) -> Tuple[bool, str]:
        """Determine if an alert should be sent based on deduplication rules

        Args:
            strategy_name: Name of the strategy
            confidence: Alert confidence (0-100)
            direction: Alert direction (LONG/SHORT/NEUTRAL)
            tier: Alert tier (1-3, higher = more important)
            cooldown_hours: Dict mapping tier -> cooldown hours
            min_confidence_delta: Minimum confidence change to trigger new alert
            max_alerts_per_day: Maximum alerts per strategy per day
            max_alerts_per_hour: Maximum total alerts per hour (global limit)

        Returns:
            Tuple of (should_alert: bool, reason: str)
        """
        last_alert = self.get_last_alert(strategy_name)
        now = datetime.now(timezone.utc)

        # NEW setup - always alert
        if not last_alert:
            return True, "NEW setup detected"

        # Check cooldown
        if last_alert['cooldown_until']:
            cooldown_time = datetime.fromisoformat(last_alert['cooldown_until'].replace('Z', '+00:00'))
            if now < cooldown_time:
                remaining = (cooldown_time - now).total_seconds() / 3600
                return False, f"Cooldown active ({remaining:.1f}h remaining)"

        # Check confidence delta
        conf_delta = abs(confidence - last_alert['last_confidence'])
        if conf_delta < min_confidence_delta:
            return False, f"Confidence change too small (Δ{conf_delta}%, need {min_confidence_delta}%)"

        # Check daily limit
        today = now.strftime('%Y-%m-%d')
        daily_count = self._get_strategy_alerts_today(strategy_name, today)
        if daily_count >= max_alerts_per_day:
            return False, f"Daily limit reached ({daily_count}/{max_alerts_per_day})"

        # Check hourly global limit
        hour_key = now.strftime('%Y-%m-%d-%H')
        hourly_count = self._get_hourly_count(hour_key)
        if hourly_count >= max_alerts_per_hour:
            return False, f"Hourly global limit ({hourly_count}/{max_alerts_per_hour})"

        return True, "Alert criteria met"

    def record_alert(
        self,
        strategy_name: str,
        confidence: int,
        direction: str,
        tier: int,
        cooldown_hours: int,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        price: Optional[float] = None,
        metadata: Optional[str] = None
    ) -> int:
        """Record an alert in the database

        Args:
            strategy_name: Name of the strategy
            confidence: Alert confidence (0-100)
            direction: Alert direction (LONG/SHORT/NEUTRAL)
            tier: Alert tier (1-3)
            cooldown_hours: Cooldown period in hours
            exchange: Exchange name (optional)
            symbol: Trading symbol (optional)
            price: Price at alert time (optional)
            metadata: Additional metadata as JSON string (optional)

        Returns:
            Alert ID (integer)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        cooldown_until = now + timedelta(hours=cooldown_hours)
        today = now.strftime('%Y-%m-%d')
        hour_key = now.strftime('%Y-%m-%d-%H')

        # Insert alert record
        cursor.execute('''
            INSERT INTO strategy_alerts
            (strategy_name, alert_time, confidence, direction, tier, cooldown_until,
             exchange, symbol, price, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (strategy_name, now.isoformat(), confidence, direction, tier,
              cooldown_until.isoformat(), exchange, symbol, price, metadata))

        alert_id = cursor.lastrowid

        # Update daily stats
        cursor.execute('''
            INSERT INTO daily_stats (date, total_alerts, tier_1_alerts, tier_2_alerts, tier_3_alerts)
            VALUES (?, 1, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_alerts = total_alerts + 1,
                tier_1_alerts = tier_1_alerts + excluded.tier_1_alerts,
                tier_2_alerts = tier_2_alerts + excluded.tier_2_alerts,
                tier_3_alerts = tier_3_alerts + excluded.tier_3_alerts
        ''', (today, 1 if tier == 1 else 0, 1 if tier == 2 else 0, 1 if tier >= 3 else 0))

        # Update hourly count
        cursor.execute('''
            INSERT INTO hourly_counts (hour_key, alert_count)
            VALUES (?, 1)
            ON CONFLICT(hour_key) DO UPDATE SET
                alert_count = alert_count + 1
        ''', (hour_key,))

        conn.commit()
        conn.close()

        return alert_id

    def record_suppression(self, today: Optional[str] = None) -> None:
        """Record a suppressed alert

        Args:
            today: Date string (YYYY-MM-DD), defaults to today
        """
        if today is None:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO daily_stats (date, suppressed_alerts)
            VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET
                suppressed_alerts = suppressed_alerts + 1
        ''', (today,))

        conn.commit()
        conn.close()

    def _get_strategy_alerts_today(self, strategy_name: str, today: str) -> int:
        """Count alerts for a strategy today"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM strategy_alerts
            WHERE strategy_name = ?
            AND DATE(alert_time) = ?
        ''', (strategy_name, today))

        count = cursor.fetchone()[0]
        conn.close()
        return count

    def _get_hourly_count(self, hour_key: str) -> int:
        """Get alert count for current hour"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT alert_count FROM hourly_counts WHERE hour_key = ?', (hour_key,))
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else 0

    def get_daily_stats(self, days: int = 7) -> Dict[str, Dict]:
        """Get daily statistics for the last N days

        Args:
            days: Number of days to retrieve

        Returns:
            Dict mapping date -> stats dict
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT date, total_alerts, tier_1_alerts, tier_2_alerts, tier_3_alerts, suppressed_alerts
            FROM daily_stats
            ORDER BY date DESC
            LIMIT ?
        ''', (days,))

        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = {
                'total_alerts': row[1],
                'tier_1': row[2],
                'tier_2': row[3],
                'tier_3': row[4],
                'suppressed': row[5]
            }

        conn.close()
        return stats

    def get_strategy_history(self, strategy_name: str, limit: int = 10) -> List[Dict]:
        """Get alert history for a specific strategy

        Args:
            strategy_name: Name of the strategy
            limit: Maximum number of alerts to retrieve

        Returns:
            List of alert dicts
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM strategy_alerts
            WHERE strategy_name = ?
            ORDER BY alert_time DESC
            LIMIT ?
        ''', (strategy_name, limit))

        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return alerts

    def record_metric(self, metric_name: str, value: float, metadata: str = "") -> None:
        """Record a performance metric

        Args:
            metric_name: Name of the metric
            value: Metric value
            metadata: Additional metadata (optional)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO metrics (metric_name, metric_value, metadata)
            VALUES (?, ?, ?)
        ''', (metric_name, value, metadata))

        conn.commit()
        conn.close()

    def get_metrics(self, metric_name: str, hours: int = 24) -> List[Tuple[datetime, float]]:
        """Get metric values for the last N hours

        Args:
            metric_name: Name of the metric
            hours: Number of hours to retrieve

        Returns:
            List of (timestamp, value) tuples
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        cursor.execute('''
            SELECT timestamp, metric_value
            FROM metrics
            WHERE metric_name = ? AND timestamp > ?
            ORDER BY timestamp ASC
        ''', (metric_name, cutoff))

        metrics = [(datetime.fromisoformat(row[0]), row[1]) for row in cursor.fetchall()]
        conn.close()

        return metrics

    def record_alert_performance(
        self,
        alert_id: int,
        outcome: str,
        profit_loss: Optional[float] = None,
        notes: Optional[str] = None
    ) -> None:
        """Record the performance/outcome of an alert

        Args:
            alert_id: ID of the alert
            outcome: Outcome (WIN/LOSS/NEUTRAL/PENDING)
            profit_loss: Profit/loss in USD (optional)
            notes: Additional notes (optional)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO alert_performance
            (alert_id, evaluation_time, outcome, profit_loss, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (alert_id, datetime.now(timezone.utc).isoformat(), outcome, profit_loss, notes))

        conn.commit()
        conn.close()

    def get_performance_stats(self, days: int = 30) -> Dict:
        """Get performance statistics for alerts

        Args:
            days: Number of days to analyze

        Returns:
            Dict with performance metrics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get outcome distribution
        cursor.execute('''
            SELECT outcome, COUNT(*), AVG(profit_loss)
            FROM alert_performance
            WHERE evaluation_time > ?
            GROUP BY outcome
        ''', (cutoff,))

        outcomes = {}
        total_pnl = 0
        total_alerts = 0

        for row in cursor.fetchall():
            outcome, count, avg_pnl = row
            outcomes[outcome] = {
                'count': count,
                'avg_pnl': avg_pnl if avg_pnl else 0
            }
            total_alerts += count
            if avg_pnl:
                total_pnl += avg_pnl * count

        win_rate = (outcomes.get('WIN', {}).get('count', 0) / total_alerts * 100) if total_alerts > 0 else 0

        conn.close()

        return {
            'total_evaluated': total_alerts,
            'outcomes': outcomes,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'days_analyzed': days
        }

    def cleanup_old_data(self, days: int = 30) -> Tuple[int, int]:
        """Remove data older than N days

        Args:
            days: Number of days to keep

        Returns:
            Tuple of (alerts_deleted, metrics_deleted)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor.execute('DELETE FROM strategy_alerts WHERE alert_time < ?', (cutoff,))
        alerts_deleted = cursor.rowcount

        cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff,))
        metrics_deleted = cursor.rowcount

        # Vacuum to reclaim space
        cursor.execute('VACUUM')

        conn.commit()
        conn.close()

        return (alerts_deleted, metrics_deleted)

    def get_statistics(self) -> Dict:
        """Get comprehensive database statistics

        Returns:
            Dictionary containing database statistics
        """
        if not os.path.exists(self.db_path):
            return {'exists': False}

        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {'exists': True}

        # Alert counts
        cursor.execute('SELECT COUNT(*) FROM strategy_alerts')
        stats['total_alerts'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT strategy_name) FROM strategy_alerts')
        stats['unique_strategies'] = cursor.fetchone()[0]

        # Tier distribution
        cursor.execute('''
            SELECT tier, COUNT(*)
            FROM strategy_alerts
            GROUP BY tier
        ''')
        stats['tier_distribution'] = dict(cursor.fetchall())

        # Database size
        stats['db_size_bytes'] = os.path.getsize(self.db_path)

        conn.close()

        return stats
