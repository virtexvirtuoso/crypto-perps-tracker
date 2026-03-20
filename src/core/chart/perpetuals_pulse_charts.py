"""
Perpetuals Pulse Chart Library - Production-Grade Plotly Visualizations

High-performance, trader-optimized visualizations for perpetual futures market data.
Designed for intraday traders and scalpers who need actionable insights in < 3 seconds.

Author: Virtuoso Team
Version: 1.0.0
Created: 2025-12-11
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import colorsys


class PerpetualsChartTheme:
    """Virtuoso brand theme for Plotly charts."""

    # Brand colors
    NEON_AMBER = '#fbbf24'
    NEON_CYAN = '#06B6D4'
    NEON_RED = '#ff0066'

    # Backgrounds
    BG_PRIMARY = '#0a0a0a'
    BG_SECONDARY = '#111111'
    BG_PANEL = '#161616'
    BG_CARD = '#1a1a1a'

    # Borders & text
    BORDER_LIGHT = '#222222'
    TEXT_PRIMARY = '#f5f5f5'
    TEXT_SECONDARY = '#a8a8a8'
    TEXT_MUTED = '#7a7a7a'

    # Semantic colors
    BULLISH = '#00d68f'
    BEARISH = '#ff5252'
    WARNING = '#ffb800'
    NEUTRAL = '#5a6c7d'

    # Chart configuration
    FONT_FAMILY = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    FONT_MONO = 'IBM Plex Mono, monospace'

    @classmethod
    def get_base_layout(cls, title: str = "", height: int = 350) -> dict:
        """Get base layout configuration for all charts."""
        return {
            'template': 'plotly_dark',
            'paper_bgcolor': cls.BG_CARD,
            'plot_bgcolor': cls.BG_PRIMARY,
            'height': height,
            'margin': dict(l=40, r=20, t=40, b=30),
            'font': dict(
                family=cls.FONT_FAMILY,
                size=12,
                color=cls.TEXT_PRIMARY
            ),
            'title': {
                'text': title,
                'font': dict(size=16, color=cls.TEXT_PRIMARY, family=cls.FONT_FAMILY),
                'x': 0.02,
                'xanchor': 'left'
            },
            'hovermode': 'x unified',
            'hoverlabel': dict(
                bgcolor=cls.BG_SECONDARY,
                font_size=11,
                font_family=cls.FONT_FAMILY,
                bordercolor=cls.NEON_AMBER
            ),
            'xaxis': {
                'showgrid': True,
                'gridcolor': cls.BORDER_LIGHT,
                'gridwidth': 1,
                'zeroline': False,
                'showline': True,
                'linecolor': cls.BORDER_LIGHT,
                'linewidth': 1,
                'color': cls.TEXT_SECONDARY
            },
            'yaxis': {
                'showgrid': True,
                'gridcolor': cls.BORDER_LIGHT,
                'gridwidth': 1,
                'zeroline': True,
                'zerolinecolor': cls.TEXT_MUTED,
                'zerolinewidth': 1,
                'showline': True,
                'linecolor': cls.BORDER_LIGHT,
                'linewidth': 1,
                'color': cls.TEXT_SECONDARY
            }
        }

    @classmethod
    def get_config(cls) -> dict:
        """Get Plotly config for consistent behavior."""
        return {
            'displayModeBar': False,
            'responsive': True,
            'displaylogo': False
        }


def create_funding_rate_microtrend(
    funding_history: List[Dict[str, Any]],
    current_data: Dict[str, Any],
    lookback_hours: int = 4
) -> go.Figure:
    """
    Create funding rate micro-trend chart for intraday traders.

    Shows recent funding rate movement with z-score zones, extremes highlighting,
    and directional momentum indicators.

    Args:
        funding_history: List of {timestamp, funding_rate, exchange} dicts
        current_data: Current perpetuals pulse data
        lookback_hours: Hours of history to display (default: 4)

    Returns:
        Plotly figure ready for rendering
    """
    theme = PerpetualsChartTheme

    # Process data
    if not funding_history:
        # Return empty state chart
        fig = go.Figure()
        fig.update_layout(**theme.get_base_layout("Funding Rate Micro-Trend", 300))
        fig.add_annotation(
            text="No funding rate history available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=theme.TEXT_MUTED)
        )
        return fig

    # Filter to lookback window
    from datetime import timezone as tz
    now = datetime.now(tz.utc)
    cutoff = now - timedelta(hours=lookback_hours)

    timestamps = []
    rates = []
    for entry in funding_history:
        ts = entry.get('timestamp')
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        elif isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts, tz=tz.utc)
        elif isinstance(ts, datetime):
            # Ensure datetime is timezone-aware
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=tz.utc)

        if ts >= cutoff:
            timestamps.append(ts)
            rates.append(entry.get('funding_rate', 0) * 100)  # Convert to bps

    if not timestamps:
        # Return empty state
        fig = go.Figure()
        fig.update_layout(**theme.get_base_layout("Funding Rate Micro-Trend", 300))
        fig.add_annotation(
            text="Insufficient recent data",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=theme.TEXT_MUTED)
        )
        return fig

    # Calculate statistics
    mean_rate = np.mean(rates)
    std_rate = np.std(rates) if len(rates) > 1 else 0.01
    current_rate = current_data.get('funding_rate', 0) * 100
    z_score = current_data.get('funding_zscore', 0)

    # Determine trend direction and color
    recent_rates = rates[-6:] if len(rates) >= 6 else rates
    trend_direction = "RISING" if recent_rates[-1] > recent_rates[0] else "FALLING"
    is_bullish = current_rate < 0  # Negative funding = longs paying shorts = bearish sentiment = contrarian bullish

    # Create figure
    fig = go.Figure()

    # Add z-score zones (shaded regions)
    fig.add_hrect(
        y0=mean_rate - 2*std_rate, y1=mean_rate - std_rate,
        fillcolor=theme.BULLISH, opacity=0.05, line_width=0,
        annotation_text="Bearish Zone", annotation_position="left",
        annotation=dict(font_size=9, font_color=theme.TEXT_MUTED)
    )
    fig.add_hrect(
        y0=mean_rate + std_rate, y1=mean_rate + 2*std_rate,
        fillcolor=theme.BEARISH, opacity=0.05, line_width=0,
        annotation_text="Bullish Zone", annotation_position="left",
        annotation=dict(font_size=9, font_color=theme.TEXT_MUTED)
    )

    # Add extreme zones (>2 sigma)
    if abs(z_score) > 2:
        fig.add_hrect(
            y0=mean_rate + 2*std_rate, y1=mean_rate + 4*std_rate,
            fillcolor=theme.BEARISH, opacity=0.1, line_width=0,
            annotation_text="EXTREME", annotation_position="right",
            annotation=dict(font_size=10, font_color=theme.BEARISH, font=dict(family=theme.FONT_MONO))
        )
        fig.add_hrect(
            y0=mean_rate - 4*std_rate, y1=mean_rate - 2*std_rate,
            fillcolor=theme.BULLISH, opacity=0.1, line_width=0,
            annotation_text="EXTREME", annotation_position="right",
            annotation=dict(font_size=10, font_color=theme.BULLISH, font=dict(family=theme.FONT_MONO))
        )

    # Add historical mean line
    fig.add_hline(
        y=mean_rate, line_dash="dot", line_color=theme.TEXT_MUTED,
        line_width=1,
        annotation_text=f"Mean: {mean_rate:.3f}%",
        annotation_position="right",
        annotation=dict(font_size=9, font_color=theme.TEXT_MUTED)
    )

    # Main funding rate line with gradient coloring
    line_color = theme.BULLISH if is_bullish else theme.BEARISH

    fig.add_trace(go.Scatter(
        x=timestamps,
        y=rates,
        mode='lines+markers',
        name='Funding Rate',
        line=dict(color=line_color, width=2.5),
        marker=dict(
            size=4,
            color=rates,
            colorscale=[
                [0, theme.BULLISH],
                [0.5, theme.NEUTRAL],
                [1, theme.BEARISH]
            ],
            showscale=False,
            line=dict(width=0)
        ),
        fill='tonexty' if len(rates) > 1 else None,
        fillcolor=f'rgba({int(line_color[1:3], 16)}, {int(line_color[3:5], 16)}, {int(line_color[5:7], 16)}, 0.1)',
        hovertemplate='<b>%{x|%H:%M}</b><br>Rate: %{y:.4f}%<br><extra></extra>'
    ))

    # Add current point annotation
    fig.add_trace(go.Scatter(
        x=[timestamps[-1]],
        y=[current_rate],
        mode='markers+text',
        name='Current',
        marker=dict(
            size=12,
            color=line_color,
            symbol='diamond',
            line=dict(color=theme.TEXT_PRIMARY, width=2)
        ),
        text=[f"{current_rate:.3f}%"],
        textposition="top center",
        textfont=dict(size=11, color=line_color, family=theme.FONT_MONO),
        showlegend=False,
        hovertemplate='<b>NOW</b><br>Rate: %{y:.4f}%<br>Z-Score: ' + f'{z_score:.2f}<extra></extra>'
    ))

    # Layout
    layout = theme.get_base_layout(
        f"Funding Rate Micro-Trend ({lookback_hours}h) · {trend_direction}",
        height=300
    )
    layout['yaxis']['title'] = 'Funding Rate (bps)'
    layout['yaxis']['tickformat'] = '.3f'
    layout['yaxis']['ticksuffix'] = '%'
    layout['xaxis']['title'] = ''
    layout['showlegend'] = False

    fig.update_layout(**layout)

    return fig


def create_long_short_gauge(current_data: Dict[str, Any]) -> go.Figure:
    """
    Create L/S positioning gauge for crowd sentiment analysis.

    Shows current long/short ratio with danger zones and entropy confidence.
    Designed for contrarian trading signals.

    Args:
        current_data: Current perpetuals pulse data

    Returns:
        Plotly figure ready for rendering
    """
    theme = PerpetualsChartTheme

    long_pct = current_data.get('long_pct', 50)
    short_pct = current_data.get('short_pct', 50)
    entropy = current_data.get('ls_entropy', 0.5)

    # Determine risk level
    if long_pct > 75 or short_pct > 75:
        risk_level = "EXTREME"
        risk_color = theme.BEARISH
    elif long_pct > 65 or short_pct > 65:
        risk_level = "HIGH"
        risk_color = theme.WARNING
    else:
        risk_level = "NORMAL"
        risk_color = theme.BULLISH

    # Create gauge
    fig = go.Figure()

    # Main gauge
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=long_pct,
        title={'text': "Long %", 'font': {'size': 14, 'color': theme.TEXT_SECONDARY}},
        delta={
            'reference': 50,
            'increasing': {'color': theme.WARNING},
            'decreasing': {'color': theme.BULLISH}
        },
        number={
            'suffix': "%",
            'font': {'size': 32, 'color': risk_color, 'family': theme.FONT_MONO}
        },
        gauge={
            'axis': {
                'range': [0, 100],
                'tickwidth': 1,
                'tickcolor': theme.TEXT_MUTED,
                'tickmode': 'array',
                'tickvals': [0, 25, 50, 75, 100],
                'ticktext': ['0', '25', '50', '75', '100']
            },
            'bar': {'color': risk_color, 'thickness': 0.7},
            'bgcolor': theme.BG_PRIMARY,
            'borderwidth': 1,
            'bordercolor': theme.BORDER_LIGHT,
            'steps': [
                {'range': [0, 35], 'color': 'rgba(0, 214, 143, 0.1)'},  # Shorts extreme
                {'range': [35, 45], 'color': 'rgba(90, 108, 125, 0.05)'},  # Neutral
                {'range': [45, 55], 'color': 'rgba(90, 108, 125, 0.05)'},  # Neutral
                {'range': [55, 65], 'color': 'rgba(255, 184, 0, 0.05)'},  # Caution
                {'range': [65, 75], 'color': 'rgba(255, 184, 0, 0.15)'},  # Warning
                {'range': [75, 100], 'color': 'rgba(255, 82, 82, 0.2)'}  # Danger
            ],
            'threshold': {
                'line': {'color': theme.NEON_AMBER, 'width': 3},
                'thickness': 0.8,
                'value': 50
            }
        },
        domain={'x': [0, 1], 'y': [0.15, 1]}
    ))

    # Add annotations
    annotations = [
        # Risk level badge
        dict(
            text=f"<b>{risk_level} RISK</b>",
            xref="paper", yref="paper",
            x=0.5, y=0.05,
            showarrow=False,
            font=dict(size=13, color=risk_color, family=theme.FONT_MONO),
            bgcolor=f'rgba({int(risk_color[1:3], 16)}, {int(risk_color[3:5], 16)}, {int(risk_color[5:7], 16)}, 0.15)',
            bordercolor=risk_color,
            borderwidth=1,
            borderpad=6
        ),
        # Entropy confidence
        dict(
            text=f"Entropy: {entropy:.3f}",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            font=dict(size=10, color=theme.TEXT_MUTED),
            xanchor='left',
            yanchor='top'
        ),
        # Short percentage
        dict(
            text=f"Short: {short_pct:.1f}%",
            xref="paper", yref="paper",
            x=0.98, y=0.98,
            showarrow=False,
            font=dict(size=10, color=theme.TEXT_MUTED),
            xanchor='right',
            yanchor='top'
        )
    ]

    # Contrarian signal
    if long_pct > 65:
        signal_text = "⚠️ CROWDED LONG → Bearish Contrarian"
        signal_color = theme.BEARISH
    elif short_pct > 65:
        signal_text = "✓ CROWDED SHORT → Bullish Contrarian"
        signal_color = theme.BULLISH
    else:
        signal_text = "Balanced positioning"
        signal_color = theme.NEUTRAL

    annotations.append(dict(
        text=signal_text,
        xref="paper", yref="paper",
        x=0.5, y=-0.05,
        showarrow=False,
        font=dict(size=11, color=signal_color),
        xanchor='center'
    ))

    layout = theme.get_base_layout("Long/Short Positioning", height=320)
    layout['annotations'] = annotations
    layout['margin'] = dict(l=20, r=20, t=60, b=60)

    fig.update_layout(**layout)

    return fig


def create_signal_strength_dashboard(current_data: Dict[str, Any]) -> go.Figure:
    """
    Create signal strength visualization for active trading signals.

    Shows direction, strength, confidence, and time horizon for each active signal.
    Optimized for quick decision-making.

    Args:
        current_data: Current perpetuals pulse data with signals

    Returns:
        Plotly figure ready for rendering
    """
    theme = PerpetualsChartTheme

    signals = current_data.get('signals', [])

    if not signals:
        # Empty state
        fig = go.Figure()
        fig.update_layout(**theme.get_base_layout("Active Trading Signals", 280))
        fig.add_annotation(
            text="No active signals",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color=theme.TEXT_MUTED)
        )
        return fig

    # Process signals
    signal_types = []
    directions = []
    strengths = []
    confidences = []
    colors = []
    descriptions = []
    horizons = []

    strength_map = {'extreme': 4, 'strong': 3, 'moderate': 2, 'weak': 1}

    for sig in signals[:5]:  # Limit to top 5 signals
        signal_type = sig.get('signal_type', 'unknown')
        direction = sig.get('direction', 'neutral')
        strength = sig.get('strength', 'moderate')
        confidence = sig.get('confidence', 0.5)
        horizon = sig.get('time_horizon_hours', 24)

        signal_types.append(signal_type.replace('_', ' ').title())
        directions.append(direction.upper())
        strengths.append(strength_map.get(strength, 2))
        confidences.append(confidence)
        horizons.append(f"{horizon}h")
        descriptions.append(sig.get('description', ''))

        # Color based on direction
        if direction == 'bullish':
            colors.append(theme.BULLISH)
        elif direction == 'bearish':
            colors.append(theme.BEARISH)
        else:
            colors.append(theme.NEUTRAL)

    # Create horizontal bar chart
    fig = go.Figure()

    # Strength bars
    fig.add_trace(go.Bar(
        y=signal_types,
        x=strengths,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(color=theme.BORDER_LIGHT, width=1)
        ),
        text=[f"{d} · {c:.0%}" for d, c in zip(directions, confidences)],
        textposition='inside',
        textfont=dict(size=11, color=theme.TEXT_PRIMARY, family=theme.FONT_MONO),
        hovertemplate='<b>%{y}</b><br>Strength: %{x}/4<br>Confidence: %{customdata[0]:.0%}<br>Horizon: %{customdata[1]}<br><extra></extra>',
        customdata=list(zip(confidences, horizons))
    ))

    layout = theme.get_base_layout("Active Trading Signals", height=max(280, 80 + len(signals) * 50))
    layout['xaxis'] = {
        'range': [0, 4.5],
        'showgrid': False,
        'showline': False,
        'showticklabels': False,
        'zeroline': False
    }
    layout['yaxis'] = {
        'showgrid': False,
        'showline': False,
        'tickfont': dict(size=11, color=theme.TEXT_PRIMARY)
    }
    layout['margin'] = dict(l=150, r=20, t=50, b=30)
    layout['showlegend'] = False

    # Add strength scale reference
    layout['annotations'] = [
        dict(
            text="<b>1</b> Weak",
            xref="x", yref="paper",
            x=1, y=-0.12,
            showarrow=False,
            font=dict(size=9, color=theme.TEXT_MUTED),
            xanchor='center'
        ),
        dict(
            text="<b>2</b> Moderate",
            xref="x", yref="paper",
            x=2, y=-0.12,
            showarrow=False,
            font=dict(size=9, color=theme.TEXT_MUTED),
            xanchor='center'
        ),
        dict(
            text="<b>3</b> Strong",
            xref="x", yref="paper",
            x=3, y=-0.12,
            showarrow=False,
            font=dict(size=9, color=theme.TEXT_MUTED),
            xanchor='center'
        ),
        dict(
            text="<b>4</b> Extreme",
            xref="x", yref="paper",
            x=4, y=-0.12,
            showarrow=False,
            font=dict(size=9, color=theme.TEXT_MUTED),
            xanchor='center'
        )
    ]

    fig.update_layout(**layout)

    return fig


def create_market_state_composite(current_data: Dict[str, Any]) -> go.Figure:
    """
    Create market state composite visualization.

    Combines entropy, exchange agreement, basis, and z-score into a single
    health indicator. Uses traffic light system for quick risk assessment.

    Args:
        current_data: Current perpetuals pulse data

    Returns:
        Plotly figure ready for rendering
    """
    theme = PerpetualsChartTheme

    # Extract metrics
    entropy = current_data.get('ls_entropy', 0.5)
    agreement = current_data.get('exchange_agreement', 0.5)
    funding_zscore = current_data.get('funding_zscore', 0)
    basis_pct = current_data.get('basis_pct', 0)
    data_quality = current_data.get('data_quality_score', 0.5)

    # Normalize metrics to 0-100 scale
    metrics = {
        'Data Quality': data_quality * 100,
        'Exchange Agreement': agreement * 100,
        'L/S Entropy': entropy * 100,
        'Funding Stability': max(0, 100 - abs(funding_zscore) * 20),  # Lower z-score = more stable
        'Basis Health': 50 + basis_pct * 10  # Normalize around 50
    }

    # Determine colors based on thresholds
    def get_health_color(value, metric_name):
        if metric_name == 'Basis Health':
            # Basis: 45-55 is good, outside is concerning
            if 45 <= value <= 55:
                return theme.BULLISH
            elif 40 <= value <= 60:
                return theme.WARNING
            else:
                return theme.BEARISH
        else:
            # Higher is better for other metrics
            if value >= 70:
                return theme.BULLISH
            elif value >= 50:
                return theme.WARNING
            else:
                return theme.BEARISH

    labels = list(metrics.keys())
    values = list(metrics.values())
    colors = [get_health_color(v, k) for k, v in metrics.items()]

    # Calculate overall health score
    # Weight: data quality (20%), agreement (25%), entropy (20%), funding (20%), basis (15%)
    weights = [0.20, 0.25, 0.20, 0.20, 0.15]
    overall_health = sum(v * w for v, w in zip(values, weights))

    # Create subplot with gauge and bars
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.4, 0.6],
        specs=[[{'type': 'indicator'}, {'type': 'bar'}]],
        horizontal_spacing=0.08
    )

    # Overall health gauge
    if overall_health >= 70:
        health_status = "HEALTHY"
        health_color = theme.BULLISH
    elif overall_health >= 50:
        health_status = "CAUTION"
        health_color = theme.WARNING
    else:
        health_status = "RISK"
        health_color = theme.BEARISH

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=overall_health,
            title={'text': "Market Health", 'font': {'size': 13, 'color': theme.TEXT_SECONDARY}},
            number={
                'font': {'size': 28, 'color': health_color, 'family': theme.FONT_MONO}
            },
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': theme.TEXT_MUTED},
                'bar': {'color': health_color, 'thickness': 0.65},
                'bgcolor': theme.BG_PRIMARY,
                'borderwidth': 1,
                'bordercolor': theme.BORDER_LIGHT,
                'steps': [
                    {'range': [0, 50], 'color': 'rgba(255, 82, 82, 0.1)'},
                    {'range': [50, 70], 'color': 'rgba(255, 184, 0, 0.1)'},
                    {'range': [70, 100], 'color': 'rgba(0, 214, 143, 0.1)'}
                ]
            }
        ),
        row=1, col=1
    )

    # Component bars
    fig.add_trace(
        go.Bar(
            y=labels,
            x=values,
            orientation='h',
            marker=dict(
                color=colors,
                line=dict(color=theme.BORDER_LIGHT, width=1)
            ),
            text=[f"{v:.0f}" for v in values],
            textposition='inside',
            textfont=dict(size=10, color=theme.TEXT_PRIMARY, family=theme.FONT_MONO),
            hovertemplate='<b>%{y}</b><br>Score: %{x:.1f}/100<extra></extra>'
        ),
        row=1, col=2
    )

    layout = theme.get_base_layout("Market State Composite", height=300)
    layout['margin'] = dict(l=20, r=20, t=50, b=40)
    layout['showlegend'] = False

    # Update subplot axes
    fig.update_xaxes(
        range=[0, 100],
        showgrid=False,
        showline=False,
        showticklabels=False,
        row=1, col=2
    )
    fig.update_yaxes(
        showgrid=False,
        showline=False,
        tickfont=dict(size=10, color=theme.TEXT_SECONDARY),
        row=1, col=2
    )

    # Add health status annotation
    fig.add_annotation(
        text=f"<b>{health_status}</b>",
        xref="paper", yref="paper",
        x=0.2, y=0.15,
        showarrow=False,
        font=dict(size=12, color=health_color, family=theme.FONT_MONO),
        bgcolor=f'rgba({int(health_color[1:3], 16)}, {int(health_color[3:5], 16)}, {int(health_color[5:7], 16)}, 0.15)',
        bordercolor=health_color,
        borderwidth=1,
        borderpad=4
    )

    fig.update_layout(**layout)

    return fig


def create_all_charts(
    current_data: Dict[str, Any],
    funding_history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, go.Figure]:
    """
    Generate all perpetuals pulse charts at once.

    Args:
        current_data: Current perpetuals pulse data
        funding_history: Optional historical funding rate data

    Returns:
        Dictionary mapping chart names to Plotly figures
    """
    charts = {}

    # Create each chart
    if funding_history:
        charts['funding_microtrend'] = create_funding_rate_microtrend(
            funding_history, current_data
        )

    charts['long_short_gauge'] = create_long_short_gauge(current_data)
    charts['signal_strength'] = create_signal_strength_dashboard(current_data)
    charts['market_state'] = create_market_state_composite(current_data)

    return charts


def charts_to_html(charts: Dict[str, go.Figure]) -> Dict[str, str]:
    """
    Convert charts to HTML divs for embedding.

    Args:
        charts: Dictionary of chart name to Plotly figure

    Returns:
        Dictionary mapping chart names to HTML strings
    """
    theme = PerpetualsChartTheme
    config = theme.get_config()

    html_charts = {}
    for name, fig in charts.items():
        html_charts[name] = fig.to_html(
            include_plotlyjs=False,
            div_id=f"chart-{name}",
            config=config
        )

    return html_charts
