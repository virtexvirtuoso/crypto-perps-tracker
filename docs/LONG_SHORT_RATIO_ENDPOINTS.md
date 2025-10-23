# Long/Short Ratio API Endpoints

## Data Availability by Exchange

### ✅ Binance (Multiple Endpoints)

**1. Global Long/Short Account Ratio**
```
GET /fapi/v1/globalLongShortAccountRatio
```
- **What:** Percentage of accounts that are net long vs net short
- **Parameters:** `symbol`, `period` (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
- **Example:** BTCUSDT, period=1h
- **Response:**
```json
[
  {
    "symbol": "BTCUSDT",
    "longShortRatio": "1.5",  // 1.5 longs for every 1 short
    "longAccount": "0.60",     // 60% of accounts are long
    "shortAccount": "0.40",    // 40% of accounts are short
    "timestamp": 1583139600000
  }
]
```

**2. Top Trader Long/Short Position Ratio**
```
GET /fapi/v1/topLongShortPositionRatio
```
- **What:** Position volume ratio of top traders (top 20% by position size)
- **Better for:** Whale sentiment, smart money positioning
- **Same parameters as above**

**3. Top Trader Long/Short Account Ratio**
```
GET /fapi/v1/topLongShortAccountRatio
```
- **What:** Account ratio of top traders
- **Difference from #2:** Accounts vs position volume

---

### ✅ Bybit

**Long/Short Account Ratio**
```
GET /v5/market/account-ratio
```
- **Parameters:** `category=linear`, `symbol`, `period` (5min, 15min, 30min, 1h, 4h, 1d)
- **Response:**
```json
{
  "result": {
    "list": [
      {
        "symbol": "BTCUSDT",
        "buyRatio": "0.6234",   // 62.34% long
        "sellRatio": "0.3766",  // 37.66% short
        "timestamp": 1672051200000
      }
    ]
  }
}
```

---

### ✅ OKX

**Long/Short Account Ratio**
```
GET /api/v5/rubik/stat/contracts/long-short-account-ratio
```
- **Parameters:** `ccy` (e.g., BTC), `begin`, `end`, `period` (5m, 15m, 30m, 1H, 2H, 4H, 1D)
- **Response:**
```json
{
  "data": [
    {
      "ts": "1597026383085",
      "ratio": "1.5",  // Long/short ratio
      "longPer": "0.6",  // 60% long
      "shortPer": "0.4"  // 40% short
    }
  ]
}
```

---

### ❌ Gate.io
- No public long/short ratio endpoint
- Can infer from funding rates

### ❌ Bitget
- No public long/short ratio endpoint available

### ❌ HyperLiquid
- DEX - no centralized long/short tracking
- All positions are on-chain but would require significant processing

### ❌ dYdX v4
- DEX - positions are on-chain
- No centralized endpoint

---

## Implementation Recommendations

### Option 1: Add to Current Exchanges (Binance, Bybit, OKX)
**Coverage:** ~75% of market volume
**Data Points:** 3 major exchanges = good consensus

**Benefits:**
- Simple integration with existing fetchers
- Binance alone is 40% of market
- Can cross-validate across 3 sources

### Option 2: Focus on Binance Only (Quick Win)
**Coverage:** ~40% of market volume
**Data Points:** Multiple endpoints (global, top trader)

**Benefits:**
- Fastest to implement
- Most comprehensive data (3 different ratios)
- Can compare retail (global) vs whale (top trader) sentiment

---

## Data Interpretation

### Long/Short Ratio
```
Ratio = Longs / Shorts

1.0 = Equal (50% long, 50% short) - Neutral
2.0 = 2:1 longs (66% long, 33% short) - Bullish crowded
0.5 = 1:2 longs (33% long, 66% short) - Bearish crowded
```

### Contrarian Signals
- **Ratio > 3.0** (75%+ long) → Potential bearish reversal
- **Ratio < 0.33** (75%+ short) → Potential bullish reversal
- **Ratio 0.8-1.2** (45-55% long) → Balanced, no extreme

### Smart Money Divergence
```
If Global Ratio = 2.5 (retail bullish)
And Top Trader Ratio = 0.8 (whales bearish)
→ STRONG contrarian signal (fade retail)
```

---

## Integration with Current System

### Add as 6th Sentiment Factor

**Current 5 Factors:**
1. Funding Rate (40%)
2. Price Momentum (25%)
3. Conviction (15%)
4. Exchange Agreement (10%)
5. OI-Price Correlation (10%)

**Proposed 6-Factor System:**
1. Funding Rate (35%)
2. Price Momentum (20%)
3. **Long/Short Bias (15%)** ← NEW
4. Conviction (15%)
5. Exchange Agreement (8%)
6. OI-Price Correlation (7%)

### Long/Short Bias Scoring
```python
def score_long_short_bias(ratio: float) -> float:
    """
    Convert ratio to -1 to +1 score

    ratio > 2.0: Overextended long (bearish contrarian) = -0.5 to -1.0
    ratio 1.5-2.0: Moderately long = -0.3 to -0.5
    ratio 0.8-1.2: Balanced = -0.2 to +0.2
    ratio 0.5-0.8: Moderately short = +0.3 to +0.5
    ratio < 0.5: Overextended short (bullish contrarian) = +0.5 to +1.0
    """
    if ratio > 2.5:
        return max(-1.0, -0.5 - (ratio - 2.5) * 0.2)  # Bearish (too many longs)
    elif ratio > 1.5:
        return -0.3 - (ratio - 1.5) * 0.2
    elif ratio < 0.4:
        return min(1.0, 0.5 + (0.4 - ratio) * 2.0)  # Bullish (too many shorts)
    elif ratio < 0.67:
        return 0.3 + (0.67 - ratio) * 0.74
    else:
        # Balanced: ratio 0.8-1.2 maps to -0.2 to +0.2
        return (1.0 - ratio) * 0.2
```

---

## Proposed Display Format

### Market Report Addition
```
💭 MARKET SENTIMENT ANALYSIS

Overall Sentiment: 🟢 BULLISH (Moderate Signal)
Composite Score:   0.423 (Range: -1.0 to +1.0)

📊 Sentiment Factor Breakdown:
Factor                    Signal               Score    Weight   Value
─────────────────────────────────────────────────────────────────────────
Funding Rate             Bullish              0.432    35%      0.0086%
Price Momentum           Bullish              0.625    20%      +3.15%
★ Long/Short Bias        BEARISH (Crowded)   -0.680    15%      3.2:1 ratio  ← NEW
Conviction               Neutral              0.075    15%      0.37x
Exchange Agreement       Strong               0.800     8%      0.0023
OI-Price Correlation     Positive             0.500     7%      Rising

⚠️ CONTRARIAN WARNING: 76% of accounts are LONG (3.2:1 ratio)
   • Crowded long positions suggest potential reversal risk
   • Consider reducing leverage or taking profits
   • Monitor for liquidation cascade if price drops
```

### Strategy Alert Enhancement
```
🚨 CONTRARIAN PLAY DETECTED

Strategy: Contrarian Play (Fade the Crowd)
Confidence: 75%

Conditions Met:
✅ Extreme Long/Short Ratio (3.2:1 - 76% long)
✅ Divergence: Smart money ratio only 1.1:1 (whales not as bullish)
✅ High funding rate (0.012%) - longs paying premium
❌ Price not yet overextended

Recommendation:
⚠️ HIGH RISK CONTRARIAN SETUP
• 76% of traders are long (retail FOMO)
• Whales more balanced (smart money less bullish)
• Consider SHORT with tight stop above recent high
• Target 5-10% correction as overleveraged longs get shaken out
```

---

## Implementation Priority

**Phase 1: Binance Only (Quick Win)**
- Implement global long/short ratio
- Add to sentiment analysis as 6th factor
- Display in market reports
- Estimated time: 1-2 hours

**Phase 2: Add Bybit + OKX**
- Cross-exchange consensus
- Compare retail vs institutional exchanges
- Estimated time: 1-2 hours

**Phase 3: Strategy Enhancements**
- Add "Crowd Fade" strategy detector
- Enhance contrarian play with L/S ratio
- Smart money divergence alerts
- Estimated time: 2-3 hours

---

## Sample Implementation (Binance)

```python
def fetch_binance_long_short_ratio(symbol: str = "BTCUSDT", period: str = "1h") -> Dict:
    """
    Fetch Binance global long/short account ratio

    Returns:
        {
            'ratio': 1.5,        # Longs per short
            'long_pct': 0.60,    # 60% long
            'short_pct': 0.40,   # 40% short
            'timestamp': 1234567890
        }
    """
    try:
        response = requests.get(
            f"https://fapi.binance.com/fapi/v1/globalLongShortAccountRatio",
            params={"symbol": symbol, "period": period, "limit": 1},
            timeout=5
        ).json()

        if response:
            data = response[0]
            return {
                'ratio': float(data['longShortRatio']),
                'long_pct': float(data['longAccount']),
                'short_pct': float(data['shortAccount']),
                'timestamp': int(data['timestamp']),
                'status': 'success'
            }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
```

---

## Expected Impact

**Enhanced Sentiment Accuracy:**
- Current: 5-factor analysis (funding, price, OI, divergence, correlation)
- Enhanced: 6-factor with direct trader positioning
- Better contrarian signal detection

**New Strategy Opportunities:**
- "Fade the Crowd" strategy when ratio extreme
- Smart money divergence (compare global vs top trader)
- Liquidation cascade prediction (extreme ratio + high funding)

**Improved Reports:**
- Clear "% long vs % short" metrics
- Contrarian warnings when crowded
- Cross-exchange consensus on positioning

---

**Next Steps:**
1. Implement Binance long/short ratio fetcher
2. Integrate into `generate_market_report.py` sentiment analysis
3. Add display to market reports
4. Enhance contrarian strategy detector
5. Test with live data

Would you like me to proceed with implementation?
