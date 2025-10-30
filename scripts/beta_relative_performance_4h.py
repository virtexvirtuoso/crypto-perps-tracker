#!/usr/bin/env python3
"""
Bitcoin Beta Time Series - 4 Hour Version (Bybit Only)
Shows individual symbol movements vs Bitcoin over the last 4 hours
"""

import sys
import os

# Add deprecated directory to path
deprecated_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deprecated')
sys.path.insert(0, deprecated_dir)

import requests
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict
import time

# Import from deprecated script
from generate_symbol_report import (
    normalize_symbol,
    analyze_symbol
)


def fetch_bybit_symbols() -> List[Dict]:
    """Fetch all Bybit perpetual symbols - Fixed version"""
    try:
        response = requests.get(
            "https://api.bybit.com/v5/market/tickers?category=linear",
            timeout=10
        )
        data = response.json()

        if data.get('retCode') != 0:
            return []

        results = []
        for ticker in data['result']['list']:
            # Helper to safely convert to float
            def safe_float(value, default=0.0):
                if value is None or value == '':
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default

            results.append({
                'exchange': 'Bybit',
                'symbol': ticker['symbol'],
                'price': safe_float(ticker.get('lastPrice'), 0),
                'volume': safe_float(ticker.get('turnover24h'), 0),
                'open_interest': safe_float(ticker.get('openInterestValue'), 0),
                'funding_rate': safe_float(ticker.get('fundingRate'), 0) * 100,
                'price_change_pct': safe_float(ticker.get('price24hPcnt'), 0) * 100,
                'num_trades': None,
                'type': 'CEX'
            })

        return results

    except Exception as e:
        print(f"Bybit error: {e}")
        import traceback
        traceback.print_exc()
        return []


