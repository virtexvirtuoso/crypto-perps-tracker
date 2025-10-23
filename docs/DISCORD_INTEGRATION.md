# Discord Integration Guide

Send automated crypto perpetual futures market reports directly to your Discord server!

---

## 🎯 Features

- ✅ **Rich Embeds:** Beautiful formatted reports with color-coded sentiment
- ✅ **Automated Scheduling:** Every 12 hours (configurable)
- ✅ **Executive Summary:** Volume, OI, sentiment at a glance
- ✅ **Arbitrage Alerts:** Automated funding rate opportunity detection
- ✅ **Trading Recommendations:** AI-generated trade ideas
- ✅ **Anomaly Detection:** Wash trading and extreme conditions
- ✅ **Mobile-Friendly:** Perfect for Discord mobile app

---

## 🚀 Quick Setup

### Step 1: Create Discord Webhook

1. Open your Discord server
2. Go to **Server Settings** → **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Give it a name (e.g., "Crypto Perps Bot")
5. Select the channel where reports should be sent
6. Click **Copy Webhook URL**

### Step 2: Configure Webhook

Edit `config/config.yaml` and update the Discord section:

```yaml
discord:
  enabled: true
  webhook_url: "YOUR_WEBHOOK_URL_HERE"
  report_interval: 43200  # 12 hours in seconds
  username: "Crypto Perps Bot"
```

### Step 3: Test the Integration

```bash
# From project root
python3 scripts/send_discord_report.py
```

You should see: `✅ Successfully sent report to Discord!`

Check your Discord channel - you should see a beautiful formatted report!

---

## 📅 Automated Scheduling

### Option 1: Cron (Recommended for Linux/macOS)

Every 12 hours at 8 AM and 8 PM:
```bash
# Edit crontab
crontab -e

# Add this line:
0 8,20 * * * cd /Users/ffv_macmini/Desktop/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

Every 6 hours (more frequent):
```bash
0 */6 * * * cd /Users/ffv_macmini/Desktop/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

Custom schedule examples:
```bash
# Every day at 9 AM
0 9 * * * cd /path/to/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh

# Every Monday at 10 AM
0 10 * * 1 cd /path/to/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh

# Every 4 hours
0 */4 * * * cd /path/to/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

### Option 2: VPS Deployment

For 24/7 automated reports on your VPS:

```bash
# On VPS
cd /tmp/crypto-perps-tracker

# Test the integration
python3 scripts/send_discord_report.py

# Setup cron
crontab -e

# Add schedule (every 12 hours)
0 */12 * * * cd /tmp/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

### Option 3: Manual Trigger

Send a report anytime:
```bash
python3 scripts/send_discord_report.py
```

---

## ⚙️ Configuration Options

### Report Interval

Change frequency in `config/config.yaml`:

```yaml
discord:
  report_interval: 21600   # 6 hours
  # report_interval: 43200  # 12 hours (default)
  # report_interval: 86400  # 24 hours (daily)
```

### Customization

```yaml
discord:
  username: "My Custom Bot"     # Bot display name
  avatar_url: "https://..."     # Custom bot avatar (optional)
  mention_role: "1234567890"    # Mention a Discord role (optional)

  # Color scheme (hex values)
  color_scheme:
    bullish: 0x00FF00   # Green for bullish markets
    bearish: 0xFF0000   # Red for bearish markets
    neutral: 0xFFFFFF   # White for neutral
    alert: 0xFFA500     # Orange for alerts

  # Choose which sections to include
  include_sections:
    executive_summary: true
    sentiment_analysis: true
    arbitrage_opportunities: true
    trading_patterns: true
    recommendations: true
    anomalies: true
```

### Disable Discord

To temporarily disable without removing config:

```yaml
discord:
  enabled: false
```

---

## 📊 Report Format

### What's Included

**1. Executive Summary Embed**
- Total 24h volume across all exchanges
- Total open interest
- Markets tracked
- Overall market sentiment (Bullish/Bearish/Neutral)
- Average price change
- Volume-weighted funding rate

**2. Sentiment Analysis Embed**
- Overall market sentiment with interpretation
- Funding rates by exchange (BTC)
- Annualized cost/yield for each exchange

**3. Arbitrage Opportunities Embed** (if opportunities exist)
- Top 5 funding rate arbitrage opportunities
- Annual yield calculations
- Strategy descriptions
- Risk levels

**4. Trading Patterns Embed**
- Market dominance metrics (HHI concentration)
- CEX vs DEX distribution
- Top 3 market leaders with volumes
- Trading style categorization (day-trading vs position holding)

