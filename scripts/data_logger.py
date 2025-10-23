#!/usr/bin/env python3
"""
Historical Market Data Logger
Stores hourly snapshots to SQLite for trend analysis, backtesting, and ML features

Usage:
    python3 scripts/data_logger.py                    # Log current snapshot
    python3 scripts/data_logger.py --init             # Initialize database
    python3 scripts/data_logger.py --stats            # Show database statistics

Add to crontab for automation:
    0 * * * * cd ~/crypto-perps-tracker && python3 scripts/data_logger.py >> logs/data_logger.log 2>&1
"""

import sys
import os
import sqlite3
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compare_all_exchanges import fetch_all_enhanced
from generate_market_report import analyze_market_sentiment


# Database schema
DB_PATH = 'data/market_history.db'

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


def init_database():
    """Initialize database with schema"""
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)

    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    # Create tables
    for table_name, schema_sql in SCHEMA.items():
        if table_name != 'indices':
            cursor.execute(schema_sql)
            print(f"✓ Created table: {table_name}")

    # Create indices
    for index_sql in SCHEMA['indices']:
        cursor.execute(index_sql)
    print(f"✓ Created {len(SCHEMA['indices'])} indices")

    db.commit()
    db.close()

    print(f"\n✅ Database initialized at: {DB_PATH}")


