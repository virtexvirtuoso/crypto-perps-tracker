"""Market sentiment analysis

Analyzes market sentiment based on multiple factors:
- Funding rates
- Price momentum
- Long/short ratios
- Open interest dynamics
"""

from typing import Dict, List
import requests


def fetch_long_short_ratio() -> Dict:
    """Fetch BTC long/short ratio from OKX

    Returns:
        Dictionary with ratio data and status
    """
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
            params={"ccy": "BTC"},
            timeout=5
        ).json()

        if response.get('code') == '0' and response.get('data'):
            latest = response['data'][0]
            ratio = float(latest[1])

            long_pct = ratio / (ratio + 1)
            short_pct = 1 / (ratio + 1)

            return {
                'ratio': ratio,
                'long_pct': long_pct,
                'short_pct': short_pct,
                'timestamp': int(latest[0]),
                'source': 'OKX',
                'status': 'success'
            }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def analyze_market_sentiment(results: List[Dict]) -> Dict:
    """Enhanced multi-factor sentiment analysis

    Analyzes market sentiment using 6 factors:
    1. Funding rates (35% weight)
    2. Price momentum (20% weight)
    3. Long/short bias (15% weight)
    4. OI/Volume ratio (15% weight)
    5. Funding divergence (8% weight)
    6. OI-Price correlation (7% weight)

    Args:
        results: List of market data dictionaries from exchanges

    Returns:
        Dictionary with sentiment analysis including:
        - composite_score: -1 to 1 (bearish to bullish)
        - sentiment: "BULLISH", "BEARISH", or "NEUTRAL"
        - strength: "STRONG", "MODERATE", "WEAK", or "NEUTRAL"
        - factors: Breakdown of each factor's contribution
    """
    successful = [r for r in results if r.get('status') == 'success']
    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

    # FACTOR 1: Funding Rate
    weighted_funding = 0
    funding_exchanges = []
    funding_rates = []

    for r in successful:
        if r.get('funding_rate') is not None:
            weight = r['volume'] / total_volume
            weighted_funding += r['funding_rate'] * weight
            funding_exchanges.append({
                'exchange': r['exchange'],
                'rate': r['funding_rate'],
                'weight': weight
            })
            funding_rates.append(r['funding_rate'])

    if weighted_funding > 0.01:
        funding_score = min(weighted_funding / 0.05, 1.0)
        funding_signal = "🟢 BULLISH"
    elif weighted_funding < -0.01:
        funding_score = max(weighted_funding / 0.05, -1.0)
        funding_signal = "🔴 BEARISH"
    else:
        funding_score = weighted_funding / 0.01
        funding_signal = "⚪ NEUTRAL"

    # FACTOR 2: Price Momentum
    weighted_price_change = 0
    price_changes = []

    for r in successful:
        if r.get('price_change_pct') is not None:
            weight = r['volume'] / total_volume
            weighted_price_change += r['price_change_pct'] * weight
            price_changes.append(r['price_change_pct'])

    if weighted_price_change > 2.0:
        price_score = min(weighted_price_change / 10.0, 1.0)
        price_signal = "🟢 RISING"
    elif weighted_price_change < -2.0:
        price_score = max(weighted_price_change / 10.0, -1.0)
        price_signal = "🔴 FALLING"
    else:
        price_score = weighted_price_change / 2.0
        price_signal = "⚪ STABLE"

    # FACTOR 3: OI/Volume Ratio
    market_oi_vol_ratio = total_oi / total_volume if total_volume > 0 else 0

    if market_oi_vol_ratio > 0.5:
        conviction_score = min((market_oi_vol_ratio - 0.3) / 0.3, 1.0)
        conviction_signal = "🎯 HIGH CONVICTION"
    elif market_oi_vol_ratio < 0.25:
        conviction_score = -min((0.25 - market_oi_vol_ratio) / 0.15, 1.0)
        conviction_signal = "📊 SPECULATION"
    else:
        conviction_score = 0
        conviction_signal = "⚖️ BALANCED"

    # FACTOR 4: Funding Divergence
    if len(funding_rates) > 1:
        funding_std = (sum((x - weighted_funding) ** 2 for x in funding_rates) / len(funding_rates)) ** 0.5
        divergence_score = -min(funding_std / 0.01, 1.0)

        if funding_std < 0.002:
            divergence_signal = "✅ CONSENSUS"
        elif funding_std < 0.005:
            divergence_signal = "⚠️ MIXED"
        else:
            divergence_signal = "🔀 DIVERGENT"
    else:
        divergence_score = 0
        divergence_signal = "⚪ INSUFFICIENT DATA"
        funding_std = 0

    # FACTOR 5: OI-Price Correlation
    if weighted_price_change > 0 and market_oi_vol_ratio > 0.35:
        oi_price_score = 0.5
        oi_price_signal = "🟢 NEW LONGS"
    elif weighted_price_change < 0 and market_oi_vol_ratio > 0.35:
        oi_price_score = -0.5
        oi_price_signal = "🔴 NEW SHORTS"
    else:
        oi_price_score = 0
        oi_price_signal = "⚪ NEUTRAL"

    # FACTOR 6: Long/Short Bias
    ls_data = fetch_long_short_ratio()

    if ls_data.get('status') == 'success':
        ratio = ls_data['ratio']
        long_pct = ls_data['long_pct']

        if ratio > 2.5:
            ls_score = max(-1.0, -0.5 - (ratio - 2.5) * 0.2)
            ls_signal = "🔴 BEARISH (Crowded Long)"
        elif ratio > 1.5:
            ls_score = -0.3 - (ratio - 1.5) * 0.2
            ls_signal = "🟡 SLIGHTLY BEARISH (Long Bias)"
        elif ratio < 0.4:
            ls_score = min(1.0, 0.5 + (0.4 - ratio) * 2.0)
            ls_signal = "🟢 BULLISH (Crowded Short)"
        elif ratio < 0.67:
            ls_score = 0.3 + (0.67 - ratio) * 0.74
            ls_signal = "🟡 SLIGHTLY BULLISH (Short Bias)"
        else:
            ls_score = (1.0 - ratio) * 0.2
            ls_signal = "⚪ NEUTRAL (Balanced)"

        ls_ratio_value = ratio
        ls_long_pct = long_pct
    else:
        ls_score = 0
        ls_signal = "⚠️ DATA UNAVAILABLE"
        ls_ratio_value = None
        ls_long_pct = None

    # COMPOSITE SCORE
    composite_score = (
        funding_score * 0.35 +
        price_score * 0.20 +
        ls_score * 0.15 +
        conviction_score * 0.15 +
        divergence_score * 0.08 +
        oi_price_score * 0.07
    )

    if composite_score > 0.3:
        sentiment = "🟢 BULLISH"
        interpretation = f"Multi-factor analysis shows bullish bias (Score: {composite_score:.2f})"
    elif composite_score < -0.3:
        sentiment = "🔴 BEARISH"
        interpretation = f"Multi-factor analysis shows bearish bias (Score: {composite_score:.2f})"
    else:
        sentiment = "⚪ NEUTRAL"
        interpretation = f"Balanced market with mixed signals (Score: {composite_score:.2f})"

    abs_score = abs(composite_score)
    if abs_score > 0.7:
        strength = "STRONG"
    elif abs_score > 0.5:
        strength = "MODERATE"
    elif abs_score > 0.3:
        strength = "WEAK"
    else:
        strength = "NEUTRAL"

    return {
        'weighted_funding': weighted_funding,
        'sentiment': sentiment,
        'interpretation': interpretation,
        'avg_price_change': weighted_price_change,
        'funding_exchanges': sorted(funding_exchanges, key=lambda x: x['rate'], reverse=True),
        'composite_score': composite_score,
        'strength': strength,
        'factors': {
            'funding': {
                'score': funding_score,
                'signal': funding_signal,
                'value': weighted_funding,
                'weight': 0.35
            },
            'price_momentum': {
                'score': price_score,
                'signal': price_signal,
                'value': weighted_price_change,
                'weight': 0.20
            },
            'long_short_bias': {
                'score': ls_score,
                'signal': ls_signal,
                'value': ls_ratio_value,
                'long_pct': ls_long_pct,
                'weight': 0.15
            },
            'conviction': {
                'score': conviction_score,
                'signal': conviction_signal,
                'value': market_oi_vol_ratio,
                'weight': 0.15
            },
            'divergence': {
                'score': divergence_score,
                'signal': divergence_signal,
                'value': funding_std,
                'weight': 0.08
            },
            'oi_price_correlation': {
                'score': oi_price_score,
                'signal': oi_price_signal,
                'value': f"{weighted_price_change:.2f}% price, {market_oi_vol_ratio:.2f}x OI/Vol",
                'weight': 0.07
            }
        }
    }
