#!/usr/bin/env python3
"""
Crypto Perpetual Futures Market Report Generator
Transforms raw exchange data into actionable market intelligence
"""

import os
import json
import yaml
import requests
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dotenv import load_dotenv
from compare_all_exchanges import fetch_all_enhanced

# Load environment variables from .env file
load_dotenv()

# Chart generation
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

# Tableau color palette (professionally designed, colorblind-safe)
TABLEAU_COLORS = {
    'blue': '#4E79A7',
    'orange': '#F28E2B',
    'red': '#E15759',
    'teal': '#76B7B2',
    'green': '#59A14F',
    'yellow': '#EDC948',
    'purple': '#B07AA1',
    'pink': '#FF9DA7',
    'brown': '#9C755F',
    'gray': '#BAB0AC'
}


def add_gradient_to_bar(ax, bar, color):
    """Add vertical gradient to a bar for visual depth"""
    x, y = bar.get_xy()
    width = bar.get_width()
    height = bar.get_height()

    # Create gradient (darker at bottom, lighter at top for positive; reverse for negative)
    if height >= 0:
        colors_gradient = [color, color + '99']  # Add transparency for lighter top
    else:
        colors_gradient = [color + '99', color]

    # Use a gradient fill
    gradient = ax.imshow(
        [[0, 0], [1, 1]],
        cmap=LinearSegmentedColormap.from_list('grad', colors_gradient),
        aspect='auto',
        extent=[x, x + width, y, y + height],
        alpha=0.3,
        zorder=1
    )
    return gradient


def generate_funding_rate_chart(results: List[Dict]) -> bytes:
    """Generate funding rate comparison bar chart with Cyberpunk Amber styling"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    # Filter successful exchanges with BTC funding rates
    exchanges = []
    rates = []
    colors = []

    for r in results:
        if r.get('status') == 'success' and r.get('funding_rate') is not None:
            exchanges.append(r['exchange'])
            rate = r['funding_rate']
            rates.append(rate)

            # Amber color palette
            if rate > 0.01:
                colors.append('#FF6B35')  # Bright amber-red - expensive to be long
            elif rate < 0:
                colors.append('#F7931E')  # Bitcoin orange - profitable to be long
            else:
                colors.append('#FDB44B')  # Warm amber - neutral

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create bars with amber palette
    bars = ax.bar(exchanges, rates, color=colors, alpha=0.9, edgecolor='#FFA500', linewidth=2, zorder=2)

    # Add subtle glow effect
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Add value labels with amber glow
    for bar, rate in zip(bars, rates):
        height = bar.get_height()
        x_pos = bar.get_x() + bar.get_width() / 2

        ax.text(x_pos, height,
                f'{rate:.4f}%',
                ha='center', va='bottom' if rate >= 0 else 'top',
                fontsize=11, fontweight='bold', color='#FFD700',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='#FFA500', alpha=0.8, linewidth=1))

    # Enhanced typography
    ax.set_xlabel('Exchange', fontsize=14, fontweight='bold', color='#FFD700', labelpad=10)
    ax.set_ylabel('Funding Rate (%)', fontsize=14, fontweight='bold', color='#FFD700', labelpad=10)
    ax.set_title('⚡ BTC Funding Rates by Exchange', fontsize=16, fontweight='bold', pad=20, color='#FFA500')

    # Reference line with amber accent
    ax.axhline(y=0, color='#FF8C00', linestyle='-', linewidth=1.5, alpha=0.6, zorder=1)
    ax.grid(axis='y', alpha=0.1, color='#FF8C00', linewidth=0.5, zorder=0)

    # Amber-tinted tick styling
    ax.tick_params(axis='x', colors='#FFD700', labelsize=11)
    ax.tick_params(axis='y', colors='#FFD700', labelsize=11)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')  # Reset style

    return chart_bytes


def generate_market_dominance_chart(dominance: Dict) -> bytes:
    """Generate market share pie chart with Cyberpunk Amber styling"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    leaders = dominance.get('leaders', [])

    exchanges = [l['exchange'] for l in leaders[:5]]
    shares = [l['share'] for l in leaders[:5]]

    # Add "Others" if there are more exchanges
    if len(leaders) > 5:
        others_share = sum(l['share'] for l in leaders[5:])
        exchanges.append('Others')
        shares.append(others_share)

    # Amber color gradient palette
    amber_pie_colors = [
        '#FF6B35',  # Bright amber-red
        '#FF8C42',  # Medium amber
        '#FFA500',  # Pure orange
        '#FFB84D',  # Light amber
        '#F7931E',  # Bitcoin orange
        '#FDB44B'   # Warm amber
    ]

    # Create chart
    fig, ax = plt.subplots(figsize=(10, 8))

    wedges, texts, autotexts = ax.pie(
        shares,
        labels=exchanges,
        autopct='%1.1f%%',
        colors=amber_pie_colors[:len(exchanges)],
        startangle=90,
        explode=[0.08] * len(exchanges),
        wedgeprops={'edgecolor': '#FFA500', 'linewidth': 2.5, 'antialiased': True},
        textprops={'fontsize': 14}
    )

    # Add subtle glow to pie chart
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Percentage text with amber glow
    for autotext in autotexts:
        autotext.set_color('#FFD700')
        autotext.set_fontsize(13)
        autotext.set_fontweight('bold')
        autotext.set_bbox(dict(boxstyle='round,pad=0.4', facecolor='#1a1a1a', edgecolor='#FFA500', alpha=0.9, linewidth=1.5))

    # Labels with amber color
    for text in texts:
        text.set_fontsize(14)
        text.set_fontweight('bold')
        text.set_color('#FFD700')

    ax.set_title('💎 Market Dominance by Exchange', fontsize=16, fontweight='bold', pad=20, color='#FFA500')

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()
    plt.style.use('default')  # Reset style

    return chart_bytes


