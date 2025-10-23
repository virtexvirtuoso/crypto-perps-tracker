#!/usr/bin/env python3
"""
Bitcoin Beta HTML Dashboard Generator
Creates interactive HTML with 10 different Bitcoin Beta visualizations
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_symbol_report import (
    fetch_symbol_data_from_exchanges,
    analyze_symbol
)
from datetime import datetime, timezone
from typing import Dict, List
import json
import requests
import time


def fetch_historical_data_for_symbols(symbols: List[str], limit: int = 24) -> Dict[str, List[Dict]]:
    """
    Fetch hourly historical OHLCV data for specified symbols from OKX

    Args:
        symbols: List of symbol names (e.g., ['BTC', 'ETH', 'SOL'])
        limit: Number of hourly candles to fetch (default 24 for 24 hours)

    Returns:
        Dict mapping symbol -> list of {timestamp, open, high, low, close, volume}
    """
    historical_data = {}

    print(f"   📊 Fetching {limit}h historical data for {len(symbols)} symbols...")

    for symbol in symbols:
        try:
            # OKX uses -USDT-SWAP pairs
            okx_symbol = f"{symbol}-USDT-SWAP"

            url = "https://www.okx.com/api/v5/market/candles"
            params = {
                'instId': okx_symbol,
                'bar': '1H',
                'limit': limit
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == '0' and data.get('data'):
                    klines = data['data']

                    # Parse klines data (OKX format: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm])
                    candles = []
                    for k in reversed(klines):  # OKX returns newest first, reverse to get oldest first
                        candles.append({
                            'timestamp': int(k[0]),  # Timestamp in ms
                            'open': float(k[1]),
                            'high': float(k[2]),
                            'low': float(k[3]),
                            'close': float(k[4]),
                            'volume': float(k[5])
                        })

                    historical_data[symbol] = candles
                    print(f"      ✓ {symbol}: {len(candles)} candles")
                else:
                    print(f"      ⚠️  {symbol}: API returned error")
            else:
                print(f"      ⚠️  {symbol}: Failed to fetch (status {response.status_code})")

            # Rate limiting
            time.sleep(0.15)

        except Exception as e:
            print(f"      ❌ {symbol}: {e}")

    return historical_data


def normalize_price_series(candles: List[Dict]) -> List[float]:
    """
    Normalize price series to percentage change from first candle

    Args:
        candles: List of OHLCV candles

    Returns:
        List of percentage changes from initial price
    """
    if not candles:
        return []

    initial_price = candles[0]['close']
    return [((c['close'] - initial_price) / initial_price) * 100 for c in candles]


def generate_beta_html_dashboard(analyses: List[Dict], btc_price_change: float = None, historical_data: Dict[str, List[Dict]] = None) -> str:
    """Generate 10-panel Bitcoin Beta visualization dashboard with multiple analysis types"""

    # Get symbols with beta data
    symbols_with_beta = [a for a in analyses if a.get('btc_beta') is not None and a['symbol'] != 'BTC']

    if not symbols_with_beta:
        return "<html><body><h1>No Beta Data Available</h1></body></html>"

    # === Chart 1 Data: Beta vs Price Change Scatter ===
    scatter_data = {
        'symbols': [a['symbol'][:8] for a in symbols_with_beta],
        'betas': [a['btc_beta'] for a in symbols_with_beta],
        'price_changes': [a.get('avg_price_change_24h', 0) for a in symbols_with_beta],
        'volumes': [a['total_volume_24h'] / 1e9 for a in symbols_with_beta],
        'colors': []
    }

    for beta in scatter_data['betas']:
        if beta > 1.5:
            scatter_data['colors'].append('#FF6B35')
        elif beta > 1.0:
            scatter_data['colors'].append('#FFA500')
        elif beta > 0.5:
            scatter_data['colors'].append('#FDB44B')
        elif beta > 0:
            scatter_data['colors'].append('#FFD700')
        else:
            scatter_data['colors'].append('#00FF7F')

    # === Chart 2 Data: Beta Distribution Histogram ===
    all_betas = [a['btc_beta'] for a in symbols_with_beta]

    # === Chart 3 Data: Time Series (uses historical_data parameter) ===
    # Data is fetched externally and passed to this function

    # === Chart 4 Data: Beta vs Volume Bubble ===
    top_volume = sorted(symbols_with_beta, key=lambda x: x['total_volume_24h'], reverse=True)[:50]

    bubble_data = {
        'symbols': [a['symbol'][:8] for a in top_volume],
        'betas': [a['btc_beta'] for a in top_volume],
        'volumes': [a['total_volume_24h'] / 1e9 for a in top_volume],
        'price_changes': [a.get('avg_price_change_24h', 0) for a in top_volume],
        'colors': []
    }

    for change in bubble_data['price_changes']:
        if change > 5:
            bubble_data['colors'].append('#00FF7F')
        elif change > 0:
            bubble_data['colors'].append('#FDB44B')
        elif change > -5:
            bubble_data['colors'].append('#FFA500')
        else:
            bubble_data['colors'].append('#FF6B35')

    # === Chart 5 Data: Correlation Heatmap (Top 20 by volume) ===
    top_20_symbols = sorted(symbols_with_beta, key=lambda x: x['total_volume_24h'], reverse=True)[:20]
    heatmap_symbols = [a['symbol'][:8] for a in top_20_symbols]
    heatmap_betas = [a['btc_beta'] for a in top_20_symbols]

    # Create correlation-style matrix (simplified - using beta as proxy for correlation strength)
    correlation_matrix = []
    for i, sym1 in enumerate(top_20_symbols):
        row = []
        for j, sym2 in enumerate(top_20_symbols):
            if i == j:
                row.append(1.0)  # Perfect correlation with self
            else:
                # Estimate correlation based on beta similarity
                beta_diff = abs(sym1['btc_beta'] - sym2['btc_beta'])
                # Closer betas = higher correlation estimate
                correlation = max(0, 1.0 - (beta_diff / 2.0))
                row.append(correlation)
        correlation_matrix.append(row)

    # === Chart 6 Data: Risk-Return Quadrant ===
    quadrant_data = {
        'symbols': [a['symbol'][:8] for a in symbols_with_beta],
        'betas': [a['btc_beta'] for a in symbols_with_beta],
        'returns': [a.get('avg_price_change_24h', 0) for a in symbols_with_beta],
        'volumes': [a['total_volume_24h'] / 1e9 for a in symbols_with_beta],
        'quadrant_colors': []
    }

    # Assign quadrant colors based on beta and return
    for beta, ret in zip(quadrant_data['betas'], quadrant_data['returns']):
        if beta > 1.0 and ret > 0:
            quadrant_data['quadrant_colors'].append('#00FF7F')  # High beta, positive return (best)
        elif beta > 1.0 and ret <= 0:
            quadrant_data['quadrant_colors'].append('#FF6B35')  # High beta, negative return (worst)
        elif beta <= 1.0 and ret > 0:
            quadrant_data['quadrant_colors'].append('#FDB44B')  # Low beta, positive return (stable growth)
        else:
            quadrant_data['quadrant_colors'].append('#FFA500')  # Low beta, negative return (defensive)

    # === Chart 7 Data: Parallel Coordinates (Top 30 by volume) ===
    top_30 = sorted(symbols_with_beta, key=lambda x: x['total_volume_24h'], reverse=True)[:30]
    parallel_data = {
        'symbols': [a['symbol'][:8] for a in top_30],
        'betas': [a['btc_beta'] for a in top_30],
        'volumes': [a['total_volume_24h'] / 1e9 for a in top_30],
        'price_changes': [a.get('avg_price_change_24h', 0) for a in top_30],
        'funding_rates': [a.get('avg_funding_rate', 0) * 100 if a.get('avg_funding_rate') is not None else 0 for a in top_30],
        'oi': [a['total_open_interest'] / 1e9 for a in top_30]
    }

    # === Chart 8 Data: Treemap (Beta Categories) ===
    # Group by beta category
    treemap_data = {
        'labels': [],
        'parents': [],
        'values': [],
        'colors': []
    }

    # Root
    treemap_data['labels'].append('All Symbols')
    treemap_data['parents'].append('')
    treemap_data['values'].append(0)
    treemap_data['colors'].append('#1a1a1a')

    # Categories
    categories = {
        'Extreme (>2.0x)': {'filter': lambda x: x > 2.0, 'color': '#FF0000'},
        'High (1.5-2.0x)': {'filter': lambda x: 1.5 < x <= 2.0, 'color': '#FF6B35'},
        'Amplifies (1.0-1.5x)': {'filter': lambda x: 1.0 < x <= 1.5, 'color': '#FFA500'},
        'Follows (0.5-1.0x)': {'filter': lambda x: 0.5 < x <= 1.0, 'color': '#FDB44B'},
        'Weak (0-0.5x)': {'filter': lambda x: 0 < x <= 0.5, 'color': '#FFD700'},
        'Inverse (<0)': {'filter': lambda x: x < 0, 'color': '#00FF7F'}
    }

    for cat_name, cat_info in categories.items():
        symbols_in_cat = [a for a in symbols_with_beta if cat_info['filter'](a['btc_beta'])]
        if symbols_in_cat:
            total_vol = sum(a['total_volume_24h'] for a in symbols_in_cat) / 1e9
            treemap_data['labels'].append(cat_name)
            treemap_data['parents'].append('All Symbols')
            treemap_data['values'].append(total_vol)
            treemap_data['colors'].append(cat_info['color'])

    # === Chart 9 Data: Box Plot by Category ===
    box_data = {}
    for cat_name, cat_info in categories.items():
        betas_in_cat = [a['btc_beta'] for a in symbols_with_beta if cat_info['filter'](a['btc_beta'])]
        if betas_in_cat:
            box_data[cat_name] = betas_in_cat

    # === Chart 10 Data: Radar Chart (Top 5 symbols) ===
    top_5_radar = sorted(symbols_with_beta, key=lambda x: x['total_volume_24h'], reverse=True)[:5]

    # Normalize metrics for radar (0-1 scale)
    max_volume = max(a['total_volume_24h'] for a in symbols_with_beta)
    max_oi = max(a['total_open_interest'] for a in symbols_with_beta)

    radar_data = []
    for a in top_5_radar:
        normalized_beta = min(abs(a['btc_beta']) / 3.0, 1.0)  # Cap at 3.0 for scaling
        normalized_volume = a['total_volume_24h'] / max_volume
        normalized_oi = a['total_open_interest'] / max_oi
        normalized_change = (a.get('avg_price_change_24h', 0) + 50) / 100  # Scale -50 to +50 -> 0 to 1
        normalized_funding = (a.get('avg_funding_rate', 0) * 100 + 50) / 100 if a.get('avg_funding_rate') else 0.5

        radar_data.append({
            'symbol': a['symbol'][:8],
            'metrics': [normalized_beta, normalized_volume, normalized_oi,
                       normalized_change, normalized_funding]
        })

    # === Generate HTML ===
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Beta Analysis Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
            font-family: 'Courier New', monospace;
            color: #FFD700;
            padding: 20px;
            min-height: 100vh;
        }}

        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 3px solid #FFA500;
            border-radius: 15px;
            box-shadow: 0 0 40px rgba(255, 165, 0, 0.4);
        }}

        .header h1 {{
            font-size: 2.8em;
            color: #FFA500;
            text-shadow: 0 0 30px rgba(255, 165, 0, 1);
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            color: #FFD700;
            font-size: 1.2em;
            margin-top: 10px;
        }}

        .btc-stat {{
            font-size: 1.4em;
            color: #FF6B35;
            margin-top: 15px;
            padding: 10px;
            background: rgba(255, 107, 53, 0.1);
            border-radius: 8px;
            display: inline-block;
        }}

        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 30px;
        }}

        .chart-container {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 3px solid #FFA500;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 0 30px rgba(255, 165, 0, 0.3);
            transition: all 0.3s ease;
        }}

        .chart-container:hover {{
            transform: translateY(-5px);
            box-shadow: 0 0 50px rgba(255, 165, 0, 0.5);
            border-color: #FF6B35;
        }}

        .chart-title {{
            color: #FFA500;
            font-size: 1.4em;
            margin-bottom: 15px;
            text-align: center;
            text-shadow: 0 0 15px rgba(255, 165, 0, 0.8);
            font-weight: bold;
        }}

        .chart-description {{
            color: #FDB44B;
            font-size: 0.9em;
            margin-bottom: 20px;
            text-align: center;
            line-height: 1.5;
        }}

        .insights-section {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 3px solid #FFA500;
            border-radius: 15px;
            padding: 30px;
            margin-top: 30px;
            box-shadow: 0 0 30px rgba(255, 165, 0, 0.3);
        }}

        .insights-title {{
            color: #FFA500;
            font-size: 1.6em;
            margin-bottom: 20px;
            text-shadow: 0 0 15px rgba(255, 165, 0, 0.8);
        }}

        .insight-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}

        .insight-card {{
            background: rgba(255, 165, 0, 0.05);
            border: 2px solid #FDB44B;
            border-radius: 10px;
            padding: 20px;
            transition: all 0.3s ease;
        }}

        .insight-card:hover {{
            background: rgba(255, 165, 0, 0.1);
            border-color: #FFA500;
            transform: scale(1.02);
        }}

        .insight-card h3 {{
            color: #FFA500;
            font-size: 1.2em;
            margin-bottom: 10px;
        }}

        .insight-card p {{
            color: #FFD700;
            line-height: 1.6;
            font-size: 0.95em;
        }}

        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #FDB44B;
            border-top: 2px solid #FFA500;
        }}

        @media (max-width: 1200px) {{
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>₿ BITCOIN BETA ANALYSIS</h1>
        <div class="subtitle">Multi-Dimensional Correlation Dashboard</div>
        <div class="subtitle">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        {f'<div class="btc-stat">BTC 24h Change: {btc_price_change:+.2f}%</div>' if btc_price_change is not None else ''}
    </div>

    <div class="chart-grid">
        <div class="chart-container">
            <div class="chart-title">📊 Beta vs Price Performance</div>
            <div class="chart-description">
                Shows how well Bitcoin Beta predicts actual 24h price moves.
                Bubble size = volume. Points near diagonal = beta is accurate.
            </div>
            <div id="chart1"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">📈 Beta Distribution</div>
            <div class="chart-description">
                Market structure across beta categories.
                Most symbols cluster around 1.0x (following BTC).
            </div>
            <div id="chart2"></div>
        </div>

        <div class="chart-container" style="grid-column: 1 / -1;">
            <div class="chart-title">📊 Individual Symbol Movements vs Bitcoin</div>
            <div class="chart-description">
                Each line represents one symbol's 24h price movement compared to Bitcoin's baseline.
                Steeper lines = higher volatility. Color = beta category. Hover for details.
            </div>
            <div id="chart3"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">💧 Beta vs Liquidity</div>
            <div class="chart-description">
                High-volume symbols plotted by beta. Color = price momentum.
                Ensure tradeable liquidity for beta plays.
            </div>
            <div id="chart4"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">🔥 Correlation Heatmap</div>
            <div class="chart-description">
                Top 20 symbols by volume showing beta similarity.
                Dark red = strong correlation, dark blue = weak correlation.
            </div>
            <div id="chart5"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">🎯 Risk-Return Quadrant</div>
            <div class="chart-description">
                Portfolio analysis view. Green = high beta + positive return (best),
                Red = high beta + negative return (worst).
            </div>
            <div id="chart6"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">🌈 Parallel Coordinates</div>
            <div class="chart-description">
                Multi-dimensional view of top 30 symbols across all metrics.
                Each line is a symbol connecting its values across dimensions.
            </div>
            <div id="chart7"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">🗺️ Beta Category Treemap</div>
            <div class="chart-description">
                Hierarchical view of market by beta category.
                Box size = total volume in category.
            </div>
            <div id="chart8"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">📦 Beta Distribution Box Plot</div>
            <div class="chart-description">
                Statistical distribution of beta values by category.
                Shows median, quartiles, and outliers.
            </div>
            <div id="chart9"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">⭐ Top 5 Radar Comparison</div>
            <div class="chart-description">
                Multi-metric comparison of highest volume symbols.
                Larger area = stronger across all dimensions.
            </div>
            <div id="chart10"></div>
        </div>
    </div>

    <div class="insights-section">
        <div class="insights-title">📖 Trading Insights & Strategy Guide</div>
        <div class="insight-grid">
            <div class="insight-card">
                <h3>🔴 High Beta (>1.5x)</h3>
                <p>
                    <strong>Strategy:</strong> Leveraged BTC exposure<br>
                    <strong>Risk:</strong> Extreme volatility, use tight stops<br>
                    <strong>Best For:</strong> Experienced traders, short-term plays<br>
                    <strong>Example:</strong> If BTC moves +5%, these move +7.5%+
                </p>
            </div>

            <div class="insight-card">
                <h3>🟠 Amplifies BTC (1.0-1.5x)</h3>
                <p>
                    <strong>Strategy:</strong> Enhanced BTC correlation<br>
                    <strong>Risk:</strong> Moderate-High, follows BTC closely<br>
                    <strong>Best For:</strong> Swing trading BTC trends<br>
                    <strong>Example:</strong> If BTC moves +5%, these move +5-7.5%
                </p>
            </div>

            <div class="insight-card">
                <h3>🟡 Follows BTC (0.5-1.0x)</h3>
                <p>
                    <strong>Strategy:</strong> Standard BTC correlation<br>
                    <strong>Risk:</strong> Moderate, predictable movement<br>
                    <strong>Best For:</strong> Long-term holds, safer alts<br>
                    <strong>Example:</strong> If BTC moves +5%, these move +2.5-5%
                </p>
            </div>

            <div class="insight-card">
                <h3>🔵 Weak Correlation (0-0.5x)</h3>
                <p>
                    <strong>Strategy:</strong> Independent/sector plays<br>
                    <strong>Risk:</strong> Variable, driven by own catalysts<br>
                    <strong>Best For:</strong> Portfolio diversification<br>
                    <strong>Example:</strong> Moves somewhat with BTC but own factors dominate
                </p>
            </div>

            <div class="insight-card">
                <h3>🟢 Inverse (<0)</h3>
                <p>
                    <strong>Strategy:</strong> Portfolio hedge, counter-BTC<br>
                    <strong>Risk:</strong> Rare, unusual market conditions<br>
                    <strong>Best For:</strong> Hedging, market neutral strategies<br>
                    <strong>Example:</strong> When BTC drops, these may pump
                </p>
            </div>

            <div class="insight-card">
                <h3>⚡ Key Considerations</h3>
                <p>
                    <strong>Volume:</strong> Always check liquidity before trading<br>
                    <strong>Timeframe:</strong> Beta calculated on 24h moves<br>
                    <strong>Market Conditions:</strong> Beta changes in different regimes<br>
                    <strong>Execution:</strong> Use limit orders on low-liquidity betas
                </p>
            </div>
        </div>
    </div>

    <div class="footer">
        <p>🔮 Bitcoin Beta Analysis Dashboard | Cyberpunk Amber Theme 🔮</p>
        <p>Interactive visualizations for correlation-based trading strategies</p>
    </div>

    <script>
        // Chart 1: Beta vs Price Performance Scatter
        var chart1Data = [{{
            type: 'scatter',
            mode: 'markers',
            x: {json.dumps(scatter_data['betas'])},
            y: {json.dumps(scatter_data['price_changes'])},
            text: {json.dumps(scatter_data['symbols'])},
            marker: {{
                size: {json.dumps([min(v * 20, 40) for v in scatter_data['volumes']])},
                color: {json.dumps(scatter_data['colors'])},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            hovertemplate: '<b>%{{text}}</b><br>Beta: %{{x:.2f}}x<br>24h Change: %{{y:+.2f}}%<extra></extra>'
        }}];

        var chart1Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Bitcoin Beta',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            yaxis: {{
                title: '24h Price Change (%)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            shapes: [
                {{
                    type: 'line',
                    x0: 1.0,
                    x1: 1.0,
                    y0: -50,
                    y1: 50,
                    line: {{
                        color: '#FFA500',
                        width: 2,
                        dash: 'dash'
                    }}
                }}
            ],
            margin: {{ l: 60, r: 40, t: 20, b: 60 }},
            height: 500,
            showlegend: false
        }};

        Plotly.newPlot('chart1', chart1Data, chart1Layout, {{responsive: true}});

        // Chart 2: Beta Distribution Histogram
        var chart2Data = [{{
            type: 'histogram',
            x: {json.dumps(all_betas)},
            marker: {{
                color: '#FFA500',
                line: {{
                    color: '#FFD700',
                    width: 2
                }}
            }},
            xbins: {{
                start: -2,
                end: 5,
                size: 0.5
            }}
        }}];

        var chart2Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Bitcoin Beta',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            yaxis: {{
                title: 'Number of Symbols',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            shapes: [
                {{
                    type: 'line',
                    x0: 1.0,
                    x1: 1.0,
                    y0: 0,
                    y1: 1,
                    yref: 'paper',
                    line: {{
                        color: '#FFA500',
                        width: 3,
                        dash: 'dash'
                    }}
                }}
            ],
            margin: {{ l: 60, r: 40, t: 20, b: 60 }},
            height: 500,
            showlegend: false
        }};

        Plotly.newPlot('chart2', chart2Data, chart2Layout, {{responsive: true}});

        // Chart 3: Time Series - Individual Symbol Price Movements
        var historicalData = {json.dumps(historical_data) if historical_data else '{}'};

        // Helper function to get color based on beta
        function getBetaColor(beta) {{
            if (beta > 1.5) return '#FF6B35';
            if (beta > 1.0) return '#FFA500';
            if (beta > 0.5) return '#FDB44B';
            if (beta > 0) return '#FFD700';
            return '#00FF7F';
        }}

        // Create time series traces
        var chart3Data = [];
        var chart3Annotations = [];

        // Get symbols with historical data
        var symbolsInChart = Object.keys(historicalData);

        // Process each symbol
        for (let symbol of symbolsInChart) {{
            let candles = historicalData[symbol];
            if (!candles || candles.length === 0) continue;

            // Normalize to percentage change from first candle
            let initialPrice = candles[0].close;
            let timestamps = candles.map(c => new Date(c.timestamp));
            let percentChanges = candles.map(c => ((c.close - initialPrice) / initialPrice) * 100);

            // Get beta for color (find in analyses)
            let beta = 1.0;  // Default
            let symbolAnalysis = {json.dumps({a['symbol']: a.get('btc_beta', 1.0) for a in symbols_with_beta})};
            if (symbolAnalysis[symbol]) {{
                beta = symbolAnalysis[symbol];
            }}

            let color = getBetaColor(beta);
            let lineWidth = (symbol === 'BTC') ? 4 : 2;
            let opacity = (symbol === 'BTC') ? 1.0 : 0.7;

            chart3Data.push({{
                type: 'scatter',
                mode: 'lines',
                x: timestamps,
                y: percentChanges,
                name: symbol,
                line: {{
                    color: color,
                    width: lineWidth,
                    opacity: opacity
                }},
                hovertemplate: '<b>' + symbol + '</b><br>%{{x}}<br>Change: %{{y:.2f}}%<br>Beta: ' + beta.toFixed(2) + 'x<extra></extra>',
                showlegend: (symbol === 'BTC'),
                legendgroup: symbol
            }});

            // Add label annotation on the right side
            let lastTimestamp = timestamps[timestamps.length - 1];
            let lastChange = percentChanges[percentChanges.length - 1];

            chart3Annotations.push({{
                x: lastTimestamp,
                y: lastChange,
                xref: 'x',
                yref: 'y',
                text: symbol,
                showarrow: false,
                xanchor: 'left',
                xshift: 5,
                font: {{
                    color: color,
                    size: 10,
                    weight: (symbol === 'BTC') ? 'bold' : 'normal'
                }},
                bgcolor: 'rgba(0,0,0,0.8)',
                borderpad: 2
            }});
        }}

        var chart3Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Time (24h Period)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                type: 'date'
            }},
            yaxis: {{
                title: 'Price Change (%)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            shapes: [
                {{
                    type: 'line',
                    xref: 'paper',
                    x0: 0,
                    x1: 1,
                    y0: 0,
                    y1: 0,
                    line: {{
                        color: '#888888',
                        width: 2,
                        dash: 'solid'
                    }}
                }}
            ],
            annotations: chart3Annotations,
            margin: {{ l: 60, r: 100, t: 20, b: 80 }},
            height: 700,
            hovermode: 'x unified',
            legend: {{
                x: 0.02,
                y: 0.98,
                bgcolor: 'rgba(0,0,0,0.7)',
                bordercolor: '#FFA500',
                borderwidth: 2
            }}
        }};

        Plotly.newPlot('chart3', chart3Data, chart3Layout, {{responsive: true}});

        // Chart 4: Beta vs Volume Bubble
        var chart4Data = [{{
            type: 'scatter',
            mode: 'markers+text',
            x: {json.dumps(bubble_data['betas'])},
            y: {json.dumps(bubble_data['volumes'])},
            text: {json.dumps(bubble_data['symbols'])},
            textposition: 'top center',
            textfont: {{
                color: '#FFD700',
                size: 9
            }},
            marker: {{
                size: {json.dumps([max(5, min(v * 5, 30)) for v in bubble_data['volumes']])},
                color: {json.dumps(bubble_data['colors'])},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            hovertemplate: '<b>%{{text}}</b><br>Beta: %{{x:.2f}}x<br>Volume: $%{{y:.2f}}B<br>24h: %{{customdata:+.1f}}%<extra></extra>',
            customdata: {json.dumps(bubble_data['price_changes'])}
        }}];

        var chart4Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Bitcoin Beta',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            yaxis: {{
                title: '24h Volume ($B)',
                type: 'log',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            shapes: [
                {{
                    type: 'line',
                    x0: 1.0,
                    x1: 1.0,
                    y0: 0,
                    y1: 1,
                    yref: 'paper',
                    line: {{
                        color: '#FFA500',
                        width: 2,
                        dash: 'dash'
                    }}
                }}
            ],
            margin: {{ l: 60, r: 40, t: 20, b: 60 }},
            height: 500,
            showlegend: false
        }};

        Plotly.newPlot('chart4', chart4Data, chart4Layout, {{responsive: true}});

        // Chart 5: Correlation Heatmap
        var chart5Data = [{{
            type: 'heatmap',
            z: {json.dumps(correlation_matrix)},
            x: {json.dumps(heatmap_symbols)},
            y: {json.dumps(heatmap_symbols)},
            colorscale: [
                [0, '#000080'],      // Dark blue - low correlation
                [0.25, '#4169E1'],   // Royal blue
                [0.5, '#FDB44B'],    // Amber
                [0.75, '#FF6B35'],   // Orange-red
                [1, '#8B0000']       // Dark red - high correlation
            ],
            text: {json.dumps([[f'{val:.2f}' for val in row] for row in correlation_matrix])},
            texttemplate: '%{{text}}',
            textfont: {{
                size: 8,
                color: '#FFD700'
            }},
            hovertemplate: '%{{y}} ↔ %{{x}}<br>Correlation: %{{z:.2f}}<extra></extra>',
            colorbar: {{
                title: 'Correlation',
                titlefont: {{ color: '#FFD700' }},
                tickfont: {{ color: '#FFD700' }}
            }}
        }}];

        var chart5Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                side: 'bottom',
                tickangle: -45,
                color: '#FFD700'
            }},
            yaxis: {{
                color: '#FFD700'
            }},
            margin: {{ l: 80, r: 100, t: 20, b: 120 }},
            height: 600
        }};

        Plotly.newPlot('chart5', chart5Data, chart5Layout, {{responsive: true}});

        // Chart 6: Risk-Return Quadrant
        var chart6Data = [{{
            type: 'scatter',
            mode: 'markers',
            x: {json.dumps(quadrant_data['betas'])},
            y: {json.dumps(quadrant_data['returns'])},
            text: {json.dumps(quadrant_data['symbols'])},
            marker: {{
                size: {json.dumps([min(v * 15, 25) for v in quadrant_data['volumes']])},
                color: {json.dumps(quadrant_data['quadrant_colors'])},
                line: {{
                    color: '#FFA500',
                    width: 1
                }}
            }},
            hovertemplate: '<b>%{{text}}</b><br>Beta: %{{x:.2f}}x<br>Return: %{{y:+.2f}}%<extra></extra>'
        }}];

        var chart6Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Beta (Risk)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            yaxis: {{
                title: '24h Return (%)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            shapes: [
                {{
                    type: 'line',
                    x0: 1.0,
                    x1: 1.0,
                    y0: -50,
                    y1: 50,
                    line: {{
                        color: '#FFA500',
                        width: 2,
                        dash: 'dash'
                    }}
                }},
                {{
                    type: 'line',
                    x0: -2,
                    x1: 5,
                    y0: 0,
                    y1: 0,
                    line: {{
                        color: '#FFA500',
                        width: 2,
                        dash: 'dash'
                    }}
                }}
            ],
            annotations: [
                {{
                    x: 2.5,
                    y: 25,
                    text: 'High Risk<br>High Reward',
                    showarrow: false,
                    font: {{ color: '#00FF7F', size: 11 }}
                }},
                {{
                    x: 2.5,
                    y: -25,
                    text: 'High Risk<br>Low Reward',
                    showarrow: false,
                    font: {{ color: '#FF6B35', size: 11 }}
                }},
                {{
                    x: 0.3,
                    y: 25,
                    text: 'Low Risk<br>Positive Return',
                    showarrow: false,
                    font: {{ color: '#FDB44B', size: 11 }}
                }},
                {{
                    x: 0.3,
                    y: -25,
                    text: 'Low Risk<br>Negative Return',
                    showarrow: false,
                    font: {{ color: '#FFA500', size: 11 }}
                }}
            ],
            margin: {{ l: 60, r: 40, t: 20, b: 60 }},
            height: 500,
            showlegend: false
        }};

        Plotly.newPlot('chart6', chart6Data, chart6Layout, {{responsive: true}});

        // Chart 7: Parallel Coordinates
        var chart7Data = [{{
            type: 'parcoords',
            line: {{
                color: {json.dumps(parallel_data['betas'])},
                colorscale: [
                    [0, '#00FF7F'],
                    [0.5, '#FFA500'],
                    [1, '#FF6B35']
                ],
                showscale: true,
                cmin: -1,
                cmax: 3,
                colorbar: {{
                    title: 'Beta',
                    titlefont: {{ color: '#FFD700' }},
                    tickfont: {{ color: '#FFD700' }}
                }}
            }},
            dimensions: [
                {{
                    label: 'Beta',
                    values: {json.dumps(parallel_data['betas'])},
                    range: [-1, 3]
                }},
                {{
                    label: 'Volume ($B)',
                    values: {json.dumps(parallel_data['volumes'])},
                    range: [0, Math.max(...{json.dumps(parallel_data['volumes'])})]
                }},
                {{
                    label: '24h Change (%)',
                    values: {json.dumps(parallel_data['price_changes'])},
                    range: [-20, 20]
                }},
                {{
                    label: 'Funding (%)',
                    values: {json.dumps(parallel_data['funding_rates'])},
                    range: [-5, 5]
                }},
                {{
                    label: 'OI ($B)',
                    values: {json.dumps(parallel_data['oi'])},
                    range: [0, Math.max(...{json.dumps(parallel_data['oi'])})]
                }}
            ],
            labelangle: -45,
            labelfont: {{
                color: '#FFD700',
                size: 11
            }},
            rangefont: {{
                color: '#FDB44B',
                size: 9
            }}
        }}];

        var chart7Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            margin: {{ l: 100, r: 150, t: 40, b: 40 }},
            height: 500
        }};

        Plotly.newPlot('chart7', chart7Data, chart7Layout, {{responsive: true}});

        // Chart 8: Treemap
        var chart8Data = [{{
            type: 'treemap',
            labels: {json.dumps(treemap_data['labels'])},
            parents: {json.dumps(treemap_data['parents'])},
            values: {json.dumps(treemap_data['values'])},
            marker: {{
                colors: {json.dumps(treemap_data['colors'])},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            textfont: {{
                color: '#FFD700',
                size: 14,
                family: 'Courier New'
            }},
            hovertemplate: '<b>%{{label}}</b><br>Volume: $%{{value:.2f}}B<extra></extra>',
            pathbar: {{
                visible: false
            }}
        }}];

        var chart8Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            margin: {{ l: 10, r: 10, t: 10, b: 10 }},
            height: 500
        }};

        Plotly.newPlot('chart8', chart8Data, chart8Layout, {{responsive: true}});

        // Chart 9: Box Plot
        var chart9Data = [];
        var boxColors = {{
            'Extreme (>2.0x)': '#FF0000',
            'High (1.5-2.0x)': '#FF6B35',
            'Amplifies (1.0-1.5x)': '#FFA500',
            'Follows (0.5-1.0x)': '#FDB44B',
            'Weak (0-0.5x)': '#FFD700',
            'Inverse (<0)': '#00FF7F'
        }};

        {json.dumps(list(box_data.keys()))}.forEach(function(category, idx) {{
            var betas = {json.dumps(list(box_data.values()))}[idx];
            chart9Data.push({{
                type: 'box',
                y: betas,
                name: category,
                marker: {{
                    color: boxColors[category],
                    line: {{
                        color: '#FFA500',
                        width: 2
                    }}
                }},
                boxmean: 'sd'
            }});
        }});

        var chart9Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                tickangle: -45,
                color: '#FFD700'
            }},
            yaxis: {{
                title: 'Beta Value',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            margin: {{ l: 60, r: 40, t: 20, b: 120 }},
            height: 500,
            showlegend: false
        }};

        Plotly.newPlot('chart9', chart9Data, chart9Layout, {{responsive: true}});

        // Chart 10: Radar Chart
        var chart10Data = [];
        var radarColors = ['#FF6B35', '#FFA500', '#FDB44B', '#FFD700', '#00FF7F'];

        {json.dumps(radar_data)}.forEach(function(item, idx) {{
            chart10Data.push({{
                type: 'scatterpolar',
                r: item.metrics.concat(item.metrics[0]),
                theta: ['Beta', 'Volume', 'OI', '24h Change', 'Funding', 'Beta'],
                fill: 'toself',
                name: item.symbol,
                line: {{
                    color: radarColors[idx % radarColors.length],
                    width: 3
                }},
                fillcolor: radarColors[idx % radarColors.length] + '40',
                marker: {{
                    size: 8,
                    color: radarColors[idx % radarColors.length]
                }}
            }});
        }});

        var chart10Layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            polar: {{
                bgcolor: 'rgba(0,0,0,0)',
                radialaxis: {{
                    visible: true,
                    range: [0, 1],
                    gridcolor: 'rgba(255, 215, 0, 0.2)',
                    tickfont: {{ color: '#FFD700' }}
                }},
                angularaxis: {{
                    gridcolor: 'rgba(255, 215, 0, 0.2)',
                    tickfont: {{ color: '#FFD700', size: 11 }}
                }}
            }},
            legend: {{
                font: {{ color: '#FFD700' }},
                bgcolor: 'rgba(0,0,0,0.3)',
                bordercolor: '#FFA500',
                borderwidth: 2
            }},
            margin: {{ l: 80, r: 80, t: 40, b: 40 }},
            height: 500
        }};

        Plotly.newPlot('chart10', chart10Data, chart10Layout, {{responsive: true}});
    </script>
</body>
</html>
"""

    return html


