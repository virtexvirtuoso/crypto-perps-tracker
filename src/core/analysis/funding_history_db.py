"""
Funding History Database

SQLite storage for historical funding rates to enable z-score calculations.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path


class FundingHistoryDB:
    """
    Manages historical funding rate storage for statistical analysis.
    
    Features:
    - Stores funding rates with timestamp and exchange
    - Automatic cleanup (30-day retention)
    - Fast queries with indexed timestamps
    - Z-score calculation support
    
    Usage:
        db = FundingHistoryDB('/path/to/perpetuals.db')
        
        # Store new funding rate
        db.add_funding_rate(0.0008, 'aggregated', timestamp)
        
        # Get last 24 hours for z-score
        rates = db.get_recent_funding_rates(hours=24)
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. 
                    Defaults to ../../../database/perpetuals.db
        """
        self.logger = logging.getLogger(__name__)
        
        if db_path is None:
            # Default: crypto-perps-tracker/database/perpetuals.db
            base_dir = Path(__file__).parent.parent.parent.parent
            db_path = base_dir / 'database' / 'perpetuals.db'
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = str(db_path)
        self._init_database()
    
    def _init_database(self):
        """Create tables and indexes if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create funding_history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS funding_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    funding_rate REAL NOT NULL,
                    exchange TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index on timestamp for fast queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_funding_timestamp 
                ON funding_history(timestamp)
            ''')
            
            # Create index on exchange for filtering
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_funding_exchange 
                ON funding_history(exchange)
            ''')
            
            conn.commit()
            self.logger.info(f"Database initialized at {self.db_path}")
    
    def add_funding_rate(
        self,
        funding_rate: float,
        exchange: str = 'aggregated',
        timestamp: Optional[float] = None
    ):
        """
        Store a funding rate in the database.
        
        Args:
            funding_rate: Funding rate (e.g., 0.0008 for 0.08%)
            exchange: Exchange name or 'aggregated' for volume-weighted average
            timestamp: Unix timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now().timestamp()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO funding_history (timestamp, funding_rate, exchange)
                VALUES (?, ?, ?)
            ''', (int(timestamp), funding_rate, exchange))
            conn.commit()
    
    def get_recent_funding_rates(
        self,
        hours: int = 24,
        exchange: str = 'aggregated'
    ) -> List[float]:
        """
        Retrieve recent funding rates for z-score calculation.
        
        Args:
            hours: Number of hours of history to fetch
            exchange: Exchange filter ('aggregated' for volume-weighted average)
        
        Returns:
            List of funding rates, oldest first
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cutoff_timestamp = int(cutoff_time.timestamp())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT funding_rate 
                FROM funding_history 
                WHERE timestamp >= ? AND exchange = ?
                ORDER BY timestamp ASC
            ''', (cutoff_timestamp, exchange))
            
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    
    def get_funding_stats(self, hours: int = 24) -> Dict[str, float]:
        """
        Calculate funding rate statistics over time period.
        
        Args:
            hours: Time window for statistics
        
        Returns:
            Dict with mean, std, min, max, current
        """
        rates = self.get_recent_funding_rates(hours=hours)
        
        if not rates:
            return {
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'current': 0.0,
                'sample_count': 0
            }
        
        import numpy as np
        
        return {
            'mean': float(np.mean(rates)),
            'std': float(np.std(rates)),
            'min': float(np.min(rates)),
            'max': float(np.max(rates)),
            'current': float(rates[-1]),
            'sample_count': len(rates)
        }
    
    def cleanup_old_data(self, days: int = 30):
        """
        Remove data older than N days to keep database size manageable.
        
        Args:
            days: Days of history to keep (default 30)
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        cutoff_timestamp = int(cutoff_time.timestamp())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM funding_history 
                WHERE timestamp < ?
            ''', (cutoff_timestamp,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old records")
            
            return deleted_count


# Example usage
if __name__ == "__main__":
    import time
    import numpy as np
    
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database
    db = FundingHistoryDB()
    
    # Simulate adding historical data (5-minute intervals for 24 hours)
    print("Adding simulated historical data...")
    base_funding = 0.0008
    now = time.time()
    
    for i in range(288):  # 288 = 24 hours at 5-minute intervals
        timestamp = now - (288 - i) * 300  # 300 seconds = 5 minutes
        # Simulate some variance
        funding = base_funding + np.random.normal(0, 0.0001)
        db.add_funding_rate(funding, 'aggregated', timestamp)
    
    print(f"Added 288 historical records")
    
    # Get recent rates
    rates = db.get_recent_funding_rates(hours=24)
    print(f"\nRetrieved {len(rates)} rates from last 24 hours")
    
    # Get statistics
    stats = db.get_funding_stats(hours=24)
    print("\n=== Funding Rate Statistics (24h) ===")
    print(f"Mean: {stats['mean']:.6f} ({stats['mean']*100:.4f}%)")
    print(f"Std Dev: {stats['std']:.6f} ({stats['std']*10000:.2f} bps)")
    print(f"Min: {stats['min']:.6f}")
    print(f"Max: {stats['max']:.6f}")
    print(f"Current: {stats['current']:.6f}")
    print(f"Samples: {stats['sample_count']}")
    
    # Test cleanup
    print("\nTesting cleanup...")
    deleted = db.cleanup_old_data(days=30)
    print(f"Deleted {deleted} records older than 30 days")
