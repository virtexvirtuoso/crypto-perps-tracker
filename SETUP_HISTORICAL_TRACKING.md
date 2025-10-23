# Historical Data & Liquidation Tracking Setup

## 🎯 Overview

This guide sets up **two powerful new features** for crypto-perps-tracker:

1. **📊 Historical Data Logger** - SQLite database storing hourly market snapshots for trend analysis and backtesting
2. **⚠️ Liquidation Tracking** - Real-time liquidation data from exchanges for cascade risk detection

---

## 📋 Prerequisites

- Python 3.8+
- crypto-perps-tracker already installed and working
- `python-dotenv` in requirements.txt (already included)

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Initialize the Database

```bash
cd /Users/ffv_macmini/Desktop/crypto-perps-tracker

# Make data_logger.py executable
chmod +x scripts/data_logger.py

# Initialize SQLite database with schema
python3 scripts/data_logger.py --init
```

**Expected Output:**
```
✓ Created table: market_snapshots
✓ Created table: exchange_snapshots
✓ Created table: sentiment_factors
✓ Created table: liquidation_snapshots
✓ Created 5 indices

✅ Database initialized at: data/market_history.db
```

### Step 2: Create Logs Directory

```bash
mkdir -p logs
```

### Step 3: Test Liquidation Fetching

```bash
# Make fetch_liquidations.py executable
chmod +x scripts/fetch_liquidations.py

# Test fetching Binance liquidations (last hour)
python3 scripts/fetch_liquidations.py --hours 1
```

**Expected Output:**
```
================================================================================
⚠️  LIQUIDATION REPORT
================================================================================

────────────────────────────────────────────────────────────────────────────────
Exchange: Binance
────────────────────────────────────────────────────────────────────────────────
Status:              ✅ Success
Time Period:         1 hour(s)
Total Liquidations:  $12.50M
  • Long Liq:        $8.20M (145 trades)
  • Short Liq:       $4.30M (78 trades)
Liquidation Count:   223
Long/Short Ratio:    1.91x
Bias:                🔴 LONGS GETTING REKT
```

### Step 4: Test Data Logging

```bash
# Log a snapshot manually
python3 scripts/data_logger.py
```

**Expected Output:**
```
📊 Logging market snapshot at 2025-10-23 15:30:00 UTC
⏳ Fetching data from 8 exchanges...
🧮 Analyzing market sentiment...
✓ Liquidation data logged
✅ Snapshot logged successfully
   • Exchanges: 8
   • Total Volume: $238.50B
   • Total OI: $63.20B
   • Composite Score: 0.125
   • Sentiment: ⚪ NEUTRAL
```

### Step 5: View Database Statistics

```bash
python3 scripts/data_logger.py --stats
```

**Expected Output:**
```
================================================================================
📊 MARKET HISTORY DATABASE STATISTICS
================================================================================

📈 Market Snapshots:
   • Total Records: 1
   • First Snapshot: 2025-10-23 15:30 UTC
   • Last Snapshot: 2025-10-23 15:30 UTC
   • Time Span: 0.0 hours (0.0 days)

📊 Average Metrics:
   • Composite Score: 0.125
   • Volume: $238.50B
   • Open Interest: $63.20B
   • OI/Vol Ratio: 0.27x

💭 Sentiment Distribution:
   • ⚪ NEUTRAL: 1 (100.0%)

🏢 Exchange Data:
   • Unique Exchanges: 8
   • Total Records: 8

⚠️  Liquidation Data:
   • Total Records: 1
   • Total Liquidations: $12.5M
   • Avg Cascade Risk: 0.35/1.0

💾 Database:
   • File Size: 24.0 KB
   • Location: data/market_history.db
```

---

## ⏰ Automated Hourly Logging (Crontab)

### Add to Crontab

```bash
# Open crontab editor
crontab -e

# Add this line (adjust path if needed):
0 * * * * cd /Users/ffv_macmini/Desktop/crypto-perps-tracker && python3 scripts/data_logger.py >> logs/data_logger.log 2>&1
```

**What this does:**
- Runs every hour at :00 minutes
- Logs to `logs/data_logger.log`
- Captures errors to same log file

### Verify Cron Job

```bash
# List current cron jobs
crontab -l
```

### Check Logs

```bash
# View recent log entries
tail -f logs/data_logger.log
```

---

## 🧪 Testing Strategy Alerts with Liquidation Data

### Test Enhanced Liquidation Cascade Detection

```bash
# Run strategy alerts (now includes liquidation data)
cd scripts
python3 strategy_alerts.py
```

**Expected Output (if cascade conditions met):**
```
🔍 Analyzing market for trading strategy opportunities...

⏳ Fetching data from 8 exchanges (20-30 seconds)...
⚠️  Liquidation data: $45.2M (Risk: HIGH)

🚨 1 STRATEGY ALERT(S) DETECTED!

================================================================================

1. Liquidation Cascade Risk (Longs) - 🟡 BUILDING RISK - Confidence: 88%
   Direction: 📉 SHORT
────────────────────────────────────────────────────────────────────────────────
🟡 BUILDING RISK DETECTED
• Longs heavily leveraged (OI/Vol: 0.65x)
• Recent liquidations: $45.2M (2.1% of volume)
• Cascade Risk Score: 0.68/1.0 (HIGH)
• Extreme funding (0.0182%) suggests crowded trade
• Strategy: 📉 Counter with SHORT with TIGHT stops (high risk)
• OR reduce leverage immediately if on longs side

================================================================================

📤 Sending alert to Discord...
```

