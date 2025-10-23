# Trading Strategy Alert System

**Automated detection of optimal trading conditions across 10 different strategies**

The strategy alert system analyzes real-time data from 8 exchanges and identifies when market conditions are optimal for specific trading strategies. Each strategy has quantifiable conditions and a confidence score (0-100%).

---

## 📊 Overview

**Strategies Monitored:** 11
**Exchanges Analyzed:** 8 (Binance, OKX, Bybit, Gate.io, Bitget, HyperLiquid, AsterDEX, dYdX v4)
**Alert Threshold:** 50% minimum confidence
**Update Frequency:** Configurable (recommended: every 4 hours)

---

## 🎯 Detected Strategies

### 1. Range Trading
**Best for:** Sideways markets with defined ranges (hours to days holding period)

**Conditions:**
- ✅ Neutral market sentiment (-0.2 to 0.2 composite score)
- ✅ Moderate volatility (3-6% 24h change) - enough movement for profitable ranges
- ✅ Balanced conviction (OI/Vol ratio 0.3-0.5x) - positions held longer
- ✅ Exchange consensus (funding divergence < 0.005)

**Confidence Calculation:** 25% per condition (100% max if all met)

**Strategy:**
- Buy at support, sell at resistance
- Hold positions hours to days
- Target 2-5% profit per trade
- Use defined risk management at range boundaries

**Risk Level:** Low-Medium (ranges can break)

**Typical Holding Time:** 4-48 hours

---

### 2. Scalping
**Best for:** Ultra-tight ranges with high liquidity (seconds to minutes holding period)

**Conditions:**
- ✅ Very neutral market (-0.15 to 0.15 composite score)
- ✅ Very low volatility (< 3% 24h change) - ultra-tight ranges
- ✅ High churn (OI/Vol ratio 0.2-0.35x) - day trading activity
- ✅ Very tight spreads (funding divergence < 0.003)
- ✅ High liquidity ($200B+ total volume) - minimal slippage

**Confidence Calculation:**
- Very neutral: 20%
- Very low volatility: 25%
- High churn: 25%
- Very tight spreads: 20%
- High liquidity: 10%

**Strategy:**
- Capture tiny price movements (0.1-0.5%)
- Hold seconds to minutes
- Very high frequency (many trades per day)
- Requires tight bid-ask spreads and deep liquidity
- Low latency execution critical

**Risk Level:** Low (tiny stops, quick exits)

**Typical Holding Time:** 10 seconds to 5 minutes

---

### 3. Trend Following
**Best for:** Strong directional markets with momentum

**Conditions:**
- ✅ Strong directional bias (|composite score| > 0.5)
- ✅ Funding and price aligned (same direction)
- ✅ High conviction (OI/Vol > 0.4)
- ✅ Exchange consensus (divergence < 0.003)

**Confidence Calculation:**
- Strong bias: 30%
- Aligned signals: 30%
- High conviction: 20%
- Consensus: 20%

**Strategy:**
- Enter in trend direction
- Use trailing stops
- Scale into positions
- Hold until trend breaks

**Risk Level:** Medium (trend reversals can be sharp)

---

### 4. Funding Rate Arbitrage
**Best for:** Market-neutral income generation

**Conditions:**
- ✅ High annualized yield available (> 8%)
- ✅ Multiple opportunities (≥ 3 pairs)
- ✅ Diversification possible (≥ 2 high-yield opportunities)

**Confidence Calculation:** Best yield × 5 (capped at 100%)

**Strategy:**
- Short high-funding exchange + Long low-funding exchange
- Delta-neutral position (no directional risk)
- Collect funding rate spread every 8 hours
- Diversify across top 3 opportunities

**Risk Level:** Very Low (market-neutral, main risk is exchange divergence)

---

### 5. Contrarian Play
**Best for:** Overextended markets due for reversal

**Conditions:**
- ⚠️ Extreme sentiment (|composite score| > 0.7)
- ⚠️ Funding/price divergence (opposite directions)
- ⚠️ High exchange disagreement (divergence > 0.008)
- ⚠️ Extreme conviction (OI/Vol > 0.6 or < 0.2)

**Confidence Calculation:** 25% per condition (need ≥2 for alert)

**Strategy:**
- Fade the extreme move
- Use VERY tight stops
- Small position sizes
- Quick profit-taking

**Risk Level:** HIGH (fighting the trend, can face strong momentum)

---

### 6. Mean Reversion
**Best for:** Markets showing signs of exhaustion

**Conditions:**
- ✅ Moderate sentiment (0.3 < |score| < 0.6)
- ✅ Funding/price divergence (confusion signals)
- ✅ Recent volatility (> 3% price change)
- ✅ Balanced conviction (0.3-0.5x OI/Vol)