def generate_basis_chart(basis_data: List[Dict]) -> bytes:
    """Generate spot-futures basis comparison chart with Cyberpunk Amber styling"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    exchanges = [b['exchange'] for b in basis_data]
    basis_pcts = [b['basis_pct'] for b in basis_data]

    # Use amber color palette for basis levels
    colors = []
    for b in basis_pcts:
        if b > 0.05:
            colors.append('#FF6B35')  # Bright amber-red (Contango)
        elif b < -0.05:
            colors.append('#F7931E')  # Bitcoin orange (Backwardation)
        else:
            colors.append('#FDB44B')  # Warm amber (Neutral)

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create bars with amber styling
    bars = ax.bar(exchanges, basis_pcts, color=colors, alpha=0.9, edgecolor='#FFA500', linewidth=2)

    # Add subtle glow effect
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Add value labels with amber styling
    for i, (bar, basis) in enumerate(zip(bars, basis_pcts)):
        height = bar.get_height()
        y_pos = height if height >= 0 else 0
        va = 'bottom' if height >= 0 else 'top'

        ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                f'{basis:.4f}%',
                ha='center', va=va,
                fontsize=11, fontweight='bold', color='#FFD700')

    # Amber typography
    ax.set_xlabel('Exchange', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_ylabel('Basis (%)', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_title('📊 Spot-Futures Basis by Exchange', fontsize=16, fontweight='bold',
                 pad=20, color='#FFA500')

    # Amber reference lines
    ax.axhline(y=0, color='#888888', linestyle='-', linewidth=1.5, alpha=0.8)
    ax.axhline(y=0.05, color='#FF6B35', linestyle='--', linewidth=1, alpha=0.7, label='Contango threshold')
    ax.axhline(y=-0.05, color='#F7931E', linestyle='--', linewidth=1, alpha=0.7, label='Backwardation threshold')
    ax.grid(axis='y', alpha=0.2, color='#FFD700', linewidth=0.5)

    # Amber legend
    legend = ax.legend(fontsize=11, framealpha=0.9)
    plt.setp(legend.get_texts(), color='#FFD700')

    # Gold tick styling
    ax.tick_params(axis='x', colors='#FFD700', labelsize=11)
    ax.tick_params(axis='y', colors='#FFD700', labelsize=11)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()

    # Reset style to avoid affecting other charts
    plt.style.use('default')

    return chart_bytes


def generate_leverage_chart(basis_metrics: Dict) -> bytes:
    """Generate futures/spot volume ratio chart with Cyberpunk Amber styling"""

    # Apply cyberpunk style
    try:
        import mplcyberpunk
        plt.style.use("cyberpunk")
    except ImportError:
        plt.style.use('dark_background')

    basis_data = basis_metrics.get('basis_data', [])

    # Filter exchanges with both volumes
    exchanges = []
    ratios = []
    colors = []

    for b in basis_data:
        if b.get('spot_volume') and b.get('futures_volume'):
            spot_vol = b['spot_volume']
            futures_vol = b['futures_volume']

            if spot_vol > 0:
                ratio = futures_vol / spot_vol
                exchanges.append(b['exchange'])
                ratios.append(ratio)

                # Use amber color palette for leverage levels
                if ratio > 5.0:
                    colors.append('#FF6B35')  # Bright amber-red (Extreme leverage)
                elif ratio > 2.0:
                    colors.append('#FFA500')  # Pure orange (High leverage)
                elif ratio < 1.0:
                    colors.append('#F7931E')  # Bitcoin orange (Spot dominant)
                else:
                    colors.append('#FDB44B')  # Warm amber (Balanced)

    if not exchanges:
        return None

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create bars with amber styling
    bars = ax.bar(exchanges, ratios, color=colors, alpha=0.9, edgecolor='#FFA500', linewidth=2)

    # Add subtle glow effect
    try:
        import mplcyberpunk
        mplcyberpunk.add_glow_effects(ax=ax)
    except (ImportError, TypeError):
        pass

    # Add value labels with amber styling
    for i, (bar, ratio) in enumerate(zip(bars, ratios)):
        height = bar.get_height()
        y_pos = height

        # Add warning emoji for extreme leverage
        label_text = f'{ratio:.2f}x'
        if ratio > 5.0:
            label_text = f'⚠️ {ratio:.2f}x'

        ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                label_text,
                ha='center', va='bottom',
                fontsize=11, fontweight='bold', color='#FFD700')

    # Amber typography
    ax.set_xlabel('Exchange', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_ylabel('Futures/Spot Volume Ratio', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_title('⚡ Leverage Activity by Exchange (Higher = More Speculation)',
                 fontsize=16, fontweight='bold', pad=20, color='#FFA500')

    # Amber reference lines
    ax.axhline(y=1.0, color='#888888', linestyle='-', linewidth=1.5, alpha=0.8)
    ax.axhline(y=3.0, color='#FFA500', linestyle='--', linewidth=1, alpha=0.7, label='High leverage threshold')
    ax.axhline(y=5.0, color='#FF6B35', linestyle='--', linewidth=1, alpha=0.7, label='Extreme leverage threshold')
    ax.grid(axis='y', alpha=0.2, color='#FFD700', linewidth=0.5)

    # Amber legend
    legend = ax.legend(fontsize=11, framealpha=0.9)
    plt.setp(legend.get_texts(), color='#FFD700')

    # Gold tick styling
    ax.tick_params(axis='x', colors='#FFD700', labelsize=11)
    ax.tick_params(axis='y', colors='#FFD700', labelsize=11)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    chart_bytes = buf.getvalue()
    plt.close()

    # Reset style to avoid affecting other charts
    plt.style.use('default')

    return chart_bytes


def fetch_long_short_ratio() -> Dict:
    """
    Fetch BTC long/short ratio from OKX

    Returns:
        {
            'ratio': 2.09,        # Longs per short
            'long_pct': 0.676,    # 67.6% long
            'short_pct': 0.324,   # 32.4% short
            'status': 'success'
        }
    """
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
            params={"ccy": "BTC"},
            timeout=5
        ).json()

        if response.get('code') == '0' and response.get('data'):
            # Get most recent ratio (first element)
            latest = response['data'][0]
            ratio = float(latest[1])  # Format: [timestamp, ratio_string]

            # Calculate percentages
            # ratio = longs / shorts
            # long% = ratio / (ratio + 1)
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
    """Enhanced multi-factor sentiment analysis using all available data"""
    successful = [r for r in results if r.get('status') == 'success']
    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

    # ========================================
    # FACTOR 1: Funding Rate (Volume-Weighted)
    # ========================================
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

    # Funding sentiment score (-1 to +1)
    if weighted_funding > 0.01:
        funding_score = min(weighted_funding / 0.05, 1.0)  # Cap at 0.05% = max bullish
        funding_signal = "🟢 BULLISH"
    elif weighted_funding < -0.01:
        funding_score = max(weighted_funding / 0.05, -1.0)  # Cap at -0.05% = max bearish
        funding_signal = "🔴 BEARISH"
    else:
        funding_score = weighted_funding / 0.01  # Scale to -1 to +1 within neutral range
        funding_signal = "⚪ NEUTRAL"

    # ========================================
    # FACTOR 2: Price Momentum (Volume-Weighted)
    # ========================================
    weighted_price_change = 0
    price_changes = []

    for r in successful:
        if r.get('price_change_pct') is not None:
            weight = r['volume'] / total_volume
            weighted_price_change += r['price_change_pct'] * weight
            price_changes.append(r['price_change_pct'])

    # Price momentum score (-1 to +1)
    if weighted_price_change > 2.0:
        price_score = min(weighted_price_change / 10.0, 1.0)  # Cap at +10% = max bullish
        price_signal = "🟢 RISING"
    elif weighted_price_change < -2.0:
        price_score = max(weighted_price_change / 10.0, -1.0)  # Cap at -10% = max bearish
        price_signal = "🔴 FALLING"
    else:
        price_score = weighted_price_change / 2.0  # Scale to -1 to +1
        price_signal = "⚪ STABLE"

    # ========================================
    # FACTOR 3: OI/Volume Ratio (Conviction)
    # ========================================
    market_oi_vol_ratio = total_oi / total_volume if total_volume > 0 else 0

    # OI/Vol conviction score (-1 to +1)
    # Low ratio (< 0.25) = speculation, neutral
    # High ratio (> 0.5) = conviction, combines with price for direction
    if market_oi_vol_ratio > 0.5:
        conviction_score = min((market_oi_vol_ratio - 0.3) / 0.3, 1.0)
        conviction_signal = "🎯 HIGH CONVICTION"
    elif market_oi_vol_ratio < 0.25:
        conviction_score = -min((0.25 - market_oi_vol_ratio) / 0.15, 1.0)
        conviction_signal = "📊 SPECULATION"
    else:
        conviction_score = 0
        conviction_signal = "⚖️ BALANCED"

    # ========================================
    # FACTOR 4: Funding Divergence (Exchange Agreement)
    # ========================================
    if len(funding_rates) > 1:
        funding_std = (sum((x - weighted_funding) ** 2 for x in funding_rates) / len(funding_rates)) ** 0.5
        # Low divergence = agreement, high = disagreement
        divergence_score = -min(funding_std / 0.01, 1.0)  # High divergence = negative

        if funding_std < 0.002:
            divergence_signal = "✅ CONSENSUS"
        elif funding_std < 0.005:
            divergence_signal = "⚠️ MIXED"
        else:
            divergence_signal = "🔀 DIVERGENT"
    else:
        divergence_score = 0
        divergence_signal = "⚪ INSUFFICIENT DATA"

    # ========================================
    # FACTOR 5: OI-Price Correlation Signal
    # ========================================
    # Rising OI + Rising Price = New longs entering (bullish)
    # Rising OI + Falling Price = New shorts entering (bearish)
    # Falling OI = Position unwinding (neutral/reversal)

    # We approximate with current state (would be better with history)
    if weighted_price_change > 0 and market_oi_vol_ratio > 0.35:
        oi_price_score = 0.5  # New longs likely
        oi_price_signal = "🟢 NEW LONGS"
    elif weighted_price_change < 0 and market_oi_vol_ratio > 0.35:
        oi_price_score = -0.5  # New shorts likely
        oi_price_signal = "🔴 NEW SHORTS"
    else:
        oi_price_score = 0
        oi_price_signal = "⚪ NEUTRAL"

    # ========================================
    # FACTOR 6: Long/Short Bias (Trader Positioning)
    # ========================================
    ls_data = fetch_long_short_ratio()

    if ls_data.get('status') == 'success':
        ratio = ls_data['ratio']
        long_pct = ls_data['long_pct']

        # Score long/short bias (contrarian indicator)
        # High ratio (too many longs) = bearish score
        # Low ratio (too many shorts) = bullish score
        if ratio > 2.5:
            # Overextended long (>71% long) = bearish contrarian
            ls_score = max(-1.0, -0.5 - (ratio - 2.5) * 0.2)
            ls_signal = "🔴 BEARISH (Crowded Long)"
        elif ratio > 1.5:
            # Moderately long (60-71% long) = slightly bearish
            ls_score = -0.3 - (ratio - 1.5) * 0.2
            ls_signal = "🟡 SLIGHTLY BEARISH (Long Bias)"
        elif ratio < 0.4:
            # Overextended short (>71% short) = bullish contrarian
            ls_score = min(1.0, 0.5 + (0.4 - ratio) * 2.0)
            ls_signal = "🟢 BULLISH (Crowded Short)"
        elif ratio < 0.67:
            # Moderately short (40-60% short) = slightly bullish
            ls_score = 0.3 + (0.67 - ratio) * 0.74
            ls_signal = "🟡 SLIGHTLY BULLISH (Short Bias)"
        else:
            # Balanced (45-55% long) = neutral
            ls_score = (1.0 - ratio) * 0.2
            ls_signal = "⚪ NEUTRAL (Balanced)"

        ls_ratio_value = ratio
        ls_long_pct = long_pct
    else:
        # If fetch failed, exclude from composite score
        ls_score = 0
        ls_signal = "⚠️ DATA UNAVAILABLE"
        ls_ratio_value = None
        ls_long_pct = None

    # ========================================
    # COMPOSITE SENTIMENT SCORE (6-FACTOR)
    # ========================================
    # Weighted combination of all factors
    composite_score = (
        funding_score * 0.35 +       # 35% weight (reduced from 40%)
        price_score * 0.20 +          # 20% weight (reduced from 25%)
        ls_score * 0.15 +             # 15% weight (NEW FACTOR)
        conviction_score * 0.15 +     # 15% weight (same)
        divergence_score * 0.08 +     # 8% weight (reduced from 10%)
        oi_price_score * 0.07         # 7% weight (reduced from 10%)
    )

    # Determine overall sentiment from composite
    if composite_score > 0.3:
        sentiment = "🟢 BULLISH"
        interpretation = f"Multi-factor analysis shows bullish bias (Score: {composite_score:.2f})"
    elif composite_score < -0.3:
        sentiment = "🔴 BEARISH"
        interpretation = f"Multi-factor analysis shows bearish bias (Score: {composite_score:.2f})"
    else:
        sentiment = "⚪ NEUTRAL"
        interpretation = f"Balanced market with mixed signals (Score: {composite_score:.2f})"

    # Strength indicator
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
        # Original metrics
        'weighted_funding': weighted_funding,
        'sentiment': sentiment,
        'interpretation': interpretation,
        'avg_price_change': weighted_price_change,
        'funding_exchanges': sorted(funding_exchanges, key=lambda x: x['rate'], reverse=True),

        # Enhanced multi-factor metrics
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
                'value': funding_std if len(funding_rates) > 1 else 0,
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


def identify_arbitrage_opportunities(results: List[Dict]) -> List[Dict]:
    """Identify potential arbitrage opportunities based on funding rate spreads"""
    successful = [r for r in results if r.get('status') == 'success' and r.get('funding_rate') is not None]

    if len(successful) < 2:
        return []

    # Sort by funding rate
    sorted_by_funding = sorted(successful, key=lambda x: x['funding_rate'])

    opportunities = []

    # Find significant spreads (>0.005% = 0.0005)
    for i, low_fr in enumerate(sorted_by_funding[:-1]):
        for high_fr in sorted_by_funding[i+1:]:
            spread = high_fr['funding_rate'] - low_fr['funding_rate']
            if spread > 0.005:  # 0.005% spread
                opportunities.append({
                    'type': 'Funding Rate Arbitrage',
                    'action': f"Short {high_fr['exchange']} / Long {low_fr['exchange']}",
                    'spread': spread,
                    'annual_yield': spread * 3 * 365,  # 3 funding periods per day
                    'risk': 'Medium' if spread < 0.02 else 'High',
                    'details': f"Collect {spread:.4f}% every 8 hours"
                })

    return sorted(opportunities, key=lambda x: x['spread'], reverse=True)


def analyze_trading_behavior(results: List[Dict]) -> Dict:
    """Analyze trading behavior patterns across exchanges"""
    successful = [r for r in results if r.get('status') == 'success']

    # Categorize exchanges by OI/Vol ratio
    day_traders = []  # < 0.3x
    balanced = []     # 0.3x - 0.5x
    position_holders = []  # > 0.5x

    for r in successful:
        oi_vol = r.get('oi_volume_ratio')
        if oi_vol is not None:
            if oi_vol < 0.3:
                day_traders.append(r['exchange'])
            elif oi_vol <= 0.5:
                balanced.append(r['exchange'])
            else:
                position_holders.append(r['exchange'])

    return {
        'day_trading_heavy': day_traders,
        'balanced': balanced,
        'position_holding': position_holders
    }


def detect_anomalies(results: List[Dict]) -> List[Dict]:
    """Detect potential wash trading or anomalies"""
    successful = [r for r in results if r.get('status') == 'success']
    anomalies = []

    for r in successful:
        # Very low OI/Vol ratio might indicate wash trading
        if r.get('oi_volume_ratio') and r['oi_volume_ratio'] < 0.15:
            anomalies.append({
                'exchange': r['exchange'],
                'type': 'Potential Wash Trading',
                'indicator': f"Very low OI/Vol ratio: {r['oi_volume_ratio']:.2f}x",
                'severity': 'Medium'
            })

        # Extreme funding rates
        if r.get('funding_rate') and abs(r['funding_rate']) > 0.05:
            anomalies.append({
                'exchange': r['exchange'],
                'type': 'Extreme Funding Rate',
                'indicator': f"Funding rate: {r['funding_rate']:.4f}%",
                'severity': 'High'
            })

    return anomalies


def fetch_spot_and_futures_basis(exchange: str) -> Optional[Dict]:
    """
    Fetch both spot and perpetual futures prices to calculate basis

    Args:
        exchange: Exchange name (OKX, Gate.io, Coinbase, Binance, or Bybit)

    Returns:
        Dict with spot_price, futures_price, basis, basis_pct, or None if failed
    """
    try:
        if exchange == "Binance":
            # Spot
            spot_resp = requests.get(
                "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
                timeout=10
            ).json()

            # Futures
            futures_resp = requests.get(
                "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT",
                timeout=10
            ).json()

            spot_price = float(spot_resp['lastPrice'])
            futures_price = float(futures_resp['lastPrice'])
            spot_volume = float(spot_resp['quoteVolume'])
            futures_volume = float(futures_resp['quoteVolume'])

        elif exchange == "Bybit":
            # Spot
            spot_resp = requests.get(
                "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT",
                timeout=10
            ).json()

            # Futures
            futures_resp = requests.get(
                "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT",
                timeout=10
            ).json()

            if spot_resp.get('retCode') != 0 or futures_resp.get('retCode') != 0:
                return None

            spot_data = spot_resp['result']['list'][0]
            futures_data = futures_resp['result']['list'][0]

            spot_price = float(spot_data['lastPrice'])
            futures_price = float(futures_data['lastPrice'])
            spot_volume = float(spot_data['turnover24h'])
            futures_volume = float(futures_data['turnover24h'])

        elif exchange == "OKX":
            # Spot
            spot_resp = requests.get(
                "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
                timeout=10
            ).json()

            # Futures
            futures_resp = requests.get(
                "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP",
                timeout=10
            ).json()

            if spot_resp.get('code') != '0' or futures_resp.get('code') != '0':
                return None

            spot_price = float(spot_resp['data'][0]['last'])
            futures_price = float(futures_resp['data'][0]['last'])
            spot_volume = float(spot_resp['data'][0]['volCcy24h'])
            futures_volume = float(futures_resp['data'][0]['volCcy24h'])

        elif exchange == "Gate.io":
            # Spot
            spot_resp = requests.get(
                "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT",
                timeout=10
            ).json()

            # Futures
            futures_resp = requests.get(
                "https://api.gateio.ws/api/v4/futures/usdt/contracts/BTC_USDT",
                timeout=10
            ).json()

            if not spot_resp or not futures_resp:
                return None

            spot_price = float(spot_resp[0]['last'])
            futures_price = float(futures_resp['mark_price'])
            spot_volume = float(spot_resp[0]['quote_volume'])
            futures_volume = None

        elif exchange == "Coinbase":
            # Spot
            spot_resp = requests.get(
                "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
                timeout=10
            ).json()

            # Futures
            futures_resp = requests.get(
                "https://api.international.coinbase.com/api/v1/instruments",
                timeout=10
            ).json()

            btc_perp = next((p for p in futures_resp if p.get('symbol') == 'BTC-PERP'), None)
            if not btc_perp:
                return None

            spot_price = float(spot_resp['price'])
            futures_price = float(btc_perp['quote']['mark_price'])
            spot_volume = None
            futures_volume = float(btc_perp['notional_24hr'])

        elif exchange == "Kraken":
            # Spot
            spot_resp = requests.get(
                "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
                timeout=10
            ).json()

            if spot_resp.get('error') and len(spot_resp['error']) > 0:
                return None

            # Futures
            futures_resp = requests.get(
                "https://futures.kraken.com/derivatives/api/v3/tickers",
                timeout=10
            ).json()

            if futures_resp.get('result') != 'success':
                return None

            # Extract BTC spot data
            spot_data = spot_resp['result']['XXBTZUSD']
            spot_price = float(spot_data['c'][0])
            spot_volume = float(spot_data['v'][1]) * spot_price  # Convert BTC to USD

            # Extract BTC perpetual futures
            btc_perp = next((t for t in futures_resp['tickers'] if t['symbol'] == 'PI_XBTUSD'), None)
            if not btc_perp:
                return None

            futures_price = float(btc_perp['markPrice'])
            futures_volume = float(btc_perp['volumeQuote'])

        else:
            return None

        # Calculate basis
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100

        return {
            'exchange': exchange,
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'spot_volume': spot_volume,
            'futures_volume': futures_volume,
            'status': 'success'
        }

    except Exception as e:
        return None


def analyze_basis_metrics() -> Dict:
    """
    Analyze spot-futures basis across available exchanges

    Returns:
        Dict with basis analysis, market structure, and arbitrage opportunities
    """
    # Fetch basis data from working exchanges
    # Note: Binance and Bybit work from VPS location, may fail locally due to geo-restrictions
    exchanges = ["Binance", "Bybit", "OKX", "Gate.io", "Coinbase", "Kraken"]
    basis_data = []

    for exchange in exchanges:
        result = fetch_spot_and_futures_basis(exchange)
        if result:
            basis_data.append(result)

    if not basis_data:
        return {'status': 'unavailable', 'exchanges_analyzed': 0}

    # Calculate average basis
    avg_basis = sum(d['basis_pct'] for d in basis_data) / len(basis_data)
    max_basis = max(d['basis_pct'] for d in basis_data)
    min_basis = min(d['basis_pct'] for d in basis_data)

    # Determine market structure
    if avg_basis > 0.15:
        market_structure = "CONTANGO (Strong)"
        structure_signal = "🟢"
        interpretation = "Futures trading at significant premium - bullish market expectations"
    elif avg_basis > 0.05:
        market_structure = "CONTANGO (Mild)"
        structure_signal = "🟢"
        interpretation = "Futures slightly above spot - neutral to bullish"
    elif avg_basis < -0.15:
        market_structure = "BACKWARDATION (Strong)"
        structure_signal = "🔴"
        interpretation = "Futures at significant discount - bearish market expectations"
    elif avg_basis < -0.05:
        market_structure = "BACKWARDATION (Mild)"
        structure_signal = "🔴"
        interpretation = "Futures slightly below spot - neutral to bearish"
    else:
        market_structure = "NEUTRAL (Tight Basis)"
        structure_signal = "⚪"
        interpretation = "Extremely efficient market - spot and futures well aligned"

    # Detect arbitrage opportunities
    arbitrage_opportunities = []
    for d in basis_data:
        if abs(d['basis_pct']) > 0.1:  # > 0.1% basis
            arb_type = "Cash-and-Carry" if d['basis_pct'] > 0 else "Reverse Cash-and-Carry"
            arbitrage_opportunities.append({
                'exchange': d['exchange'],
                'type': arb_type,
                'basis_capture': abs(d['basis_pct']),
                'action': f"Buy {d['exchange']} Spot / Sell Futures" if d['basis_pct'] > 0 else
                         f"Short {d['exchange']} Spot / Buy Futures"
            })

    # Calculate volume ratios where available
    volume_analysis = []
    for d in basis_data:
        if d.get('spot_volume') and d.get('futures_volume'):
            ratio = d['futures_volume'] / d['spot_volume']
            if ratio > 3.0:
                signal = "🔴 HIGH LEVERAGE"
                meaning = "Speculative activity dominant"
            elif ratio < 1.5:
                signal = "🟢 SPOT DOMINANT"
                meaning = "Institutional buying likely"
            else:
                signal = "⚪ BALANCED"
                meaning = "Healthy market structure"

            volume_analysis.append({
                'exchange': d['exchange'],
                'ratio': ratio,
                'signal': signal,
                'meaning': meaning
            })

    return {
        'status': 'success',
        'exchanges_analyzed': len(basis_data),
        'basis_data': basis_data,
        'avg_basis': avg_basis,
        'max_basis': max_basis,
        'min_basis': min_basis,
        'market_structure': market_structure,
        'structure_signal': structure_signal,
        'interpretation': interpretation,
        'arbitrage_opportunities': arbitrage_opportunities,
        'volume_analysis': volume_analysis
    }


def calculate_market_dominance(results: List[Dict]) -> Dict:
    """Calculate market dominance and concentration"""
    successful = [r for r in results if r.get('status') == 'success']
    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)

    # Sort by volume
    sorted_by_volume = sorted(successful, key=lambda x: x['volume'], reverse=True)

    # Calculate concentration (top 3 exchanges)
    top3_volume = sum(r['volume'] for r in sorted_by_volume[:3])
    top3_concentration = (top3_volume / total_volume) * 100

    # HHI (Herfindahl-Hirschman Index) for market concentration
    hhi = sum((r['volume'] / total_volume * 100) ** 2 for r in successful)

    # CEX vs DEX
    cex_volume = sum(r['volume'] for r in successful if r['type'] == 'CEX')
    dex_volume = sum(r['volume'] for r in successful if r['type'] == 'DEX')

    return {
        'top3_concentration': top3_concentration,
        'hhi': hhi,
        'concentration_level': 'High' if hhi > 2500 else 'Moderate' if hhi > 1500 else 'Low',
        'cex_dominance': (cex_volume / total_volume) * 100,
        'dex_share': (dex_volume / total_volume) * 100,
        'leaders': [
            {
                'exchange': r['exchange'],
                'volume': r['volume'],
                'share': (r['volume'] / total_volume) * 100
            }
            for r in sorted_by_volume[:3]
        ]
    }


def generate_recommendations(sentiment: Dict, arb_ops: List[Dict], behavior: Dict, anomalies: List[Dict]) -> List[str]:
    """Generate actionable trading recommendations"""
    recommendations = []

    # Sentiment-based recommendations
    if sentiment['sentiment'] == "🟢 BULLISH":
        recommendations.append("✅ LONG BIAS: Consider long positions on dips, funding rates favor shorts")
        recommendations.append("⚠️  CAUTION: High funding costs for longs, consider timing entries carefully")
    elif sentiment['sentiment'] == "🔴 BEARISH":
        recommendations.append("✅ SHORT BIAS: Consider short positions on rallies, funding rates favor longs")
        recommendations.append("⚠️  CAUTION: Shorts paying longs, monitor for potential squeeze")
    else:
        recommendations.append("⚪ NEUTRAL: Market balanced, focus on range trading and scalping")

    # Arbitrage opportunities
    if arb_ops:
        recommendations.append(f"💰 {len(arb_ops)} ARBITRAGE OPPORTUNITIES: Funding rate spreads detected")
        if arb_ops[0]['annual_yield'] > 10:
            recommendations.append(f"🔥 HIGH YIELD: Top opportunity offers {arb_ops[0]['annual_yield']:.1f}% annualized")

    # Trading behavior insights
    if len(behavior['day_trading_heavy']) > 3:
        recommendations.append("📊 HIGH CHURN: Multiple exchanges show day-trading patterns, expect volatility")

    if len(behavior['position_holding']) > 2:
        recommendations.append("🎯 CONVICTION TRADES: Strong position holding suggests directional conviction")

    # Anomalies
    if anomalies:
        recommendations.append(f"⚠️  {len(anomalies)} ANOMALIES DETECTED: Review market health section")

    return recommendations


def format_market_report(results: List[Dict]) -> str:
    """Generate comprehensive market report"""
    successful = [r for r in results if r.get('status') == 'success']

    # Calculate metrics
    sentiment = analyze_market_sentiment(results)
    basis_metrics = analyze_basis_metrics()  # NEW: Spot-futures basis analysis
    arb_opportunities = identify_arbitrage_opportunities(results)
    trading_behavior = analyze_trading_behavior(results)
    anomalies = detect_anomalies(results)
    dominance = calculate_market_dominance(results)
    recommendations = generate_recommendations(sentiment, arb_opportunities, trading_behavior, anomalies)

    # Calculate totals
    total_volume = sum(r['volume'] for r in successful)
    total_oi = sum(r.get('open_interest', 0) or 0 for r in successful)
    total_markets = sum(r['markets'] for r in successful)

    output = []

    # Header
    output.append("\n")
    output.append("="*150)
    
    output.append(f"{'CRYPTO PERPETUAL FUTURES MARKET REPORT':^150}")
    output.append(f"{'Cross-Exchange Analysis • Generated: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'):^150}")
    output.append(f"{'Powered by Virtuoso Crypto [virtuosocrypto.com]':^150}")
    
    output.append("="*150)
    output.append("")

    # Executive Summary - Enhanced for Traders
    output.append("\n" + "="*100)
    output.append("📊 EXECUTIVE SUMMARY")
    output.append("="*150)

    # Core Market Data
    output.append(f"Total Daily Volume:        ${total_volume/1e9:>8.2f}B across {len(successful)} exchanges")
    output.append(f"Total Open Interest:       ${total_oi/1e9:>8.2f}B")
    output.append(f"Markets Tracked:           {total_markets:>8,} trading pairs")

    # Market Sentiment (Enhanced)
    output.append(f"\n{'─'*150}")
    output.append("🎯 MARKET SENTIMENT & POSITIONING")
    output.append(f"{'─'*150}")
    output.append(f"Overall Direction:         {sentiment['sentiment']} ({sentiment['strength']} Signal, Score: {sentiment['composite_score']:.3f})")
    output.append(f"Price Momentum (24h):      {sentiment['avg_price_change']:>7.2f}%")

    # Long/Short Bias
    ls_ratio = sentiment.get('factors', {}).get('long_short_bias', {}).get('value')
    ls_long_pct = sentiment.get('factors', {}).get('long_short_bias', {}).get('long_pct')
    if ls_ratio and ls_long_pct:
        ls_emoji = "🟢" if ls_long_pct > 0.65 else "🔴" if ls_long_pct < 0.35 else "⚪"
        contrarian_signal = "Bearish" if ls_long_pct > 0.65 else "Bullish" if ls_long_pct < 0.35 else "Neutral"
        output.append(f"Trader Positioning:        {ls_emoji} {ls_long_pct*100:.1f}% Long / {(1-ls_long_pct)*100:.1f}% Short (Contrarian: {contrarian_signal})")

    # Funding Rate Summary
    output.append(f"\n{'─'*150}")
    output.append("💰 FUNDING RATE ENVIRONMENT")
    output.append(f"{'─'*150}")
    output.append(f"Weighted Avg Funding:      {sentiment['weighted_funding']:>7.4f}% per 8h ({sentiment['weighted_funding']*3*365:.2f}% annual)")

    # Funding extremes
    funding_exchanges = sentiment.get('funding_exchanges', [])
    if funding_exchanges:
        highest_funding = max(funding_exchanges, key=lambda x: x['rate'])
        lowest_funding = min(funding_exchanges, key=lambda x: x['rate'])
        funding_spread = highest_funding['rate'] - lowest_funding['rate']

        output.append(f"Highest Funding:           {highest_funding['exchange']}: {highest_funding['rate']:.4f}% ({highest_funding['rate']*3*365:.1f}% annual)")
        output.append(f"Lowest Funding:            {lowest_funding['exchange']}: {lowest_funding['rate']:.4f}% ({lowest_funding['rate']*3*365:.1f}% annual)")
        output.append(f"Funding Spread:            {funding_spread:.4f}% ({funding_spread*3*365:.1f}% arb potential)")

        # Funding cost interpretation
        if sentiment['weighted_funding'] > 0.01:
            output.append(f"⚠️  Longs Expensive:        Paying {sentiment['weighted_funding']*3*365:.1f}% annual to hold long positions")
        elif sentiment['weighted_funding'] < -0.01:
            output.append(f"💎 Longs Profitable:       Collecting {abs(sentiment['weighted_funding'])*3*365:.1f}% annual to hold long positions")
        else:
            output.append(f"✅ Neutral Funding:         Minimal cost to hold either direction")

    # Market Structure (Spot-Futures)
    high_leverage_count = 0  # Initialize for risk assessment later
    if basis_metrics.get('status') == 'success':
        output.append(f"\n{'─'*150}")
        output.append("📈 MARKET STRUCTURE (SPOT vs FUTURES)")
        output.append(f"{'─'*150}")
        output.append(f"Basis Environment:         {basis_metrics['structure_signal']} {basis_metrics['market_structure']}")
        output.append(f"Average Basis:             {basis_metrics['avg_basis']:>7.4f}% ({basis_metrics['interpretation']})")

        # Leverage assessment
        high_leverage_count = sum(1 for va in basis_metrics.get('volume_analysis', []) if va['ratio'] > 3.0)
        if high_leverage_count > 0:
            output.append(f"⚠️  High Leverage Alert:    {high_leverage_count} exchange(s) showing speculative dominance (>3x futures/spot)")

    # OI/Vol Conviction
    conviction_value = sentiment.get('factors', {}).get('conviction', {}).get('value')
    if conviction_value:
        if conviction_value > 0.5:
            conviction_msg = f"🎯 High Conviction:        {conviction_value:.2f}x OI/Vol - Traders holding positions"
        elif conviction_value < 0.3:
            conviction_msg = f"⚡ Day-Trading Heavy:      {conviction_value:.2f}x OI/Vol - Quick profit-taking dominant"
        else:
            conviction_msg = f"⚖️  Balanced Trading:       {conviction_value:.2f}x OI/Vol - Mixed timeframes"
        output.append(f"\n{conviction_msg}")

    # Opportunities & Alerts
    output.append(f"\n{'─'*150}")
    output.append("🔔 OPPORTUNITIES & ALERTS")
    output.append(f"{'─'*150}")

    # Arbitrage opportunities
    arb_count = len(arb_opportunities) if arb_opportunities else 0
    if arb_count > 0:
        top_arb = arb_opportunities[0]
        output.append(f"💎 Arbitrage Opportunities: {arb_count} detected (Best: {top_arb['annual_yield']:.1f}% annual)")
    else:
        output.append(f"💎 Arbitrage Opportunities: None detected (tight market)")

    # Anomalies
    if anomalies:
        output.append(f"⚠️  Market Anomalies:        {len(anomalies)} detected - Review health section")
        for anomaly in anomalies[:2]:  # Show top 2
            output.append(f"   • {anomaly['exchange']}: {anomaly['type']}")
    else:
        output.append(f"✅ Market Health:           No anomalies detected")

    # Quick Action Summary
    output.append(f"\n{'─'*150}")
    output.append("⚡ QUICK ACTION SUMMARY")
    output.append(f"{'─'*150}")

    # Direction bias
    if sentiment['sentiment'] == "🟢 BULLISH":
        output.append("📈 Bias: LONG on dips | ⚠️  High funding costs")
    elif sentiment['sentiment'] == "🔴 BEARISH":
        output.append("📉 Bias: SHORT on rallies | ⚠️  Potential squeeze risk")
    else:
        output.append("↔️  Bias: RANGE TRADING | Focus on scalping and mean reversion")

    # Top opportunity
    if arb_count > 0:
        output.append(f"💰 Best Trade: {arb_opportunities[0]['action']} ({arb_opportunities[0]['annual_yield']:.1f}% annual)")

    # Risk level
    risk_factors = []
    if sentiment.get('weighted_funding', 0) > 0.01 or sentiment.get('weighted_funding', 0) < -0.01:
        risk_factors.append("Extreme Funding")
    if high_leverage_count > 2:
        risk_factors.append("High Leverage")
    if anomalies and len(anomalies) > 1:
        risk_factors.append("Multiple Anomalies")

    if risk_factors:
        output.append(f"⚠️  Risk Factors: {', '.join(risk_factors)}")
    else:
        output.append("✅ Risk Level: NORMAL - Stable market conditions")

    # Market Sentiment Analysis
    output.append("\n" + "="*100)
    output.append("💭 ENHANCED MULTI-FACTOR SENTIMENT ANALYSIS")
    output.append("="*150)
    output.append(f"Overall Sentiment: {sentiment['sentiment']} ({sentiment['strength']} Signal)")
    output.append(f"Composite Score:   {sentiment['composite_score']:.3f} (Range: -1.0 to +1.0)")
    output.append(f"Interpretation:    {sentiment['interpretation']}\n")

    # Multi-factor breakdown
    output.append("📊 Sentiment Factor Breakdown:")
    output.append(f"{'Factor':<25} {'Signal':<20} {'Score':<10} {'Weight':<10} {'Value'}")
    output.append("-"*150)

    factors = sentiment['factors']
    output.append(
        f"{'1. Funding Rate':<25} {factors['funding']['signal']:<20} "
        f"{factors['funding']['score']:>8.3f}  {factors['funding']['weight']*100:>7.0f}%    "
        f"{factors['funding']['value']:.4f}%"
    )
    output.append(
        f"{'2. Price Momentum':<25} {factors['price_momentum']['signal']:<20} "
        f"{factors['price_momentum']['score']:>8.3f}  {factors['price_momentum']['weight']*100:>7.0f}%    "
        f"{factors['price_momentum']['value']:.2f}%"
    )

    # Long/Short Bias (NEW!)
    ls_value = factors['long_short_bias']['value']
    ls_long_pct = factors['long_short_bias'].get('long_pct')
    if ls_value is not None and ls_long_pct is not None:
        ls_display = f"{ls_value:.2f}:1 ({ls_long_pct*100:.1f}% long)"
    else:
        ls_display = "N/A"

    output.append(
        f"{'3. Long/Short Bias ⭐':<25} {factors['long_short_bias']['signal']:<20} "
        f"{factors['long_short_bias']['score']:>8.3f}  {factors['long_short_bias']['weight']*100:>7.0f}%    "
        f"{ls_display}"
    )

    output.append(
        f"{'4. OI/Vol Conviction':<25} {factors['conviction']['signal']:<20} "
        f"{factors['conviction']['score']:>8.3f}  {factors['conviction']['weight']*100:>7.0f}%    "
        f"{factors['conviction']['value']:.3f}x"
    )
    output.append(
        f"{'5. Exchange Agreement':<25} {factors['divergence']['signal']:<20} "
        f"{factors['divergence']['score']:>8.3f}  {factors['divergence']['weight']*100:>7.0f}%    "
        f"{factors['divergence']['value']:.4f}% std"
    )
    output.append(
        f"{'6. OI-Price Pattern':<25} {factors['oi_price_correlation']['signal']:<20} "
        f"{factors['oi_price_correlation']['score']:>8.3f}  {factors['oi_price_correlation']['weight']*100:>7.0f}%    "
        f"{factors['oi_price_correlation']['value']}"
    )

    output.append("\n💡 Factor Explanations:")
    output.append("   • Funding Rate: Longs pay shorts (positive) or vice versa (negative)")
    output.append("   • Price Momentum: 24h volume-weighted price change across all exchanges")
    output.append("   ⭐ Long/Short Bias: % of traders long vs short (contrarian indicator)")
    output.append("   • OI/Vol Conviction: High ratio = position holders, Low = day traders")
    output.append("   • Exchange Agreement: How much funding rates vary across exchanges")
    output.append("   • OI-Price Pattern: Rising OI + Rising Price = New longs, etc.")

    output.append("\n📈 Funding Rates by Exchange (BTC):")
    output.append(f"{'Exchange':<15} {'Funding Rate':>12} {'Volume Weight':>12} {'Annual Cost/Yield'}")
    output.append("-"*150)
    for fe in sentiment['funding_exchanges']:
        annual = fe['rate'] * 3 * 365  # 3 funding periods per day
        output.append(
            f"{fe['exchange']:<15} {fe['rate']:>11.4f}% {fe['weight']*100:>11.1f}% "
            f"{annual:>15.2f}%"
        )

    # Spot-Futures Basis Analysis
    if basis_metrics.get('status') == 'success':
        output.append("\n" + "="*100)
        output.append("💱 SPOT-FUTURES BASIS ANALYSIS (CONTANGO/BACKWARDATION)")
        output.append("="*150)
        output.append(f"Market Structure:     {basis_metrics['structure_signal']} {basis_metrics['market_structure']}")
        output.append(f"Average Basis:        {basis_metrics['avg_basis']:>7.4f}%")
        output.append(f"Basis Range:          {basis_metrics['min_basis']:>7.4f}% to {basis_metrics['max_basis']:>7.4f}%")
        output.append(f"Exchanges Analyzed:   {basis_metrics['exchanges_analyzed']}")
        output.append(f"\nInterpretation:       {basis_metrics['interpretation']}")

        # Basis details by exchange
        output.append("\n📊 Basis Breakdown by Exchange:")
        output.append(f"{'Exchange':<15} {'Spot Price':>12} {'Futures Price':>14} {'Basis ($)':>10} {'Basis (%)':>10}")
        output.append("-"*150)
        for bd in basis_metrics['basis_data']:
            output.append(
                f"{bd['exchange']:<15} ${bd['spot_price']:>11,.2f} ${bd['futures_price']:>13,.2f} "
                f"${bd['basis']:>9,.2f} {bd['basis_pct']:>9.4f}%"
            )

        # Volume ratio analysis
        if basis_metrics['volume_analysis']:
            output.append("\n📈 Spot vs Futures Volume Ratio:")
            output.append(f"{'Exchange':<15} {'Ratio':>10} {'Signal':<20} {'Interpretation'}")
            output.append("-"*150)
            for va in basis_metrics['volume_analysis']:
                output.append(
                    f"{va['exchange']:<15} {va['ratio']:>9.2f}x {va['signal']:<20} {va['meaning']}"
                )

        # Cash-and-carry arbitrage opportunities
        if basis_metrics['arbitrage_opportunities']:
            output.append("\n💰 Basis Arbitrage Opportunities:")
            for arb in basis_metrics['arbitrage_opportunities']:
                output.append(f"\n   {arb['type']} - {arb['exchange']}")
                output.append(f"   Action: {arb['action']}")
                output.append(f"   Basis Capture: {arb['basis_capture']:.4f}%")
        else:
            output.append("\n✅ No significant basis arbitrage opportunities (tight basis < 0.1%)")

        output.append("\n💡 Key Concepts:")
        output.append("   • Contango = Futures > Spot (bullish expectations, futures at premium)")
        output.append("   • Backwardation = Futures < Spot (bearish expectations, futures at discount)")
        output.append("   • Tight basis (< 0.05%) = Efficient market, no arbitrage")
        output.append("   • Wide basis (> 0.15%) = Potential cash-and-carry arbitrage")
        output.append("   • High futures/spot volume ratio (>3x) = Speculation, leverage risk")
        output.append("   • Low ratio (<1.5x) = Spot dominant, institutional buying")

    # Market Dominance
    output.append("\n" + "="*100)
    output.append("🏆 MARKET DOMINANCE & CONCENTRATION")
    output.append("="*150)
    output.append(f"Top 3 Concentration:    {dominance['top3_concentration']:.1f}% (HHI: {dominance['hhi']:.0f} - {dominance['concentration_level']})")
    output.append(f"CEX Dominance:          {dominance['cex_dominance']:.1f}%")
    output.append(f"DEX Market Share:       {dominance['dex_share']:.1f}%\n")

    output.append("Market Leaders:")
    for i, leader in enumerate(dominance['leaders'], 1):
        output.append(f"{i}. {leader['exchange']:<12} ${leader['volume']/1e9:>6.2f}B ({leader['share']:>5.1f}% market share)")

    # Trading Behavior
    output.append("\n" + "="*100)
    output.append("📈 TRADING BEHAVIOR PATTERNS")
    output.append("="*150)

    if trading_behavior['day_trading_heavy']:
        output.append(f"Day-Trading Heavy (<0.3x OI/Vol):    {', '.join(trading_behavior['day_trading_heavy'])}")
    if trading_behavior['balanced']:
        output.append(f"Balanced (0.3-0.5x OI/Vol):          {', '.join(trading_behavior['balanced'])}")
    if trading_behavior['position_holding']:
        output.append(f"Position Holding (>0.5x OI/Vol):     {', '.join(trading_behavior['position_holding'])}")

    output.append("\nInterpretation:")
    output.append("• Low OI/Vol = High intraday speculation, quick profit-taking")
    output.append("• High OI/Vol = Conviction trades, traders holding positions overnight")

    # Arbitrage Opportunities
    if arb_opportunities:
        output.append("\n" + "="*100)
        output.append("💰 ARBITRAGE OPPORTUNITIES")
        output.append("="*150)
        output.append(f"Found {len(arb_opportunities)} potential opportunities:\n")

        for i, opp in enumerate(arb_opportunities[:5], 1):  # Top 5
            output.append(f"{i}. {opp['type']}")
            output.append(f"   Action: {opp['action']}")
            output.append(f"   Spread: {opp['spread']:.4f}% per funding period")
            output.append(f"   Annualized Yield: {opp['annual_yield']:.2f}%")
            output.append(f"   Risk Level: {opp['risk']}")
            output.append(f"   Details: {opp['details']}\n")

    # Anomalies
    if anomalies:
        output.append("\n" + "="*100)
        output.append("⚠️  MARKET HEALTH & ANOMALIES")
        output.append("="*150)
        for anomaly in anomalies:
            output.append(f"[{anomaly['severity']}] {anomaly['exchange']}: {anomaly['type']}")
            output.append(f"         {anomaly['indicator']}\n")

    # Recommendations
    output.append("\n" + "="*100)
    output.append("🎯 TRADING RECOMMENDATIONS")
    output.append("="*150)
    for i, rec in enumerate(recommendations, 1):
        output.append(f"{i}. {rec}")

    # Risk Warnings
    output.append("\n" + "="*100)
    output.append("⚠️  RISK DISCLOSURE")
    output.append("="*150)
    output.append("• Perpetual futures trading involves significant risk of loss")
    output.append("• Funding rates can change rapidly; past rates don't guarantee future rates")
    output.append("• High leverage amplifies both gains and losses")
    output.append("• Market conditions can change quickly; this report is a snapshot in time")
    output.append("• Always use proper risk management and position sizing")

    # Footer
    output.append("\n" + "="*100)
    output.append("📝 REPORT METADATA")
    output.append("="*150)
    output.append(f"Data Sources: {len(successful)} exchanges (Binance, OKX, Bybit, Gate.io, Bitget, Coinbase INTX, HyperLiquid, AsterDEX, dYdX)")
    output.append(f"OI Coverage: 8/9 exchanges (88.9% coverage)")
    output.append(f"Spot-Futures Analysis: {basis_metrics.get('exchanges_analyzed', 0)}/6 exchanges (Binance, Bybit, OKX, Gate.io, Coinbase, Kraken)")
    output.append(f"Report Version: 2.2 (6-Exchange Spot-Futures + Institutional Insight)")
    output.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    output.append("="*150 + "\n")

    return "\n".join(output)


def extract_executive_summary(report_text: str, results: List[Dict]) -> Dict:
    """Extract key metrics from report for Discord summary embed"""

    # Calculate metrics from results
    successful = [r for r in results if r.get('status') == 'success']

    total_volume = sum(r.get('volume', 0) for r in successful)
    total_oi = sum(r.get('open_interest', 0) for r in successful if r.get('open_interest'))

    # Get sentiment from report
    sentiment_line = [line for line in report_text.split('\n') if 'Overall Sentiment:' in line]
    sentiment = sentiment_line[0].split(':')[1].strip() if sentiment_line else "UNKNOWN"

    # Get top exchange
    top_exchange = max(successful, key=lambda x: x.get('volume', 0))

    # Get basis metrics
    basis_line = [line for line in report_text.split('\n') if 'Average Basis:' in line]
    avg_basis = basis_line[0].split(':')[1].strip() if basis_line else "N/A"

    # Get arbitrage opportunities count
    arb_line = [line for line in report_text.split('\n') if 'Found' in line and 'opportunities' in line]
    arb_count = 0
    best_arb_yield = "N/A"

    if arb_line:
        try:
            arb_count = int(arb_line[0].split('Found')[1].split('potential')[0].strip())
            # Get best yield
            yield_lines = [line for line in report_text.split('\n') if 'Annualized Yield:' in line]
            if yield_lines:
                best_arb_yield = yield_lines[0].split(':')[1].strip()
        except Exception:
            pass

    # Get anomalies count
    anomaly_section = report_text.split('MARKET HEALTH & ANOMALIES')
    anomaly_count = 0
    if len(anomaly_section) > 1:
        anomaly_count = anomaly_section[1].count('[Medium]') + anomaly_section[1].count('[High]')

    return {
        'volume': f"${total_volume/1e9:.2f}B",
        'oi': f"${total_oi/1e9:.2f}B",
        'sentiment': sentiment,
        'top_exchange': f"{top_exchange['exchange']} (${top_exchange.get('volume', 0)/1e9:.2f}B)",
        'avg_basis': avg_basis,
        'arb_count': arb_count,
        'best_arb_yield': best_arb_yield,
        'anomaly_count': anomaly_count,
        'health': f"{anomaly_count} anomaly detected" if anomaly_count == 1 else f"{anomaly_count} anomalies detected" if anomaly_count > 0 else "No anomalies ✅"
    }


def generate_actionable_recommendations(results: List[Dict], sentiment: Dict, basis_metrics: Dict, arb_opportunities: List[Dict]) -> List[str]:
    """Generate specific, actionable trading recommendations"""

    recommendations = []
    composite_score = sentiment.get('composite_score', 0)
    price_change = sentiment.get('price_momentum', 0)

    # 1. Sentiment-based entry/exit
    if composite_score > 0.3:
        recommendations.append(
            f"🟢 BULLISH BIAS: Consider long entries on dips\n"
            f"   • Entry zone: Current price - {abs(price_change * 0.3):.1f}% (minor pullback)\n"
            f"   • Position size: 1-2% of portfolio per trade\n"
            f"   • Stop loss: Below {abs(price_change * 0.5):.1f}% from entry\n"
            f"   • Take profit: Scale out at +{abs(price_change * 1.5):.1f}% and +{abs(price_change * 3):.1f}%"
        )
    elif composite_score < -0.3:
        recommendations.append(
            f"🔴 BEARISH BIAS: Consider short entries on rallies\n"
            f"   • Entry zone: Current price + {abs(price_change * 0.3):.1f}% (minor bounce)\n"
            f"   • Position size: 1-2% of portfolio per trade\n"
            f"   • Stop loss: Above +{abs(price_change * 0.5):.1f}% from entry\n"
            f"   • Take profit: Scale out at -{abs(price_change * 1.5):.1f}% and -{abs(price_change * 3):.1f}%"
        )
    else:
        if abs(price_change) < 2:
            recommendations.append(
                "⚪ NEUTRAL MARKET: Range trading strategy\n"
                "   • Buy zone: Support at current - 1.5% to -2.5%\n"
                "   • Sell zone: Resistance at current + 1.5% to +2.5%\n"
                "   • Position size: 2-3% of portfolio (low volatility = larger size OK)\n"
                "   • Stop loss: Tight stops at -0.8% from entry\n"
                "   • Take profit: Scale out at +1.2% and +2.0%"
            )

    # 2. Funding rate arbitrage with specifics
    if arb_opportunities:
        top_arb = arb_opportunities[0]
        yield_pct = top_arb.get('annual_yield', 0)

        if yield_pct > 8:
            recommendations.append(
                f"💰 FUNDING ARBITRAGE: {top_arb.get('type', 'Unknown')}\n"
                f"   • Action: {top_arb.get('action', 'Unknown')}\n"
                f"   • Expected yield: {yield_pct:.2f}% annual ({yield_pct/12:.2f}% monthly)\n"
                f"   • Position size: 5-10% of portfolio (low-risk hedged position)\n"
                f"   • Hold duration: Monitor funding rates; exit if spread compresses below 0.003%\n"
                f"   • Risk: {top_arb.get('risk', 'Unknown')} - Cross-exchange execution risk"
            )

    # 3. Basis trading recommendations
    if basis_metrics.get('status') == 'success':
        basis_data = basis_metrics.get('basis_data', [])

        if basis_data:
            widest = max(basis_data, key=lambda x: abs(x.get('basis_pct', 0)))
            basis_pct = widest.get('basis_pct', 0)

            if abs(basis_pct) > 0.15:
                if basis_pct > 0:
                    recommendations.append(
                        f"📈 CASH-AND-CARRY OPPORTUNITY: {widest.get('exchange', 'Unknown')}\n"
                        f"   • Action: Buy spot + Short futures on {widest['exchange']}\n"
                        f"   • Basis capture: {basis_pct:.3f}%\n"
                        f"   • Position size: 10-15% of portfolio (market-neutral)\n"
                        f"   • Expected profit: {basis_pct:.3f}% + funding collection\n"
                        f"   • Hold until: Basis converges to < 0.05%\n"
                        f"   • Risk: Low (hedged position, main risk is exchange/liquidation)"
                    )

    return recommendations


def send_market_report_to_discord(report_text: str, results: List[Dict], webhook_url: str) -> bool:
    """Send market report to Discord as summary embed + file attachment"""

    try:
        # Extract summary
        summary = extract_executive_summary(report_text, results)

        # Determine sentiment color
        if '🟢' in summary['sentiment'] or 'BULLISH' in summary['sentiment']:
            color = 0x00FF00  # Green
        elif '🔴' in summary['sentiment'] or 'BEARISH' in summary['sentiment']:
            color = 0xFF0000  # Red
        else:
            color = 0x3498db  # Blue (neutral)

        # Create summary embed
        embed = {
            "title": f"📊 Crypto Market Report - {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}",
            "description": (
                f"**Total Volume:** {summary['volume']}\n"
                f"**Open Interest:** {summary['oi']}\n"
                f"**Market Sentiment:** {summary['sentiment']}"
            ),
            "color": color,
            "fields": [
                {
                    "name": "🏆 Top Exchange",
                    "value": summary['top_exchange'],
                    "inline": True
                },
                {
                    "name": "💰 Arbitrage",
                    "value": f"{summary['arb_count']} opportunities\nBest: {summary['best_arb_yield']}",
                    "inline": True
                },
                {
                    "name": "📈 Avg Spot-Futures Basis",
                    "value": summary['avg_basis'],
                    "inline": True
                },
                {
                    "name": "⚠️ Market Health",
                    "value": summary['health'],
                    "inline": False
                }
            ],
            "footer": {
                "text": "Full report + charts attached • 9 exchanges + 6 spot markets analyzed"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Create filename
        filename = f"market_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.txt"

        # Generate charts
        funding_chart = None
        dominance_chart = None
        basis_chart = None
        leverage_chart = None

        # 1. Funding rate chart
        try:
            funding_chart = generate_funding_rate_chart(results)
            print("   • Funding rate chart generated")
        except Exception as e:
            print(f"   ⚠️  Could not generate funding chart: {e}")

        # 2. Market dominance chart
        try:
            dominance = calculate_market_dominance(results)
            dominance_chart = generate_market_dominance_chart(dominance)
            print("   • Market dominance chart generated")
        except Exception as e:
            print(f"   ⚠️  Could not generate dominance chart: {e}")

        # 3. Spot-futures basis chart
        try:
            basis_metrics = analyze_basis_metrics()
            if basis_metrics.get('status') == 'success' and basis_metrics.get('basis_data'):
                basis_chart = generate_basis_chart(basis_metrics['basis_data'])
                print("   • Spot-futures basis chart generated")
        except Exception as e:
            print(f"   ⚠️  Could not generate basis chart: {e}")

        # 4. Leverage activity chart
        try:
            if basis_metrics and basis_metrics.get('status') == 'success':
                leverage_chart = generate_leverage_chart(basis_metrics)
                if leverage_chart:
                    print("   • Leverage activity chart generated")
        except Exception as e:
            print(f"   ⚠️  Could not generate leverage chart: {e}")

        # Prepare multipart form data
        files = {
            'file1': (filename, report_text.encode('utf-8'), 'text/plain')
        }

        # Add charts if generated successfully
        file_counter = 2
        timestamp_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')

        if funding_chart:
            files[f'file{file_counter}'] = (f"funding_rates_{timestamp_str}.png", funding_chart, 'image/png')
            file_counter += 1

        if dominance_chart:
            files[f'file{file_counter}'] = (f"market_dominance_{timestamp_str}.png", dominance_chart, 'image/png')
            file_counter += 1

        if basis_chart:
            files[f'file{file_counter}'] = (f"spot_futures_basis_{timestamp_str}.png", basis_chart, 'image/png')
            file_counter += 1

        if leverage_chart:
            files[f'file{file_counter}'] = (f"leverage_activity_{timestamp_str}.png", leverage_chart, 'image/png')
            file_counter += 1

        payload = {
            'username': 'Market Report Bot',
            'embeds': [embed]
        }

        # Send to Discord
        response = requests.post(
            webhook_url,
            files=files,
            data={'payload_json': json.dumps(payload)},
            timeout=10
        )

        if response.status_code == 200:
            chart_count = sum([bool(funding_chart), bool(dominance_chart), bool(basis_chart), bool(leverage_chart)])
            print(f"\n✅ Market report sent to Discord!")
            print(f"   • Summary embed posted")
            print(f"   • Full report attached: {filename}")
            if funding_chart:
                print(f"   • Funding rate chart attached")
            if dominance_chart:
                print(f"   • Market dominance chart attached")
            if basis_chart:
                print(f"   • Spot-futures basis chart attached")
            if leverage_chart:
                print(f"   • Leverage activity chart attached")
            print(f"   • Total: {chart_count}/4 charts generated")
            return True
        else:
            print(f"\n❌ Discord webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Error sending to Discord: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 Generating Crypto Perpetual Futures Market Report...\n")
    print("⏳ Fetching data from 9 exchanges + spot markets (25-35 seconds)...\n")

    # Fetch data
    results = fetch_all_enhanced()

    # Generate report
    report = format_market_report(results)

    # Display report
    print(report)

    # Optionally save to file
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"data/market_report_{timestamp}.txt"

    try:
        with open(filename, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to: {filename}")
    except Exception as e:
        print(f"⚠️  Could not save report to file: {e}")
        print("   (Report displayed above)")

    # Send to Discord if configured
    try:
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        discord_config = config.get('discord', {})
        webhook_url = discord_config.get('webhook_url')

        # Expand environment variables in webhook URL
        if webhook_url and webhook_url.startswith('${') and webhook_url.endswith('}'):
            env_var = webhook_url[2:-1]  # Extract variable name
            webhook_url = os.getenv(env_var)

        if webhook_url and discord_config.get('enabled', False):
            send_market_report_to_discord(report, results, webhook_url)
        else:
            print("\n⚠️  Discord integration not enabled in config/config.yaml")
    except FileNotFoundError:
        print("\n⚠️  Config file not found: config/config.yaml")
    except Exception as e:
        print(f"\n⚠️  Could not load Discord config: {e}")
