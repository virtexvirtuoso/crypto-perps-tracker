#!/usr/bin/env python3
"""
Trading Strategy Alert System
Monitors market conditions and alerts when optimal strategies are detected
"""

import sys
import os
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
import yaml
from dotenv import load_dotenv
import argparse
import json
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Import from new architecture
from src.container import Container
from src.models.config import Config

# Import analysis functions from src/analysis/ (Phase 3 complete!)
from src.analysis.sentiment import analyze_market_sentiment
from src.analysis.arbitrage import identify_arbitrage_opportunities
from src.analysis.dominance import calculate_market_dominance
from src.analysis.basis import analyze_basis_metrics


# ========================================
# STRATEGY TIER CLASSIFICATIONS
# ========================================
# Tier 1: CRITICAL - Immediate action required (alert immediately)
# Tier 2: HIGH PRIORITY - Act within 1-4 hours (alert with validation)
# Tier 3-4: BACKGROUND - Longer timeframe (scheduled reports only)

STRATEGY_TIERS = {
    # Tier 1 - CRITICAL
    'Liquidation Cascade Risk': 1,
    'Momentum Breakout': 1,
    'Institutional-Retail Divergence': 1,

    # Tier 2 - HIGH PRIORITY
    'Contrarian Play': 2,
    'Breakout Trading': 2,
    'Volatility Expansion': 2,
    'Trend Following': 2,

    # Tier 3-4 - BACKGROUND (not alerted in real-time)
    'Range Trading': 3,
    'Scalping': 3,
    'Delta Neutral': 3,
    'Delta Neutral / Market Making': 3,
    'Funding Rate Arbitrage': 3,
    'Funding Arbitrage': 3,
    'Basis Arbitrage': 3,
    'Contango/Backwardation': 3,
    'Contango/Backwardation Play': 3,
    'Mean Reversion': 3,
}


def get_strategy_tier(strategy_name: str) -> int:
    """
    Get the tier (urgency level) of a strategy

    Returns:
        1 = CRITICAL (immediate)
        2 = HIGH PRIORITY (within hours)
        3-4 = BACKGROUND (scheduled reports only)
    """
    # Try exact match first
    if strategy_name in STRATEGY_TIERS:
        return STRATEGY_TIERS[strategy_name]

    # Try partial match (handles variations like "Trend Following (BULLISH)")
    for key, tier in STRATEGY_TIERS.items():
        if key in strategy_name or strategy_name.startswith(key):
            return tier

    # Default to tier 3 if unknown
    return 3


def load_config() -> Dict:
    """Load configuration from YAML file with environment variable substitution"""
    try:
        with open('config/config.yaml', 'r') as f:
            content = f.read()
            # Substitute environment variables
            content = os.path.expandvars(content)
            return yaml.safe_load(content)
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return {}


# ========================================
# ALERT STATE MANAGEMENT (Phase 2)
# ========================================

STATE_FILE = 'data/alert_state.json'

# Cooldown periods by tier (in hours)
COOLDOWN_HOURS = {
    1: 1,   # Tier 1 (CRITICAL): 1 hour cooldown
    2: 2,   # Tier 2 (HIGH): 2 hour cooldown
    3: 4,   # Tier 3+ (BACKGROUND): 4 hour cooldown
}

# Alert limits
MAX_ALERTS_PER_STRATEGY_PER_DAY = 3
MAX_ALERTS_PER_HOUR = 10
MIN_CONFIDENCE_DELTA = 20  # Minimum confidence change to re-alert


def load_alert_state() -> Dict:
    """
    Load alert state from JSON file

    Returns:
        Dictionary with state data or empty state if file doesn't exist
    """
    try:
        if Path(STATE_FILE).exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        else:
            # Initialize empty state
            return {
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'strategies': {},
                'daily_stats': {
                    'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'total_alerts': 0,
                    'alerts_by_tier': {'tier_1': 0, 'tier_2': 0, 'tier_3': 0},
                    'suppressed_alerts': 0,
                    'hourly_counts': {}
                }
            }
    except Exception as e:
        print(f"⚠️  Error loading alert state: {e}")
        return load_alert_state()  # Return empty state


def save_alert_state(state: Dict) -> None:
    """
    Save alert state to JSON file

    Args:
        state: State dictionary to save
    """
    try:
        # Ensure data directory exists
        Path('data').mkdir(exist_ok=True)

        # Update timestamp
        state['last_updated'] = datetime.now(timezone.utc).isoformat()

        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving alert state: {e}")


def reset_daily_stats_if_needed(state: Dict) -> Dict:
    """
    Reset daily statistics if it's a new day

    Args:
        state: Current state dictionary

    Returns:
        Updated state dictionary
    """
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    current_date = state.get('daily_stats', {}).get('date', '')

    if today != current_date:
        print(f"📅 New day detected. Resetting daily stats...")
        state['daily_stats'] = {
            'date': today,
            'total_alerts': 0,
            'alerts_by_tier': {'tier_1': 0, 'tier_2': 0, 'tier_3': 0},
            'suppressed_alerts': 0,
            'hourly_counts': {}
        }

    return state


def should_alert(strategy_name: str, confidence: int, direction: str, state: Dict) -> Tuple[bool, str]:
    """
    Determine if an alert should be sent based on deduplication rules

    Args:
        strategy_name: Name of the strategy
        confidence: Confidence percentage
        direction: Trading direction
        state: Current alert state

    Returns:
        Tuple of (should_alert: bool, reason: str)
    """
    now = datetime.now(timezone.utc)
    tier = get_strategy_tier(strategy_name)
    cooldown_hours = COOLDOWN_HOURS.get(tier, 2)

    # Check if strategy has been alerted before
    strategy_state = state['strategies'].get(strategy_name, {})

    # NEW STRATEGY - Always alert
    if not strategy_state:
        return True, "NEW setup detected"

    # Parse last alert time
    last_alert_str = strategy_state.get('last_alert_time')
    if last_alert_str:
        last_alert_time = datetime.fromisoformat(last_alert_str.replace('Z', '+00:00'))

        # COOLDOWN CHECK - Within cooldown period?
        time_since_last = (now - last_alert_time).total_seconds() / 3600  # Hours
        if time_since_last < cooldown_hours:
            remaining = cooldown_hours - time_since_last
            return False, f"Cooldown active ({remaining:.1f}h remaining)"

    # CONFIDENCE DELTA CHECK - Significant change?
    last_confidence = strategy_state.get('last_confidence', 0)
    confidence_change = abs(confidence - last_confidence)

    if confidence_change < MIN_CONFIDENCE_DELTA:
        return False, f"Confidence change too small ({confidence_change}% < {MIN_CONFIDENCE_DELTA}%)"

    # DAILY LIMIT CHECK - Too many alerts today?
    alert_count_today = strategy_state.get('alert_count_today', 0)
    if alert_count_today >= MAX_ALERTS_PER_STRATEGY_PER_DAY:
        return False, f"Daily limit reached ({alert_count_today}/{MAX_ALERTS_PER_STRATEGY_PER_DAY})"

    # GLOBAL HOURLY LIMIT CHECK
    current_hour = now.strftime('%Y-%m-%d-%H')
    hourly_counts = state['daily_stats'].get('hourly_counts', {})
    alerts_this_hour = hourly_counts.get(current_hour, 0)

    if alerts_this_hour >= MAX_ALERTS_PER_HOUR:
        return False, f"Global hourly limit reached ({alerts_this_hour}/{MAX_ALERTS_PER_HOUR})"

    # All checks passed
    return True, f"Confidence increased {confidence_change}%"


