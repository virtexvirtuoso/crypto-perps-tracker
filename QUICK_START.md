# Quick Start Guide

Get up and running with Crypto Perps Tracker in 5 minutes!

---

## ⚡ Fastest Path

```bash
# Navigate to project
cd ~/Desktop/crypto-perps-tracker

# Install dependencies (only need requests)
pip3 install requests

# Run the complete 8-exchange comparison
python3 scripts/compare_all_exchanges.py
```

That's it! You'll see real-time data from 8 exchanges.

---

## 📊 What You'll See

```
==================================================================
        ENHANCED PERPETUAL FUTURES EXCHANGE COMPARISON
                Updated: 2025-10-22 18:13:33 UTC
==================================================================

#  Exchange      Type 24h Volume    Open Interest  Funding  OI/Vol
-------------------------------------------------------------------
1  Binance       CEX  $ 90.6B      $20.9B        0.0092%   0.23x
2  OKX           CEX  $ 42.1B           N/A      0.0050%     N/A
3  Bybit         CEX  $ 35.8B      $14.2B        0.0069%   0.40x
4  Gate.io       CEX  $ 27.7B      $13.8B        0.0056%   0.50x
5  Bitget        CEX  $ 16.3B      $ 7.2B        0.0078%   0.44x
6  HyperLiquid   DEX  $ 12.2B      $ 7.1B        0.0013%   0.58x
7  AsterDEX      DEX  $ 12.2B           N/A           N/A     N/A
8  dYdX v4       DEX  $  0.26B     $ 0.12B       0.0001%   0.47x

Total Volume: $237B | Total OI: $63.2B | Markets: 3,409
```

---

## 🎯 Individual Exchange Scripts

Fetch data from a single exchange:

```bash
# Bitget (CEX #5)
python3 scripts/fetch_bitget.py

# Gate.io (CEX #4)
python3 scripts/fetch_gateio.py

# AsterDEX (DEX #2)
python3 scripts/fetch_asterdex.py

# OKX (CEX #2)
python3 scripts/fetch_okx.py
```

---

## 📖 Understanding the Output

### Key Metrics

**24h Volume**
- Total trading volume in last 24 hours
- Indicator of liquidity and activity

**Open Interest (OI)**
- Total value of all open positions
- Shows market exposure and leverage

**Funding Rate**
- Hourly rate longs pay shorts (or vice versa)
- **> +0.01%** = Bullish sentiment (longs paying)
- **< -0.01%** = Bearish sentiment (shorts paying)
- **±0.01%** = Neutral

**OI/Vol Ratio**
- Open Interest ÷ Daily Volume
- **0.1-0.3x** = Heavy day trading
- **0.3-0.5x** = Balanced
- **0.5x+** = Position holding (conviction trades)

---

## 🔧 Troubleshooting

### Script Not Running?

```bash
# Make sure you're in the right directory
cd ~/Desktop/crypto-perps-tracker

# Check if scripts are executable
chmod +x scripts/*.py

# Verify requests is installed
pip3 list | grep requests
```

### Geo-Restricted?

Some exchanges block certain regions. If you see errors:

```bash
# Run from VPS instead
ssh vps
cd /tmp
# Copy scripts and run there
```

### Slow Performance?

The script fetches data from 8 exchanges simultaneously with FULL Open Interest coverage:
- Normal runtime: 20-30 seconds
- Includes 615 parallel OI API calls for Binance (full coverage)
- Additional OI calls for other exchanges
- Be patient - comprehensive data takes time!

---

## 📝 Next Steps

1. **Read the README:** `README.md` for full documentation
2. **Check API Docs:** `docs/API_ENDPOINTS.md` for endpoint details
3. **Customize Config:** `config/config.yaml` for settings
4. **Explore Scripts:** Look at `scripts/` for examples

---

## 🎯 Common Use Cases

### Monitor Market Sentiment
```bash
# Run hourly via cron
*/60 * * * * cd ~/Desktop/crypto-perps-tracker && python3 scripts/compare_all_exchanges.py >> data/hourly.log
```

### Quick Market Check
```bash
# Add alias to .zshrc or .bashrc
alias perps="cd ~/Desktop/crypto-perps-tracker && python3 scripts/compare_all_exchanges.py"

# Then just type:
perps
```

### Save Output
```bash
# Save to file with timestamp
python3 scripts/compare_all_exchanges.py > data/snapshot_$(date +%Y%m%d_%H%M%S).txt
```

### Daily Market Reports
```bash
# Generate comprehensive report with analysis
python3 scripts/generate_market_report.py

# Automated daily report at 8 AM (add to crontab)
0 8 * * * cd ~/Desktop/crypto-perps-tracker && python3 scripts/generate_market_report.py >> data/daily_reports.log 2>&1

# Email yourself the report (macOS/Linux)
python3 scripts/generate_market_report.py | mail -s "Daily Crypto Perps Report" your@email.com
```

### Quick Arbitrage Check
```bash
# Generate report and filter for arbitrage opportunities only
python3 scripts/generate_market_report.py | grep -A 20 "ARBITRAGE OPPORTUNITIES"
```

---

## 💡 Pro Tips

1. **First run** takes 10-15 seconds (fetching OI data)
2. **Funding rates** update every 8 hours typically
3. **Volume resets** at 00:00 UTC daily
4. **OI changes** indicate market direction
5. **Compare OI/Vol** across exchanges to spot wash trading

---

## 🆘 Getting Help

1. Check `README.md` for detailed docs
2. Review `docs/API_ENDPOINTS.md` for API info
3. Verify internet connection
4. Try running from VPS if geo-restricted

---

**Ready to track 91.7% of the global perpetual futures market!** 🚀