def log_market_snapshot() -> bool:
    """
    Fetch current market data and log to database

    Returns:
        bool: True if successful, False otherwise
    """
    timestamp = int(datetime.now(timezone.utc).timestamp())

    print(f"\n📊 Logging market snapshot at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    try:
        # Fetch data from all exchanges
        print("⏳ Fetching data from 8 exchanges...")
        results = fetch_all_enhanced()

        # Analyze sentiment
        print("🧮 Analyzing market sentiment...")
        sentiment = analyze_market_sentiment(results)

        # Calculate totals
        successful = [r for r in results if r.get('status') == 'success']
        total_volume = sum(r['volume'] for r in successful)
        total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

        # CEX vs DEX
        cex_volume = sum(r['volume'] for r in successful if r.get('type') == 'CEX')
        dex_volume = sum(r['volume'] for r in successful if r.get('type') == 'DEX')

        # Connect to database
        db = sqlite3.connect(DB_PATH)
        cursor = db.cursor()

        # 1. Insert market snapshot
        cursor.execute('''
            INSERT OR REPLACE INTO market_snapshots (
                timestamp, composite_score, funding_rate, total_volume, total_oi,
                price_change, long_pct, sentiment, strength, oi_vol_ratio,
                funding_divergence, exchanges_count, cex_volume, dex_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            sentiment['composite_score'],
            sentiment['weighted_funding'],
            total_volume,
            total_oi if total_oi > 0 else None,
            sentiment['avg_price_change'],
            sentiment['factors']['long_short_bias'].get('long_pct'),
            sentiment['sentiment'],
            sentiment['strength'],
            total_oi / total_volume if total_volume > 0 and total_oi > 0 else None,
            sentiment['factors']['divergence']['value'],
            len(successful),
            cex_volume,
            dex_volume
        ))

        # 2. Insert exchange snapshots
        for r in successful:
            cursor.execute('''
                INSERT OR REPLACE INTO exchange_snapshots (
                    timestamp, exchange, exchange_type, volume, open_interest,
                    funding_rate, price_change, markets, num_trades
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                r['exchange'],
                r.get('type'),
                r['volume'],
                r.get('open_interest'),
                r.get('funding_rate'),
                r.get('price_change_pct'),
                r.get('markets'),
                r.get('num_trades')
            ))

        # 3. Insert sentiment factors
        factors = sentiment['factors']
        cursor.execute('''
            INSERT OR REPLACE INTO sentiment_factors (
                timestamp, funding_score, price_score, ls_bias_score,
                conviction_score, divergence_score, oi_price_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            factors['funding']['score'],
            factors['price_momentum']['score'],
            factors['long_short_bias']['score'],
            factors['conviction']['score'],
            factors['divergence']['score'],
            factors['oi_price_correlation']['score']
        ))

        # 4. Try to log liquidations (if available)
        try:
            from fetch_liquidations import fetch_all_liquidations, calculate_liquidation_metrics

            liq_data = fetch_all_liquidations()

            for liq in liq_data:
                if liq.get('status') == 'success':
                    liq_metrics = calculate_liquidation_metrics([liq], total_volume)

                    cursor.execute('''
                        INSERT OR REPLACE INTO liquidation_snapshots (
                            timestamp, exchange, total_liquidations, long_liquidations,
                            short_liquidations, liquidation_count, cascade_risk_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        timestamp,
                        liq['exchange'],
                        liq.get('total_liquidations_usd'),
                        liq.get('long_liquidations'),
                        liq.get('short_liquidations'),
                        liq.get('liquidation_count'),
                        liq_metrics.get('cascade_risk_score')
                    ))

            print("✓ Liquidation data logged")

        except ImportError:
            print("⚠️  Liquidation tracking not available (fetch_liquidations.py not found)")
        except Exception as e:
            print(f"⚠️  Liquidation logging failed: {e}")

        # Commit and close
        db.commit()
        db.close()

        print(f"✅ Snapshot logged successfully")
        print(f"   • Exchanges: {len(successful)}")
        print(f"   • Total Volume: ${total_volume/1e9:.2f}B")
        print(f"   • Total OI: ${total_oi/1e9:.2f}B" if total_oi > 0 else "   • Total OI: N/A")
        print(f"   • Composite Score: {sentiment['composite_score']:.3f}")
        print(f"   • Sentiment: {sentiment['sentiment']}")

        return True

    except Exception as e:
        print(f"❌ Error logging snapshot: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_database_stats():
    """Display database statistics"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        print("   Run with --init to initialize")
        return

    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    print("\n" + "="*80)
    print("📊 MARKET HISTORY DATABASE STATISTICS")
    print("="*80)

    # Market snapshots
    cursor.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM market_snapshots')
    count, min_ts, max_ts = cursor.fetchone()

    if count > 0:
        first_snapshot = datetime.fromtimestamp(min_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        last_snapshot = datetime.fromtimestamp(max_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        hours = (max_ts - min_ts) / 3600

        print(f"\n📈 Market Snapshots:")
        print(f"   • Total Records: {count:,}")
        print(f"   • First Snapshot: {first_snapshot}")
        print(f"   • Last Snapshot: {last_snapshot}")
        print(f"   • Time Span: {hours:.1f} hours ({hours/24:.1f} days)")

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

        print(f"\n📊 Average Metrics:")
        print(f"   • Composite Score: {avg_score:.3f}")
        print(f"   • Volume: ${avg_vol/1e9:.2f}B")
        print(f"   • Open Interest: ${avg_oi/1e9:.2f}B" if avg_oi else "   • Open Interest: N/A")
        print(f"   • OI/Vol Ratio: {avg_ratio:.2f}x" if avg_ratio else "   • OI/Vol Ratio: N/A")

        # Sentiment distribution
        cursor.execute('''
            SELECT sentiment, COUNT(*)
            FROM market_snapshots
            GROUP BY sentiment
        ''')
        sentiment_dist = cursor.fetchall()

        print(f"\n💭 Sentiment Distribution:")
        for sentiment, count in sentiment_dist:
            pct = (count / sum(c for _, c in sentiment_dist)) * 100
            print(f"   • {sentiment}: {count} ({pct:.1f}%)")
    else:
        print("\n⚠️  No market snapshots recorded yet")

    # Exchange snapshots
    cursor.execute('SELECT COUNT(DISTINCT exchange) FROM exchange_snapshots')
    exchange_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM exchange_snapshots')
    total_exchange_records = cursor.fetchone()[0]

    print(f"\n🏢 Exchange Data:")
    print(f"   • Unique Exchanges: {exchange_count}")
    print(f"   • Total Records: {total_exchange_records:,}")

    # Liquidation data
    cursor.execute('SELECT COUNT(*) FROM liquidation_snapshots')
    liq_count = cursor.fetchone()[0]

    if liq_count > 0:
        cursor.execute('''
            SELECT
                SUM(total_liquidations),
                AVG(cascade_risk_score)
            FROM liquidation_snapshots
        ''')
        total_liq, avg_risk = cursor.fetchone()

        print(f"\n⚠️  Liquidation Data:")
        print(f"   • Total Records: {liq_count:,}")
        print(f"   • Total Liquidations: ${total_liq/1e6:.1f}M")
        print(f"   • Avg Cascade Risk: {avg_risk:.2f}/1.0")
    else:
        print(f"\n⚠️  Liquidation Data: Not available")

    # Database size
    db_size = os.path.getsize(DB_PATH)
    print(f"\n💾 Database:")
    print(f"   • File Size: {db_size/1024:.1f} KB")
    print(f"   • Location: {DB_PATH}")

    db.close()

    print("\n" + "="*80)


def cleanup_old_data(days_to_keep: int = 90):
    """Remove data older than specified days"""
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    cutoff_timestamp = int((datetime.now(timezone.utc).timestamp() - (days_to_keep * 24 * 3600)))

    # Count records to delete
    cursor.execute('SELECT COUNT(*) FROM market_snapshots WHERE timestamp < ?', (cutoff_timestamp,))
    to_delete = cursor.fetchone()[0]

    if to_delete == 0:
        print(f"✓ No records older than {days_to_keep} days")
        db.close()
        return

    print(f"🗑️  Deleting {to_delete} records older than {days_to_keep} days...")

    # Delete old records (cascades to related tables via foreign keys)
    cursor.execute('DELETE FROM market_snapshots WHERE timestamp < ?', (cutoff_timestamp,))
    cursor.execute('DELETE FROM exchange_snapshots WHERE timestamp < ?', (cutoff_timestamp,))
    cursor.execute('DELETE FROM sentiment_factors WHERE timestamp < ?', (cutoff_timestamp,))
    cursor.execute('DELETE FROM liquidation_snapshots WHERE timestamp < ?', (cutoff_timestamp,))

    # Vacuum to reclaim space
    cursor.execute('VACUUM')

    db.commit()
    db.close()

    print(f"✅ Cleanup complete")


def main():
    parser = argparse.ArgumentParser(description='Market Data Logger')
    parser.add_argument('--init', action='store_true', help='Initialize database')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Remove data older than DAYS')

    args = parser.parse_args()

    if args.init:
        init_database()
    elif args.stats:
        show_database_stats()
    elif args.cleanup:
        cleanup_old_data(args.cleanup)
    else:
        # Default: log current snapshot
        log_market_snapshot()


if __name__ == "__main__":
    main()
