"""
Database Historical Data Fetcher

Fetches historical market data from SQLite database for fast chart generation.
"""

import sqlite3
from typing import Dict, List
from pathlib import Path


def fetch_historical_data_from_db(
    symbols: List[str],
    hours: int = 12,
    db_path: str = "data/market_history.db"
) -> Dict[str, List[Dict]]:
    """
    Fetch historical price data from database for specified symbols

    Args:
        symbols: List of symbol names (e.g., ['BTC', 'ETH', 'SOL'])
        hours: Number of hours of historical data to fetch (default 12)
        db_path: Path to SQLite database file

    Returns:
        Dict mapping symbol -> list of {timestamp, close, ...}
        Format matches the OKX API format used by fetch_historical_data_for_symbols()
    """
    # Check if database exists
    if not Path(db_path).exists():
        print(f"⚠️  Database not found: {db_path}")
        return {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Calculate cutoff time (hours ago)
    import time
    cutoff_timestamp = int(time.time()) - (hours * 3600)

    historical_data = {}

    for symbol in symbols:
        # Convert symbol format if needed (e.g., BTC -> BTCUSDT)
        if not symbol.endswith('USDT'):
            query_symbol = symbol + 'USDT'
        else:
            query_symbol = symbol

        # Fetch data for this symbol
        cursor.execute('''
            SELECT timestamp, price, volume_24h, price_change_24h_pct
            FROM market_snapshots
            WHERE symbol = ? AND timestamp > ?
            ORDER BY timestamp ASC
        ''', (query_symbol, cutoff_timestamp))

        rows = cursor.fetchall()

        if rows:
            # Convert to format expected by dashboard
            candles = []
            for row in rows:
                timestamp, price, volume, price_change_pct = row
                candles.append({
                    'timestamp': timestamp * 1000,  # Convert to milliseconds
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                })

            # Use the base symbol name for the key (without USDT)
            key_symbol = symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol
            historical_data[key_symbol] = candles

    conn.close()

    return historical_data


def get_database_stats(db_path: str = "data/market_history.db") -> Dict:
    """
    Get statistics about the historical database

    Returns:
        Dict with total_records, unique_symbols, time_range_hours, etc.
    """
    if not Path(db_path).exists():
        return {
            'exists': False,
            'total_records': 0,
            'unique_symbols': 0,
            'time_range_hours': 0
        }

    conn = sqlite3.connect(db_path)
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
            'exists': True,
            'total_records': total_records,
            'unique_symbols': unique_symbols,
            'time_range_hours': time_range_hours,
            'oldest_timestamp': min_ts,
            'newest_timestamp': max_ts
        }
    finally:
        conn.close()
