# Market Report Format Deprecation Summary

**Date:** October 24, 2025
**Action:** Deprecated and archived old simple-embed market report format

## Background

Two different market report formats were identified running in production:

### 1. Simple Embed Format (DEPRECATED)
- **Location:** Old version of `scripts/send_discord_report.py`
- **Last Seen:** VPS logs from October 23, 2025
- **Format:**
  - Bot Name: "Crypto Perps Bot" (from config.yaml)
  - Title: "📊 Crypto Perpetual Futures Market Report"
  - Subtitle: "Market Snapshot • [timestamp]"
  - 6 separate embeds for different sections
  - Text-only, no charts or attachments

### 2. Enhanced Format with Charts (CURRENT)
- **Location:** Current `scripts/send_discord_report.py` + `scripts/generate_market_report.py`
- **Active Since:** Commit dadf3d3 (October 23, 2025)
- **Format:**
  - Bot Name: "Market Report Bot"
  - Title: "📊 Crypto Market Report - [timestamp]"
  - Single concise embed with key metrics
  - 4 professional charts attached (funding rates, dominance, basis, leverage)
  - Full text report file attached
  - Includes spot-futures analysis from 6 exchanges

## Actions Taken

1. ✅ Identified the deprecated format in VPS logs
2. ✅ Retrieved old version from git history (commit before dadf3d3)
3. ✅ Archived old version to `scripts/archived/send_discord_report_v1_simple_embed.py`
4. ✅ Created documentation in `scripts/archived/DEPRECATED_README.md`
5. ✅ Updated VPS to latest version (git pull)
6. ✅ Verified VPS is now using enhanced format

## Current Status

**Active Report:** Enhanced format with charts
**Schedule:** Every 12 hours (0:00 and 12:00 UTC) via cron on VPS
**Cron Job:** `0 0,12 * * * cd ~/crypto-perps-tracker && /bin/bash scripts/schedule_discord_reports.sh`

**Reports Sent:**
- Market Report (comprehensive analysis with charts)
- Symbol Report (818+ symbols analyzed)

## Next Steps

No further action needed. The deprecated format has been completely replaced and archived for reference.

## Files Modified

- ✅ Created: `scripts/archived/send_discord_report_v1_simple_embed.py`
- ✅ Created: `scripts/archived/DEPRECATED_README.md`
- ✅ Created: `DEPRECATION_SUMMARY.md` (this file)
- ✅ Updated: VPS to commit 83009ae

## Verification

To verify only the new format is running:
```bash
# Check next scheduled run at 00:00 or 12:00 UTC
ssh vps "tail -f ~/crypto-perps-tracker/data/discord_reports.log"
```

The new format will show:
- "Generating Discord Market Report..."
- "Generating charts..."
- "4/4 charts generated"
- "Market Report Bot" username in Discord