---

## 📚 Usage Guide

### Data Logger Commands

```bash
# Log current snapshot
python3 scripts/data_logger.py

# Initialize/reset database
python3 scripts/data_logger.py --init

# View statistics
python3 scripts/data_logger.py --stats

# Cleanup old data (keep 90 days)
python3 scripts/data_logger.py --cleanup 90
```

### Liquidation Fetcher Commands

```bash
# Last 1 hour (default)
python3 scripts/fetch_liquidations.py

# Last 24 hours
python3 scripts/fetch_liquidations.py --hours 24

# Specific exchange
python3 scripts/fetch_liquidations.py --exchange binance

# With market volume for ratios
python3 scripts/fetch_liquidations.py --volume 238000000000
```

---

## 🗄️ Database Schema

### Tables Created

**market_snapshots** - Hourly market overview
- Composite score, sentiment, volume, OI
- 15 columns tracking market state

**exchange_snapshots** - Per-exchange data
- Volume, OI, funding, price changes per exchange
- Linked to market_snapshots via timestamp

**sentiment_factors** - Multi-factor scores
- 6 sentiment factors (funding, price, conviction, etc.)
- Enables trend analysis of individual factors

**liquidation_snapshots** - Liquidation tracking
- Total/long/short liquidations per exchange
- Cascade risk scores

### Indices

Optimized for fast queries:
- Timestamp descending (recent data first)
- Exchange lookups
- Sentiment analysis queries

---

## 📈 What's Now Possible

### 1. Trend Detection
```python
# Example: Get 24h sentiment trend
# (Future feature - coming soon in Phase 2)
SELECT composite_score, timestamp
FROM market_snapshots
WHERE timestamp > (strftime('%s', 'now') - 86400)
ORDER BY timestamp;
```

### 2. Backtesting Strategies
```python
# Example: Test if Range Trading worked historically
# (Future feature - coming soon in Phase 3)
SELECT
    COUNT(*) as opportunities,
    AVG(price_change) as avg_move
FROM market_snapshots
WHERE composite_score BETWEEN -0.2 AND 0.2
  AND oi_vol_ratio BETWEEN 0.3 AND 0.5;
```

### 3. Liquidation Cascade Detection
- **Before:** Based on OI/Vol ratio only (estimated risk)
- **After:** Uses REAL liquidation data (confirmed cascades)
- **Impact:** +20% confidence bonus when cascade active

### 4. Historical Analysis
```bash
# Show sentiment distribution over time
python3 scripts/data_logger.py --stats
```

---

## 🔧 Troubleshooting

### Database Not Found
```bash
python3 scripts/data_logger.py --init
```

### Liquidations Not Showing in Strategy Alerts
- Check `fetch_liquidations.py` is in scripts/ directory
- Verify Binance API is accessible
- Run standalone test: `python3 scripts/fetch_liquidations.py`

### Cron Job Not Running
```bash
# Check cron service status
# macOS:
launchctl list | grep cron

# View system log for cron errors
tail -f /var/log/system.log | grep cron

# Ensure full path in crontab
0 * * * * cd /Users/ffv_macmini/Desktop/crypto-perps-tracker && /usr/bin/python3 scripts/data_logger.py
```

### Database Growing Too Large
```bash
# Remove data older than 30 days
python3 scripts/data_logger.py --cleanup 30

# Check database size
du -h data/market_history.db
```

---

## 📊 Example: 7-Day Data Collection

After running for 7 days (168 hours):

```
📈 Market Snapshots:
   • Total Records: 168
   • Time Span: 168.0 hours (7.0 days)
   • Database Size: ~400 KB

💭 Sentiment Distribution:
   • 🟢 BULLISH: 45 (26.8%)
   • ⚪ NEUTRAL: 89 (53.0%)
   • 🔴 BEARISH: 34 (20.2%)

⚠️  Liquidation Data:
   • Total Liquidations: $2.3B (7 days)
   • Cascade Events: 3 (HIGH risk or above)
```

---

## 🎯 Next Steps

### Phase 2: Trend Detection (Next Week)
- [ ] Add historical trend analysis to strategies
- [ ] Require sustained composite scores for Trend Following
- [ ] Detect volatility regime changes

### Phase 3: Machine Learning (Week 3-4)
- [ ] Train funding rate predictor
- [ ] Optimize strategy weights via backtesting
- [ ] Add confidence boosting from historical success rates

---

## 📞 Support

If you encounter issues:

1. **Check logs:** `tail -f logs/data_logger.log`
2. **Test components individually:**
   - Data logger: `python3 scripts/data_logger.py`
   - Liquidations: `python3 scripts/fetch_liquidations.py`
   - Strategy alerts: `cd scripts && python3 strategy_alerts.py`

3. **Verify database:** `python3 scripts/data_logger.py --stats`

---

**Status:** ✅ Production Ready
**Version:** 1.0.0
**Last Updated:** October 23, 2025
