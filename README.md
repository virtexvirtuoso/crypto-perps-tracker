# Crypto Perps Tracker

**Real-time monitoring and analytics for cryptocurrency perpetual futures markets**

Track 91.7% of the global perpetual futures market across 8 major exchanges with comprehensive metrics including volume, open interest, funding rates, and market sentiment.

---

## 🎯 Overview

Crypto Perps Tracker provides real-time data aggregation and analysis for perpetual futures trading across the top centralized (CEX) and decentralized (DEX) exchanges.

### Exchanges Covered

**Centralized Exchanges (CEX):**
- Binance ($92B/day) - #1 globally
- OKX ($42B/day) - #2 globally
- Bybit ($36B/day) - #3 globally
- Gate.io ($28B/day) - #4 globally
- Bitget ($16B/day) - #5 globally

**Decentralized Exchanges (DEX):**
- HyperLiquid ($12B/day) - Leading on-chain perps
- AsterDEX ($12B/day) - High-performance DEX
- dYdX v4 ($260M/day) - Historical DEX leader

### Market Coverage
- **Total Volume Tracked:** $238B/day
- **Market Share:** 91.7% of global perpetual futures
- **Total Markets:** 3,409 trading pairs
- **Total Trades:** 254M+ daily

---

## 📊 Metrics Tracked

### Priority 1 Metrics (Available Now)
- ✅ **24h Trading Volume** - Market size and liquidity
- ✅ **Open Interest (OI)** - Total position exposure (Full coverage: 7/8 exchanges, 615 Binance pairs)
- ✅ **Funding Rate** - Long/short sentiment indicator
- ✅ **OI/Volume Ratio** - Trading behavior (day trading vs position holding)
- ✅ **24h Price Change %** - Market momentum
- ✅ **Number of Trades** - Activity validation (where available)

### Calculated Analytics
- Market sentiment (via funding rates)
- Trading style analysis (via OI/Vol ratios)
- CEX vs DEX volume distribution
- Exchange rankings by volume and OI

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Internet connection (no API keys required for public data)

### Installation

```bash
# Clone or download the project
cd ~/Desktop/crypto-perps-tracker

# Install dependencies
pip install -r requirements.txt
```

### Usage

**Compare all 8 exchanges:**
```bash
python scripts/compare_all_exchanges.py
```

**Fetch individual exchange data:**
```bash
python scripts/fetch_bitget.py
python scripts/fetch_gateio.py
python scripts/fetch_asterdex.py
python scripts/fetch_okx.py
```

**Analyze specific coins (BTC, ETH, SOL) across all exchanges:**
```bash
python scripts/analyze_coins.py
```

**Per-Coin Analysis Includes:**
- 💰 Price comparison & spread detection
- 📊 Volume & OI distribution by exchange
- 💸 Funding rate arbitrage opportunities
- 🎯 Best exchange for each coin
- ⚠️ Arbitrage alerts for significant spreads

**Generate comprehensive market report:**
```bash
python scripts/generate_market_report.py
```

**What the Market Report Includes:**
- 📊 **Executive Summary** - Total volume, OI, market sentiment
- 💭 **Sentiment Analysis** - Volume-weighted funding rates, market direction
- 🏆 **Market Dominance** - Exchange rankings, CEX vs DEX distribution, HHI concentration
- 📈 **Trading Patterns** - Day-trading vs position holding behavior
- 💰 **Arbitrage Opportunities** - Funding rate spreads with annualized yields
- ⚠️ **Anomaly Detection** - Potential wash trading, extreme funding rates
- 🎯 **Actionable Recommendations** - Trade ideas based on current conditions
- 📝 **Auto-saved Reports** - Timestamped files in `data/` directory

**Send reports to Discord (automated):**
```bash
# Send once
python scripts/send_discord_report.py

# Automate every 12 hours (add to crontab)
0 */12 * * * cd ~/Desktop/crypto-perps-tracker && ./scripts/schedule_discord_reports.sh
```