def fetch_historical_data_for_symbols(symbols: List[str], hours: int = 4) -> Dict[str, List[Dict]]:
    """
    Fetch hourly historical OHLCV data for specified symbols from OKX

    Args:
        symbols: List of symbol names (e.g., ['BTC', 'ETH', 'SOL'])
        hours: Number of hours of data to fetch (default 4)

    Returns:
        Dict mapping symbol -> list of {timestamp, open, high, low, close, volume}
    """
    historical_data = {}

    print(f"   📊 Fetching {hours}h historical data for {len(symbols)} symbols...")

    for symbol in symbols:
        try:
            # OKX uses -USDT-SWAP pairs
            okx_symbol = f"{symbol}-USDT-SWAP"

            url = "https://www.okx.com/api/v5/market/candles"
            params = {
                'instId': okx_symbol,
                'bar': '1H',
                'limit': hours
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


def generate_timeseries_html(analyses: List[Dict], btc_price_change: float = None, historical_data: Dict[str, List[Dict]] = None, hours: int = 4) -> str:
    """Generate single-chart time series HTML dashboard"""

    # Get symbols with beta data
    symbols_with_beta = [a for a in analyses if a.get('btc_beta') is not None and a['symbol'] != 'BTC']

    if not symbols_with_beta:
        return "<html><body><h1>No Beta Data Available</h1></body></html>"

    # Create volume rank mapping (for tooltips)
    volume_rank_map = {}
    for idx, a in enumerate(analyses, 1):
        volume_rank_map[a['symbol']] = {
            'rank': idx,
            'volume': a['total_volume_24h']
        }

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Beta Time Series - {hours}H (Bybit)</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
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
        .bybit-badge {{
            display: inline-block;
            background: rgba(255, 165, 0, 0.2);
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 1.1em;
            margin-top: 10px;
            border: 2px solid #FFA500;
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
        .chart-container {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 3px solid #FFA500;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 0 30px rgba(255, 165, 0, 0.3);
            margin: 0 auto;
            max-width: 1800px;
        }}
        .chart-title {{
            color: #FFA500;
            font-size: 1.6em;
            margin-bottom: 15px;
            text-align: center;
            text-shadow: 0 0 15px rgba(255, 165, 0, 0.8);
            font-weight: bold;
        }}
        .chart-description {{
            color: #FDB44B;
            font-size: 1em;
            margin-bottom: 30px;
            text-align: center;
            line-height: 1.6;
        }}
        .legend-info {{
            background: rgba(255, 165, 0, 0.1);
            border: 2px solid #FDB44B;
            border-radius: 10px;
            padding: 20px;
            margin: 20px auto;
            max-width: 1000px;
        }}
        .legend-info h3 {{
            color: #FFA500;
            margin-bottom: 10px;
        }}
        .legend-info p {{
            color: #FFD700;
            line-height: 1.6;
        }}
        .color-guide {{
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 15px;
        }}
        .color-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .color-box {{
            width: 20px;
            height: 20px;
            border-radius: 3px;
            border: 1px solid #FFA500;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>₿ BITCOIN RELATIVE PERFORMANCE - {hours}H</h1>
        <div class="bybit-badge">🏦 Data Source: Bybit Exchange</div>
        <div class="subtitle">Actual Performance vs Bitcoin Baseline</div>
        <div class="subtitle">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        {f'<div class="btc-stat">BTC 24h Change: {btc_price_change:+.2f}%</div>' if btc_price_change is not None else ''}
    </div>

    <div class="legend-info">
        <h3>📖 How to Read This Chart</h3>
        <p>
            Each line shows <strong>relative performance vs Bitcoin</strong> over {hours} hours. BTC is shown as a flat line at 0% (baseline).
            All other symbols display their actual price movement minus BTC's movement. Positive values = outperforming BTC, negative = underperforming.
            Lines are color-coded by their Bitcoin Beta (historical correlation strength).
        </p>
        <p style="margin-top: 10px;">
            <strong>Example:</strong> If BTC goes +2% and ETH goes +3%, ETH shows +1% (outperformed by 1%).
            If BTC goes +2% and a coin goes -1%, it shows -3% (underperformed by 3%).
        </p>
        <p style="margin-top: 10px;">
            <strong>Interactive Features:</strong> Use the time range buttons (1H, 2H, 4H, All) to zoom into specific periods.
            Click legend items to show/hide symbols. The slider below the chart allows precise time selection.
            Hover over any line to see details including volume rank. Top 10 by beta shown by default - click legend to show more.
        </p>
        <p style="margin-top: 10px;">
            <strong>Reference Lines:</strong> Dotted lines at ±5% and dashed lines at ±10% help identify significant divergence.
        </p>
        <div class="color-guide">
            <div class="color-item">
                <div class="color-box" style="background: #FF6B35;"></div>
                <span>High Beta (>1.5x) - Very Volatile</span>
            </div>
            <div class="color-item">
                <div class="color-box" style="background: #FFA500;"></div>
                <span>High Beta (1.0-1.5x) - Amplifies BTC</span>
            </div>
            <div class="color-item">
                <div class="color-box" style="background: #FDB44B;"></div>
                <span>Medium Beta (0.5-1.0x) - Follows BTC</span>
            </div>
            <div class="color-item">
                <div class="color-box" style="background: #FFD700;"></div>
                <span>Low Beta (0-0.5x) - Weak Correlation</span>
            </div>
            <div class="color-item">
                <div class="color-box" style="background: #00FF7F;"></div>
                <span>Inverse (<0) - Opposite BTC</span>
            </div>
        </div>
    </div>

    <div class="chart-container">
        <div class="chart-title">📊 {hours}-Hour Price Movement Comparison</div>
        <div class="chart-description">
            Each line shows a symbol's price change over {hours} hours. Legend sorted by performance (best to worst).
            Hover over any line to see rank, volume, and beta. Bitcoin (BTC) shown as a bold line for reference.
            Use time range buttons above and slider below to zoom. Click legend to toggle symbols (showing top 10 performers by default).
        </div>
        <div id="chart"></div>
    </div>

    <script>
        // Helper function to get color based on beta
        function getBetaColor(beta) {{
            if (beta > 1.5) return '#FF6B35';
            if (beta > 1.0) return '#FFA500';
            if (beta > 0.5) return '#FDB44B';
            if (beta > 0) return '#FFD700';
            return '#00FF7F';
        }}

        // Time Series Data
        var historicalData = {json.dumps(historical_data) if historical_data else '{}'};
        var volumeRankData = {json.dumps(volume_rank_map)};
        var chartData = [];
        var chartAnnotations = [];

        // Get symbols with historical data
        var symbolsInChart = Object.keys(historicalData);

        // Get beta values for sorting
        var symbolAnalysis = {json.dumps({a['symbol']: a.get('btc_beta', 1.0) for a in symbols_with_beta})};

        // Sort symbols by absolute beta (highest to lowest)
        symbolsInChart.sort(function(a, b) {{
            let betaA = Math.abs(symbolAnalysis[a] || 1.0);
            let betaB = Math.abs(symbolAnalysis[b] || 1.0);
            return betaB - betaA;  // Descending by absolute beta
        }});

        // Get BTC price changes first (for relative performance calculation)
        let btcCandles = historicalData['BTC'];
        let btcInitialPrice = btcCandles ? btcCandles[0].close : null;
        let btcPercentChanges = btcCandles ? btcCandles.map(c => ((c.close - btcInitialPrice) / btcInitialPrice) * 100) : [];

        // Process each symbol
        symbolsInChart.forEach(function(symbol, index) {{
            let candles = historicalData[symbol];
            if (!candles || candles.length === 0) return;

            let timestamps = candles.map(c => new Date(c.timestamp));

            // Get beta for this symbol
            let beta = symbolAnalysis[symbol] || 1.0;

            // Calculate relative performance vs BTC
            // BTC = 0%, all others = their actual change - BTC's change
            let percentChanges;
            if (symbol === 'BTC') {{
                // BTC is the baseline at 0%
                percentChanges = btcPercentChanges.map(() => 0);
            }} else {{
                // Relative performance: actual movement minus BTC's movement
                // If BTC moves +2% and ETH moves +3%, ETH shows +1% (outperformed)
                // If BTC moves +2% and a coin moves -1%, it shows -3% (underperformed)
                let initialPrice = candles[0].close;
                let actualChanges = candles.map(c => ((c.close - initialPrice) / initialPrice) * 100);
                percentChanges = actualChanges.map((change, i) => change - btcPercentChanges[i]);
            }}

            // Get volume rank info
            let rankInfo = volumeRankData[symbol] || {{ rank: 'N/A', volume: 0 }};
            let volumeStr = rankInfo.volume >= 1e9
                ? '$' + (rankInfo.volume / 1e9).toFixed(2) + 'B'
                : '$' + (rankInfo.volume / 1e6).toFixed(0) + 'M';

            let color = getBetaColor(beta);
            let lineWidth = (symbol === 'BTC') ? 5 : 2.5;
            let opacity = (symbol === 'BTC') ? 1.0 : 0.75;

            // Get beta for legend
            let betaStr = (beta >= 0 ? '+' : '') + beta.toFixed(2) + 'x';

            // Show only top 10 symbols by default (by absolute beta)
            let isVisible = (index < 10) ? true : 'legendonly';

            chartData.push({{
                type: 'scatter',
                mode: 'lines',
                x: timestamps,
                y: percentChanges,
                name: symbol + ' ' + betaStr,
                visible: isVisible,
                line: {{
                    color: color,
                    width: lineWidth,
                    opacity: opacity
                }},
                hovertemplate: '<b>' + symbol + '</b> (Rank #' + rankInfo.rank + ')<br>%{{x}}<br>Change: %{{y:.2f}}%<br>Beta: ' + beta.toFixed(2) + 'x<br>Volume: ' + volumeStr + '<extra></extra>',
                showlegend: true,
                legendgroup: symbol
            }});

            // Add label annotation on the right side (only for visible traces)
            if (isVisible === true) {{
                let lastTimestamp = timestamps[timestamps.length - 1];
                let lastChange = percentChanges[percentChanges.length - 1];

                chartAnnotations.push({{
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
                        size: 11,
                        weight: (symbol === 'BTC') ? 'bold' : 'normal'
                    }},
                    bgcolor: 'rgba(0,0,0,0.85)',
                    borderpad: 3
                }});
            }}
        }});

        var chartLayout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {{
                color: '#FFD700',
                family: 'Courier New'
            }},
            xaxis: {{
                title: 'Time ({hours} Hour Period)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                type: 'date',
                rangeselector: {{
                    buttons: [
                        {{
                            count: 1,
                            label: '1H',
                            step: 'hour',
                            stepmode: 'backward'
                        }},
                        {{
                            count: 2,
                            label: '2H',
                            step: 'hour',
                            stepmode: 'backward'
                        }},
                        {{
                            count: 4,
                            label: '4H',
                            step: 'hour',
                            stepmode: 'backward'
                        }},
                        {{
                            step: 'all',
                            label: 'All'
                        }}
                    ],
                    bgcolor: 'rgba(255, 165, 0, 0.2)',
                    activecolor: '#FFA500',
                    font: {{ color: '#FFD700' }},
                    x: 0,
                    y: 1.05,
                    xanchor: 'left',
                    yanchor: 'top'
                }},
                rangeslider: {{
                    visible: true,
                    bgcolor: 'rgba(255, 165, 0, 0.1)',
                    bordercolor: '#FFA500',
                    borderwidth: 1
                }}
            }},
            yaxis: {{
                title: 'Relative Performance vs BTC (%)',
                gridcolor: 'rgba(255, 215, 0, 0.1)',
                color: '#FFD700',
                zeroline: true,
                zerolinecolor: '#888888',
                zerolinewidth: 3
            }},
            shapes: [
                {{
                    // Zero line (baseline)
                    type: 'line',
                    xref: 'paper',
                    x0: 0,
                    x1: 1,
                    y0: 0,
                    y1: 0,
                    line: {{
                        color: '#888888',
                        width: 3,
                        dash: 'solid'
                    }}
                }},
                {{
                    // +5% threshold
                    type: 'line',
                    xref: 'paper',
                    x0: 0,
                    x1: 1,
                    y0: 5,
                    y1: 5,
                    line: {{
                        color: '#00FF7F',
                        width: 1,
                        dash: 'dot'
                    }}
                }},
                {{
                    // +10% threshold
                    type: 'line',
                    xref: 'paper',
                    x0: 0,
                    x1: 1,
                    y0: 10,
                    y1: 10,
                    line: {{
                        color: '#00FF7F',
                        width: 1.5,
                        dash: 'dash'
                    }}
                }},
                {{
                    // -5% threshold
                    type: 'line',
                    xref: 'paper',
                    x0: 0,
                    x1: 1,
                    y0: -5,
                    y1: -5,
                    line: {{
                        color: '#FF6B35',
                        width: 1,
                        dash: 'dot'
                    }}
                }},
                {{
                    // -10% threshold
                    type: 'line',
                    xref: 'paper',
                    x0: 0,
                    x1: 1,
                    y0: -10,
                    y1: -10,
                    line: {{
                        color: '#FF6B35',
                        width: 1.5,
                        dash: 'dash'
                    }}
                }}
            ],
            annotations: chartAnnotations,
            margin: {{ l: 70, r: 300, t: 30, b: 80 }},
            height: 800,
            hovermode: 'x unified',
            legend: {{
                x: 1.02,
                y: 1,
                xanchor: 'left',
                yanchor: 'top',
                bgcolor: 'rgba(0,0,0,0.85)',
                bordercolor: '#FFA500',
                borderwidth: 2,
                font: {{ size: 11 }}
            }}
        }};

        Plotly.newPlot('chart', chartData, chartLayout, {{responsive: true}});
    </script>