**Confidence Calculation:**
- Moderate sentiment: 30%
- Divergence: 40%
- Volatility: 20%
- Balanced conviction: 10%

**Strategy:**
- Trade against recent price move
- Target previous range levels
- Use support/resistance as exits
- Risk management critical

**Risk Level:** Medium (momentum can continue)

---

### 7. Breakout Trading 🆕
**Best for:** Coiled spring markets ready to explode

**Conditions:**
- ✅ Low current volatility (< 4% but building pressure)
- ✅ Rising conviction (OI/Vol > 0.4) - positions accumulating
- ✅ Consolidating price (|score| < 0.3)
- ✅ Exchange agreement (divergence < 0.004)

**Confidence Calculation:**
- Low volatility: 25%
- Building OI: 30%
- Consolidation: 25%
- Agreement: 20%

**Strategy:**
- Set buy-stops above resistance
- Set sell-stops below support
- Trail stops quickly once breakout confirmed
- Watch for volume spike

**Risk Level:** Medium (false breakouts common)

---

### 8. Liquidation Cascade Risk 🆕
**Best for:** Risk management AND counter-positioning opportunity

**Conditions:**
- ⚠️ Extreme leverage (OI/Vol > 0.6)
- ⚠️ Extreme funding (|funding| > 0.015%)
- ⚠️ Strong directional bias (|score| > 0.4)
- ⚠️ High volatility (> 5% price change)

**Confidence Calculation:** 25% per condition (need ≥3 for alert)

**Strategy:**
- **If long:** Reduce leverage OR take profits
- **If opposite:** Counter-position with tight stops (risky!)
- Watch for cascade trigger points
- Extreme volatility likely

**Risk Level:** VERY HIGH (cascades are violent and fast)

**Note:** This is primarily a RISK ALERT to warn traders of dangerous leverage conditions

---

### 9. Volatility Expansion 🆕
**Best for:** Options-style strategies in confused markets

**Conditions:**
- ✅ Compressed volatility (< 3% current)
- ✅ High exchange disagreement (divergence > 0.006)
- ✅ Signal divergence (funding vs price > 0.5 difference)
- ✅ Positions building (0.35-0.6x OI/Vol)

**Confidence Calculation:**
- Compressed vol: 30%
- High divergence: 30%
- Signal divergence: 25%
- Positions building: 15%

**Strategy:**
- Straddle/strangle positions (profit from move in either direction)
- Wide bracket orders
- Expect volatility spike
- Direction unclear - profit from magnitude not direction

**Risk Level:** Medium (requires volatility expansion to profit)

---

### 10. Momentum Breakout 🆕
**Best for:** Accelerating trends with expanding participation

**Different from Trend Following:** Focuses on ACCELERATION not established trends

**Conditions:**
- ✅ Strong recent move (> 5% price change)
- ✅ Expanding participation (OI/Vol > 0.45)
- ✅ STRONGLY aligned signals (funding/price both extreme same direction)
- ✅ Universal confirmation (divergence < 0.003)

**Confidence Calculation:**
- Strong move: 30%
- Expanding OI: 30%
- Strong alignment: 25%
- Universal confirmation: 15%

**Strategy:**
- Ride momentum with wide stops
- Take partial profits along the way
- New participants joining = fuel for continuation
- Exit when OI stops expanding

**Risk Level:** Medium-High (parabolic moves can reverse quickly)

---

### 11. Delta Neutral / Market Making 🆕
**Best for:** Passive income in stable, low-volatility markets

**Conditions:**
- ✅ Very low volatility (< 2% price change)
- ✅ Neutral sentiment (-0.15 to 0.15)
- ✅ Low funding rates (< 0.01%) - cheap carry cost
- ✅ Stable OI (0.3-0.5x) - not too much churn
- ✅ Tight spreads (divergence < 0.003)

**Confidence Calculation:**
- Very low vol: 25%
- Neutral: 25%
- Cheap carry: 25%
- Stable OI: 15%
- Tight spreads: 10%

**Strategy:**
- Market making (provide liquidity, capture spreads)
- Basis trading (spot vs futures arbitrage)
- Yield farming with minimal risk
- Delta-neutral positions

**Risk Level:** Very Low (most conservative strategy)

---

## 🔔 Alert Configuration

### Setup Discord Alerts

**Edit `config/config.yaml`:**
```yaml
discord:
  enabled: true
  webhook_url: "YOUR_DISCORD_WEBHOOK_URL"
  report_interval: 14400  # 4 hours in seconds
```

### Manual Check
```bash
python3 scripts/strategy_alerts.py
```

### Automated Monitoring (Recommended)