**5. Recommendations Embed**
- AI-generated trading recommendations based on:
  - Current sentiment
  - Arbitrage opportunities
  - Trading behavior patterns
  - Market anomalies

**6. Anomalies Embed** (if anomalies detected)
- Potential wash trading indicators
- Extreme funding rates
- Other market health warnings

---

## 🎨 Color Coding

Reports use color-coded embeds based on market conditions:

- 🟢 **Green (Bullish):** Funding rate >0.01% (longs paying shorts)
- 🔴 **Red (Bearish):** Funding rate <-0.01% (shorts paying longs)
- ⚪ **White (Neutral):** Funding rate between -0.01% and 0.01%
- 🟠 **Orange (Alert):** Arbitrage opportunities or anomalies

---

## 🔧 Troubleshooting

### Report Not Sending

**Check webhook URL:**
```bash
# Verify webhook in config
grep webhook_url config/config.yaml
```

**Test manually:**
```bash
python3 scripts/send_discord_report.py
```

**Check logs:**
```bash
tail -50 data/discord_reports.log
```

### Discord Returns Error 401

- Your webhook URL is invalid or expired
- Regenerate webhook in Discord server settings

### Discord Returns Error 429

- You're being rate limited
- Reduce report frequency
- Discord limit: ~30 requests per minute

### Missing Embeds

- Check `include_sections` in config
- Ensure sections are set to `true`
- Some sections only appear if data exists (e.g., anomalies)

### PyYAML Import Error

```bash
# Install PyYAML
pip3 install pyyaml

# Or with brew (macOS)
brew install pyyaml
```

---

## 📱 Mobile App

The Discord reports are optimized for mobile viewing:
- Install Discord mobile app
- Enable push notifications for the channel
- Get instant market alerts on your phone!

---

## 💡 Pro Tips

### 1. Create Dedicated Channel

Create a `#crypto-market-reports` channel in your Discord server for clean organization.

### 2. Role Mentions

Mention a role to notify specific users:
```yaml
discord:
  mention_role: "1234567890"  # Your role ID
```

Get role ID: Right-click role → Copy ID (need Developer Mode enabled)

### 3. Multiple Servers

Send to multiple Discord servers:
```bash
# Create separate config files
cp config/config.yaml config/config_server1.yaml
cp config/config.yaml config/config_server2.yaml

# Edit each with different webhook URLs
# Run with different configs:
python3 scripts/send_discord_report.py config/config_server1.yaml
```

### 4. Testing Schedule

Test your cron schedule:
```bash
# Run scheduler script manually
./scripts/schedule_discord_reports.sh

# Check log output
cat data/discord_reports.log
```

### 5. Timezone Considerations

Cron uses server time. For UTC scheduling on local machine:
```bash
# Show current timezone
date

# For UTC times, adjust accordingly:
# If you want 8 AM UTC and you're in EST (UTC-5):
# Use 3 AM EST = 8 AM UTC
0 3 * * * cd /path/to/project && ./scripts/schedule_discord_reports.sh
```

---

## 🔒 Security

**⚠️ Important Security Notes:**

1. **Keep Webhook URL Secret**
   - Never commit webhook URL to public Git repositories
   - Add `config/config.yaml` to `.gitignore` if sharing code
   - Regenerate webhook if accidentally exposed

2. **Limit Webhook Access**
   - Only share with trusted users
   - Anyone with webhook URL can post to your channel
   - Revoke and regenerate if compromised

3. **Server Permissions**
   - Ensure webhook has proper permissions
   - Verify channel access settings

---

## 📈 Log Monitoring

View recent report activity:
```bash
# Last 50 lines
tail -50 data/discord_reports.log

# Follow live
tail -f data/discord_reports.log

# Search for errors
grep "❌" data/discord_reports.log

# Count successful sends
grep "✅" data/discord_reports.log | wc -l
```

---

## 🎯 Example Use Cases

### Daily Morning Briefing
```bash
# 8 AM daily
0 8 * * * cd ~/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

### Trading Session Updates
```bash
# Before major trading sessions
0 0,8,16 * * * cd ~/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
# Midnight, 8 AM, 4 PM
```

### Weekend Summary
```bash
# Saturday at noon
0 12 * * 6 cd ~/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

### High-Frequency Monitoring
```bash
# Every 2 hours during market volatility
0 */2 * * * cd ~/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

---

## 🆘 Support

Issues with Discord integration?

1. Check this documentation
2. Verify webhook URL in Discord settings
3. Review logs: `data/discord_reports.log`
4. Test manually: `python3 scripts/send_discord_report.py`
5. Ensure PyYAML is installed: `python3 -c "import yaml"`

---

**Enjoy automated market intelligence delivered straight to Discord!** 🚀
