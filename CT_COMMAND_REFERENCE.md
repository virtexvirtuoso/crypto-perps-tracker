# `ct` Command Reference

Quick control utility for crypto-perps-tracker operations.

## Usage

### VPS
```bash
# Full path (works immediately)
/home/virtuoso/crypto-perps-tracker/ct <command>

# Or after logging in (alias auto-loads)
ct <command>
```

### Local
```bash
./scripts/ct <command>
```

## Commands

### 📊 Data Operations

**Take Manual Snapshot**
```bash
ct snapshot    # or: ct s
```

**View Database Statistics**
```bash
ct stats       # or: ct st
```

**Recent Snapshots**
```bash
ct recent 10   # Last 10 snapshots
ct r 5         # Last 5 (shorthand)
```

**Sentiment Trends**
```bash
ct trends 24   # Last 24 hours
ct tr 48       # Last 48 hours
```

**Compare Current vs Past**
```bash
ct compare     # Current vs 24h ago
ct cmp         # Shorthand
```

### 💾 Database Management

**Database Info**
```bash
ct db          # Size and record count
```

**Custom SQL Query**
```bash
ct query "SELECT * FROM market_snapshots ORDER BY timestamp DESC LIMIT 5"
ct q "SELECT sentiment, COUNT(*) FROM market_snapshots GROUP BY sentiment"
```

**Initialize Database**
```bash
ct init
```

**Cleanup Old Data**
```bash
ct cleanup 30  # Keep only 30 days
ct clean 90    # Keep 90 days (default)
```

**Export to CSV**
```bash
ct export      # Creates timestamped CSV file
ct exp         # Shorthand
```

### 📈 Market Data

**Fetch Liquidations**
```bash
ct liquidations 1   # Last 1 hour
ct liq 24           # Last 24 hours
```

### 📋 Monitoring

**View Logs (Live)**
```bash
ct log         # Tail -f (live)
ct l           # Shorthand
```

**View Recent Log Lines**
```bash
ct logs 50     # Last 50 lines
ct tail 20     # Last 20 lines (shorthand)
ct t 20        # Ultra shorthand
```

**Show Crontab Entries**
```bash
ct cron
```

### 🔧 Utilities

**Show File Paths**
```bash
ct path        # Shows project, DB, log locations
ct p           # Shorthand
```

## Example Workflows

### Check System Health
```bash
ct stats       # Overall stats
ct cron        # Verify automated logging
ct recent 5    # Check recent snapshots
```

### Investigate Market Trends
```bash
ct trends 24   # Sentiment over last day
ct compare     # Current vs yesterday
ct recent 10   # Latest data points
```

### Database Maintenance
```bash
ct db          # Check size
ct stats       # View record counts
ct cleanup 60  # Keep 60 days, remove older
```

### Manual Data Collection
```bash
ct snapshot    # Log snapshot now
ct stats       # Verify it was logged
ct recent 1    # View the new snapshot
```

### Debugging
```bash
ct tail 50     # Recent log entries
ct log         # Watch live logs
ct path        # Verify file locations
```

## Advanced SQL Queries

**Volume Trends**
```bash
ct q "SELECT datetime(timestamp, 'unixepoch'), total_volume/1e9 FROM market_snapshots ORDER BY timestamp DESC LIMIT 10"
```

**Sentiment Distribution**
```bash
ct q "SELECT sentiment, COUNT(*) as count, printf('%.1f%%', COUNT()*100.0/(SELECT COUNT(*) FROM market_snapshots)) FROM market_snapshots GROUP BY sentiment"
```

**Hourly Breakdown**
```bash
ct q "SELECT strftime('%H:00', timestamp, 'unixepoch') as hour, AVG(composite_score) FROM market_snapshots GROUP BY hour ORDER BY hour"
```

**Top Composite Scores**
```bash
ct q "SELECT datetime(timestamp, 'unixepoch'), composite_score, sentiment FROM market_snapshots ORDER BY composite_score DESC LIMIT 10"
```

## Files and Locations

**VPS:**
- Script: `/home/virtuoso/crypto-perps-tracker/ct`
- Alias: In `~/.bashrc`
- Database: `~/crypto-perps-tracker/data/market_history.db`
- Logs: `~/crypto-perps-tracker/logs/data_logger.log`

**Local:**
- Script: `./scripts/ct`
- Database: `./data/market_history.db`
- Logs: `./logs/data_logger.log`

## Comparison with Other Commands

**Similar to `wh` (Whale Hunter):**
- `wh start/stop/status` → N/A (ct uses cron, not daemon)
- `wh log` → `ct log`
- `wh config` → N/A (ct uses YAML via scripts)

**Similar to `vt` (Virtuoso Trading):**
- Not yet implemented (ct is the first of this style for crypto-perps)

## Tips

1. **Use shorthand**: `ct s` instead of `ct snapshot`
2. **Pipe SQL queries**: `ct q "SELECT * FROM..." | grep BULLISH`
3. **Export before cleanup**: `ct exp && ct clean 30`
4. **Monitor in tmux**: `ct log` in split pane
5. **Daily health check**: `ct stats && ct cron`

## Troubleshooting

**"command not found"**
- VPS: Use full path `/home/virtuoso/crypto-perps-tracker/ct`
- Local: Use `./scripts/ct`
- Or re-login to load bashrc alias

**"sqlite3: command not found"**
```bash
# VPS
sudo apt-get install sqlite3

# Mac
brew install sqlite3
```

**"Database not found"**
```bash
ct init       # Initialize database
ct path       # Verify locations
```

**Empty logs**
```bash
ct cron       # Verify crontab is set
ct snapshot   # Manual snapshot
ct tail 100   # Check for errors
```