**Add to crontab:**
```bash
# Check every 4 hours
0 */4 * * * cd ~/Desktop/crypto-perps-tracker && python3 scripts/strategy_alerts.py >> data/strategy_alerts.log 2>&1

# Or every 2 hours for more frequent updates
0 */2 * * * cd ~/Desktop/crypto-perps-tracker && python3 scripts/strategy_alerts.py >> data/strategy_alerts.log 2>&1
```

---

## 📊 Understanding Confidence Scores

**90-100%:** Extremely high confidence - all conditions perfectly met
**70-89%:** High confidence - most conditions met
**50-69%:** Moderate confidence - key conditions met (minimum for alert)
**Below 50%:** Low confidence - conditions not met (no alert sent)

---

## 🎨 Discord Alert Format

**Main Embed:**
- Strategy name and confidence %
- Full recommendation text
- Conditions checklist (✅/❌)
- Key metrics

**Additional Embeds:**
- Other viable strategies (if any)
- Top arbitrage opportunities (for funding arb strategy)
- Low-risk opportunities (for delta neutral strategy)

---

## 📈 Multi-Factor Sentiment Analysis

The system uses a **5-factor weighted composite score** (-1.0 to +1.0):

1. **Funding Rate** (40% weight) - Long/short bias
2. **Price Momentum** (25% weight) - Recent directional move
3. **Conviction** (15% weight) - OI/Vol ratio (position holding)
4. **Exchange Agreement** (10% weight) - Funding divergence
5. **OI-Price Correlation** (10% weight) - Position flow analysis

**Interpretation:**
- **> 0.3:** Bullish bias
- **-0.3 to 0.3:** Neutral
- **< -0.3:** Bearish bias

---

## 🔍 Example Alert Output

```
🚨 2 STRATEGY ALERT(S) DETECTED!

================================================================================

1. Range Trading - Confidence: 100%
--------------------------------------------------------------------------------
✅ OPTIMAL for range trading
• Clear range established (volatility: 3.03%)
• Neutral bias (score: 0.168)
• Buy support, sell resistance
• Hold hours to days, target 2-5% per trade


2. Funding Rate Arbitrage - Confidence: 51%
--------------------------------------------------------------------------------
✅ OPTIMAL for funding arbitrage
• Best yield: 10.21% annualized
• 6 opportunities available
• Low-risk market-neutral strategy
• Diversify across top 3 spreads

================================================================================
```

---

## ⚙️ Technical Details

**Data Sources:**
- Real-time aggregation from 8 exchanges
- Volume-weighted metrics
- Full OI coverage (615 Binance pairs)

**Performance:**
- Analysis runtime: 20-30 seconds
- Parallel API fetching
- Rate-limit compliant

**Reliability:**
- Error handling on all API calls
- Fallback for missing data
- Minimum confidence threshold prevents false alerts

---

## 🚀 Advanced Usage

### Backtesting Strategy Performance

Track historical alerts in `data/strategy_alerts.log` and correlate with actual market moves to validate strategy accuracy.

### Custom Thresholds

Modify detection thresholds in `strategy_alerts.py`:
- Volatility thresholds
- OI/Vol ratio ranges
- Funding rate extremes
- Confidence minimums

### Integration with Trading Bots

The alert system can be integrated with automated trading systems:
```python
from strategy_alerts import analyze_all_strategies
from generate_market_report import fetch_all_enhanced

# Get current strategy alerts
results = fetch_all_enhanced()
alerts = analyze_all_strategies(results)

# Execute trades based on alerts
for alert in alerts:
    if alert['strategy'] == 'Range Trading / Scalping' and alert['confidence'] >= 80:
        # Execute range trading logic
        pass
```

---

## 📝 Changelog

**v2.1 (October 2025):**
- ✅ Separated Range Trading and Scalping into distinct strategies
- ✅ Added timeframe-specific criteria (Range: hours-days, Scalping: seconds-minutes)
- ✅ Enhanced scalping detector with liquidity requirements
- ✅ Total strategies: 11 (up from 10)

**v2.0 (October 2025):**
- ✅ Added 5 new advanced strategies (Breakout, Liquidation Risk, Volatility Expansion, Momentum, Delta Neutral)
- ✅ Fixed datetime deprecation warnings
- ✅ Enhanced Discord integration
- ✅ Improved confidence scoring

**v1.0 (October 2025):**
- ✅ Initial release with 5 core strategies
- ✅ Discord webhook integration
- ✅ Multi-factor sentiment analysis

---

**Built for:** Crypto Perps Tracker
**Last Updated:** October 22, 2025
**Strategy Count:** 11
**Confidence Threshold:** 50% minimum
