#!/usr/bin/env python3
"""
Historical Market Data Logger

Logs market snapshots to SQLite database for fast historical chart generation.
Run this script every 5 minutes via cron for 12h+ of historical data.

Crontab example:
*/5 * * * * cd ~/crypto-perps-tracker && ~/crypto-perps-tracker/venv/bin/python3 scripts/log_historical_data.py >> logs/historical_logger.log 2>&1
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import time
from datetime import datetime, timezone
from typing import List, Dict

from src.container import Container
from src.models.config import Config


class HistoricalDataLogger:
    """Logs market data to SQLite database"""

    def __init__(self, db_path: str = "data/market_history.db"):
        """Initialize logger with database path"""
        self.db_path = db_path
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Create database and tables if they don't exist"""
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create market_snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_snapshots (
                timestamp INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                price REAL NOT NULL,
                volume_24h REAL,
                price_change_24h_pct REAL,
                funding_rate REAL,
                open_interest REAL,
                PRIMARY KEY (timestamp, symbol, exchange)
            )
        ''')

        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_symbol_timestamp
            ON market_snapshots(symbol, timestamp)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON market_snapshots(timestamp)
        ''')

        conn.commit()
        conn.close()

    def log_snapshot(self, container: Container) -> int:
        """
        Log current market snapshot to database

        Returns:
            Number of records inserted
        """
        timestamp = int(time.time())

        # Fetch all market data to get top symbols
        try:
            markets = container.exchange_service.fetch_all_markets(use_cache=False)
        except Exception as e:
            print(f"❌ Error fetching market data: {e}")
            return 0

        if not markets:
            print("⚠️  No market data available")
            return 0

        # Use OKX for price data (works globally)
        print("   📊 Fetching price data from OKX...")

        import requests
        okx_tickers = {}
        try:
            response = requests.get('https://www.okx.com/api/v5/market/tickers?instType=SWAP', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    for ticker in data.get('data', []):
                        # OKX format: BTC-USDT-SWAP -> BTCUSDT
                        inst_id = ticker['instId']
                        if '-USDT-SWAP' in inst_id:
                            symbol = inst_id.replace('-USDT-SWAP', '') + 'USDT'
                            okx_tickers[symbol] = ticker
        except Exception as e:
            print(f"❌ Error fetching OKX tickers: {e}")

        if not okx_tickers:
            print("⚠️  No OKX ticker data available")
            return 0

        print(f"   ✓ Fetched {len(okx_tickers)} OKX tickers")

        # Prepare data for insertion - collect unique symbols from all markets
        records = []
        unique_symbols = set()

        for market in markets:
            if not market.top_pairs:
                continue

            for pair in market.top_pairs[:10]:  # Top 10 per exchange
                symbol = pair.symbol

                if symbol in unique_symbols:
                    continue

                unique_symbols.add(symbol)

                # Get price data from OKX
                if symbol not in okx_tickers:
                    continue

                ticker = okx_tickers[symbol]

                try:
                    price = float(ticker['last'])
                    # OKX provides change in price, not percentage
                    open_price = float(ticker['open24h'])
                    if open_price > 0:
                        price_change_pct = ((price - open_price) / open_price) * 100
                    else:
                        price_change_pct = 0.0

                    volume = float(ticker['volCcy24h'])  # Volume in USDT
                    funding_rate = None  # OKX requires separate API call
                    open_interest = None  # OKX requires separate API call

                    records.append((
                        timestamp,
                        symbol,
                        'OKX',
                        price,
                        volume,
                        price_change_pct,
                        funding_rate,
                        open_interest
                    ))
                except Exception as e:
                    continue

        if not records:
            print("⚠️  No trading pairs to log")
            return 0

        # Insert into database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.executemany('''
                INSERT OR REPLACE INTO market_snapshots
                (timestamp, symbol, exchange, price, volume_24h,
                 price_change_24h_pct, funding_rate, open_interest)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)

            conn.commit()

            # Clean up old data (keep 24 hours)
            cutoff_time = timestamp - (24 * 3600)
            cursor.execute('DELETE FROM market_snapshots WHERE timestamp < ?', (cutoff_time,))
            deleted_count = cursor.rowcount
            conn.commit()

            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"✅ [{current_time}] Logged {len(records)} records (deleted {deleted_count} old records)")

            return len(records)

        except Exception as e:
            print(f"❌ Error inserting records: {e}")
            return 0
        finally:
            conn.close()

    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Total records
            cursor.execute('SELECT COUNT(*) FROM market_snapshots')
            total_records = cursor.fetchone()[0]

            # Unique symbols
            cursor.execute('SELECT COUNT(DISTINCT symbol) FROM market_snapshots')
            unique_symbols = cursor.fetchone()[0]

            # Time range
            cursor.execute('SELECT MIN(timestamp), MAX(timestamp) FROM market_snapshots')
            min_ts, max_ts = cursor.fetchone()

            if min_ts and max_ts:
                time_range_hours = (max_ts - min_ts) / 3600
            else:
                time_range_hours = 0

            return {
                'total_records': total_records,
                'unique_symbols': unique_symbols,
                'time_range_hours': time_range_hours,
                'oldest_timestamp': min_ts,
                'newest_timestamp': max_ts
            }
        finally:
            conn.close()


def main():
    """Main entry point"""
    print("=" * 60)
    print("Historical Market Data Logger")
    print("=" * 60)

    # Load config
    try:
        config = Config.from_yaml('config/config.yaml')
        container = Container(config)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

    # Initialize logger
    logger = HistoricalDataLogger()

    # Log snapshot
    records_logged = logger.log_snapshot(container)

    # Show stats
    stats = logger.get_stats()
    print(f"📊 Database Stats:")
    print(f"   Total records: {stats['total_records']:,}")
    print(f"   Unique symbols: {stats['unique_symbols']}")
    print(f"   Time range: {stats['time_range_hours']:.1f} hours")

    # Cleanup
    container.cleanup()

    if records_logged == 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
