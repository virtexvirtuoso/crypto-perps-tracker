"""IV Skew Validation Logger

Logs IV skew data for validation and correlation analysis.
Purpose: Collect data to validate IV skew's predictive edge before
integrating into Market Mood sentiment component.

Schema captures:
- Raw IV values (put, call) for formula experimentation
- Calculated skew and direction
- Current price for future correlation analysis
- Market context (funding rate, LSR) for multi-factor analysis

Database: data/iv_skew_validation.db
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class IVSkewLogger:
    """Logger for Options IV skew validation data"""

    # Database path relative to project root
    DEFAULT_DB_PATH = "data/iv_skew_validation.db"

    def __init__(self, db_path: Optional[str] = None):
        """Initialize IV skew logger

        Args:
            db_path: Path to SQLite database. Defaults to data/iv_skew_validation.db
        """
        if db_path is None:
            # Find project root (go up from src/signals/)
            project_root = Path(__file__).parent.parent.parent
            self.db_path = project_root / self.DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path)

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()
        logger.info(f"IV Skew Logger initialized with database: {self.db_path}")

    def _init_db(self):
        """Create database tables if they don't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main IV skew observations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS iv_skew_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    symbol TEXT NOT NULL,

                    -- Raw IV values (for formula experimentation)
                    iv_put REAL NOT NULL,
                    iv_call REAL NOT NULL,

                    -- Calculated metrics
                    iv_skew REAL NOT NULL,
                    iv_skew_pct REAL NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL,

                    -- Price data (for correlation analysis)
                    current_price REAL NOT NULL,

                    -- Market context (optional, for multi-factor analysis)
                    funding_rate REAL,
                    long_short_ratio REAL,

                    -- Metadata
                    source TEXT DEFAULT 'bybit',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for efficient time-based queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_iv_skew_symbol_time
                ON iv_skew_observations(symbol, timestamp DESC)
            """)

            # Price outcomes table (for validation)
            # Fill this retrospectively to correlate IV skew with price moves
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observation_id INTEGER NOT NULL,

                    -- Future prices at different horizons
                    price_1h REAL,
                    price_4h REAL,
                    price_24h REAL,

                    -- Calculated returns
                    return_1h_pct REAL,
                    return_4h_pct REAL,
                    return_24h_pct REAL,

                    -- Direction match (did prediction match?)
                    direction_correct_1h INTEGER,
                    direction_correct_4h INTEGER,
                    direction_correct_24h INTEGER,

                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (observation_id) REFERENCES iv_skew_observations(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_outcomes_obs
                ON price_outcomes(observation_id)
            """)

            conn.commit()
            logger.debug("IV Skew validation database initialized")

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def log_iv_skew(
        self,
        symbol: str,
        iv_put: float,
        iv_call: float,
        current_price: float,
        funding_rate: Optional[float] = None,
        long_short_ratio: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        source: str = "bybit"
    ) -> int:
        """Log an IV skew observation

        Args:
            symbol: Asset symbol (BTC, ETH)
            iv_put: Put option implied volatility
            iv_call: Call option implied volatility
            current_price: Current spot/perp price
            funding_rate: Current funding rate (optional context)
            long_short_ratio: Current L/S ratio (optional context)
            timestamp: Observation timestamp (defaults to now)
            source: Data source identifier

        Returns:
            ID of inserted observation
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Calculate IV skew metrics
        iv_skew = iv_put - iv_call
        iv_skew_pct = ((iv_put - iv_call) / iv_call * 100) if iv_call > 0 else 0

        # Determine direction based on skew
        # Positive skew (put IV > call IV) = fear = bearish sentiment
        # Negative skew (call IV > put IV) = greed = bullish sentiment
        if iv_skew_pct > 5:  # >5% put premium
            direction = "bearish"
            confidence = min(100, 50 + abs(iv_skew_pct) * 2)
        elif iv_skew_pct < -5:  # >5% call premium
            direction = "bullish"
            confidence = min(100, 50 + abs(iv_skew_pct) * 2)
        else:
            direction = "neutral"
            confidence = 50

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO iv_skew_observations (
                    timestamp, symbol, iv_put, iv_call, iv_skew, iv_skew_pct,
                    direction, confidence, current_price, funding_rate,
                    long_short_ratio, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp.isoformat(),
                symbol,
                iv_put,
                iv_call,
                iv_skew,
                iv_skew_pct,
                direction,
                confidence,
                current_price,
                funding_rate,
                long_short_ratio,
                source
            ))
            conn.commit()
            observation_id = cursor.lastrowid

        logger.info(
            f"Logged IV skew for {symbol}: skew={iv_skew_pct:.2f}% ({direction}), "
            f"price=${current_price:,.2f}"
        )
        return observation_id

    def get_recent_observations(
        self,
        symbol: str,
        limit: int = 100,
        hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent IV skew observations

        Args:
            symbol: Asset symbol
            limit: Maximum number of records
            hours: Only return records from last N hours

        Returns:
            List of observation dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if hours:
                cursor.execute("""
                    SELECT * FROM iv_skew_observations
                    WHERE symbol = ?
                    AND timestamp > datetime('now', ? || ' hours')
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (symbol, f"-{hours}", limit))
            else:
                cursor.execute("""
                    SELECT * FROM iv_skew_observations
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (symbol, limit))

            return [dict(row) for row in cursor.fetchall()]

    def get_validation_stats(self, symbol: str) -> Dict[str, Any]:
        """Get validation statistics for a symbol

        Returns aggregated stats useful for validating IV skew edge.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Basic observation stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_observations,
                    MIN(timestamp) as first_observation,
                    MAX(timestamp) as last_observation,
                    AVG(iv_skew_pct) as avg_skew_pct,
                    MIN(iv_skew_pct) as min_skew_pct,
                    MAX(iv_skew_pct) as max_skew_pct,
                    SUM(CASE WHEN direction = 'bullish' THEN 1 ELSE 0 END) as bullish_count,
                    SUM(CASE WHEN direction = 'bearish' THEN 1 ELSE 0 END) as bearish_count,
                    SUM(CASE WHEN direction = 'neutral' THEN 1 ELSE 0 END) as neutral_count
                FROM iv_skew_observations
                WHERE symbol = ?
            """, (symbol,))

            row = cursor.fetchone()
            if not row or row['total_observations'] == 0:
                return {"error": f"No observations for {symbol}"}

            return {
                "symbol": symbol,
                "total_observations": row['total_observations'],
                "first_observation": row['first_observation'],
                "last_observation": row['last_observation'],
                "avg_skew_pct": round(row['avg_skew_pct'], 2),
                "min_skew_pct": round(row['min_skew_pct'], 2),
                "max_skew_pct": round(row['max_skew_pct'], 2),
                "direction_distribution": {
                    "bullish": row['bullish_count'],
                    "bearish": row['bearish_count'],
                    "neutral": row['neutral_count']
                }
            }

    def update_price_outcome(
        self,
        observation_id: int,
        horizon: str,
        future_price: float
    ):
        """Update price outcome for a past observation

        This is called retrospectively to fill in what actually happened
        after the IV skew was observed.

        Args:
            observation_id: ID of the observation to update
            horizon: Time horizon ('1h', '4h', '24h')
            future_price: The actual price at that horizon
        """
        horizon_col_map = {
            '1h': ('price_1h', 'return_1h_pct', 'direction_correct_1h'),
            '4h': ('price_4h', 'return_4h_pct', 'direction_correct_4h'),
            '24h': ('price_24h', 'return_24h_pct', 'direction_correct_24h'),
        }

        if horizon not in horizon_col_map:
            raise ValueError(f"Invalid horizon: {horizon}. Use '1h', '4h', or '24h'")

        price_col, return_col, correct_col = horizon_col_map[horizon]

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get original observation
            cursor.execute("""
                SELECT current_price, direction FROM iv_skew_observations
                WHERE id = ?
            """, (observation_id,))
            obs = cursor.fetchone()

            if not obs:
                logger.warning(f"Observation {observation_id} not found")
                return

            original_price = obs['current_price']
            predicted_direction = obs['direction']

            # Calculate return
            return_pct = ((future_price - original_price) / original_price) * 100

            # Check if direction was correct
            # Bullish prediction = expecting price up = return > 0
            # Bearish prediction = expecting price down = return < 0
            if predicted_direction == 'neutral':
                direction_correct = None  # N/A for neutral
            elif predicted_direction == 'bullish':
                direction_correct = 1 if return_pct > 0 else 0
            else:  # bearish
                direction_correct = 1 if return_pct < 0 else 0

            # Check if outcome record exists
            cursor.execute("""
                SELECT id FROM price_outcomes WHERE observation_id = ?
            """, (observation_id,))

            if cursor.fetchone():
                # Update existing
                cursor.execute(f"""
                    UPDATE price_outcomes
                    SET {price_col} = ?, {return_col} = ?, {correct_col} = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE observation_id = ?
                """, (future_price, return_pct, direction_correct, observation_id))
            else:
                # Insert new
                cursor.execute(f"""
                    INSERT INTO price_outcomes (observation_id, {price_col}, {return_col}, {correct_col})
                    VALUES (?, ?, ?, ?)
                """, (observation_id, future_price, return_pct, direction_correct))

            conn.commit()
            logger.debug(
                f"Updated {horizon} outcome for obs {observation_id}: "
                f"return={return_pct:.2f}%, correct={direction_correct}"
            )


# Singleton instance for easy import
_logger_instance: Optional[IVSkewLogger] = None

def get_iv_skew_logger() -> IVSkewLogger:
    """Get singleton IV skew logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = IVSkewLogger()
    return _logger_instance