**Discord Features:**
- 🎨 Rich embeds with color-coded sentiment (green/red/white)
- 📱 Mobile-friendly formatting
- 🔔 Automated scheduling (configurable interval)
- 💰 Instant arbitrage opportunity alerts
- 📊 Historical reports searchable in Discord

**Setup:** See [`docs/DISCORD_INTEGRATION.md`](docs/DISCORD_INTEGRATION.md) for complete guide

---

## 📁 Project Structure

```
crypto-perps-tracker/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .gitignore                  # Git ignore rules
├── config/
│   └── config.yaml             # Configuration settings
├── scripts/
│   ├── compare_all_exchanges.py      # Main comparison script (8 exchanges)
│   ├── generate_market_report.py     # Comprehensive market analysis & report
│   ├── send_discord_report.py        # Discord webhook integration
│   ├── schedule_discord_reports.sh   # Automation scheduler for Discord
│   ├── analyze_coins.py              # Per-coin analysis (BTC, ETH, SOL)
│   ├── fetch_bitget.py              # Individual exchange fetchers
│   ├── fetch_gateio.py
│   ├── fetch_asterdex.py
│   └── fetch_okx.py
├── data/                        # Data storage (local cache, exports)
└── docs/                        # Additional documentation
    └── API_ENDPOINTS.md        # API endpoint reference
```

---

## 📈 Sample Output

```
==============================================================================
                    ENHANCED PERPETUAL FUTURES EXCHANGE COMPARISON
                            Updated: 2025-10-22 18:00:16 UTC
==============================================================================

#  Exchange      Type 24h Volume      Open Interest   Funding  OI/Vol  Δ Price  Markets
--------------------------------------------------------------------------------------
1  Binance       CEX  $ 91.2B        $20.9B         0.0086%    0.23x  -3.76%   615
2  OKX           CEX  $ 42.4B              N/A       0.0042%      N/A  -3.80%   263
3  Bybit         CEX  $ 36.0B        $14.2B         0.0069%    0.39x  -3.78%   644
4  Gate.io       CEX  $ 27.5B        $13.7B         0.0047%    0.50x  -3.79%   591
5  Bitget        CEX  $ 16.4B        $ 7.2B         0.0062%    0.44x  -3.76%   590
6  HyperLiquid   DEX  $ 12.3B        $ 7.1B         0.0013%    0.58x  -3.74%   218
7  AsterDEX      DEX  $ 12.3B              N/A            N/A     N/A  -3.73%   204
8  dYdX v4       DEX  $  0.26B        $ 0.12B        0.0007%    0.47x  -3.95%   284

Total Volume: $238.3B | Total OI: $63.2B | CEX: 89.6% | DEX: 10.4%
```

---

## 🔍 Use Cases

### For Traders
- **Market Reports:** Auto-generated analysis with arbitrage opportunities & sentiment
- **Funding Rate Arbitrage:** Identify spreads up to 10% annualized yield
- **Sentiment Tracking:** Volume-weighted funding rates for market direction
- **Trading Pattern Analysis:** Find exchanges with day-trading vs conviction behavior
- **Daily Briefing:** Automated reports for morning trading preparation

### For Analysts
- **Market Research:** Track volume and OI trends
- **Exchange Comparison:** Benchmark exchange performance
- **Trading Style Analysis:** Understand day trading vs position holding patterns
- **Wash Trading Detection:** Use OI/Vol ratios to identify suspicious activity

### For Developers
- **Data Integration:** Clean API access to 8 exchanges
- **Alerting Systems:** Build custom notifications
- **Backtesting:** Historical market data
- **Dashboard Building:** Pre-aggregated market metrics

---

## 🛠️ Technical Details

### API Endpoints Used

