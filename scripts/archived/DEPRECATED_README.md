# Archived/Deprecated Scripts

This directory contains deprecated scripts that have been replaced or are no longer in use.

## send_discord_report_v1_simple_embed.py

**Status:** Deprecated
**Deprecated Date:** October 24, 2025
**Reason:** Replaced with enhanced version that includes charts and attachments

### What It Was
The original version of `send_discord_report.py` that sent a simple multi-embed Discord message with market data. It created 6 separate embeds:
1. Executive Summary (Market Snapshot with volume, OI, markets tracked)
2. Sentiment Analysis (funding rates table)
3. Arbitrage Opportunities (top 5 opportunities)
4. Trading Patterns (market dominance, leaders, trading styles)
5. Recommendations (trading suggestions)
6. Anomalies (if any detected)

### Why It Was Deprecated
- No visual charts or graphs
- Text-only format was less engaging
- Lacked the detailed spot-futures basis analysis
- No file attachments for full report details
- Multiple embeds took up more space in Discord

### What Replaced It
The current `send_discord_report.py` (v2) which:
- Generates 4 professional charts (funding rates, market dominance, spot-futures basis, leverage activity)
- Sends a single concise embed with key metrics
- Attaches full text report file
- Includes spot-futures basis analysis from 6 exchanges
- More visually appealing with cyberpunk-styled charts
- Better suited for mobile viewing

### If You Need To Restore It
```bash
# Copy from archive back to scripts/
cp scripts/archived/send_discord_report_v1_simple_embed.py scripts/send_discord_report.py
```

**Note:** The old version is fully functional but superseded by the enhanced version with charts.
