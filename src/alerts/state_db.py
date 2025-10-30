"""
SQLite-based Alert State Management (Phase 3+)
Replaces JSON with database for better scalability and concurrent access
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path


class AlertStateDB:
    """Manages alert state in SQLite database"""

    def __init__(self, db_path: str = 'data/alert_state.db'):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Strategy alert history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence INTEGER NOT NULL,
                direction TEXT NOT NULL,
                tier INTEGER NOT NULL,
                cooldown_until TIMESTAMP,
                alert_count_today INTEGER DEFAULT 1
            )
        ''')

        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_strategy_time
            ON strategy_alerts(strategy_name, alert_time DESC)
        ''')

        # Daily statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_alerts INTEGER DEFAULT 0,
                tier_1_alerts INTEGER DEFAULT 0,
                tier_2_alerts INTEGER DEFAULT 0,
                tier_3_alerts INTEGER DEFAULT 0,
                suppressed_alerts INTEGER DEFAULT 0
            )
        ''')

        # Hourly counts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hourly_counts (
                hour_key TEXT PRIMARY KEY,
                alert_count INTEGER DEFAULT 0
            )
        ''')

        # Metrics tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def get_last_alert(self, strategy_name: str) -> Optional[Dict]:
        """Get the last alert for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT alert_time, confidence, direction, tier, cooldown_until, alert_count_today
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
            'alert_count_today': row[5]
        }

    def should_alert(self, strategy_name: str, confidence: int, direction: str,
                     tier: int, cooldown_hours: Dict[int, int],
                     min_confidence_delta: int = 20,
                     max_alerts_per_day: int = 3,
                     max_alerts_per_hour: int = 10) -> Tuple[bool, str]:
        """
        Determine if an alert should be sent based on deduplication rules
        Returns (should_alert, reason)
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

    def record_alert(self, strategy_name: str, confidence: int, direction: str,
                     tier: int, cooldown_hours: int):
        """Record an alert in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        cooldown_until = now + timedelta(hours=cooldown_hours)
        today = now.strftime('%Y-%m-%d')
        hour_key = now.strftime('%Y-%m-%d-%H')

        # Insert alert record
        cursor.execute('''
            INSERT INTO strategy_alerts
            (strategy_name, alert_time, confidence, direction, tier, cooldown_until)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (strategy_name, now.isoformat(), confidence, direction, tier, cooldown_until.isoformat()))

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

    def record_suppression(self, today: str):
        """Record a suppressed alert"""
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT alert_count FROM hourly_counts WHERE hour_key = ?', (hour_key,))
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else 0

    def get_daily_stats(self, days: int = 7) -> Dict:
        """Get daily statistics for the last N days"""
        conn = sqlite3.connect(self.db_path)
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

    def cleanup_old_data(self, days: int = 30):
        """Remove data older than N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor.execute('DELETE FROM strategy_alerts WHERE alert_time < ?', (cutoff,))
        cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff,))

        conn.commit()
        conn.close()

    def record_metric(self, metric_name: str, value: float, metadata: str = ""):
        """Record a performance metric"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO metrics (metric_name, metric_value, metadata)
            VALUES (?, ?, ?)
        ''', (metric_name, value, metadata))

        conn.commit()
        conn.close()