def update_alert_state(strategy_name: str, confidence: int, direction: str, state: Dict) -> Dict:
    """
    Update state after sending an alert

    Args:
        strategy_name: Name of the strategy
        confidence: Confidence percentage
        direction: Trading direction
        state: Current alert state

    Returns:
        Updated state dictionary
    """
    now = datetime.now(timezone.utc)
    tier = get_strategy_tier(strategy_name)
    cooldown_hours = COOLDOWN_HOURS.get(tier, 2)

    # Update strategy state
    strategy_state = state['strategies'].get(strategy_name, {
        'alert_count_today': 0
    })

    strategy_state.update({
        'last_alert_time': now.isoformat(),
        'last_confidence': confidence,
        'last_direction': direction,
        'alert_count_today': strategy_state.get('alert_count_today', 0) + 1,
        'cooldown_until': (now + timedelta(hours=cooldown_hours)).isoformat()
    })

    state['strategies'][strategy_name] = strategy_state

    # Update daily stats
    state['daily_stats']['total_alerts'] += 1
    tier_key = f'tier_{tier}'
    state['daily_stats']['alerts_by_tier'][tier_key] = state['daily_stats']['alerts_by_tier'].get(tier_key, 0) + 1

    # Update hourly count
    current_hour = now.strftime('%Y-%m-%d-%H')
    hourly_counts = state['daily_stats'].get('hourly_counts', {})
    hourly_counts[current_hour] = hourly_counts.get(current_hour, 0) + 1
    state['daily_stats']['hourly_counts'] = hourly_counts

    return state


def increment_suppressed_count(state: Dict) -> Dict:
    """
    Increment the suppressed alerts counter

    Args:
        state: Current alert state

    Returns:
        Updated state dictionary
    """
    state['daily_stats']['suppressed_alerts'] = state['daily_stats'].get('suppressed_alerts', 0) + 1
    return state