| Exchange | Endpoint | Rate Limit | Authentication |
|----------|----------|------------|----------------|
| Binance | `fapi.binance.com/fapi/v1` | 2400/min | Not required |
| Bybit | `api.bybit.com/v5/market` | 600/min | Not required |
| OKX | `api.okx.com/api/v5/market` | 300/min | Not required |
| Bitget | `api.bitget.com/api/mix/v1` | 600/min | Not required |
| Gate.io | `api.gateio.ws/api/v4/futures` | 900/min | Not required |
| HyperLiquid | `api.hyperliquid.xyz/info` | No limit | Not required |
| AsterDEX | `fapi.asterdex.com/fapi/v1` | 1200/min | Not required |
| dYdX v4 | `indexer.dydx.trade/v4` | No limit | Not required |

### Performance
- **Parallel Execution:** Fetches all 8 exchanges simultaneously
- **Typical Runtime:** 20-30 seconds (including full OI coverage for 615 Binance pairs)
- **Data Freshness:** Real-time (< 1 second old)
- **OI Coverage:** Full coverage using parallel API calls (ThreadPoolExecutor with 30 workers)

---

## 📝 Metrics Explained

### Funding Rate
- **What:** Hourly rate longs pay shorts (or vice versa)
- **Range:** Typically -0.05% to +0.1%
- **Bullish:** > +0.01% (longs paying shorts)
- **Bearish:** < -0.01% (shorts paying longs)
- **Neutral:** ±0.01%

### OI/Volume Ratio
- **What:** Open Interest ÷ Daily Volume
- **Low (0.1-0.3x):** Heavy day trading, high churn
- **Medium (0.3-0.5x):** Balanced trading
- **High (0.5x+):** Position holding, conviction trades

### Open Interest
- **What:** Total value of all open positions
- **Growing OI + Rising Price:** Bullish (new longs)
- **Growing OI + Falling Price:** Bearish (new shorts)
- **Declining OI:** Position unwinding

**Implementation:**
- **Binance:** Full coverage (615 pairs via parallel API calls)
- **OKX:** Full coverage (single bulk endpoint)
- **Bybit, Gate.io, Bitget:** Full coverage (included in ticker response)
- **HyperLiquid, dYdX v4:** Full coverage (included in asset context)
- **AsterDEX:** Not available (API limitation)

---

## 🎯 Roadmap

### Phase 1: Core Functionality ✅ (Complete)
- [x] 8-exchange data aggregation
- [x] Enhanced metrics (Volume, OI, Funding, etc.)
- [x] Real-time comparison

### Phase 2: Automation (Next)
- [ ] Automated hourly tracking (cron job)
- [ ] SQLite database for historical data
- [ ] Data export (CSV, JSON)

### Phase 3: Alerts & Analysis
- [ ] Funding rate alerts (>0.1% or <-0.05%)
- [ ] Arbitrage scanner (price discrepancies >0.1%)
- [ ] Volume spike detection
- [ ] OI change notifications

### Phase 4: Visualization
- [ ] Web dashboard
- [ ] Real-time charts
- [ ] Historical trends
- [ ] Exchange rankings over time

---

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

### Areas for Improvement
- Additional exchanges (MEXC, KuCoin, etc.)
- More metrics (liquidations, long/short ratios, etc.)
- Historical data analysis
- Machine learning predictions
- Alert systems

---

## ⚠️ Disclaimer

This tool is for informational purposes only. Always verify data with official exchange sources before making trading decisions. Cryptocurrency trading carries significant risk.

---

## 📄 License

MIT License - Feel free to use and modify

---

## 🔗 Related Projects

- **Virtuoso_ccxt** - Main trading system project
- Located at: `/Users/ffv_macmini/Desktop/Virtuoso_ccxt`

---

## 📞 Support

For issues or questions:
1. Check the `docs/` folder for additional documentation
2. Review API endpoint documentation
3. Verify network connectivity to exchanges

---

**Built with Python 3.11 | Last Updated: October 2025**
