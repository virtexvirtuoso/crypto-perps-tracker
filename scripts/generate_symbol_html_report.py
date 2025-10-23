#!/usr/bin/env python3
"""
Symbol Report HTML Dashboard Generator
Creates interactive HTML dashboard with Cyberpunk Amber styling
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_symbol_report import (
    fetch_symbol_data_from_exchanges,
    analyze_symbol,
    normalize_symbol
)
from datetime import datetime, timezone
from typing import Dict, List
import json


def generate_html_dashboard(analyses: List[Dict], btc_price_change: float = None) -> str:
    """Generate comprehensive HTML dashboard with interactive Plotly charts"""

    # Prepare data for charts
    top_20 = analyses[:20]

    # Volume data
    volume_symbols = [a['symbol'][:8] for a in top_20]
    volume_values = [a['total_volume_24h'] / 1e9 for a in top_20]

    # Funding rate data (top 15 by volume with funding)
    funding_data = [a for a in analyses[:30] if a.get('avg_funding_rate') is not None][:15]
    funding_symbols = [a['symbol'][:8] for a in funding_data]
    funding_rates = [a['avg_funding_rate'] for a in funding_data]
    funding_colors = ['#FF6B35' if r > 0.03 else '#00FF7F' if r < -0.03 else '#FDB44B' for r in funding_rates]

    # Bitcoin Beta data (most interesting)
    beta_data = [a for a in analyses if a.get('btc_beta') is not None and a['symbol'] != 'BTC']
    beta_data.sort(key=lambda x: abs(x['btc_beta'] - 1.0), reverse=True)
    beta_symbols = [a['symbol'][:8] for a in beta_data[:20]]
    beta_values = [a['btc_beta'] for a in beta_data[:20]]
    beta_colors = []
    for b in beta_values:
        if b > 1.5:
            beta_colors.append('#FF6B35')
        elif b > 1.0:
            beta_colors.append('#FFA500')
        elif b > 0.5:
            beta_colors.append('#FDB44B')
        elif b > 0:
            beta_colors.append('#FFD700')
        else:
            beta_colors.append('#00FF7F')

    # Arbitrage opportunities
    arb_data = [a for a in analyses if a.get('arbitrage_opportunity') is not None]
    arb_data = [a for a in arb_data if a['arbitrage_opportunity']['spread_pct'] <= 100][:15]
    arb_symbols = [a['symbol'][:8] for a in arb_data]
    arb_spreads = [a['arbitrage_opportunity']['spread_pct'] for a in arb_data]
    arb_labels = [
        f"{a['arbitrage_opportunity']['buy'][:3]}→{a['arbitrage_opportunity']['sell'][:3]}"
        for a in arb_data
    ]

    # OI vs Volume scatter
    scatter_data = analyses[:50]
    scatter_volumes = [a['total_volume_24h'] / 1e9 for a in scatter_data]
    scatter_ois = [a['total_open_interest'] / 1e9 for a in scatter_data]
    scatter_symbols = [a['symbol'][:8] for a in scatter_data]
    scatter_colors = []
    for a in scatter_data:
        ratio = a['total_open_interest'] / a['total_volume_24h'] if a['total_volume_24h'] > 0 else 0
        if ratio > 0.5:
            scatter_colors.append('#00FF7F')
        elif ratio < 0.25:
            scatter_colors.append('#FF6B35')
        else:
            scatter_colors.append('#FFA500')

    # Exchange distribution (count symbols per exchange)
    exchange_counts = {}
    for a in analyses:
        for ex in a['exchanges']:
            exchange_counts[ex] = exchange_counts.get(ex, 0) + 1

    # Market cap proxy (volume * 50 as rough estimate)
    market_data = analyses[:30]
    market_symbols = [a['symbol'][:8] for a in market_data]
    market_volumes = [a['total_volume_24h'] / 1e9 for a in market_data]
    market_ois = [a['total_open_interest'] / 1e9 for a in market_data]

    # Summary stats
    total_symbols = len(analyses)
    total_volume = sum(a['total_volume_24h'] for a in analyses) / 1e9
    total_oi = sum(a['total_open_interest'] for a in analyses) / 1e9
    arb_count = len([a for a in analyses if a.get('arbitrage_opportunity') is not None])

    # Generate HTML
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Symbol Market Analysis - Cyberpunk Dashboard</title>
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
            border: 2px solid #FFA500;
            border-radius: 10px;
            box-shadow: 0 0 30px rgba(255, 165, 0, 0.3);
        }}

        .header h1 {{
            font-size: 2.5em;
            color: #FFA500;
            text-shadow: 0 0 20px rgba(255, 165, 0, 0.8);
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            color: #FFD700;
            font-size: 1.1em;
            margin-top: 10px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 2px solid #FFA500;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 0 20px rgba(255, 165, 0, 0.2);
            transition: all 0.3s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 0 30px rgba(255, 165, 0, 0.4);
            border-color: #FF6B35;
        }}

        .stat-card .label {{
            color: #FDB44B;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}

        .stat-card .value {{
            color: #FFA500;
            font-size: 2em;
            font-weight: bold;
            text-shadow: 0 0 10px rgba(255, 165, 0, 0.6);
        }}

        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 30px;
            margin-bottom: 30px;
        }}

        .chart-container {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 2px solid #FFA500;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 0 20px rgba(255, 165, 0, 0.2);
        }}

        .chart-title {{
            color: #FFA500;
            font-size: 1.3em;
            margin-bottom: 15px;
            text-align: center;
            text-shadow: 0 0 10px rgba(255, 165, 0, 0.6);
        }}

        .full-width {{
            grid-column: 1 / -1;
        }}

        .table-container {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 2px solid #FFA500;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            overflow-x: auto;
            box-shadow: 0 0 20px rgba(255, 165, 0, 0.2);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            color: #FFD700;
        }}

        th {{
            background: linear-gradient(135deg, #2a2a2a 0%, #3a3a3a 100%);
            color: #FFA500;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid #FFA500;
        }}

        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #333;
        }}

        tr:hover {{
            background: rgba(255, 165, 0, 0.1);
        }}

        .positive {{
            color: #00FF7F;
        }}

        .negative {{
            color: #FF6B35;
        }}

        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #FDB44B;
            border-top: 2px solid #FFA500;
        }}

        @media (max-width: 768px) {{
            .chart-grid {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 1.8em;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ SYMBOL MARKET ANALYSIS ⚡</h1>
        <div class="subtitle">Cross-Exchange Intelligence Dashboard</div>
        <div class="subtitle">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">Symbols Tracked</div>
            <div class="value">{total_symbols}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Volume (24h)</div>
            <div class="value">${total_volume:.2f}B</div>
        </div>
        <div class="stat-card">
            <div class="label">Open Interest</div>
            <div class="value">${total_oi:.2f}B</div>
        </div>
        <div class="stat-card">
            <div class="label">Arbitrage Opportunities</div>
            <div class="value">{arb_count}</div>
        </div>
    </div>

    <div class="chart-grid">
        <div class="chart-container full-width">
            <div class="chart-title">📊 Top 20 Symbols by Trading Volume</div>
            <div id="volumeChart"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">💰 Funding Rates Comparison</div>
            <div id="fundingChart"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">₿ Bitcoin Beta Analysis</div>
            <div id="betaChart"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">🎯 Arbitrage Opportunities</div>
            <div id="arbChart"></div>
        </div>

        <div class="chart-container">
            <div class="chart-title">📈 Volume vs Open Interest</div>
            <div id="scatterChart"></div>
        </div>

        <div class="chart-container full-width">
            <div class="chart-title">🔥 Volume & OI Heatmap</div>
            <div id="heatmapChart"></div>
        </div>
    </div>

    <div class="table-container">
        <div class="chart-title">Top 20 Symbols - Detailed Metrics</div>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Symbol</th>
                    <th>Volume (24h)</th>
                    <th>OI</th>
                    <th>Exchanges</th>
                    <th>Price</th>
                    <th>24h Change</th>
                    <th>Funding</th>
                    <th>Beta</th>
                </tr>
            </thead>
            <tbody>
"""

    # Add table rows
    for i, a in enumerate(top_20, 1):
        volume_str = f"${a['total_volume_24h']/1e9:.2f}B" if a['total_volume_24h'] > 1e9 else f"${a['total_volume_24h']/1e6:.0f}M"
        oi_str = f"${a['total_open_interest']/1e9:.2f}B" if a['total_open_interest'] > 1e9 else f"${a['total_open_interest']/1e6:.0f}M"
        price_str = f"${a['avg_price']:,.2f}"
        change_class = "positive" if a.get('avg_price_change_24h', 0) >= 0 else "negative"
        change_str = f"{a.get('avg_price_change_24h', 0):+.1f}%" if a.get('avg_price_change_24h') is not None else "N/A"
        funding_str = f"{a['avg_funding_rate']:.3f}%" if a.get('avg_funding_rate') is not None else "N/A"
        beta_str = f"{a['btc_beta']:.2f}x" if a.get('btc_beta') is not None else "N/A"

        html += f"""
                <tr>
                    <td>{i}</td>
                    <td><strong>{a['symbol'][:10]}</strong></td>
                    <td>{volume_str}</td>
                    <td>{oi_str}</td>
                    <td>{a['num_exchanges']}x</td>
                    <td>{price_str}</td>
                    <td class="{change_class}">{change_str}</td>
                    <td>{funding_str}</td>
                    <td>{beta_str}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>

    <div class="footer">
        <p>🔮 Generated with Crypto Perps Tracker | Cyberpunk Amber Theme 🔮</p>
        <p>Real-time cross-exchange market intelligence</p>
    </div>

    <script>
"""

    # Volume Chart (Horizontal Bar)
    html += f"""
        var volumeData = [{{
            type: 'bar',
            x: {json.dumps(volume_values)},
            y: {json.dumps(volume_symbols)},
            orientation: 'h',
            marker: {{
                color: {json.dumps(['#FF6B35' if i == 0 else '#FFA500' if i < 3 else '#FDB44B' for i in range(len(volume_values))])},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            text: {json.dumps([f'${v:.2f}B' for v in volume_values])},
            textposition: 'outside',
            textfont: {{
                color: '#FFD700',
                size: 12,
                family: 'Courier New'
            }}
        }}];

        var volumeLayout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: '24h Volume (Billions USD)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            yaxis: {{
                autorange: 'reversed',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            margin: {{ l: 80, r: 40, t: 20, b: 60 }},
            height: 600
        }};

        Plotly.newPlot('volumeChart', volumeData, volumeLayout, {{responsive: true}});
"""

    # Funding Chart
    html += f"""
        var fundingData = [{{
            type: 'bar',
            x: {json.dumps(funding_rates)},
            y: {json.dumps(funding_symbols)},
            orientation: 'h',
            marker: {{
                color: {json.dumps(funding_colors)},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            text: {json.dumps([f'{r:.3f}%' for r in funding_rates])},
            textposition: 'outside',
            textfont: {{
                color: '#FFD700',
                size: 11,
                family: 'Courier New'
            }}
        }}];

        var fundingLayout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Funding Rate (% per 8h)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            yaxis: {{
                autorange: 'reversed',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            margin: {{ l: 80, r: 40, t: 20, b: 60 }},
            height: 500
        }};

        Plotly.newPlot('fundingChart', fundingData, fundingLayout, {{responsive: true}});
"""

    # Beta Chart
    html += f"""
        var betaData = [{{
            type: 'bar',
            x: {json.dumps(beta_values)},
            y: {json.dumps(beta_symbols)},
            orientation: 'h',
            marker: {{
                color: {json.dumps(beta_colors)},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            text: {json.dumps([f'{b:.2f}x' for b in beta_values])},
            textposition: 'outside',
            textfont: {{
                color: '#FFD700',
                size: 11,
                family: 'Courier New'
            }}
        }}];

        var betaLayout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Bitcoin Beta (Correlation Multiplier)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 2
            }},
            yaxis: {{
                autorange: 'reversed',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            shapes: [{{
                type: 'line',
                x0: 1.0,
                x1: 1.0,
                y0: -0.5,
                y1: {len(beta_symbols) - 0.5},
                line: {{
                    color: '#FFA500',
                    width: 2,
                    dash: 'dash'
                }}
            }}],
            margin: {{ l: 80, r: 40, t: 20, b: 60 }},
            height: 600
        }};

        Plotly.newPlot('betaChart', betaData, betaLayout, {{responsive: true}});
"""

    # Arbitrage Chart
    html += f"""
        var arbData = [{{
            type: 'bar',
            x: {json.dumps(arb_spreads)},
            y: {json.dumps(arb_symbols)},
            orientation: 'h',
            marker: {{
                color: {json.dumps(['#FF6B35' if s > 10 else '#FFA500' if s > 2 else '#FDB44B' for s in arb_spreads])},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            text: {json.dumps([f'{s:.2f}% ({l})' for s, l in zip(arb_spreads, arb_labels)])},
            textposition: 'outside',
            textfont: {{
                color: '#FFD700',
                size: 10,
                family: 'Courier New'
            }}
        }}];

        var arbLayout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Price Spread (%)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            yaxis: {{
                autorange: 'reversed',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            margin: {{ l: 80, r: 40, t: 20, b: 60 }},
            height: 500
        }};

        Plotly.newPlot('arbChart', arbData, arbLayout, {{responsive: true}});
"""

    # Scatter Chart
    html += f"""
        var scatterData = [{{
            type: 'scatter',
            mode: 'markers+text',
            x: {json.dumps(scatter_volumes)},
            y: {json.dumps(scatter_ois)},
            text: {json.dumps(scatter_symbols)},
            textposition: 'top center',
            textfont: {{
                color: '#FFD700',
                size: 10,
                family: 'Courier New'
            }},
            marker: {{
                size: 12,
                color: {json.dumps(scatter_colors)},
                line: {{
                    color: '#FFA500',
                    width: 2
                }}
            }},
            hovertemplate: '<b>%{{text}}</b><br>Volume: $%{{x:.2f}}B<br>OI: $%{{y:.2f}}B<extra></extra>'
        }}];

        var maxVal = Math.max(...{json.dumps(scatter_volumes)}, ...{json.dumps(scatter_ois)});

        var scatterLayout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: '24h Volume (Billions USD)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            yaxis: {{
                title: 'Open Interest (Billions USD)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700'
            }},
            shapes: [{{
                type: 'line',
                x0: 0,
                x1: maxVal,
                y0: 0,
                y1: maxVal,
                line: {{
                    color: '#FF6B35',
                    width: 2,
                    dash: 'dash'
                }}
            }}],
            margin: {{ l: 60, r: 40, t: 20, b: 60 }},
            height: 500,
            showlegend: false
        }};

        Plotly.newPlot('scatterChart', scatterData, scatterLayout, {{responsive: true}});
"""

    # Heatmap Chart
    html += f"""
        var heatmapData = [{{
            type: 'heatmap',
            z: [{json.dumps(market_volumes)}, {json.dumps(market_ois)}],
            x: {json.dumps(market_symbols)},
            y: ['Volume', 'OI'],
            colorscale: [
                [0, '#1a1a1a'],
                [0.2, '#FF6B35'],
                [0.5, '#FFA500'],
                [0.8, '#FDB44B'],
                [1, '#FFD700']
            ],
            showscale: true,
            colorbar: {{
                title: 'Billions USD',
                titlefont: {{ color: '#FFD700' }},
                tickfont: {{ color: '#FFD700' }}
            }},
            hovertemplate: '<b>%{{x}}</b><br>%{{y}}: $%{{z:.2f}}B<extra></extra>'
        }}];

        var heatmapLayout = {{
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
                color: '#FFD700'
            }},
            margin: {{ l: 60, r: 40, t: 20, b: 120 }},
            height: 300
        }};

        Plotly.newPlot('heatmapChart', heatmapData, heatmapLayout, {{responsive: true}});
    </script>
</body>
</html>
"""

    return html


if __name__ == "__main__":
    print("\n🚀 Generating Interactive HTML Symbol Report...\n")
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

    # Generate HTML
    print("🎨 Generating HTML dashboard...\n")
    html_content = generate_html_dashboard(analyses, btc_price_change)

    # Save HTML
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

    # Get project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')

    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)

    filename = os.path.join(data_dir, f"symbol_report_{timestamp}.html")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ HTML Dashboard saved to: {filename}")
        print(f"\n🌐 Open in browser to view interactive charts!")

        # Try to open in browser
        import webbrowser
        filepath = os.path.abspath(filename)
        webbrowser.open('file://' + filepath)
        print(f"🔥 Opening in browser...")

    except Exception as e:
        print(f"⚠️  Could not save HTML: {e}")