def detect_range_trading_setup(sentiment: Dict, dominance: Dict, results: List[Dict] = None) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for range trading (hours to days holding period)

    Conditions:
    - Composite score between -0.2 and +0.2 (neutral market)
    - Moderate volatility (3-6% 24h change) - enough movement for range profits
    - Balanced conviction (OI/Vol 0.3-0.5) - positions held longer
    - Exchange consensus (low funding divergence)
    """
    score = sentiment['composite_score']
    price_change = abs(sentiment['avg_price_change'])
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Check conditions
    is_neutral = -0.2 <= score <= 0.2
    good_range_volatility = 3.0 <= price_change <= 6.0  # Need some movement for ranges
    balanced_conviction = 0.3 <= conviction <= 0.5
    consensus = divergence < 0.005

    # All conditions must be met
    is_optimal = is_neutral and good_range_volatility and balanced_conviction and consensus

    confidence = 0
    if is_neutral: confidence += 25
    if good_range_volatility: confidence += 25
    if balanced_conviction: confidence += 25
    if consensus: confidence += 25

    # Determine bias direction for range trading
    price_momentum = sentiment['factors']['price_momentum']['score']
    if price_momentum > 0.2:
        bias_direction = "BULLISH"
        range_recommendation = "📈 BIAS: LONG near support, take profit at resistance"
    elif price_momentum < -0.2:
        bias_direction = "BEARISH"
        range_recommendation = "📉 BIAS: SHORT near resistance, take profit at support"
    else:
        bias_direction = "NEUTRAL"
        range_recommendation = "⚖️ BOTH: BUY support, SELL resistance equally"

    details = {
        'strategy': 'Range Trading',
        'confidence': confidence,
        'direction': bias_direction,
        'conditions_met': {
            'neutral_market': is_neutral,
            'range_volatility': good_range_volatility,
            'balanced_conviction': balanced_conviction,
            'exchange_consensus': consensus
        },
        'metrics': {
            'composite_score': score,
            'price_volatility': price_change,
            'oi_vol_ratio': conviction,
            'funding_divergence': divergence,
            'bias_direction': bias_direction
        },
        'recommendation': (
            f"✅ OPTIMAL for range trading\n"
            f"• Clear range established (volatility: {price_change:.2f}%)\n"
            f"• Neutral bias (score: {score:.3f})\n"
            f"• {range_recommendation}\n"
            f"• Hold hours to days, target 2-5% per trade"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_scalping_setup(sentiment: Dict, results: List[Dict]) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for scalping (seconds to minutes holding period)

    Conditions:
    - Very neutral market (-0.15 to +0.15) - no directional bias
    - Very low volatility (< 3% 24h) - tight ranges
    - Low conviction (OI/Vol 0.2-0.35) - high churn, day trading activity
    - Very tight spreads (divergence < 0.003)
    - High total volume (liquidity requirement)
    """
    score = sentiment['composite_score']
    price_change = abs(sentiment['avg_price_change'])
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Calculate total volume for liquidity check
    successful = [r for r in results if r.get('status') == 'success']
    total_volume = sum(r['volume'] for r in successful)

    # Check conditions
    very_neutral = -0.15 <= score <= 0.15
    very_low_volatility = price_change < 3.0
    high_churn = 0.2 <= conviction <= 0.35  # Day trading, not position holding
    very_tight_spreads = divergence < 0.003
    high_liquidity = total_volume > 200_000_000_000  # $200B+ for deep liquidity

    # All conditions must be met for scalping
    is_optimal = very_neutral and very_low_volatility and high_churn and very_tight_spreads and high_liquidity

    confidence = 0
    if very_neutral: confidence += 20
    if very_low_volatility: confidence += 25
    if high_churn: confidence += 25
    if very_tight_spreads: confidence += 20
    if high_liquidity: confidence += 10

    # Determine bias direction for scalping
    price_momentum = sentiment['factors']['price_momentum']['score']
    if price_momentum > 0.15:
        scalp_direction = "BULLISH"
        scalp_recommendation = "📈 FAVOR LONG: Buy dips, quick profits on bounces"
    elif price_momentum < -0.15:
        scalp_direction = "BEARISH"
        scalp_recommendation = "📉 FAVOR SHORT: Sell rips, quick profits on pullbacks"
    else:
        scalp_direction = "NEUTRAL"
        scalp_recommendation = "⚖️ BOTH SIDES: Scalp both directions equally"

    details = {
        'strategy': 'Scalping',
        'confidence': confidence,
        'direction': scalp_direction,
        'conditions_met': {
            'very_neutral_market': very_neutral,
            'very_low_volatility': very_low_volatility,
            'high_trading_churn': high_churn,
            'very_tight_spreads': very_tight_spreads,
            'high_liquidity': high_liquidity
        },
        'metrics': {
            'composite_score': score,
            'price_volatility': price_change,
            'oi_vol_ratio': conviction,
            'funding_divergence': divergence,
            'total_volume': total_volume / 1e9,
            'bias_direction': scalp_direction
        },
        'recommendation': (
            f"✅ OPTIMAL for scalping\n"
            f"• Ultra-tight ranges (volatility: {price_change:.2f}%)\n"
            f"• High liquidity (${total_volume/1e9:.1f}B volume)\n"
            f"• {scalp_recommendation}\n"
            f"• Target 0.1-0.5% moves, seconds to minutes holding"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_trend_following_setup(sentiment: Dict) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for trend following

    Conditions:
    - Strong directional bias (|composite_score| > 0.5)
    - Funding and price aligned (same direction)
    - High conviction (OI/Vol > 0.4)
    - Exchange consensus (agreement on direction)
    """
    score = sentiment['composite_score']
    funding_score = sentiment['factors']['funding']['score']
    price_score = sentiment['factors']['price_momentum']['score']
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Check conditions
    strong_bias = abs(score) > 0.5
    aligned = (funding_score > 0 and price_score > 0) or (funding_score < 0 and price_score < 0)
    high_conviction = conviction > 0.4
    consensus = divergence < 0.003

    is_optimal = strong_bias and aligned and high_conviction and consensus

    confidence = 0
    if strong_bias: confidence += 30
    if aligned: confidence += 30
    if high_conviction: confidence += 20
    if consensus: confidence += 20

    direction = "BULLISH" if score > 0 else "BEARISH"

    # Explicit trade direction
    if direction == "BULLISH":
        trade_direction = "LONG"
        action = "📈 GO LONG with trailing stops"
    else:
        trade_direction = "SHORT"
        action = "📉 GO SHORT with trailing stops"

    details = {
        'strategy': f'Trend Following ({direction})',
        'confidence': confidence,
        'direction': trade_direction,
        'conditions_met': {
            'strong_directional_bias': strong_bias,
            'funding_price_aligned': aligned,
            'high_conviction': high_conviction,
            'exchange_consensus': consensus
        },
        'metrics': {
            'composite_score': score,
            'direction': direction,
            'conviction': conviction,
            'alignment': 'Yes' if aligned else 'No',
            'trade_direction': trade_direction
        },
        'recommendation': (
            f"✅ OPTIMAL for trend following ({direction})\n"
            f"• {action}\n"
            f"• Strong {direction.lower()} bias (score: {score:.3f})\n"
            f"• Funding and price aligned\n"
            f"• High conviction traders (OI/Vol: {conviction:.2f}x)\n"
            f"• Use wide stops, let winners run"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_funding_arbitrage_setup(arb_opportunities: List[Dict]) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for funding rate arbitrage

    Conditions:
    - At least one opportunity with >8% annualized yield
    - Multiple opportunities available (diversification)
    - Stable market (not extreme volatility)
    """
    if not arb_opportunities:
        return False, {'strategy': 'Funding Arbitrage', 'confidence': 0}

    best_yield = arb_opportunities[0]['annual_yield']
    num_opportunities = len(arb_opportunities)
    high_yield_count = sum(1 for opp in arb_opportunities if opp['annual_yield'] > 8.0)

    # Check conditions
    has_good_yield = best_yield > 8.0
    multiple_opportunities = num_opportunities >= 3
    has_diversity = high_yield_count >= 2

    is_optimal = has_good_yield and (multiple_opportunities or has_diversity)

    confidence = min(int(best_yield * 5), 100)  # Scale by yield

    # Parse best arbitrage direction
    if is_optimal and arb_opportunities:
        best_arb = arb_opportunities[0]
        arb_direction = best_arb['action']  # e.g., "Short Bitget / Long HyperLiquid"
    else:
        arb_direction = "N/A"

    details = {
        'strategy': 'Funding Rate Arbitrage',
        'confidence': confidence,
        'direction': 'NEUTRAL (Delta Neutral)',
        'conditions_met': {
            'high_yield_available': has_good_yield,
            'multiple_opportunities': multiple_opportunities,
            'diversification_possible': has_diversity
        },
        'metrics': {
            'best_yield': best_yield,
            'total_opportunities': num_opportunities,
            'high_yield_opportunities': high_yield_count,
            'best_trade': arb_direction
        },
        'recommendation': (
            f"✅ OPTIMAL for funding arbitrage\n"
            f"• 💰 BEST TRADE: {arb_direction}\n"
            f"• Yield: {best_yield:.2f}% annualized\n"
            f"• {num_opportunities} opportunities available\n"
            f"• Low-risk market-neutral strategy\n"
            f"• Diversify across top {min(3, num_opportunities)} spreads"
        ) if is_optimal else None,
        'top_opportunities': arb_opportunities[:3] if is_optimal else []
    }

    return is_optimal, details


def detect_contrarian_setup(sentiment: Dict) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for contrarian plays

    Conditions:
    - Extreme sentiment (|composite_score| > 0.7)
    - Funding and price diverging (opposite directions)
    - High divergence among exchanges (disagreement)
    - Very high or very low conviction
    - Crowded positioning (>70% long or >70% short) ⭐ NEW
    """
    score = sentiment['composite_score']
    funding_score = sentiment['factors']['funding']['score']
    price_score = sentiment['factors']['price_momentum']['score']
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Get long/short bias
    ls_ratio = sentiment['factors']['long_short_bias']['value']
    ls_long_pct = sentiment['factors']['long_short_bias'].get('long_pct')

    # Check conditions
    extreme_sentiment = abs(score) > 0.7
    diverging = (funding_score > 0.3 and price_score < -0.3) or (funding_score < -0.3 and price_score > 0.3)
    high_divergence = divergence > 0.008
    extreme_conviction = conviction > 0.6 or conviction < 0.2

    # NEW: Crowded positioning (contrarian indicator)
    crowded_positioning = False
    crowd_direction = None
    if ls_ratio is not None and ls_long_pct is not None:
        if ls_long_pct > 0.70:  # >70% long
            crowded_positioning = True
            crowd_direction = "LONG"
        elif ls_long_pct < 0.30:  # >70% short
            crowded_positioning = True
            crowd_direction = "SHORT"

    # Need at least 2 conditions for contrarian (now checking 5 conditions)
    conditions_met = sum([extreme_sentiment, diverging, high_divergence, extreme_conviction, crowded_positioning])
    is_optimal = conditions_met >= 2

    confidence = min(conditions_met * 20, 100)  # Adjusted from 25 to 20 since we have 5 conditions now

    # Determine contrarian direction (fade the crowd or sentiment)
    if crowded_positioning:
        # Fade the crowded side
        if crowd_direction == "LONG":
            contrarian_direction = "SHORT"
            fade_action = "📉 GO SHORT (Fade crowded longs)"
        else:
            contrarian_direction = "LONG"
            fade_action = "📈 GO LONG (Fade crowded shorts)"
    elif score > 0.7:
        # Fade bullish extreme
        contrarian_direction = "SHORT"
        fade_action = "📉 GO SHORT (Fade extreme bullish sentiment)"
    elif score < -0.7:
        # Fade bearish extreme
        contrarian_direction = "LONG"
        fade_action = "📈 GO LONG (Fade extreme bearish sentiment)"
    else:
        contrarian_direction = "UNCLEAR"
        fade_action = "⚠️ WAIT for clearer extreme"

    # Build recommendation
    if is_optimal:
        recommendation = "⚠️ CONTRARIAN OPPORTUNITY\n"
        recommendation += f"• {fade_action}\n"
        recommendation += f"• Extreme conditions detected ({conditions_met}/5 signals)\n"
        if crowded_positioning:
            recommendation += f"• CROWDED {crowd_direction}: {ls_long_pct*100:.1f}% of traders are {crowd_direction.lower()}\n"
            recommendation += "• Potential for liquidation cascade if market reverses\n"
        recommendation += "• Market may be overextended\n"
        recommendation += "• Use TIGHT STOPS - cut losses quick if wrong\n"
        recommendation += "• HIGH RISK - use small position sizes (1-2% of capital)"
    else:
        recommendation = None

    details = {
        'strategy': 'Contrarian Play',
        'confidence': confidence,
        'direction': contrarian_direction,
        'conditions_met': {
            'extreme_sentiment': extreme_sentiment,
            'funding_price_divergence': diverging,
            'exchange_disagreement': high_divergence,
            'extreme_conviction': extreme_conviction,
            'crowded_positioning': crowded_positioning
        },
        'metrics': {
            'composite_score': score,
            'divergence': divergence,
            'conviction': conviction,
            'long_short_ratio': ls_ratio,
            'long_pct': ls_long_pct,
            'conditions_count': conditions_met,
            'fade_direction': contrarian_direction
        },
        'recommendation': recommendation
    }

    return is_optimal, details


def detect_mean_reversion_setup(sentiment: Dict) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for mean reversion

    Conditions:
    - Moderate sentiment (0.3 < |score| < 0.6)
    - Funding and price diverging (market confusion)
    - Recent volatility (price change > 3%)
    - Balanced conviction (not extreme)
    """
    score = sentiment['composite_score']
    funding_score = sentiment['factors']['funding']['score']
    price_score = sentiment['factors']['price_momentum']['score']
    price_change = abs(sentiment['avg_price_change'])
    conviction = sentiment['factors']['conviction']['value']

    # Check conditions
    moderate_sentiment = 0.3 < abs(score) < 0.6
    diverging = (funding_score * price_score) < 0  # Opposite signs
    has_volatility = price_change > 3.0
    balanced_conviction = 0.3 < conviction < 0.5

    is_optimal = moderate_sentiment and diverging and has_volatility

    confidence = 0
    if moderate_sentiment: confidence += 30
    if diverging: confidence += 40
    if has_volatility: confidence += 20
    if balanced_conviction: confidence += 10

    reversion_direction = "LONG" if price_score < 0 else "SHORT"

    # Explicit action
    if reversion_direction == "LONG":
        reversion_action = "📈 GO LONG (Buy the dip, price fell too far)"
    else:
        reversion_action = "📉 GO SHORT (Fade the rip, price rose too far)"

    details = {
        'strategy': f'Mean Reversion ({reversion_direction})',
        'confidence': confidence,
        'direction': reversion_direction,
        'conditions_met': {
            'moderate_sentiment': moderate_sentiment,
            'funding_price_divergence': diverging,
            'sufficient_volatility': has_volatility,
            'balanced_conviction': balanced_conviction
        },
        'metrics': {
            'composite_score': score,
            'price_volatility': price_change,
            'reversion_direction': reversion_direction,
            'conviction': conviction
        },
        'recommendation': (
            f"✅ OPTIMAL for mean reversion\n"
            f"• {reversion_action}\n"
            f"• Price moved {price_change:.2f}% (likely overextended)\n"
            f"• Funding/price divergence suggests correction coming\n"
            f"• Target previous range levels for profit taking"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_breakout_setup(sentiment: Dict) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for breakout trading

    Conditions:
    - Low current volatility but building pressure (< 4% price change)
    - Rising conviction (OI/Vol > 0.4) - positions accumulating
    - Neutral to weak sentiment (-0.3 to 0.3) - coiling spring
    - Low divergence (exchange agreement on direction when it breaks)
    """
    score = sentiment['composite_score']
    price_change = abs(sentiment['avg_price_change'])
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Get signed price momentum for directional bias
    price_momentum = sentiment['factors']['price_momentum']['score']
    funding_score = sentiment['factors']['funding']['score']

    # Check conditions
    low_volatility = price_change < 4.0
    building_oi = conviction > 0.4
    consolidating = abs(score) < 0.3
    exchange_agreement = divergence < 0.004

    is_optimal = low_volatility and building_oi and consolidating and exchange_agreement

    confidence = 0
    if low_volatility: confidence += 25
    if building_oi: confidence += 30
    if consolidating: confidence += 25
    if exchange_agreement: confidence += 20

    # Determine breakout bias direction
    # Even in consolidation, there's often a slight bias
    if score > 0.1 or (price_momentum > 0.1 and funding_score > 0):
        breakout_bias = "BULLISH"
        breakout_recommendation = "📈 FAVOR LONG breakouts (set buy-stops above resistance)"
    elif score < -0.1 or (price_momentum < -0.1 and funding_score < 0):
        breakout_bias = "BEARISH"
        breakout_recommendation = "📉 FAVOR SHORT breakouts (set sell-stops below support)"
    else:
        breakout_bias = "BOTH"
        breakout_recommendation = "⚖️ WATCH BOTH SIDES (buy-stops above, sell-stops below)"

    details = {
        'strategy': 'Breakout Trading',
        'confidence': confidence,
        'direction': breakout_bias,
        'conditions_met': {
            'low_current_volatility': low_volatility,
            'building_open_interest': building_oi,
            'price_consolidation': consolidating,
            'exchange_agreement': exchange_agreement
        },
        'metrics': {
            'composite_score': score,
            'price_volatility': price_change,
            'oi_vol_ratio': conviction,
            'funding_divergence': divergence,
            'breakout_bias': breakout_bias
        },
        'recommendation': (
            f"✅ OPTIMAL for breakout trading\n"
            f"• Coiled spring: Low vol ({price_change:.2f}%) with building OI ({conviction:.2f}x)\n"
            f"• {breakout_recommendation}\n"
            f"• Watch for volume spike + directional move\n"
            f"• Trail stops quickly once breakout confirmed"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_liquidation_cascade_setup(sentiment: Dict, liquidation_metrics: Dict = None) -> Tuple[bool, Dict]:
    """
    ENHANCED: Detect liquidation cascade conditions using REAL liquidation data

    Conditions (6 factors):
    - Very high leverage (OI/Vol > 0.6)
    - Extreme funding rates (|funding| > 0.015%)
    - Strong directional bias (|score| > 0.4)
    - Recent volatility (price change > 5%)
    - HIGH recent liquidations (>2% of volume) ⭐ NEW
    - Elevated cascade risk score (>0.6) ⭐ NEW

    This is both a RISK indicator and an OPPORTUNITY for counter-positioning
    """
    score = sentiment['composite_score']
    price_change = abs(sentiment['avg_price_change'])
    conviction = sentiment['factors']['conviction']['value']
    funding_value = sentiment['factors']['funding']['value']

    # NEW: Real liquidation data (if available)
    if liquidation_metrics and liquidation_metrics.get('total_liquidations', 0) > 0:
        cascade_risk = liquidation_metrics.get('cascade_risk_score', 0)
        liq_vol_ratio = liquidation_metrics.get('liquidation_volume_ratio', 0)
        recent_liquidations = liquidation_metrics.get('total_liquidations', 0)
        has_liq_data = True
    else:
        cascade_risk = 0
        liq_vol_ratio = 0
        recent_liquidations = 0
        has_liq_data = False

    # Check conditions
    extreme_leverage = conviction > 0.6
    extreme_funding = abs(funding_value) > 0.015
    directional_bias = abs(score) > 0.4
    has_volatility = price_change > 5.0
    high_recent_liquidations = liq_vol_ratio > 0.02  # NEW: >2% liquidations
    elevated_cascade_risk = cascade_risk > 0.6  # NEW: Risk score threshold

    # Need at least 4 of 6 conditions (stricter with more data)
    conditions_met = sum([
        extreme_leverage,
        extreme_funding,
        directional_bias,
        has_volatility,
        high_recent_liquidations,
        elevated_cascade_risk
    ])

    is_optimal = conditions_met >= 4

    # Base confidence from conditions
    confidence = min(conditions_met * 17, 100)  # 17% per condition (6 conditions)

    # Bonus confidence if REAL liquidation data shows active cascade
    if has_liq_data and high_recent_liquidations and elevated_cascade_risk:
        confidence = min(confidence + 20, 100)  # +20% bonus for confirmed cascade

    direction = "LONG" if score > 0 else "SHORT"
    risk_side = "Longs" if score > 0 else "Shorts"

    # Counter-position opportunity is OPPOSITE of the risk
    counter_direction = "SHORT" if score > 0 else "LONG"
    counter_action = "📉 Counter with SHORT" if score > 0 else "📈 Counter with LONG"

    # Determine cascade status
    if has_liq_data:
        if high_recent_liquidations:
            cascade_status = "⚠️ ACTIVE CASCADE"
        elif elevated_cascade_risk:
            cascade_status = "🟡 BUILDING RISK"
        else:
            cascade_status = "🟢 ELEVATED RISK"
    else:
        cascade_status = "⚪ RISK INDICATORS"

    # Build recommendation
    if is_optimal:
        rec = f"{cascade_status} DETECTED\n"
        rec += f"• {risk_side} heavily leveraged (OI/Vol: {conviction:.2f}x)\n"

        if has_liq_data:
            rec += f"• Recent liquidations: ${recent_liquidations/1e6:.1f}M ({liq_vol_ratio*100:.2f}% of volume)\n"
            rec += f"• Cascade Risk Score: {cascade_risk:.2f}/1.0 ({liquidation_metrics.get('risk_level', 'UNKNOWN')})\n"

        rec += f"• Extreme funding ({funding_value:.4f}%) suggests crowded trade\n"

        if high_recent_liquidations:
            rec += f"• ⚠️ CASCADE IN PROGRESS: Liquidations accelerating\n"

        rec += f"• Strategy: {counter_action} with TIGHT stops (high risk)\n"
        rec += f"• OR reduce leverage immediately if on {risk_side.lower()} side"

        recommendation = rec
    else:
        recommendation = None

    details = {
        'strategy': f'Liquidation Cascade Risk ({risk_side}) - {cascade_status}',
        'confidence': confidence,
        'direction': counter_direction,  # Direction is the COUNTER-POSITION opportunity
        'conditions_met': {
            'extreme_leverage': extreme_leverage,
            'extreme_funding': extreme_funding,
            'strong_directional_bias': directional_bias,
            'high_volatility': has_volatility,
            'recent_liquidations': high_recent_liquidations,  # NEW
            'cascade_risk_elevated': elevated_cascade_risk    # NEW
        },
        'metrics': {
            'composite_score': score,
            'oi_vol_ratio': conviction,
            'funding_rate': funding_value,
            'price_volatility': price_change,
            'at_risk': risk_side,
            'counter_opportunity': counter_direction,
            'recent_liquidations_usd': recent_liquidations if has_liq_data else None,  # NEW
            'liquidation_volume_ratio': liq_vol_ratio if has_liq_data else None,      # NEW
            'cascade_risk_score': cascade_risk if has_liq_data else None,             # NEW
            'cascade_status': cascade_status,                                          # NEW
            'liquidation_data_available': has_liq_data                                 # NEW
        },
        'recommendation': recommendation
    }

    return is_optimal, details


def detect_volatility_expansion_setup(sentiment: Dict) -> Tuple[bool, Dict]:
    """
    Detect conditions favoring volatility expansion strategies (straddles/strangles)

    Conditions:
    - Currently compressed volatility (< 3% price change)
    - High funding divergence (exchanges disagree)
    - Funding and price diverging (confusion)
    - Moderate to high OI (0.35-0.6) - positions built but unclear direction
    """
    score = sentiment['composite_score']
    funding_score = sentiment['factors']['funding']['score']
    price_score = sentiment['factors']['price_momentum']['score']
    price_change = abs(sentiment['avg_price_change'])
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Check conditions
    compressed_vol = price_change < 3.0
    high_divergence = divergence > 0.006
    signals_diverging = abs(funding_score - price_score) > 0.5
    positions_built = 0.35 < conviction < 0.6

    is_optimal = compressed_vol and high_divergence and signals_diverging

    confidence = 0
    if compressed_vol: confidence += 30
    if high_divergence: confidence += 30
    if signals_diverging: confidence += 25
    if positions_built: confidence += 15

    details = {
        'strategy': 'Volatility Expansion (Straddle/Strangle)',
        'confidence': confidence,
        'direction': 'BOTH (Non-Directional)',  # Profit from movement in EITHER direction
        'conditions_met': {
            'compressed_volatility': compressed_vol,
            'exchange_disagreement': high_divergence,
            'signal_divergence': signals_diverging,
            'positions_building': positions_built
        },
        'metrics': {
            'price_volatility': price_change,
            'funding_divergence': divergence,
            'signal_difference': abs(funding_score - price_score),
            'oi_vol_ratio': conviction
        },
        'recommendation': (
            f"✅ OPTIMAL for volatility expansion strategies\n"
            f"• Compressed vol ({price_change:.2f}%) with market confusion\n"
            f"• Exchanges disagree (divergence: {divergence:.4f})\n"
            f"• Signals diverging - direction unclear\n"
            f"• 📊 TRADE BOTH SIDES: Straddle/strangle OR wide bracket orders\n"
            f"• Profit from expansion in EITHER direction"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_momentum_breakout_setup(sentiment: Dict) -> Tuple[bool, Dict]:
    """
    Detect accelerating momentum with expanding participation

    Different from trend following - focuses on ACCELERATION not established trends

    Conditions:
    - Strong recent move (|price_change| > 5%)
    - Rising conviction (OI/Vol > 0.45) - new participants joining
    - Funding and price STRONGLY aligned (both extreme same direction)
    - Low divergence (all exchanges confirming)
    """
    score = sentiment['composite_score']
    funding_score = sentiment['factors']['funding']['score']
    price_score = sentiment['factors']['price_momentum']['score']
    price_change = sentiment['avg_price_change']  # Keep sign for direction
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Check conditions
    strong_move = abs(price_change) > 5.0
    expanding_oi = conviction > 0.45
    strongly_aligned = (funding_score > 0.5 and price_score > 0.5) or (funding_score < -0.5 and price_score < -0.5)
    all_confirm = divergence < 0.003

    is_optimal = strong_move and expanding_oi and strongly_aligned and all_confirm

    confidence = 0
    if strong_move: confidence += 30
    if expanding_oi: confidence += 30
    if strongly_aligned: confidence += 25
    if all_confirm: confidence += 15

    direction_label = "BULLISH" if price_change > 0 else "BEARISH"
    trade_direction = "LONG" if price_change > 0 else "SHORT"
    momentum_action = "📈 RIDE LONG momentum" if price_change > 0 else "📉 RIDE SHORT momentum"

    details = {
        'strategy': f'Momentum Breakout ({direction_label})',
        'confidence': confidence,
        'direction': trade_direction,  # Explicit LONG or SHORT
        'conditions_met': {
            'strong_recent_move': strong_move,
            'expanding_participation': expanding_oi,
            'strongly_aligned_signals': strongly_aligned,
            'universal_confirmation': all_confirm
        },
        'metrics': {
            'price_change': price_change,
            'direction': direction_label,
            'oi_vol_ratio': conviction,
            'composite_score': score,
            'divergence': divergence
        },
        'recommendation': (
            f"✅ OPTIMAL for momentum breakout ({direction_label})\n"
            f"• {momentum_action} with wide stops\n"
            f"• Strong {direction_label.lower()} acceleration ({abs(price_change):.2f}%)\n"
            f"• New participants joining (OI expanding: {conviction:.2f}x)\n"
            f"• All signals aligned - universal confirmation\n"
            f"• Strategy: Trail stops, take partial profits along the way"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_delta_neutral_setup(sentiment: Dict, arb_opportunities: List[Dict]) -> Tuple[bool, Dict]:
    """
    Detect optimal conditions for delta-neutral strategies (market making, basis trading)

    Conditions:
    - Very low volatility (< 2% price change)
    - Neutral sentiment (-0.15 to 0.15)
    - Low funding rates (< 0.01%) - cheap to hold positions
    - Stable OI (0.3-0.5x) - not too much churn, not too stagnant
    - Tight spreads (low divergence)
    """
    score = sentiment['composite_score']
    price_change = abs(sentiment['avg_price_change'])
    funding_value = abs(sentiment['factors']['funding']['value'])
    conviction = sentiment['factors']['conviction']['value']
    divergence = sentiment['factors']['divergence']['value']

    # Check conditions
    very_low_vol = price_change < 2.0
    neutral = abs(score) < 0.15
    cheap_carry = funding_value < 0.01
    stable_oi = 0.3 < conviction < 0.5
    tight_spreads = divergence < 0.003

    is_optimal = very_low_vol and neutral and cheap_carry and stable_oi

    confidence = 0
    if very_low_vol: confidence += 25
    if neutral: confidence += 25
    if cheap_carry: confidence += 25
    if stable_oi: confidence += 15
    if tight_spreads: confidence += 10

    # Check if there are any low-risk arb opportunities
    low_risk_arbs = [opp for opp in arb_opportunities if opp['annual_yield'] > 3.0 and opp['annual_yield'] < 10.0]

    details = {
        'strategy': 'Delta Neutral / Market Making',
        'confidence': confidence,
        'direction': 'NEUTRAL (Delta Neutral)',  # Market-neutral by definition
        'conditions_met': {
            'very_low_volatility': very_low_vol,
            'neutral_market': neutral,
            'cheap_carry_cost': cheap_carry,
            'stable_open_interest': stable_oi,
            'tight_spreads': tight_spreads
        },
        'metrics': {
            'price_volatility': price_change,
            'composite_score': score,
            'funding_rate': funding_value,
            'oi_vol_ratio': conviction,
            'available_arbs': len(low_risk_arbs)
        },
        'recommendation': (
            f"✅ OPTIMAL for delta-neutral strategies\n"
            f"• ⚖️ MARKET-NEUTRAL positioning (hedge both sides)\n"
            f"• Extremely low volatility ({price_change:.2f}%)\n"
            f"• Neutral market (score: {score:.3f})\n"
            f"• Low carry cost (funding: {funding_value:.4f}%)\n"
            f"• Strategy: Market making, basis trading, or yield farming"
            + (f"\n• {len(low_risk_arbs)} low-risk arbitrage opportunities available" if low_risk_arbs else "")
        ) if is_optimal else None,
        'low_risk_opportunities': low_risk_arbs[:3] if is_optimal and low_risk_arbs else []
    }

    return is_optimal, details


def detect_basis_arbitrage_setup(basis_metrics: Dict) -> Tuple[bool, Dict]:
    """
    Detect cash-and-carry or reverse cash-and-carry arbitrage opportunities

    Conditions:
    - Basis > 0.15% (cash-and-carry) or < -0.15% (reverse)
    - Tight market (multiple exchanges showing similar opportunities)
    """
    if basis_metrics.get('status') != 'success':
        return False, {}

    arb_opportunities = basis_metrics.get('arbitrage_opportunities', [])

    if not arb_opportunities:
        return False, {}

    # Get the best opportunity
    best_opp = max(arb_opportunities, key=lambda x: x['basis_capture'])
    basis_capture = best_opp['basis_capture']

    # Determine confidence based on basis size
    if basis_capture > 0.30:
        confidence = 100  # Extreme arbitrage opportunity
    elif basis_capture > 0.20:
        confidence = 85
    elif basis_capture > 0.15:
        confidence = 70
    else:
        confidence = 50  # Below threshold but still notable

    is_optimal = basis_capture >= 0.15  # Minimum 0.15% basis for alert

    details = {
        'strategy': 'Basis Arbitrage',
        'confidence': confidence,
        'direction': 'NEUTRAL (Market Neutral)',
        'conditions_met': {
            'wide_basis': basis_capture >= 0.15,
            'opportunity_count': len(arb_opportunities)
        },
        'metrics': {
            'best_exchange': best_opp['exchange'],
            'basis_capture_pct': basis_capture,
            'arbitrage_type': best_opp['type'],
            'total_opportunities': len(arb_opportunities)
        },
        'recommendation': (
            f"✅ CASH-AND-CARRY ARBITRAGE DETECTED\n"
            f"• Exchange: {best_opp['exchange']}\n"
            f"• Type: {best_opp['type']}\n"
            f"• Action: {best_opp['action']}\n"
            f"• Basis Capture: {basis_capture:.3f}%\n"
            f"• Risk: Low (market-neutral hedged position)\n"
            f"• Expected Yield: {basis_capture:.3f}% + funding collection\n"
            f"• Strategy: Buy spot, sell futures (or vice versa) to lock in basis"
        ) if is_optimal else None
    }

    return is_optimal, details


def detect_contango_backwardation_shift(basis_metrics: Dict) -> Tuple[bool, Dict]:
    """
    Detect significant contango/backwardation market structure

    Conditions:
    - Strong contango (avg basis > 0.20%) or backwardation (< -0.20%)
    - Wide basis range indicating market inefficiency
    """
    if basis_metrics.get('status') != 'success':
        return False, {}

    avg_basis = basis_metrics.get('avg_basis', 0)
    basis_range = abs(basis_metrics['max_basis'] - basis_metrics['min_basis'])
    market_structure = basis_metrics.get('market_structure', '')

    # Determine if structure is significant
    is_strong_contango = avg_basis > 0.20
    is_strong_backwardation = avg_basis < -0.20
    is_wide_range = basis_range > 0.30

    is_optimal = is_strong_contango or is_strong_backwardation

    if not is_optimal:
        return False, {}

    # Confidence based on strength
    if abs(avg_basis) > 0.40:
        confidence = 95
    elif abs(avg_basis) > 0.30:
        confidence = 80
    elif abs(avg_basis) > 0.20:
        confidence = 65
    else:
        confidence = 50

    # Determine direction and strategy
    if is_strong_contango:
        direction = "BULLISH"
        interpretation = "Futures trading at significant premium - market expects higher prices"
        strategy_rec = "Consider long positions, collect basis + funding"
    else:  # Strong backwardation
        direction = "BEARISH"
        interpretation = "Futures at significant discount - market expects lower prices"
        strategy_rec = "Consider short positions or stay in spot"

    details = {
        'strategy': 'Contango/Backwardation Play',
        'confidence': confidence,
        'direction': direction,
        'conditions_met': {
            'strong_structure': is_strong_contango or is_strong_backwardation,
            'wide_range': is_wide_range
        },
        'metrics': {
            'market_structure': market_structure,
            'avg_basis_pct': avg_basis,
            'basis_range_pct': basis_range,
            'exchanges_analyzed': basis_metrics['exchanges_analyzed']
        },
        'recommendation': (
            f"⚠️ STRONG {market_structure.upper()} DETECTED\n"
            f"• Average Basis: {avg_basis:+.3f}%\n"
            f"• Basis Range: {basis_metrics['min_basis']:.3f}% to {basis_metrics['max_basis']:.3f}%\n"
            f"• Interpretation: {interpretation}\n"
            f"• Strategy: {strategy_rec}\n"
            f"• Market expecting {'UPWARD' if is_strong_contango else 'DOWNWARD'} price movement"
        )
    }

    return is_optimal, details


def detect_institutional_divergence_setup(basis_metrics: Dict) -> Tuple[bool, Dict]:
    """
    Detect divergence between institutional (Kraken) and retail (Binance/Bybit) exchanges

    Conditions:
    - Kraken vs Binance/Bybit basis spread > 0.20%
    - Volume ratio divergence (spot dominant vs high leverage)
    """
    if basis_metrics.get('status') != 'success':
        return False, {}

    basis_data = basis_metrics.get('basis_data', [])

    # Find Kraken and retail exchanges
    kraken_data = next((d for d in basis_data if d['exchange'] == 'Kraken'), None)
    binance_data = next((d for d in basis_data if d['exchange'] == 'Binance'), None)
    bybit_data = next((d for d in basis_data if d['exchange'] == 'Bybit'), None)

    if not kraken_data:
        return False, {}  # Can't detect divergence without Kraken

    # Check divergence with retail exchanges
    retail_divergences = []

    if binance_data:
        spread = kraken_data['basis_pct'] - binance_data['basis_pct']
        retail_divergences.append({
            'exchange': 'Binance',
            'spread': spread,
            'kraken_basis': kraken_data['basis_pct'],
            'retail_basis': binance_data['basis_pct']
        })

    if bybit_data:
        spread = kraken_data['basis_pct'] - bybit_data['basis_pct']
        retail_divergences.append({
            'exchange': 'Bybit',
            'spread': spread,
            'kraken_basis': kraken_data['basis_pct'],
            'retail_basis': bybit_data['basis_pct']
        })

    if not retail_divergences:
        return False, {}

    # Get maximum divergence
    max_div = max(retail_divergences, key=lambda x: abs(x['spread']))
    abs_spread = abs(max_div['spread'])

    is_optimal = abs_spread > 0.20  # Significant divergence threshold

    if not is_optimal:
        return False, {}

    # Confidence based on divergence size
    if abs_spread > 0.40:
        confidence = 95
    elif abs_spread > 0.30:
        confidence = 80
    elif abs_spread > 0.20:
        confidence = 65
    else:
        confidence = 50

    # Determine direction
    if max_div['spread'] > 0:
        # Kraken more bullish than retail
        direction = "LONG (Follow Institutions)"
        interpretation = "Institutions (Kraken) paying premium while retail selling at discount"
        strategy_rec = "Buy on retail exchanges, institutions see value retail doesn't"
    else:
        # Retail more bullish than Kraken
        direction = "SHORT (Fade Retail)"
        interpretation = "Retail paying premium while institutions selling at discount"
        strategy_rec = "Short on retail exchanges, institutional caution signals weakness"

    details = {
        'strategy': 'Institutional-Retail Divergence',
        'confidence': confidence,
        'direction': direction,
        'conditions_met': {
            'significant_divergence': abs_spread > 0.20,
            'kraken_available': True
        },
        'metrics': {
            'kraken_basis_pct': max_div['kraken_basis'],
            'retail_basis_pct': max_div['retail_basis'],
            'basis_spread_pct': abs_spread,
            'retail_exchange': max_div['exchange']
        },
        'recommendation': (
            f"🏦 INSTITUTIONAL vs RETAIL DIVERGENCE\n"
            f"• Kraken (Institutional): {max_div['kraken_basis']:+.3f}% basis\n"
            f"• {max_div['exchange']} (Retail): {max_div['retail_basis']:+.3f}% basis\n"
            f"• Spread: {abs_spread:.3f}% divergence\n"
            f"• Interpretation: {interpretation}\n"
            f"• Strategy: {strategy_rec}\n"
            f"• Risk: Medium (cross-market arbitrage)"
        )
    }

    return is_optimal, details


def analyze_all_strategies(results: List[Dict]) -> List[Dict]:
    """Analyze all trading strategies and return alerts"""

    # Get market data
    sentiment = analyze_market_sentiment(results)
    arb_opportunities = identify_arbitrage_opportunities(results)
    dominance = calculate_market_dominance(results)
    basis_metrics = analyze_basis_metrics()  # Spot-futures basis analysis

    # NEW: Fetch liquidation data
    liquidation_metrics = None
    try:
        from fetch_liquidations import fetch_all_liquidations, calculate_liquidation_metrics

        # Get total market volume for liquidation ratio calculation
        successful = [r for r in results if r.get('status') == 'success']
        total_volume = sum(r['volume'] for r in successful)

        # Fetch liquidations from last hour
        liq_data = fetch_all_liquidations(hours=1)
        liquidation_metrics = calculate_liquidation_metrics(liq_data, total_volume)

        # Log if liquidations detected
        if liquidation_metrics.get('total_liquidations', 0) > 0:
            print(f"⚠️  Liquidation data: ${liquidation_metrics['total_liquidations']/1e6:.1f}M "
                  f"(Risk: {liquidation_metrics['risk_level']})")

    except ImportError:
        print("⚠️  Liquidation tracking not available (fetch_liquidations.py not found)")
    except Exception as e:
        print(f"⚠️  Liquidation fetch failed: {e}")

    alerts = []

    # Check each strategy
    strategies = [
        detect_range_trading_setup(sentiment, dominance),
        detect_scalping_setup(sentiment, results),
        detect_trend_following_setup(sentiment),
        detect_funding_arbitrage_setup(arb_opportunities),
        detect_contrarian_setup(sentiment),
        detect_mean_reversion_setup(sentiment),
        detect_breakout_setup(sentiment),
        detect_liquidation_cascade_setup(sentiment, liquidation_metrics),  # ⭐ NOW USES REAL DATA
        detect_volatility_expansion_setup(sentiment),
        detect_momentum_breakout_setup(sentiment),
        detect_delta_neutral_setup(sentiment, arb_opportunities),
        # Spot-futures basis strategies
        detect_basis_arbitrage_setup(basis_metrics),
        detect_contango_backwardation_shift(basis_metrics),
        detect_institutional_divergence_setup(basis_metrics)
    ]

    for is_optimal, details in strategies:
        if is_optimal and details.get('confidence', 0) >= 50:  # Minimum 50% confidence
            alerts.append(details)

    # Sort by confidence
    alerts.sort(key=lambda x: x['confidence'], reverse=True)

    return alerts


def filter_alerts(alerts: List[Dict], tiers: List[int] = None, min_confidence: int = 50,
                  enable_dedup: bool = False, state: Optional[Dict] = None) -> Tuple[List[Dict], Dict, Dict]:
    """
    Filter alerts based on tier, minimum confidence, and deduplication rules

    Args:
        alerts: List of alert dictionaries
        tiers: List of tier numbers to include (e.g., [1, 2] for Tier 1 and 2 only)
               If None, include all tiers
        min_confidence: Minimum confidence percentage (default 50)
        enable_dedup: Enable deduplication logic (Phase 2)
        state: Alert state dictionary (required if enable_dedup=True)

    Returns:
        Tuple of (filtered_alerts, updated_state, filter_stats)
    """
    filtered = []
    filter_stats = {
        'total_checked': len(alerts),
        'tier_filtered': 0,
        'confidence_filtered': 0,
        'dedup_suppressed': 0,
        'passed': 0
    }

    # Initialize state if dedup enabled
    if enable_dedup and state is None:
        state = load_alert_state()
        state = reset_daily_stats_if_needed(state)

    for alert in alerts:
        strategy_name = alert.get('strategy', '')
        confidence = alert.get('confidence', 0)
        direction = alert.get('direction', 'N/A')
        tier = get_strategy_tier(strategy_name)

        # Check tier filter
        if tiers is not None and tier not in tiers:
            filter_stats['tier_filtered'] += 1
            continue

        # Check confidence filter
        if confidence < min_confidence:
            filter_stats['confidence_filtered'] += 1
            continue

        # Check deduplication rules (Phase 2)
        if enable_dedup:
            should_send, reason = should_alert(strategy_name, confidence, direction, state)

            if not should_send:
                filter_stats['dedup_suppressed'] += 1
                state = increment_suppressed_count(state)
                print(f"   🔇 Suppressed: {strategy_name} ({confidence}%) - {reason}")
                continue
            else:
                # Update state for alerts we're sending
                state = update_alert_state(strategy_name, confidence, direction, state)
                print(f"   ✅ Alerting: {strategy_name} ({confidence}%) - {reason}")

        filtered.append(alert)
        filter_stats['passed'] += 1

    # Save state if dedup enabled
    if enable_dedup and state:
        save_alert_state(state)

    return filtered, state, filter_stats


def send_strategy_alert_to_discord(alerts: List[Dict], webhook_url: str) -> bool:
    """Send strategy alerts to Discord"""

    if not alerts:
        return False  # No alerts to send

    embeds = []

    # Main alert embed
    top_alert = alerts[0]

    color = 0x00FF00 if top_alert['confidence'] >= 80 else 0xFFA500

    # Get direction emoji
    direction = top_alert.get('direction', 'N/A')
    if 'LONG' in direction and 'SHORT' not in direction:
        direction_emoji = "📈"
    elif 'SHORT' in direction and 'LONG' not in direction:
        direction_emoji = "📉"
    elif 'BOTH' in direction:
        direction_emoji = "⚖️"
    elif 'NEUTRAL' in direction:
        direction_emoji = "⚪"
    else:
        direction_emoji = "❓"

    main_embed = {
        "title": f"🚨 STRATEGY ALERT: {top_alert['strategy']}",
        "description": f"**Confidence: {top_alert['confidence']}%**\n**Direction: {direction_emoji} {direction}**\n\n{top_alert['recommendation']}",
        "color": color,
        "fields": [],
        "footer": {
            "text": f"Alert generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Add conditions
    conditions_text = ""
    for condition, met in top_alert['conditions_met'].items():
        emoji = "✅" if met else "❌"
        conditions_text += f"{emoji} {condition.replace('_', ' ').title()}\n"

    main_embed['fields'].append({
        "name": "📋 Conditions",
        "value": conditions_text,
        "inline": False
    })

    # Add metrics
    metrics_text = ""
    for metric, value in top_alert['metrics'].items():
        if isinstance(value, float):
            metrics_text += f"• {metric.replace('_', ' ').title()}: {value:.3f}\n"
        else:
            metrics_text += f"• {metric.replace('_', ' ').title()}: {value}\n"

    main_embed['fields'].append({
        "name": "📊 Key Metrics",
        "value": metrics_text,
        "inline": False
    })

    # Add arbitrage opportunities if present
    if top_alert.get('top_opportunities'):
        arb_text = ""
        for i, opp in enumerate(top_alert['top_opportunities'][:3], 1):
            arb_text += f"{i}. {opp['action']}\n   Yield: {opp['annual_yield']:.2f}%\n"

        main_embed['fields'].append({
            "name": "💰 Top Arbitrage Opportunities",
            "value": arb_text,
            "inline": False
        })

    embeds.append(main_embed)

    # Additional strategies embed
    if len(alerts) > 1:
        other_strategies = alerts[1:]
        other_text = ""
        for alert in other_strategies[:3]:  # Max 3 additional
            other_text += f"**{alert['strategy']}** ({alert['confidence']}%)\n"

        embeds.append({
            "title": "📌 Other Viable Strategies",
            "description": other_text,
            "color": 0x808080
        })

    # Send to Discord
    payload = {
        "username": "Strategy Alert Bot",
        "embeds": embeds
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if response.status_code == 204:
            print(f"✅ Strategy alert sent to Discord!")
            print(f"   Primary: {top_alert['strategy']} ({top_alert['confidence']}% confidence)")
            return True
        else:
            print(f"❌ Discord webhook failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")
        return False


def main():
    """Main function"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Crypto Perpetual Futures Strategy Alert System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # PHASE 1: Alert on Tier 1-2 strategies only with 85%+ confidence (no dedup)
  python strategy_alerts.py --tier 1,2 --min-confidence 85

  # PHASE 2: Same as Phase 1 but with deduplication (recommended)
  python strategy_alerts.py --tier 1,2 --min-confidence 80 --enable-dedup

  # Alert on Tier 1 (CRITICAL) only with dedup
  python strategy_alerts.py --tier 1 --min-confidence 70 --enable-dedup

  # All strategies with 50%+ confidence (not recommended - too noisy)
  python strategy_alerts.py
        """
    )
    parser.add_argument(
        '--tier',
        type=str,
        default=None,
        help='Comma-separated tier numbers to alert on (1=CRITICAL, 2=HIGH, 3+=BACKGROUND). Example: 1,2'
    )
    parser.add_argument(
        '--min-confidence',
        type=int,
        default=50,
        help='Minimum confidence percentage for alerts (default: 50)'
    )
    parser.add_argument(
        '--enable-dedup',
        action='store_true',
        help='Enable deduplication logic (Phase 2) - prevents repeat alerts'
    )
    args = parser.parse_args()

    # Parse tier filter
    tier_filter = None
    if args.tier:
        try:
            tier_filter = [int(t.strip()) for t in args.tier.split(',')]
            print(f"📊 Tier filter: {tier_filter} (1=CRITICAL, 2=HIGH, 3+=BACKGROUND)")
        except ValueError:
            print(f"❌ Invalid tier format: {args.tier}. Use comma-separated numbers like: 1,2")
            return

    print(f"📊 Minimum confidence: {args.min_confidence}%")

    if args.enable_dedup:
        print(f"🔒 Deduplication: ENABLED (Phase 2)")
        print(f"   - Cooldowns: Tier 1={COOLDOWN_HOURS[1]}h, Tier 2={COOLDOWN_HOURS[2]}h")
        print(f"   - Max per strategy/day: {MAX_ALERTS_PER_STRATEGY_PER_DAY}")
        print(f"   - Max per hour (global): {MAX_ALERTS_PER_HOUR}")
        print(f"   - Min confidence delta: {MIN_CONFIDENCE_DELTA}%")
    else:
        print(f"🔓 Deduplication: DISABLED (Phase 1)")

    print("\n🔍 Analyzing market for trading strategy opportunities...\n")

    # Load config
    config = load_config()

    # Try to get strategy_alerts webhook first, fallback to discord webhook
    webhook_url = config.get('strategy_alerts', {}).get('webhook_url')
    if not webhook_url:
        webhook_url = config.get('discord', {}).get('webhook_url')

    if not webhook_url:
        print("⚠️  No Discord webhook configured. Alerts will be displayed only.")
        print("   Configure webhook_url in config/config.yaml to enable Discord alerts.\n")

    # Fetch data using new architecture
    print("⏳ Fetching data from exchanges (20-30 seconds)...\n")

    # Initialize container with config
    app_config = Config.from_yaml('config/config.yaml')
    container = Container(app_config)

    # Fetch markets using ExchangeService
    markets = container.exchange_service.fetch_all_markets()

    # Convert MarketData objects to dict format expected by legacy code
    results = []
    for market in markets:
        results.append({
            'exchange': market.exchange.value,
            'volume': market.volume_24h,
            'open_interest': market.open_interest,
            'funding_rate': market.funding_rate,
            'price_change_pct': getattr(market, 'price_change_24h_pct', None),
            'status': 'success'
        })

    # Analyze strategies
    all_alerts = analyze_all_strategies(results)

    # Apply filters (with optional deduplication)
    alerts, updated_state, filter_stats = filter_alerts(
        all_alerts,
        tiers=tier_filter,
        min_confidence=args.min_confidence,
        enable_dedup=args.enable_dedup
    )

    # Show filtering statistics
    print(f"\n📊 Filtering Results:")
    print(f"   Total strategies checked: {filter_stats['total_checked']}")
    print(f"   Filtered by tier: {filter_stats['tier_filtered']}")
    print(f"   Filtered by confidence: {filter_stats['confidence_filtered']}")

    if args.enable_dedup:
        print(f"   Suppressed by dedup: {filter_stats['dedup_suppressed']}")
        print(f"   Passed all filters: {filter_stats['passed']}")

        # Show daily statistics
        if updated_state:
            daily_stats = updated_state.get('daily_stats', {})
            print(f"\n📈 Today's Statistics ({daily_stats.get('date', 'N/A')}):")
            print(f"   Total alerts sent: {daily_stats.get('total_alerts', 0)}")
            print(f"   Total suppressed: {daily_stats.get('suppressed_alerts', 0)}")

            alerts_by_tier = daily_stats.get('alerts_by_tier', {})
            if alerts_by_tier:
                print(f"   Alerts by tier:")
                print(f"      Tier 1 (CRITICAL): {alerts_by_tier.get('tier_1', 0)}")
                print(f"      Tier 2 (HIGH): {alerts_by_tier.get('tier_2', 0)}")
                print(f"      Tier 3+ (BACKGROUND): {alerts_by_tier.get('tier_3', 0)}")
    else:
        print(f"   Passed filters: {filter_stats['passed']}")

    print()

    if not alerts:
        print("✅ Market analyzed. No high-confidence strategy setups detected.")
        print("   Current conditions don't favor any specific strategy.\n")
        if all_alerts:
            print(f"   ({len(all_alerts)} lower-confidence alert(s) were filtered out)")
        return

    # Display alerts
    print(f"🚨 {len(alerts)} STRATEGY ALERT(S) DETECTED!\n")
    print("="*80)

    for i, alert in enumerate(alerts, 1):
        direction = alert.get('direction', 'N/A')

        # Direction emoji
        if 'LONG' in direction and 'SHORT' not in direction:
            direction_emoji = "📈"
        elif 'SHORT' in direction and 'LONG' not in direction:
            direction_emoji = "📉"
        elif 'BOTH' in direction:
            direction_emoji = "⚖️"
        elif 'NEUTRAL' in direction:
            direction_emoji = "⚪"
        else:
            direction_emoji = "❓"

        print(f"\n{i}. {alert['strategy']} - Confidence: {alert['confidence']}%")
        print(f"   Direction: {direction_emoji} {direction}")
        print("-"*80)
        print(alert['recommendation'])
        print()

    print("="*80)

    # Send to Discord if configured
    if webhook_url and alerts:
        print("\n📤 Sending alert to Discord...\n")
        send_strategy_alert_to_discord(alerts, webhook_url)


if __name__ == "__main__":
    main()
