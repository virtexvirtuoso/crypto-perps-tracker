"""
Sector Rotation Database Storage - Multi-Exchange Version

SQLite storage for multi-exchange sector rotation snapshots, signals,
and composition history. Enhanced schema includes:
- CEX vs DEX flow metrics
- Cross-exchange funding spreads
- Per-exchange breakdown (JSON)

Migrated from Virtuoso_ccxt with multi-exchange support.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager

from .storage import (
    SectorSnapshot,
    SectorSignal,
    SectorCorrelation,
    ExchangeBreakdown,
    SECTOR_CONFIG,
)

logger = logging.getLogger(__name__)


class SectorRotationStorage:
    """
    Handles persistence of multi-exchange sector rotation data to SQLite.

    Enhanced from single-exchange version with:
    - CEX/DEX flow fields in snapshots
    - Cross-exchange funding spread
    - Per-exchange breakdown stored as JSON
    - Multi-exchange signal context
    """

    def __init__(self, db_path: str = None):
        """Initialize sector rotation storage.

        Args:
            db_path: Path to SQLite database file. If None, uses default.
        """
        if db_path is None:
            # Default to data/sector_rotation.db in project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )))
            db_path = os.path.join(project_root, 'data', 'sector_rotation.db')

        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self.db_path = db_path
        self.logger = logger
        self._init_database()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=30000")
                conn.execute("PRAGMA synchronous=NORMAL")
                cursor = conn.cursor()

                # Table 1: sector_snapshots - Multi-exchange sector metrics
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sector_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sector_code TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,

                        -- Volume metrics
                        total_volume_24h REAL DEFAULT 0,
                        volume_share_pct REAL DEFAULT 0,
                        volume_share_zscore REAL DEFAULT 0,
                        volume_change_4h REAL DEFAULT 0,

                        -- Price metrics
                        avg_price_change_4h REAL DEFAULT 0,
                        avg_price_change_24h REAL DEFAULT 0,
                        momentum_24h REAL DEFAULT 0,
                        momentum_persistence REAL DEFAULT 0,

                        -- Open Interest metrics (aggregated)
                        total_oi REAL DEFAULT 0,
                        oi_change_4h REAL DEFAULT 0,
                        oi_change_zscore REAL DEFAULT 0,
                        oi_price_signal TEXT DEFAULT 'neutral',

                        -- Funding metrics (volume-weighted avg)
                        avg_funding_rate REAL DEFAULT 0,
                        funding_zscore REAL DEFAULT 0,

                        -- NEW: Cross-exchange funding spread
                        funding_spread REAL DEFAULT 0,
                        funding_spread_zscore REAL DEFAULT 0,

                        -- Correlation metrics
                        btc_correlation REAL DEFAULT 0,
                        btc_correlation_zscore REAL DEFAULT 0,
                        sector_beta REAL DEFAULT 0,

                        -- Breadth metrics
                        symbols_up INTEGER DEFAULT 0,
                        symbols_down INTEGER DEFAULT 0,
                        breadth_ratio REAL DEFAULT 0,
                        weighted_breadth REAL DEFAULT 0,

                        -- Flow metrics
                        net_flow_ratio REAL DEFAULT 0,

                        -- NEW: CEX vs DEX flow metrics
                        cex_volume_share REAL DEFAULT 0,
                        dex_volume_share REAL DEFAULT 0,
                        cex_oi_share REAL DEFAULT 0,
                        dex_oi_share REAL DEFAULT 0,
                        cex_dex_flow_score REAL DEFAULT 0,
                        cex_dex_flow_zscore REAL DEFAULT 0,

                        -- Composite metrics
                        rotation_score REAL DEFAULT 0,
                        signal_strength TEXT DEFAULT 'weak',

                        -- Data quality
                        symbol_count INTEGER DEFAULT 0,
                        exchange_count INTEGER DEFAULT 0,
                        data_quality_score REAL DEFAULT 0,
                        confidence_level REAL DEFAULT 0,
                        sample_size_flag TEXT DEFAULT 'normal',

                        -- Relative strength
                        sector_rs REAL DEFAULT 0,
                        sector_rs_zscore REAL DEFAULT 0,

                        -- NEW: Per-exchange breakdown (JSON)
                        exchange_breakdown TEXT DEFAULT '[]',

                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                        UNIQUE(sector_code, timestamp)
                    )
                ''')

                # Table 2: sector_signals - Multi-exchange rotation signals
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sector_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sector_code TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
                        signal_strength TEXT DEFAULT 'weak',
                        rotation_score REAL DEFAULT 0,

                        first_detected DATETIME NOT NULL,
                        last_confirmed DATETIME NOT NULL,
                        confirmation_count INTEGER DEFAULT 1,
                        is_confirmed BOOLEAN DEFAULT 0,

                        from_sector TEXT,
                        to_sector TEXT,
                        volume_zscore REAL DEFAULT 0,
                        btc_correlation REAL DEFAULT 0,
                        oi_signal TEXT,
                        breadth REAL DEFAULT 0,

                        -- NEW: Multi-exchange context
                        funding_spread REAL DEFAULT 0,
                        cex_dex_flow REAL DEFAULT 0,
                        exchange_consensus REAL DEFAULT 0,

                        confidence_level REAL DEFAULT 0,

                        is_active BOOLEAN DEFAULT 1,
                        expired_at DATETIME,

                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Table 3: sector_composition_history - Survivorship bias protection
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sector_composition_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sector_code TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        effective_from DATETIME NOT NULL,
                        effective_to DATETIME,
                        status TEXT DEFAULT 'active',
                        migrated_to TEXT,
                        reason TEXT,

                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                        UNIQUE(sector_code, symbol, effective_from)
                    )
                ''')

                # Table 4: sector_correlations - Cross-sector correlations
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sector_correlations (
                        snapshot_id INTEGER NOT NULL,
                        sector_a TEXT NOT NULL,
                        sector_b TEXT NOT NULL,
                        correlation REAL DEFAULT 0,
                        is_significant BOOLEAN DEFAULT 0,
                        timestamp DATETIME NOT NULL,

                        PRIMARY KEY (snapshot_id, sector_a, sector_b),
                        FOREIGN KEY (snapshot_id) REFERENCES sector_snapshots(id)
                    )
                ''')

                # Create indexes for performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_sector_snapshots_timestamp
                    ON sector_snapshots(timestamp DESC)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_sector_snapshots_sector_time
                    ON sector_snapshots(sector_code, timestamp DESC)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_sector_signals_active
                    ON sector_signals(is_active, sector_code)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_sector_composition_sector
                    ON sector_composition_history(sector_code, status)
                ''')

                conn.commit()
                self.logger.info(f"Sector rotation database initialized at {self.db_path}")

        except Exception as e:
            self.logger.error(f"Error initializing sector rotation database: {e}")
            raise

    # ==================== SNAPSHOT OPERATIONS ====================

    def save_snapshot(self, snapshot: SectorSnapshot) -> int:
        """Save a sector snapshot to the database.

        Args:
            snapshot: SectorSnapshot dataclass instance

        Returns:
            The ID of the inserted row
        """
        try:
            # Serialize exchange breakdown to JSON
            exchange_breakdown_json = json.dumps([
                eb.to_dict() if hasattr(eb, 'to_dict') else eb
                for eb in (snapshot.exchange_breakdown or [])
            ])

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO sector_snapshots (
                        sector_code, timestamp,
                        total_volume_24h, volume_share_pct, volume_share_zscore, volume_change_4h,
                        avg_price_change_4h, avg_price_change_24h, momentum_24h, momentum_persistence,
                        total_oi, oi_change_4h, oi_change_zscore, oi_price_signal,
                        avg_funding_rate, funding_zscore, funding_spread, funding_spread_zscore,
                        btc_correlation, btc_correlation_zscore, sector_beta,
                        symbols_up, symbols_down, breadth_ratio, weighted_breadth,
                        net_flow_ratio,
                        cex_volume_share, dex_volume_share, cex_oi_share, dex_oi_share,
                        cex_dex_flow_score, cex_dex_flow_zscore,
                        rotation_score, signal_strength,
                        symbol_count, exchange_count, data_quality_score, confidence_level, sample_size_flag,
                        sector_rs, sector_rs_zscore,
                        exchange_breakdown
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    snapshot.sector_code, snapshot.timestamp,
                    snapshot.total_volume_24h, snapshot.volume_share_pct, snapshot.volume_share_zscore, snapshot.volume_change_4h,
                    snapshot.avg_price_change_4h, snapshot.avg_price_change_24h, snapshot.momentum_24h, snapshot.momentum_persistence,
                    snapshot.total_oi, snapshot.oi_change_4h, snapshot.oi_change_zscore, snapshot.oi_price_signal,
                    snapshot.avg_funding_rate, snapshot.funding_zscore, snapshot.funding_spread, snapshot.funding_spread_zscore,
                    snapshot.btc_correlation, snapshot.btc_correlation_zscore, snapshot.sector_beta,
                    snapshot.symbols_up, snapshot.symbols_down, snapshot.breadth_ratio, snapshot.weighted_breadth,
                    snapshot.net_flow_ratio,
                    snapshot.cex_volume_share, snapshot.dex_volume_share, snapshot.cex_oi_share, snapshot.dex_oi_share,
                    snapshot.cex_dex_flow_score, snapshot.cex_dex_flow_zscore,
                    snapshot.rotation_score, snapshot.signal_strength,
                    snapshot.symbol_count, snapshot.exchange_count, snapshot.data_quality_score, snapshot.confidence_level, snapshot.sample_size_flag,
                    snapshot.sector_rs, snapshot.sector_rs_zscore,
                    exchange_breakdown_json,
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error saving sector snapshot: {e}")
            raise

    def save_snapshots_batch(self, snapshots: List[SectorSnapshot]) -> List[int]:
        """Save multiple snapshots in a single transaction.

        Args:
            snapshots: List of SectorSnapshot instances

        Returns:
            List of inserted row IDs
        """
        ids = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for snapshot in snapshots:
                    exchange_breakdown_json = json.dumps([
                        eb.to_dict() if hasattr(eb, 'to_dict') else eb
                        for eb in (snapshot.exchange_breakdown or [])
                    ])

                    cursor.execute('''
                        INSERT OR REPLACE INTO sector_snapshots (
                            sector_code, timestamp,
                            total_volume_24h, volume_share_pct, volume_share_zscore, volume_change_4h,
                            avg_price_change_4h, avg_price_change_24h, momentum_24h, momentum_persistence,
                            total_oi, oi_change_4h, oi_change_zscore, oi_price_signal,
                            avg_funding_rate, funding_zscore, funding_spread, funding_spread_zscore,
                            btc_correlation, btc_correlation_zscore, sector_beta,
                            symbols_up, symbols_down, breadth_ratio, weighted_breadth,
                            net_flow_ratio,
                            cex_volume_share, dex_volume_share, cex_oi_share, dex_oi_share,
                            cex_dex_flow_score, cex_dex_flow_zscore,
                            rotation_score, signal_strength,
                            symbol_count, exchange_count, data_quality_score, confidence_level, sample_size_flag,
                            sector_rs, sector_rs_zscore,
                            exchange_breakdown
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        snapshot.sector_code, snapshot.timestamp,
                        snapshot.total_volume_24h, snapshot.volume_share_pct, snapshot.volume_share_zscore, snapshot.volume_change_4h,
                        snapshot.avg_price_change_4h, snapshot.avg_price_change_24h, snapshot.momentum_24h, snapshot.momentum_persistence,
                        snapshot.total_oi, snapshot.oi_change_4h, snapshot.oi_change_zscore, snapshot.oi_price_signal,
                        snapshot.avg_funding_rate, snapshot.funding_zscore, snapshot.funding_spread, snapshot.funding_spread_zscore,
                        snapshot.btc_correlation, snapshot.btc_correlation_zscore, snapshot.sector_beta,
                        snapshot.symbols_up, snapshot.symbols_down, snapshot.breadth_ratio, snapshot.weighted_breadth,
                        snapshot.net_flow_ratio,
                        snapshot.cex_volume_share, snapshot.dex_volume_share, snapshot.cex_oi_share, snapshot.dex_oi_share,
                        snapshot.cex_dex_flow_score, snapshot.cex_dex_flow_zscore,
                        snapshot.rotation_score, snapshot.signal_strength,
                        snapshot.symbol_count, snapshot.exchange_count, snapshot.data_quality_score, snapshot.confidence_level, snapshot.sample_size_flag,
                        snapshot.sector_rs, snapshot.sector_rs_zscore,
                        exchange_breakdown_json,
                    ))
                    ids.append(cursor.lastrowid)
                conn.commit()
            return ids

        except Exception as e:
            self.logger.error(f"Error saving sector snapshots batch: {e}")
            raise

    def get_latest_snapshots(self) -> Dict[str, SectorSnapshot]:
        """Get the most recent snapshot for each sector.

        Returns:
            Dictionary mapping sector_code to SectorSnapshot
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT s1.* FROM sector_snapshots s1
                    INNER JOIN (
                        SELECT sector_code, MAX(timestamp) as max_ts
                        FROM sector_snapshots
                        GROUP BY sector_code
                    ) s2 ON s1.sector_code = s2.sector_code AND s1.timestamp = s2.max_ts
                    ORDER BY s1.rotation_score DESC
                ''')

                results = {}
                for row in cursor.fetchall():
                    snapshot = self._row_to_snapshot(row)
                    results[snapshot.sector_code] = snapshot
                return results

        except Exception as e:
            self.logger.error(f"Error getting latest snapshots: {e}")
            return {}

    def get_sector_history(
        self,
        sector_code: str,
        days: int = 7,
        limit: int = 100
    ) -> List[SectorSnapshot]:
        """Get historical snapshots for a specific sector.

        Args:
            sector_code: The sector to query
            days: Number of days of history
            limit: Maximum number of snapshots to return

        Returns:
            List of SectorSnapshot instances, newest first
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM sector_snapshots
                    WHERE sector_code = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (sector_code, cutoff, limit))

                return [self._row_to_snapshot(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting sector history: {e}")
            return []

    def get_snapshots_for_zscore(
        self,
        sector_code: str,
        periods: int = 180
    ) -> List[SectorSnapshot]:
        """Get snapshots for z-score calculation (30-day baseline).

        Args:
            sector_code: The sector to query
            periods: Number of 4h periods (180 = 30 days)

        Returns:
            List of SectorSnapshot instances, oldest first
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM sector_snapshots
                    WHERE sector_code = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (sector_code, periods))

                snapshots = [self._row_to_snapshot(row) for row in cursor.fetchall()]
                return list(reversed(snapshots))  # Return oldest first

        except Exception as e:
            self.logger.error(f"Error getting snapshots for z-score: {e}")
            return []

    def get_snapshots_since(
        self,
        from_time: datetime,
        sector_code: str = None
    ) -> List[SectorSnapshot]:
        """Get all snapshots since a specific time.

        Args:
            from_time: Start time (inclusive)
            sector_code: Optional sector filter

        Returns:
            List of SectorSnapshot instances, newest first
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if sector_code:
                    cursor.execute('''
                        SELECT * FROM sector_snapshots
                        WHERE sector_code = ? AND timestamp >= ?
                        ORDER BY timestamp DESC
                    ''', (sector_code, from_time))
                else:
                    cursor.execute('''
                        SELECT * FROM sector_snapshots
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                    ''', (from_time,))

                return [self._row_to_snapshot(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting snapshots since {from_time}: {e}")
            return []

    def _row_to_snapshot(self, row: sqlite3.Row) -> SectorSnapshot:
        """Convert a database row to a SectorSnapshot instance."""
        # Parse exchange breakdown JSON
        exchange_breakdown = []
        if row['exchange_breakdown']:
            try:
                breakdown_data = json.loads(row['exchange_breakdown'])
                exchange_breakdown = [
                    ExchangeBreakdown(**eb) if isinstance(eb, dict) else eb
                    for eb in breakdown_data
                ]
            except (json.JSONDecodeError, TypeError):
                pass

        return SectorSnapshot(
            id=row['id'],
            sector_code=row['sector_code'],
            timestamp=datetime.fromisoformat(row['timestamp']) if isinstance(row['timestamp'], str) else row['timestamp'],
            total_volume_24h=row['total_volume_24h'] or 0,
            volume_share_pct=row['volume_share_pct'] or 0,
            volume_share_zscore=row['volume_share_zscore'] or 0,
            volume_change_4h=row['volume_change_4h'] or 0,
            avg_price_change_4h=row['avg_price_change_4h'] or 0,
            avg_price_change_24h=row['avg_price_change_24h'] or 0,
            momentum_24h=row['momentum_24h'] or 0,
            momentum_persistence=row['momentum_persistence'] or 0,
            total_oi=row['total_oi'] or 0,
            oi_change_4h=row['oi_change_4h'] or 0,
            oi_change_zscore=row['oi_change_zscore'] or 0,
            oi_price_signal=row['oi_price_signal'] or 'neutral',
            avg_funding_rate=row['avg_funding_rate'] or 0,
            funding_zscore=row['funding_zscore'] or 0,
            funding_spread=row['funding_spread'] or 0,
            funding_spread_zscore=row['funding_spread_zscore'] or 0,
            btc_correlation=row['btc_correlation'] or 0,
            btc_correlation_zscore=row['btc_correlation_zscore'] or 0,
            sector_beta=row['sector_beta'] or 0,
            symbols_up=row['symbols_up'] or 0,
            symbols_down=row['symbols_down'] or 0,
            breadth_ratio=row['breadth_ratio'] or 0,
            weighted_breadth=row['weighted_breadth'] or 0,
            net_flow_ratio=row['net_flow_ratio'] or 0,
            cex_volume_share=row['cex_volume_share'] or 0,
            dex_volume_share=row['dex_volume_share'] or 0,
            cex_oi_share=row['cex_oi_share'] or 0,
            dex_oi_share=row['dex_oi_share'] or 0,
            cex_dex_flow_score=row['cex_dex_flow_score'] or 0,
            cex_dex_flow_zscore=row['cex_dex_flow_zscore'] or 0,
            rotation_score=row['rotation_score'] or 0,
            signal_strength=row['signal_strength'] or 'weak',
            symbol_count=row['symbol_count'] or 0,
            exchange_count=row['exchange_count'] or 0,
            data_quality_score=row['data_quality_score'] or 0,
            confidence_level=row['confidence_level'] or 0,
            sample_size_flag=row['sample_size_flag'] or 'normal',
            sector_rs=row['sector_rs'] or 0,
            sector_rs_zscore=row['sector_rs_zscore'] or 0,
            exchange_breakdown=exchange_breakdown,
        )

    # ==================== SIGNAL OPERATIONS ====================

    def save_signal(self, signal: SectorSignal) -> int:
        """Save a rotation signal to the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sector_signals (
                        sector_code, signal_type, signal_strength, rotation_score,
                        first_detected, last_confirmed, confirmation_count, is_confirmed,
                        from_sector, to_sector, volume_zscore, btc_correlation,
                        oi_signal, breadth,
                        funding_spread, cex_dex_flow, exchange_consensus,
                        confidence_level, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    signal.sector_code, signal.signal_type, signal.signal_strength, signal.rotation_score,
                    signal.first_detected, signal.last_confirmed, signal.confirmation_count, signal.is_confirmed,
                    signal.from_sector, signal.to_sector, signal.volume_zscore, signal.btc_correlation,
                    signal.oi_signal, signal.breadth,
                    signal.funding_spread, signal.cex_dex_flow, signal.exchange_consensus,
                    signal.confidence_level, signal.is_active,
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error saving sector signal: {e}")
            raise

    def update_signal_confirmation(self, signal_id: int, new_count: int) -> bool:
        """Update a signal's confirmation count."""
        try:
            is_confirmed = new_count >= 2
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE sector_signals
                    SET confirmation_count = ?,
                        is_confirmed = ?,
                        last_confirmed = ?
                    WHERE id = ?
                ''', (new_count, is_confirmed, datetime.utcnow(), signal_id))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            self.logger.error(f"Error updating signal confirmation: {e}")
            return False

    def expire_signal(self, signal_id: int) -> bool:
        """Mark a signal as expired/inactive."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE sector_signals
                    SET is_active = 0, expired_at = ?
                    WHERE id = ?
                ''', (datetime.utcnow(), signal_id))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            self.logger.error(f"Error expiring signal: {e}")
            return False

    def get_active_signals(self) -> List[SectorSignal]:
        """Get all currently active signals."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM sector_signals
                    WHERE is_active = 1
                    ORDER BY rotation_score DESC
                ''')

                return [self._row_to_signal(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting active signals: {e}")
            return []

    def get_confirmed_signals(self) -> List[SectorSignal]:
        """Get only confirmed signals (2+ periods)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM sector_signals
                    WHERE is_active = 1 AND is_confirmed = 1
                    ORDER BY rotation_score DESC
                ''')

                return [self._row_to_signal(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting confirmed signals: {e}")
            return []

    def _row_to_signal(self, row: sqlite3.Row) -> SectorSignal:
        """Convert a database row to a SectorSignal instance."""
        return SectorSignal(
            id=row['id'],
            sector_code=row['sector_code'],
            signal_type=row['signal_type'],
            signal_strength=row['signal_strength'],
            rotation_score=row['rotation_score'] or 0,
            first_detected=datetime.fromisoformat(row['first_detected']) if isinstance(row['first_detected'], str) else row['first_detected'],
            last_confirmed=datetime.fromisoformat(row['last_confirmed']) if isinstance(row['last_confirmed'], str) else row['last_confirmed'],
            confirmation_count=row['confirmation_count'] or 1,
            is_confirmed=bool(row['is_confirmed']),
            from_sector=row['from_sector'],
            to_sector=row['to_sector'],
            volume_zscore=row['volume_zscore'] or 0,
            btc_correlation=row['btc_correlation'] or 0,
            oi_signal=row['oi_signal'],
            breadth=row['breadth'] or 0,
            funding_spread=row['funding_spread'] or 0,
            cex_dex_flow=row['cex_dex_flow'] or 0,
            exchange_consensus=row['exchange_consensus'] or 0,
            confidence_level=row['confidence_level'] or 0,
            is_active=bool(row['is_active']),
            expired_at=datetime.fromisoformat(row['expired_at']) if row['expired_at'] else None,
        )

    # ==================== CORRELATION OPERATIONS ====================

    def save_correlations(
        self,
        snapshot_id: int,
        correlations: List[SectorCorrelation]
    ) -> int:
        """Save cross-sector correlations for a snapshot."""
        count = 0
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for corr in correlations:
                    cursor.execute('''
                        INSERT OR REPLACE INTO sector_correlations
                        (snapshot_id, sector_a, sector_b, correlation, is_significant, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        snapshot_id, corr.sector_a, corr.sector_b,
                        corr.correlation, corr.is_significant, corr.timestamp,
                    ))
                    count += 1
                conn.commit()
                return count

        except Exception as e:
            self.logger.error(f"Error saving correlations: {e}")
            raise

    def get_latest_correlation_matrix(self) -> Dict[Tuple[str, str], float]:
        """Get the most recent correlation matrix.

        Returns:
            Dictionary mapping (sector_a, sector_b) tuples to correlation values
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT MAX(snapshot_id) as max_id FROM sector_correlations
                ''')
                result = cursor.fetchone()
                if not result or result['max_id'] is None:
                    return {}

                max_id = result['max_id']
                cursor.execute('''
                    SELECT sector_a, sector_b, correlation
                    FROM sector_correlations
                    WHERE snapshot_id = ?
                ''', (max_id,))

                return {
                    (row['sector_a'], row['sector_b']): row['correlation']
                    for row in cursor.fetchall()
                }

        except Exception as e:
            self.logger.error(f"Error getting correlation matrix: {e}")
            return {}

    # ==================== COMPOSITION HISTORY ====================

    def initialize_composition_history(self) -> int:
        """Initialize composition history with current sector config.

        Call this once to set up the baseline composition.

        Returns:
            Number of records created
        """
        count = 0
        now = datetime.utcnow()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for sector_code, symbols in SECTOR_CONFIG.items():
                    for symbol in symbols:
                        cursor.execute('''
                            SELECT id FROM sector_composition_history
                            WHERE sector_code = ? AND symbol = ? AND status = 'active'
                        ''', (sector_code, symbol))

                        if cursor.fetchone() is None:
                            cursor.execute('''
                                INSERT INTO sector_composition_history
                                (sector_code, symbol, effective_from, status)
                                VALUES (?, ?, ?, 'active')
                            ''', (sector_code, symbol, now))
                            count += 1

                conn.commit()
                self.logger.info(f"Initialized {count} composition history records")
                return count

        except Exception as e:
            self.logger.error(f"Error initializing composition history: {e}")
            raise

    def get_sector_composition_at(
        self,
        sector_code: str,
        at_time: datetime
    ) -> List[str]:
        """Get sector composition as of a specific time.

        Args:
            sector_code: The sector to query
            at_time: The point in time to check

        Returns:
            List of symbols that were in the sector at that time
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT symbol FROM sector_composition_history
                    WHERE sector_code = ?
                      AND effective_from <= ?
                      AND (effective_to IS NULL OR effective_to > ?)
                ''', (sector_code, at_time, at_time))

                return [row['symbol'] for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting sector composition at time: {e}")
            return []

    # ==================== CLEANUP & STATS ====================

    def cleanup_old_data(self, days: int = 90) -> Dict[str, int]:
        """Remove data older than specified days.

        Args:
            days: Age threshold for deletion

        Returns:
            Dictionary with count of deleted records per table
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = {}

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Clean snapshots
                cursor.execute('''
                    DELETE FROM sector_snapshots WHERE timestamp < ?
                ''', (cutoff,))
                deleted['snapshots'] = cursor.rowcount

                # Clean expired signals
                cursor.execute('''
                    DELETE FROM sector_signals
                    WHERE is_active = 0 AND expired_at < ?
                ''', (cutoff,))
                deleted['signals'] = cursor.rowcount

                # Clean old correlations
                cursor.execute('''
                    DELETE FROM sector_correlations
                    WHERE snapshot_id NOT IN (SELECT id FROM sector_snapshots)
                ''')
                deleted['correlations'] = cursor.rowcount

                conn.commit()
                self.logger.info(f"Cleaned up old sector rotation data: {deleted}")
                return deleted

        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                stats = {}

                # Count snapshots
                cursor.execute('SELECT COUNT(*) as count FROM sector_snapshots')
                stats['snapshot_count'] = cursor.fetchone()['count']

                # Count signals
                cursor.execute('SELECT COUNT(*) as count FROM sector_signals WHERE is_active = 1')
                stats['active_signals'] = cursor.fetchone()['count']

                cursor.execute('SELECT COUNT(*) as count FROM sector_signals WHERE is_confirmed = 1 AND is_active = 1')
                stats['confirmed_signals'] = cursor.fetchone()['count']

                # Get date range
                cursor.execute('SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM sector_snapshots')
                row = cursor.fetchone()
                stats['oldest_snapshot'] = row['min_ts']
                stats['newest_snapshot'] = row['max_ts']

                # Sectors with data
                cursor.execute('SELECT DISTINCT sector_code FROM sector_snapshots')
                stats['sectors_with_data'] = [row['sector_code'] for row in cursor.fetchall()]

                # Exchange coverage (from latest snapshots)
                cursor.execute('''
                    SELECT AVG(exchange_count) as avg_exchanges
                    FROM sector_snapshots
                    WHERE timestamp > datetime('now', '-1 day')
                ''')
                row = cursor.fetchone()
                stats['avg_exchange_count'] = row['avg_exchanges'] if row['avg_exchanges'] else 0

                return stats

        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {}