</body>
</html>
"""

    return html


def fetch_symbol_data_from_bybit_only() -> Dict[str, List[Dict]]:
    """
    Fetch data from Bybit only and group by symbol

    Returns:
        Dict mapping symbol -> list of exchange data for that symbol
    """
    symbol_data = defaultdict(list)

    print("   📊 Fetching data from Bybit...")

    # Fetch only from Bybit
    try:
        results = fetch_bybit_symbols()
        print(f"      ✓ Fetched {len(results)} symbols from Bybit")

        # Group by symbol
        for item in results:
            symbol = normalize_symbol(item['symbol'])
            if symbol:  # Skip empty symbols
                symbol_data[symbol].append(item)

    except Exception as e:
        print(f"      ❌ Error fetching Bybit data: {e}")

    return dict(symbol_data)


def select_liquid_extremes(analyses: List[Dict], limit: int = 30) -> List[Dict]:
    """
    OPTION F: LIQUID EXTREMES - Mix of high liquidity + extreme outliers

    Strategy:
    - Minimum $50M volume (tradable but allows interesting coins)
    - Prioritize EXTREME betas (>5x or <-2x) within liquid pool
    - Include top liquid symbols (BTC, ETH, SOL always)
    - Add extreme gainers/losers (but only if >$50M volume)
    - Fill with high-beta liquid symbols

    Balance: 50% extreme outliers + 50% liquid market leaders
    """
    MIN_VOLUME = 50e6  # $50M minimum (sweet spot)

    selected = []
    selected_symbols = set()

    # Filter to minimum volume first
    filtered = [a for a in analyses if a['total_volume_24h'] >= MIN_VOLUME]

    print(f"   After $50M volume filter: {len(filtered)} symbols available")

    # === PHASE 1: Always include top 3 by volume (market leaders) ===
    by_volume = sorted(filtered, key=lambda x: x['total_volume_24h'], reverse=True)
    for a in by_volume[:3]:
        if a['symbol'] not in selected_symbols:
            selected.append(a)
            selected_symbols.add(a['symbol'])

    print(f"   ✓ Added {len(selected)} market leaders (BTC, ETH, SOL)")

    # === PHASE 2: Extreme high beta (>5x) - up to 7 symbols ===
    extreme_high = sorted([a for a in filtered if a.get('btc_beta', 0) > 5.0],
                          key=lambda x: x['btc_beta'], reverse=True)
    count = 0
    for a in extreme_high:
        if a['symbol'] not in selected_symbols and count < 7:
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   ✓ Added {count} extreme high beta symbols (>5x)")

    # === PHASE 3: Extreme inverse beta (<-2x) - up to 5 symbols ===
    extreme_inverse = sorted([a for a in filtered if a.get('btc_beta', 0) < -2.0],
                             key=lambda x: x['btc_beta'])
    count = 0
    for a in extreme_inverse:
        if a['symbol'] not in selected_symbols and count < 5:
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    print(f"   ✓ Added {count} extreme inverse symbols (<-2x)")

    # === PHASE 4: Top gainers (>10% change) - up to 4 symbols ===
    top_gainers = sorted([a for a in filtered
                         if a.get('avg_price_change_24h', 0) > 10.0],
                        key=lambda x: x['avg_price_change_24h'], reverse=True)
    count = 0
    for a in top_gainers:
        if a['symbol'] not in selected_symbols and count < 4:
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    if count > 0:
        print(f"   ✓ Added {count} top gainers (>10%)")

    # === PHASE 5: Top losers (<-10% change) - up to 4 symbols ===
    top_losers = sorted([a for a in filtered
                        if a.get('avg_price_change_24h', 0) < -10.0],
                       key=lambda x: x['avg_price_change_24h'])
    count = 0
    for a in top_losers:
        if a['symbol'] not in selected_symbols and count < 4:
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    if count > 0:
        print(f"   ✓ Added {count} top losers (<-10%)")

    # === PHASE 6: Medium-high beta (2-5x) for balance - up to 5 symbols ===
    medium_high = sorted([a for a in filtered
                         if 2.0 <= a.get('btc_beta', 0) < 5.0],
                        key=lambda x: x['total_volume_24h'], reverse=True)
    count = 0
    for a in medium_high:
        if a['symbol'] not in selected_symbols and count < 5:
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    if count > 0:
        print(f"   ✓ Added {count} medium-high beta symbols (2-5x)")

    # === PHASE 7: Fill remaining with highest volume ===
    remaining = sorted([a for a in filtered if a['symbol'] not in selected_symbols],
                      key=lambda x: x['total_volume_24h'], reverse=True)
    count = 0
    for a in remaining:
        if len(selected) < limit:
            selected.append(a)
            selected_symbols.add(a['symbol'])
            count += 1

    if count > 0:
        print(f"   ✓ Filled {count} spots with high volume symbols")

    print(f"\n   📊 Total selected: {len(selected)} symbols")

    # Print beta summary
    betas = [a.get('btc_beta', 0) for a in selected if a.get('btc_beta') is not None]
    if betas:
        print(f"   📈 Beta range: {min(betas):.2f}x to {max(betas):.2f}x")
        print(f"   🔥 Extreme (>5x): {len([b for b in betas if b > 5.0])} symbols")
        print(f"   ❄️  Inverse (<-2x): {len([b for b in betas if b < -2.0])} symbols")

    return selected


if __name__ == "__main__":
    HOURS = 4  # Number of hours of historical data
    TOP_SYMBOLS = 30  # Number of top symbols to show

    print(f"\n🚀 Generating Bitcoin Relative Performance Chart ({HOURS}H - Bybit Only)...\n")
    print("⏳ Fetching data from Bybit...\n")

    # Fetch Bybit-only data
    symbol_data = fetch_symbol_data_from_bybit_only()

    print(f"\n✅ Collected data for {len(symbol_data)} symbols from Bybit\n")

    # Get BTC price change for beta calculation
    btc_data = symbol_data.get('BTC', [])
    btc_price_change = None
    if btc_data:
        btc_changes = [d.get('price_change_pct') for d in btc_data if d.get('price_change_pct') is not None]
        if btc_changes:
            btc_price_change = sum(btc_changes) / len(btc_changes)
            print(f"📊 BTC 24h change: {btc_price_change:+.2f}% (using for beta calculation)\n")

    # Analyze symbols
    print("🔍 Analyzing symbols...")
    analyses = []
    for symbol, data in symbol_data.items():
        analysis = analyze_symbol(symbol, data, btc_price_change=btc_price_change)
        if analysis:
            analyses.append(analysis)

    print(f"   ✓ Analyzed {len(analyses)} symbols\n")

    # Use Option F: Liquid Extremes selection
    print(f"🎯 Selecting symbols using LIQUID EXTREMES method (Option F)...\n")
    selected_analyses = select_liquid_extremes(analyses, limit=TOP_SYMBOLS)

    # Get symbol list for historical data fetching
    selected_symbols = [a['symbol'] for a in selected_analyses]

    # Fetch historical data for selected symbols
    print(f"\n📈 Fetching {HOURS}h historical price data for {len(selected_symbols)} selected symbols...\n")
    historical_data = fetch_historical_data_for_symbols(selected_symbols, hours=HOURS)
    print(f"\n✅ Fetched historical data for {len(historical_data)} symbols\n")

    # Generate HTML
    print(f"🎨 Generating {HOURS}h time series dashboard (Bybit data)...\n")
    html_content = generate_timeseries_html(analyses, btc_price_change, historical_data, hours=HOURS)

    # Save HTML
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

    # Get project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')

    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)

    filename = os.path.join(data_dir, f"bitcoin_relative_performance_{HOURS}h_bybit_{timestamp}.html")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Bitcoin Relative Performance ({HOURS}H) saved to: {filename}")
        print(f"\n🌐 Open in browser to view the {HOURS}-hour relative performance chart!")

        # Try to open in browser
        import webbrowser
        filepath = os.path.abspath(filename)
        webbrowser.open('file://' + filepath)
        print(f"🔥 Opening in browser...")

    except Exception as e:
        print(f"⚠️  Could not save HTML: {e}")
