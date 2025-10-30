"""Market data repository for SQLite persistence"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class MarketRepository:
    """Repository for storing and retrieving market snapshot data

    Handles all database operations for market data, including:
    - Market snapshots (aggregate data)
    - Exchange snapshots (per-exchange data)
    - Sentiment factors (multi-factor scores)
    - Liquidation data (if available)
    """

    SCHEMA = {
        'market_snapshots': '''
            CREATE TABLE IF NOT EXISTS market_snapshots (
                timestamp INTEGER PRIMARY KEY,
                composite_score REAL NOT NULL,
                funding_rate REAL,
                total_volume REAL NOT NULL,
                total_oi REAL,
                price_change REAL,
                long_pct REAL,
                sentiment TEXT,
                strength TEXT,
                oi_vol_ratio REAL,
                funding_divergence REAL,
                exchanges_count INTEGER,
                cex_volume REAL,
                dex_volume REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',

        'exchange_snapshots': '''
            CREATE TABLE IF NOT EXISTS exchange_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                exchange TEXT NOT NULL,
                exchange_type TEXT,
                volume REAL,
                open_interest REAL,
                funding_rate REAL,
                price_change REAL,
                markets INTEGER,
                num_trades INTEGER,
                UNIQUE(timestamp, exchange),
                FOREIGN KEY (timestamp) REFERENCES market_snapshots(timestamp)
            )
        ''',

        'sentiment_factors': '''
            CREATE TABLE IF NOT EXISTS sentiment_factors (
                timestamp INTEGER PRIMARY KEY,
                funding_score REAL,
                price_score REAL,
                ls_bias_score REAL,
                conviction_score REAL,
                divergence_score REAL,
                oi_price_score REAL,
                FOREIGN KEY (timestamp) REFERENCES market_snapshots(timestamp)
            )
        ''',

        'liquidation_snapshots': '''
            CREATE TABLE IF NOT EXISTS liquidation_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                exchange TEXT NOT NULL,
                total_liquidations REAL,
                long_liquidations REAL,
                short_liquidations REAL,
                liquidation_count INTEGER,
                cascade_risk_score REAL,
                UNIQUE(timestamp, exchange),
                FOREIGN KEY (timestamp) REFERENCES market_snapshots(timestamp)
            )
        ''',

        'indices': [
            'CREATE INDEX IF NOT EXISTS idx_market_timestamp ON market_snapshots(timestamp DESC)',
            'CREATE INDEX IF NOT EXISTS idx_exchange_timestamp ON exchange_snapshots(timestamp DESC, exchange)',
            'CREATE INDEX IF NOT EXISTS idx_exchange_type ON exchange_snapshots(exchange_type)',
            'CREATE INDEX IF NOT EXISTS idx_sentiment_timestamp ON sentiment_factors(timestamp DESC)',
            'CREATE INDEX IF NOT EXISTS idx_liquidation_timestamp ON liquidation_snapshots(timestamp DESC, exchange)'
        ]
    }

    def __init__(self, db_path: str = 'data/market_history.db'):
        """Initialize repository with database path

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure data directory exists
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

    def save_market_snapshot(
        self,
        timestamp: int,
        composite_score: float,
        funding_rate: Optional[float],
        total_volume: float,
        total_oi: Optional[float],
        price_change: Optional[float],
        long_pct: Optional[float],
        sentiment: str,
        strength: str,
        oi_vol_ratio: Optional[float],
        funding_divergence: float,
        exchanges_count: int,
        cex_volume: float,
        dex_volume: float
    ) -> None:
        """Save market snapshot to database

        Args:
            timestamp: Unix timestamp of snapshot
            composite_score: Composite sentiment score (-1 to 1)
            funding_rate: Weighted average funding rate
            total_volume: Total 24h volume across all exchanges
            total_oi: Total open interest across all exchanges
            price_change: Average 24h price change
            long_pct: Percentage of longs
            sentiment: Sentiment classification (BULLISH/BEARISH/NEUTRAL)
            strength: Sentiment strength (STRONG/MODERATE/WEAK)
            oi_vol_ratio: Open interest to volume ratio
            funding_divergence: Standard deviation of funding rates
            exchanges_count: Number of exchanges included
            cex_volume: Total CEX volume
            dex_volume: Total DEX volume
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO market_snapshots (
                timestamp, composite_score, funding_rate, total_volume, total_oi,
                price_change, long_pct, sentiment, strength, oi_vol_ratio,
                funding_divergence, exchanges_count, cex_volume, dex_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, composite_score, funding_rate, total_volume, total_oi,
            price_change, long_pct, sentiment, strength, oi_vol_ratio,
            funding_divergence, exchanges_count, cex_volume, dex_volume
        ))

        conn.commit()
        conn.close()

    def save_exchange_snapshot(
        self,
        timestamp: int,
        exchange: str,
        exchange_type: str,
        volume: float,
        open_interest: Optional[float],
        funding_rate: Optional[float],
        price_change: Optional[float],
        markets: int,
        num_trades: Optional[int]
    ) -> None:
        """Save exchange snapshot to database

        Args:
            timestamp: Unix timestamp of snapshot
            exchange: Exchange name
            exchange_type: CEX or DEX
            volume: 24h volume
            open_interest: Open interest
            funding_rate: Funding rate
            price_change: 24h price change
            markets: Number of markets
            num_trades: Number of trades (if available)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO exchange_snapshots (
                timestamp, exchange, exchange_type, volume, open_interest,
                funding_rate, price_change, markets, num_trades
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, exchange, exchange_type, volume, open_interest,
            funding_rate, price_change, markets, num_trades
        ))

        conn.commit()
        conn.close()

    def save_sentiment_factors(
        self,
        timestamp: int,
        funding_score: float,
        price_score: float,
        ls_bias_score: float,
        conviction_score: float,
        divergence_score: float,
        oi_price_score: float
    ) -> None:
        """Save sentiment factor scores to database

        Args:
            timestamp: Unix timestamp of snapshot
            funding_score: Funding rate factor score
            price_score: Price momentum factor score
            ls_bias_score: Long/short bias factor score
            conviction_score: OI/Vol conviction factor score
            divergence_score: Exchange agreement factor score
            oi_price_score: OI-price correlation factor score
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO sentiment_factors (
                timestamp, funding_score, price_score, ls_bias_score,
                conviction_score, divergence_score, oi_price_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, funding_score, price_score, ls_bias_score,
            conviction_score, divergence_score, oi_price_score
        ))

        conn.commit()
        conn.close()

    def get_statistics(self) -> Dict:
        """Get database statistics

        Returns:
            Dictionary containing database statistics
        """
        if not os.path.exists(self.db_path):
            return {'exists': False}

        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {'exists': True}

        # Market snapshots
        cursor.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM market_snapshots')
        count, min_ts, max_ts = cursor.fetchone()

        stats['market_snapshots'] = {
            'count': count,
            'first_timestamp': min_ts,
            'last_timestamp': max_ts
        }

        if count > 0:
            # Average metrics
            cursor.execute('''
                SELECT
                    AVG(composite_score),
                    AVG(total_volume),
                    AVG(total_oi),
                    AVG(oi_vol_ratio)
                FROM market_snapshots
            ''')
            avg_score, avg_vol, avg_oi, avg_ratio = cursor.fetchone()

            stats['averages'] = {
                'composite_score': avg_score,
                'volume': avg_vol,
                'open_interest': avg_oi,
                'oi_vol_ratio': avg_ratio
            }

            # Sentiment distribution
            cursor.execute('''
                SELECT sentiment, COUNT(*)
                FROM market_snapshots
                GROUP BY sentiment
            ''')
            stats['sentiment_distribution'] = dict(cursor.fetchall())

        # Exchange snapshots
        cursor.execute('SELECT COUNT(DISTINCT exchange) FROM exchange_snapshots')
        stats['unique_exchanges'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM exchange_snapshots')
        stats['exchange_snapshot_count'] = cursor.fetchone()[0]

        # Database size
        stats['db_size_bytes'] = os.path.getsize(self.db_path)

        conn.close()

        return stats

    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Remove data older than specified days

        Args:
            days_to_keep: Number of days to retain

        Returns:
            Number of market snapshots deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_timestamp = int((datetime.now(timezone.utc).timestamp() - (days_to_keep * 24 * 3600)))

        # Count records to delete
        cursor.execute('SELECT COUNT(*) FROM market_snapshots WHERE timestamp < ?', (cutoff_timestamp,))
        to_delete = cursor.fetchone()[0]

        if to_delete == 0:
            conn.close()
            return 0

        # Delete old records
        cursor.execute('DELETE FROM market_snapshots WHERE timestamp < ?', (cutoff_timestamp,))
        cursor.execute('DELETE FROM exchange_snapshots WHERE timestamp < ?', (cutoff_timestamp,))
        cursor.execute('DELETE FROM sentiment_factors WHERE timestamp < ?', (cutoff_timestamp,))
        cursor.execute('DELETE FROM liquidation_snapshots WHERE timestamp < ?', (cutoff_timestamp,))

        # Vacuum to reclaim space
        cursor.execute('VACUUM')

        conn.commit()
        conn.close()

        return to_delete

    def get_recent_snapshots(self, limit: int = 100) -> List[Dict]:
        """Get most recent market snapshots

        Args:
            limit: Number of snapshots to retrieve

        Returns:
            List of snapshot dictionaries
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM market_snapshots
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        snapshots = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return snapshots

    def get_snapshot_by_timestamp(self, timestamp: int) -> Optional[Dict]:
        """Get specific snapshot by timestamp

        Args:
            timestamp: Unix timestamp

        Returns:
            Snapshot dictionary or None if not found
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM market_snapshots
            WHERE timestamp = ?
        ''', (timestamp,))

        row = cursor.fetchone()
        snapshot = dict(row) if row else None

        conn.close()

        return snapshot
