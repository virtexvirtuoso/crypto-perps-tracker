"""Health monitoring and alerting utilities"""

import requests
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Dict
from pathlib import Path


@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    message: str
    timestamp: datetime
    details: Optional[Dict] = None


class HealthMonitor:
    """Monitor application health"""

    def __init__(self):
        self.checks = []

    def check_database(self, db_path: str) -> HealthCheck:
        """
        Check database accessibility and basic stats

        Args:
            db_path: Path to database file

        Returns:
            HealthCheck result
        """
        try:
            db_file = Path(db_path)

            if not db_file.exists():
                return HealthCheck(
                    name='database',
                    status='unhealthy',
                    message=f'Database not found: {db_path}',
                    timestamp=datetime.now(timezone.utc)
                )

            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # Check if we have market_snapshots table
            if 'market_snapshots' in tables:
                result = conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()
                snapshot_count = result[0]

                # Get latest snapshot time
                latest = conn.execute(
                    "SELECT MAX(timestamp) FROM market_snapshots"
                ).fetchone()[0]

                conn.close()

                if snapshot_count == 0:
                    return HealthCheck(
                        name='database',
                        status='degraded',
                        message='Database empty - no snapshots',
                        timestamp=datetime.now(timezone.utc),
                        details={'snapshot_count': 0}
                    )

                # Check if latest snapshot is recent (within 1 hour)
                if latest:
                    latest_dt = datetime.fromtimestamp(latest, tz=timezone.utc)
                    age_minutes = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 60

                    if age_minutes > 60:
                        status = 'degraded'
                        message = f'Latest snapshot is {age_minutes:.0f} minutes old'
                    else:
                        status = 'healthy'
                        message = f'Database OK ({snapshot_count:,} snapshots)'
                else:
                    status = 'degraded'
                    message = f'Database has snapshots but no timestamps'

                return HealthCheck(
                    name='database',
                    status=status,
                    message=message,
                    timestamp=datetime.now(timezone.utc),
                    details={
                        'snapshot_count': snapshot_count,
                        'latest_snapshot_age_minutes': age_minutes if latest else None
                    }
                )
            else:
                conn.close()
                return HealthCheck(
                    name='database',
                    status='degraded',
                    message='Database exists but missing expected tables',
                    timestamp=datetime.now(timezone.utc),
                    details={'tables': tables}
                )

        except Exception as e:
            return HealthCheck(
                name='database',
                status='unhealthy',
                message=f'Database error: {str(e)}',
                timestamp=datetime.now(timezone.utc)
            )

    def check_exchanges(self, exchange_service) -> HealthCheck:
        """
        Check exchange connectivity

        Args:
            exchange_service: ExchangeService instance

        Returns:
            HealthCheck result
        """
        try:
            # Fetch without cache to test live connectivity
            markets = exchange_service.fetch_all_markets(use_cache=False)

            total_exchanges = len(exchange_service.clients)
            successful = len(markets)

            if successful == 0:
                status = 'unhealthy'
                message = 'No exchanges responding'
            elif successful < total_exchanges * 0.5:
                status = 'degraded'
                message = f'Only {successful}/{total_exchanges} exchanges responding'
            else:
                status = 'healthy'
                message = f'{successful}/{total_exchanges} exchanges responding'

            # Calculate total volume
            total_volume = sum(m.total_volume_usd for m in markets)

            return HealthCheck(
                name='exchanges',
                status=status,
                message=message,
                timestamp=datetime.now(timezone.utc),
                details={
                    'total_exchanges': total_exchanges,
                    'successful_exchanges': successful,
                    'total_volume_usd': total_volume,
                    'exchanges': [m.exchange.value for m in markets]
                }
            )
        except Exception as e:
            return HealthCheck(
                name='exchanges',
                status='unhealthy',
                message=f'Exchange check failed: {str(e)}',
                timestamp=datetime.now(timezone.utc)
            )

    def check_disk_space(self, path: str = ".", min_gb: float = 1.0) -> HealthCheck:
        """
        Check available disk space

        Args:
            path: Path to check
            min_gb: Minimum required GB

        Returns:
            HealthCheck result
        """
        try:
            import shutil

            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024 ** 3)
            total_gb = total / (1024 ** 3)
            used_pct = (used / total) * 100

            if free_gb < min_gb:
                status = 'unhealthy'
                message = f'Low disk space: {free_gb:.2f}GB free'
            elif free_gb < min_gb * 2:
                status = 'degraded'
                message = f'Disk space warning: {free_gb:.2f}GB free'
            else:
                status = 'healthy'
                message = f'Disk space OK: {free_gb:.2f}GB free ({used_pct:.1f}% used)'

            return HealthCheck(
                name='disk_space',
                status=status,
                message=message,
                timestamp=datetime.now(timezone.utc),
                details={
                    'free_gb': free_gb,
                    'total_gb': total_gb,
                    'used_pct': used_pct
                }
            )
        except Exception as e:
            return HealthCheck(
                name='disk_space',
                status='unhealthy',
                message=f'Disk space check failed: {str(e)}',
                timestamp=datetime.now(timezone.utc)
            )

    def check_all(self, container, db_path: str = 'data/market_history.db') -> List[HealthCheck]:
        """
        Run all health checks

        Args:
            container: Application container with services
            db_path: Path to database file

        Returns:
            List of HealthCheck results
        """
        checks = [
            self.check_database(db_path),
            self.check_exchanges(container.exchange_service),
            self.check_disk_space(),
        ]
        self.checks = checks
        return checks

    def send_alert_if_unhealthy(self, checks: List[HealthCheck], webhook_url: str):
        """
        Send Discord alert if any checks are unhealthy

        Args:
            checks: List of health check results
            webhook_url: Discord webhook URL
        """
        unhealthy = [c for c in checks if c.status in ('unhealthy', 'degraded')]

        if not unhealthy:
            return

        # Build alert message
        if any(c.status == 'unhealthy' for c in unhealthy):
            emoji = "🚨"
            level = "CRITICAL"
        else:
            emoji = "⚠️"
            level = "WARNING"

        message = f"{emoji} **Health Check {level}**\n\n"

        for check in unhealthy:
            status_emoji = '❌' if check.status == 'unhealthy' else '⚠️'
            message += f"{status_emoji} **{check.name}**: {check.message}\n"

        message += f"\n*Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*"

        try:
            response = requests.post(
                webhook_url,
                json={'content': message},
                timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send Discord alert: {e}")

    def get_status_summary(self, checks: List[HealthCheck]) -> str:
        """
        Get a summary status across all checks

        Args:
            checks: List of health check results

        Returns:
            Overall status: 'healthy', 'degraded', or 'unhealthy'
        """
        if any(c.status == 'unhealthy' for c in checks):
            return 'unhealthy'
        elif any(c.status == 'degraded' for c in checks):
            return 'degraded'
        else:
            return 'healthy'