if __name__ == "__main__":
    print("\n🚀 Generating Bitcoin Beta HTML Dashboard...\n")
    print("⏳ Fetching data from 8 exchanges (30-40 seconds)...\n")

    # Fetch and group data
    symbol_data = fetch_symbol_data_from_exchanges()

    print(f"✅ Collected data for {len(symbol_data)} symbols\n")

    # Get BTC price change for beta calculation
    btc_data = symbol_data.get('BTC', [])
    btc_price_change = None
    if btc_data:
        btc_changes = [d.get('price_change_pct') for d in btc_data if d.get('price_change_pct') is not None]
        if btc_changes:
            btc_price_change = sum(btc_changes) / len(btc_changes)
            print(f"📊 BTC 24h change: {btc_price_change:+.2f}% (using for beta calculation)\n")

    # Analyze symbols
    print("🔍 Analyzing symbols...\n")
    analyses = []
    for symbol, data in symbol_data.items():
        analysis = analyze_symbol(symbol, data, btc_price_change=btc_price_change)
        if analysis:
            analyses.append(analysis)

    # Sort by volume
    analyses.sort(key=lambda x: x['total_volume_24h'], reverse=True)

    print(f"✅ Analyzed {len(analyses)} symbols\n")

    # Fetch historical data for top 25 symbols (including BTC)
    print("📈 Fetching historical price data for top 25 symbols...\n")
    top_symbols = ['BTC'] + [a['symbol'] for a in analyses[:24] if a['symbol'] != 'BTC']
    historical_data = fetch_historical_data_for_symbols(top_symbols, limit=24)
    print(f"\n✅ Fetched historical data for {len(historical_data)} symbols\n")

    # Generate HTML
    print("🎨 Generating Bitcoin Beta dashboard...\n")
    html_content = generate_beta_html_dashboard(analyses, btc_price_change, historical_data)

    # Save HTML
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

    # Get project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')

    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)

    filename = os.path.join(data_dir, f"bitcoin_beta_dashboard_{timestamp}.html")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Bitcoin Beta Dashboard saved to: {filename}")
        print(f"\n🌐 Open in browser to explore 10 different beta visualizations!")

        # Try to open in browser
        import webbrowser
        filepath = os.path.abspath(filename)
        webbrowser.open('file://' + filepath)
        print(f"🔥 Opening in browser...")

    except Exception as e:
        print(f"⚠️  Could not save HTML: {e}")
