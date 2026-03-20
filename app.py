#!/usr/bin/env python3
"""
Crypto Perps Dashboard - Real-Time Market Intelligence
Main Dash application with auto-refresh and live data
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import existing Container architecture
from src.models.config import Config
from src.container import Container

# Import dashboard analytics (optimized with caching)
from dashboard.utils.analytics_optimized import (
    get_symbol_analytics,
    get_market_summary,
    get_arbitrage_opportunities,
    get_funding_extremes,
    get_performance_chart_plotly
)
import base64
import io

# Initialize Dash app with dark theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

# Expose Flask server for Gunicorn
server = app.server

# Initialize Container for data fetching
config = Config.from_yaml('config/config.yaml')
container = Container(config)

# Custom CSS for dark orange/gold theme
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Crypto Perps Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
                font-family: 'Courier New', monospace;
                color: #FFD700;
            }
            .dash-graph {
                background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
                border: 3px solid #FFA500;
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 0 30px rgba(255, 165, 0, 0.3);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# App Layout
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.Div([
                html.H1('🚀 Crypto Perps Dashboard',
                       style={'color': '#FFA500', 'textShadow': '0 0 30px rgba(255, 165, 0, 1)'}),
                html.Div([
                    html.Span('●', style={'color': '#00ff00', 'animation': 'pulse 2s infinite'}),
                    html.Span(' Live Market Intelligence', style={'color': '#FDB44B', 'marginLeft': '8px'})
                ])
            ]),
            html.Div(id='header-stats', style={
                'display': 'flex',
                'gap': '30px',
                'alignItems': 'center'
            })
        ], style={
            'maxWidth': '1800px',
            'margin': '0 auto',
            'display': 'flex',
            'justifyContent': 'space-between',
            'alignItems': 'center'
        })
    ], style={
        'background': 'linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%)',
        'borderBottom': '3px solid #FFA500',
        'padding': '20px 40px',
        'boxShadow': '0 0 40px rgba(255, 165, 0, 0.4)',
        'position': 'sticky',
        'top': '0',
        'zIndex': '1000'
    }),

    # Navigation Tabs
    html.Div([
        dcc.Tabs(
            id='tabs',
            value='market-overview',
            children=[
                dcc.Tab(label='📊 Market Overview', value='market-overview',
                       style={'background': '#1a1a1a', 'border': '2px solid #FFA500', 'color': '#FDB44B'},
                       selected_style={'background': '#2a2a2a', 'color': '#FFA500', 'borderBottom': '3px solid #FFA500'}),
                dcc.Tab(label='📈 Symbol Analysis', value='symbol-analysis',
                       style={'background': '#1a1a1a', 'border': '2px solid #FFA500', 'color': '#FDB44B'},
                       selected_style={'background': '#2a2a2a', 'color': '#FFA500', 'borderBottom': '3px solid #FFA500'}),
                dcc.Tab(label='💎 Arbitrage Scanner', value='arbitrage',
                       style={'background': '#1a1a1a', 'border': '2px solid #FFA500', 'color': '#FDB44B'},
                       selected_style={'background': '#2a2a2a', 'color': '#FFA500', 'borderBottom': '3px solid #FFA500'}),
                dcc.Tab(label='⚡ Strategy Alerts', value='alerts',
                       style={'background': '#1a1a1a', 'border': '2px solid #FFA500', 'color': '#FDB44B'},
                       selected_style={'background': '#2a2a2a', 'color': '#FFA500', 'borderBottom': '3px solid #FFA500'}),
            ],
            style={'maxWidth': '1800px', 'margin': '0 auto', 'padding': '20px 40px 0'}
        )
    ]),

    # Main Content with Loading Spinner
    dcc.Loading(
        id="loading-content",
        type="cube",
        color="#FFA500",
        children=html.Div(id='tab-content', style={
            'maxWidth': '1800px',
            'margin': '0 auto',
            'padding': '25px 40px'
        })
    ),

    # Auto-refresh interval (120 seconds)
    dcc.Interval(
        id='interval-component',
        interval=120*1000,  # 120 seconds in milliseconds
        n_intervals=0
    ),

    # Footer
    html.Div([
        html.Div('Powered by Virtuoso Crypto • virtuosocrypto.com', style={'marginBottom': '10px'}),
        html.Div(id='update-time', style={'color': '#FFA500', 'fontWeight': 'bold'})
    ], style={
        'textAlign': 'center',
        'padding': '30px',
        'color': '#FDB44B',
        'fontSize': '0.9em',
        'borderTop': '2px solid #FFA500',
        'marginTop': '40px'
    })
])

# Callbacks

@app.callback(
    Output('header-stats', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_header_stats(n):
    """Update header statistics"""
    try:
        # Fetch real market data
        markets = container.exchange_service.fetch_all_markets()

        # All returned MarketData objects are successful
        total_volume = sum(m.volume_24h for m in markets)
        total_oi = sum(m.open_interest or 0 for m in markets)

        return [
            html.Div([
                html.Div('Total Volume', style={'fontSize': '0.8em', 'color': '#FDB44B'}),
                html.Div(f'${total_volume/1e9:.1f}B', style={'fontSize': '1.3em', 'fontWeight': 'bold'})
            ]),
            html.Div([
                html.Div('Total OI', style={'fontSize': '0.8em', 'color': '#FDB44B'}),
                html.Div(f'${total_oi/1e9:.1f}B', style={'fontSize': '1.3em', 'fontWeight': 'bold'})
            ]),
            html.Div([
                html.Div('Active Exchanges', style={'fontSize': '0.8em', 'color': '#FDB44B'}),
                html.Div(str(len(markets)), style={'fontSize': '1.3em', 'fontWeight': 'bold'})
            ])
        ]
    except Exception as e:
        print(f"Error updating header stats: {e}")
        return [html.Div(f"Error: {str(e)}", style={'color': '#ff6b6b'})]

@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value'),
     Input('interval-component', 'n_intervals')]
)
def render_content(tab, n):
    """Render tab content with live data"""

    if tab == 'market-overview':
        try:
            # Fetch market data
            markets = container.exchange_service.fetch_all_markets()

            # Create funding rate chart (all returned markets are successful)
            exchanges = [m.exchange for m in markets]
            funding_rates = [(m.funding_rate or 0) * 100 for m in markets]  # Convert to percentage

            funding_fig = go.Figure([
                go.Bar(
                    x=exchanges,
                    y=funding_rates,
                    marker={'color': ['#FFA500'] * len(exchanges), 'line': {'color': '#FFD700', 'width': 2}}
                )
            ])

            funding_fig.update_layout(
                title='',
                paper_bgcolor='#0a0a0a',
                plot_bgcolor='#1a1a1a',
                font={'color': '#FFD700', 'family': 'Courier New'},
                xaxis={'gridcolor': '#333333'},
                yaxis={'title': 'Funding Rate (%)', 'gridcolor': '#333333'},
                showlegend=False,
                height=500
            )

            # Create market dominance chart
            volumes = [m.volume_24h for m in markets]
            total_vol = sum(volumes)
            percentages = [(v/total_vol)*100 for v in volumes]

            dominance_fig = go.Figure([
                go.Pie(
                    labels=exchanges,
                    values=percentages,
                    marker={'colors': ['#FF6B35', '#FFA500', '#FDB44B', '#FFD700', '#FF9F40', '#FFC966', '#FFAA00', '#FF8C00', '#FFA07A', '#FFB347', '#FFC36E']},
                    textinfo='label+percent',
                    textfont={'color': '#0a0a0a', 'size': 14, 'family': 'Courier New'}
                )
            ])

            dominance_fig.update_layout(
                title='',
                paper_bgcolor='#0a0a0a',
                font={'color': '#FFD700', 'family': 'Courier New'},
                showlegend=True,
                legend={'font': {'color': '#FFD700'}},
                height=500
            )

            return html.Div([
                html.Div([
                    html.H3('⚡ Funding Rates by Exchange',
                           style={'color': '#FFA500', 'textAlign': 'center', 'marginBottom': '15px'}),
                    dcc.Graph(figure=funding_fig)
                ], className='dash-graph', style={'marginBottom': '25px'}),

                html.Div([
                    html.H3('🥧 Market Dominance (24h Volume)',
                           style={'color': '#FFA500', 'textAlign': 'center', 'marginBottom': '15px'}),
                    dcc.Graph(figure=dominance_fig)
                ], className='dash-graph')
            ])

        except Exception as e:
            return html.Div(f"Error loading market data: {str(e)}", style={'color': '#ff6b6b'})

    elif tab == 'symbol-analysis':
        try:
            # Get comprehensive symbol analytics (reduced to 8 for much faster loading)
            # Performance chart disabled by default - too slow
            analyses = get_symbol_analytics(container, top_n=8)
            summary = get_market_summary(analyses)
            arb_opps = get_arbitrage_opportunities(analyses, min_spread=0.2)

            # Executive Summary
            exec_summary = html.Div([
                html.H3('📊 TOKEN ANALYTICS INTEL', style={'color': '#FFA500', 'textAlign': 'center'}),
                html.P(f'Cross-Exchange Analysis • {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}',
                       style={'color': '#FDB44B', 'textAlign': 'center', 'fontSize': '0.9em', 'marginBottom': '20px'}),
                html.Div([
                    html.Div([
                        html.Div('Symbols Tracked', style={'fontSize': '0.8em', 'color': '#FDB44B'}),
                        html.Div(f'{summary.get("total_symbols", 0)}', style={'fontSize': '1.5em', 'fontWeight': 'bold', 'color': '#FFD700'})
                    ], style={'flex': '1', 'textAlign': 'center'}),
                    html.Div([
                        html.Div('Market Volume', style={'fontSize': '0.8em', 'color': '#FDB44B'}),
                        html.Div(f'${summary.get("total_volume_24h", 0)/1e9:.1f}B', style={'fontSize': '1.5em', 'fontWeight': 'bold', 'color': '#FFD700'})
                    ], style={'flex': '1', 'textAlign': 'center'}),
                    html.Div([
                        html.Div('Open Interest', style={'fontSize': '0.8em', 'color': '#FDB44B'}),
                        html.Div(f'${summary.get("total_open_interest", 0)/1e9:.1f}B', style={'fontSize': '1.5em', 'fontWeight': 'bold', 'color': '#FFD700'})
                    ], style={'flex': '1', 'textAlign': 'center'}),
                    html.Div([
                        html.Div('Exchanges', style={'fontSize': '0.8em', 'color': '#FDB44B'}),
                        html.Div(f'{summary.get("num_exchanges", 0)}', style={'fontSize': '1.5em', 'fontWeight': 'bold', 'color': '#FFD700'})
                    ], style={'flex': '1', 'textAlign': 'center'}),
                ], style={'display': 'flex', 'gap': '30px', 'justifyContent': 'space-around', 'marginTop': '20px'})
            ], style={'marginBottom': '30px'})

            # Top Symbols Table
            symbols_table_data = []
            for i, a in enumerate(analyses[:10], 1):
                volume_str = f"${a['total_volume_24h']/1e9:.2f}B" if a['total_volume_24h'] > 1e9 else f"${a['total_volume_24h']/1e6:.0f}M"
                oi_str = f"${a['total_open_interest']/1e9:.2f}B" if a['total_open_interest'] > 1e9 else f"${a['total_open_interest']/1e6:.0f}M"
                funding_str = f"{a['avg_funding_rate']:.3f}%" if a.get('avg_funding_rate') is not None else "N/A"
                change_str = f"{a['avg_price_change_24h']:+.1f}%" if a.get('avg_price_change_24h') is not None else "N/A"
                change_color = '#00ff88' if a.get('avg_price_change_24h', 0) > 0 else '#ff6b6b'
                beta_str = f"{a['btc_beta']:.2f}" if a.get('btc_beta') is not None else "N/A"

                symbols_table_data.append(html.Tr([
                    html.Td(f"#{i}", style={'color': '#FDB44B'}),
                    html.Td(a['symbol'], style={'color': '#FFD700', 'fontWeight': 'bold'}),
                    html.Td(volume_str, style={'color': '#FDB44B'}),
                    html.Td(oi_str, style={'color': '#FDB44B'}),
                    html.Td(f"{a['num_exchanges']}x", style={'color': '#FFA500'}),
                    html.Td(f"${a['avg_price']:,.2f}", style={'color': '#FFD700'}),
                    html.Td(f"{a['price_spread_pct']:.2f}%", style={'color': '#FFA500'}),
                    html.Td(funding_str, style={'color': '#FFA500'}),
                    html.Td(change_str, style={'color': change_color, 'fontWeight': 'bold'}),
                    html.Td(beta_str, style={'color': '#FFD700'})
                ]))

            symbols_table = html.Table([
                html.Thead(html.Tr([
                    html.Th('#', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('Symbol', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('Volume 24h', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('OI', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('Exchanges', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('Avg Price', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('Spread', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('Funding', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('24h Δ', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'}),
                    html.Th('BTC β', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '10px', 'border': '1px solid #FFA500'})
                ])),
                html.Tbody(symbols_table_data)
            ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '0.9em'})

            # Create charts
            # 1. Bitcoin Beta Chart (show all available)
            beta_analyses = [a for a in analyses if a.get('btc_beta') is not None]
            if beta_analyses:
                beta_symbols = [a['symbol'] for a in beta_analyses]
                beta_values = [a['btc_beta'] for a in beta_analyses]
                beta_colors = ['#00ff88' if b > 0 else '#ff6b6b' for b in beta_values]

                beta_fig = go.Figure([
                    go.Bar(
                        x=beta_values,
                        y=beta_symbols,
                        orientation='h',
                        marker={'color': beta_colors, 'line': {'color': '#FFD700', 'width': 1}},
                        text=[f"{b:.2f}" for b in beta_values],
                        textposition='outside'
                    )
                ])
                beta_fig.update_layout(
                    title='Bitcoin Beta (β) - Correlation to BTC Price Movement',
                    paper_bgcolor='#0a0a0a',
                    plot_bgcolor='#1a1a1a',
                    font={'color': '#FFD700', 'family': 'Courier New'},
                    xaxis={'title': 'Beta Coefficient', 'gridcolor': '#333333'},
                    yaxis={'gridcolor': '#333333'},
                    height=500,
                    margin={'l': 80, 'r': 80, 't': 50, 'b': 50}
                )
                beta_chart = dcc.Graph(figure=beta_fig, config={'displayModeBar': False})
            else:
                beta_chart = html.Div()

            # 2. Volume Comparison Chart (show all available)
            vol_symbols = [a['symbol'] for a in analyses]
            vol_values = [a['total_volume_24h']/1e9 for a in analyses]

            vol_fig = go.Figure([
                go.Bar(
                    x=vol_symbols,
                    y=vol_values,
                    marker={'color': '#FFA500', 'line': {'color': '#FFD700', 'width': 2}},
                    text=[f"${v:.1f}B" for v in vol_values],
                    textposition='outside'
                )
            ])
            vol_fig.update_layout(
                title=f'Top {len(analyses)} Symbols by 24h Volume',
                paper_bgcolor='#0a0a0a',
                plot_bgcolor='#1a1a1a',
                font={'color': '#FFD700', 'family': 'Courier New'},
                xaxis={'title': 'Symbol', 'gridcolor': '#333333'},
                yaxis={'title': 'Volume (Billions USD)', 'gridcolor': '#333333'},
                height=400,
                showlegend=False
            )
            vol_chart = dcc.Graph(figure=vol_fig, config={'displayModeBar': False})

            # 3. Funding Rate Chart (show all available)
            funding_analyses = [a for a in analyses if a.get('avg_funding_rate') is not None]
            if funding_analyses:
                funding_symbols = [a['symbol'] for a in funding_analyses]
                funding_rates = [a['avg_funding_rate'] for a in funding_analyses]
                funding_colors = ['#ff6b6b' if f > 0 else '#00ff88' for f in funding_rates]

                funding_fig = go.Figure([
                    go.Bar(
                        x=funding_symbols,
                        y=funding_rates,
                        marker={'color': funding_colors, 'line': {'color': '#FFD700', 'width': 1}},
                        text=[f"{f:.4f}%" for f in funding_rates],
                        textposition='outside'
                    )
                ])
                funding_fig.update_layout(
                    title='Average Funding Rates Across Exchanges',
                    paper_bgcolor='#0a0a0a',
                    plot_bgcolor='#1a1a1a',
                    font={'color': '#FFD700', 'family': 'Courier New'},
                    xaxis={'title': 'Symbol', 'gridcolor': '#333333'},
                    yaxis={'title': 'Funding Rate (%)', 'gridcolor': '#333333'},
                    height=400,
                    showlegend=False
                )
                funding_chart = dcc.Graph(figure=funding_fig, config={'displayModeBar': False})
            else:
                funding_chart = html.Div()

            # Arbitrage Opportunities Section
            arb_section = html.Div([
                html.H4(f'💰 Arbitrage Opportunities ({len(arb_opps)})', style={'color': '#FFA500', 'marginTop': '30px'}),
                html.P('Price spreads > 0.2%', style={'color': '#FDB44B', 'fontSize': '0.9em'}),
                html.Div([
                    html.Div([
                        html.Strong(a['symbol'], style={'color': '#FFD700'}),
                        html.Span(f" • {a['price_spread_pct']:.2f}% spread", style={'color': '#00ff88'}),
                        html.Br(),
                        html.Span(f"Buy {a['arbitrage_opportunity']['buy']} @ ${a['arbitrage_opportunity']['buy_price']:,.2f} → ", style={'color': '#FDB44B', 'fontSize': '0.85em'}),
                        html.Span(f"Sell {a['arbitrage_opportunity']['sell']} @ ${a['arbitrage_opportunity']['sell_price']:,.2f}", style={'color': '#FDB44B', 'fontSize': '0.85em'})
                    ], style={'padding': '8px', 'marginBottom': '8px', 'borderLeft': '3px solid #FFA500', 'backgroundColor': 'rgba(255, 165, 0, 0.05)'})
                    for a in arb_opps[:5]
                ])
            ]) if arb_opps else html.Div()

            # PERFORMANCE CHART - Now with database caching (Phase 3)
            try:
                chart_data = get_performance_chart_plotly(container, analyses, top_n=20)
                if chart_data:
                    # Create Plotly figure
                    fig = go.Figure()

                    # Add all traces
                    for trace in chart_data['traces']:
                        fig.add_trace(go.Scatter(
                            x=trace['x'],
                            y=trace['y'],
                            mode=trace['mode'],
                            name=trace['name'],
                            line=trace['line'],
                            hovertemplate=trace['hovertemplate']
                        ))

                    # Update layout with dark theme
                    fig.update_layout(
                        title={
                            'text': f"CRYPTO PERFORMANCE TRACKER<br><sub>12h Returns | {chart_data['outperformers']} Outperformers • {chart_data['underperformers']} Underperformers<br>Generated: {chart_data['current_time']}</sub>",
                            'x': 0.5,
                            'xanchor': 'center',
                            'font': {'size': 16, 'color': '#FFA500', 'family': 'Arial Black'}
                        },
                        xaxis={
                            'title': 'Time (12h Period)',
                            'titlefont': {'color': '#FFD700', 'size': 12},
                            'tickfont': {'color': '#FFD700', 'size': 10},
                            'gridcolor': 'rgba(255, 215, 0, 0.08)',
                            'showgrid': True
                        },
                        yaxis={
                            'title': 'Price Change (%)',
                            'titlefont': {'color': '#FFD700', 'size': 12},
                            'tickfont': {'color': '#FFD700', 'size': 10},
                            'gridcolor': 'rgba(255, 215, 0, 0.08)',
                            'showgrid': True,
                            'zeroline': True,
                            'zerolinecolor': '#888888',
                            'zerolinewidth': 2
                        },
                        plot_bgcolor='#0a0a0a',
                        paper_bgcolor='#0a0a0a',
                        font={'color': '#FFD700'},
                        hovermode='x unified',
                        showlegend=True,
                        legend={
                            'font': {'size': 9, 'color': '#FFD700'},
                            'bgcolor': 'rgba(26, 26, 26, 0.95)',
                            'bordercolor': '#FFA500',
                            'borderwidth': 2,
                            'orientation': 'v',
                            'yanchor': 'middle',
                            'y': 0.5,
                            'xanchor': 'left',
                            'x': 1.01
                        },
                        height=600,
                        margin={'l': 50, 'r': 150, 't': 100, 'b': 50}
                    )

                    performance_chart_section = html.Div([
                        html.H3('🚀 12-Hour Performance Tracker',
                               style={'color': '#FFA500', 'textAlign': 'center', 'marginBottom': '15px'}),
                        html.P('📊 Database-cached for instant loading • Hover for details • Zoom/Pan • Click legend to toggle • Auto-refresh: 10min',
                               style={'color': '#FDB44B', 'textAlign': 'center', 'fontSize': '0.9em', 'marginBottom': '20px'}),
                        dcc.Graph(
                            figure=fig,
                            config={'displayModeBar': True, 'displaylogo': False},
                            style={'border': '2px solid #FFA500', 'borderRadius': '8px'}
                        )
                    ], className='dash-graph', style={'marginBottom': '30px'})
                else:
                    performance_chart_section = html.Div([
                        html.H3('⏳ Building Performance History',
                               style={'color': '#FFA500', 'textAlign': 'center'}),
                        html.P('Historical data logger is collecting snapshots. Chart will appear after 1 hour of data.',
                              style={'color': '#FDB44B', 'textAlign': 'center', 'fontSize': '0.9em'})
                    ], className='dash-graph', style={'padding': '30px', 'marginBottom': '30px'})
            except Exception as e:
                print(f"⚠️  Could not generate performance chart: {e}")
                import traceback
                traceback.print_exc()
                performance_chart_section = html.Div([
                    html.H3('❌ Performance Chart Error',
                           style={'color': '#FF6B6B', 'textAlign': 'center'}),
                    html.P(f'Error: {str(e)}',
                          style={'color': '#FDB44B', 'textAlign': 'center', 'fontSize': '0.9em'})
                ], className='dash-graph', style={'padding': '30px', 'marginBottom': '30px'})

            return html.Div([
                performance_chart_section,  # Performance tracker at the top

                html.Div([
                    exec_summary,
                    html.H4('📈 Top Symbols by Volume', style={'color': '#FFA500', 'marginBottom': '15px'}),
                    symbols_table,
                ], className='dash-graph'),

                html.Div([vol_chart], className='dash-graph', style={'marginTop': '20px'}),

                html.Div([beta_chart], className='dash-graph', style={'marginTop': '20px'}),

                html.Div([funding_chart], className='dash-graph', style={'marginTop': '20px'}),

                html.Div([arb_section], className='dash-graph', style={'marginTop': '20px'})
            ])

        except Exception as e:
            import traceback
            return html.Div([
                html.P(f"Error loading symbol data: {str(e)}", style={'color': '#ff6b6b'}),
                html.Pre(traceback.format_exc(), style={'color': '#ff6b6b', 'fontSize': '0.8em'})
            ])

    elif tab == 'arbitrage':
        try:
            # Fetch market data to show exchange comparison
            markets = container.exchange_service.fetch_all_markets()

            # For now, show exchanges by market count and volume
            # (Real arbitrage requires per-symbol price data across exchanges)
            table_data = []
            for m in markets:
                table_data.append(html.Tr([
                    html.Td(m.exchange, style={'color': '#FFD700'}),
                    html.Td(f"${m.volume_24h/1e9:.2f}B", style={'color': '#FDB44B'}),
                    html.Td(f"{m.market_count or 0}", style={'color': '#FFA500'}),
                    html.Td(f"{(m.funding_rate or 0)*100:.4f}%", style={'color': '#FFD700'})
                ]))

            table = html.Table([
                html.Thead(html.Tr([
                    html.Th('Exchange', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'}),
                    html.Th('Volume 24h', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'}),
                    html.Th('Markets', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'}),
                    html.Th('Avg Funding', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'})
                ])),
                html.Tbody(table_data)
            ], style={'width': '100%', 'borderCollapse': 'collapse', 'marginTop': '15px'})

            return html.Div([
                html.Div([
                    html.H3('💎 Exchange Comparison', style={'color': '#FFA500', 'textAlign': 'center', 'marginBottom': '15px'}),
                    html.P(f'Comparing {len(markets)} exchanges by volume and markets', style={'color': '#FDB44B', 'textAlign': 'center', 'marginBottom': '20px'}),
                    table
                ], className='dash-graph')
            ])

        except Exception as e:
            return html.Div(f"Error loading arbitrage data: {str(e)}", style={'color': '#ff6b6b'})

    elif tab == 'alerts':
        try:
            import sqlite3
            import os

            # Check if alert database exists
            db_path = 'data/alert_state.db'
            if not os.path.exists(db_path):
                return html.Div([
                    html.Div([
                        html.H3('⚡ Strategy Alerts', style={'color': '#FFA500', 'textAlign': 'center'}),
                        html.P('No alert database found. Alerts will appear here once the strategy alert system runs.',
                              style={'color': '#FDB44B', 'textAlign': 'center', 'marginTop': '20px'})
                    ], className='dash-graph')
                ])

            # Read recent alerts from SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get table schema first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            if not tables:
                conn.close()
                return html.Div([
                    html.Div([
                        html.H3('⚡ Strategy Alerts', style={'color': '#FFA500', 'textAlign': 'center'}),
                        html.P('Alert database is empty. Waiting for first alert...',
                              style={'color': '#FDB44B', 'textAlign': 'center', 'marginTop': '20px'})
                    ], className='dash-graph')
                ])

            # Try to get recent alerts
            try:
                cursor.execute("""
                    SELECT timestamp, strategy, symbol, confidence, tier
                    FROM alerts
                    ORDER BY timestamp DESC
                    LIMIT 10
                """)
                alerts = cursor.fetchall()
            except sqlite3.OperationalError:
                # Table might not exist or have different schema
                conn.close()
                return html.Div([
                    html.Div([
                        html.H3('⚡ Strategy Alerts', style={'color': '#FFA500', 'textAlign': 'center'}),
                        html.P('Alert system is initializing...',
                              style={'color': '#FDB44B', 'textAlign': 'center', 'marginTop': '20px'})
                    ], className='dash-graph')
                ])

            conn.close()

            if not alerts:
                return html.Div([
                    html.Div([
                        html.H3('⚡ Strategy Alerts', style={'color': '#FFA500', 'textAlign': 'center'}),
                        html.P('No alerts yet. System is monitoring...',
                              style={'color': '#FDB44B', 'textAlign': 'center', 'marginTop': '20px'})
                    ], className='dash-graph')
                ])

            # Create alert table
            table_data = []
            for alert in alerts:
                timestamp, strategy, symbol, confidence, tier = alert
                tier_badge_style = {
                    'display': 'inline-block',
                    'padding': '5px 12px',
                    'borderRadius': '5px',
                    'fontSize': '0.9em',
                    'fontWeight': 'bold',
                    'background': 'rgba(255, 107, 53, 0.3)' if tier == 1 else 'rgba(255, 165, 0, 0.3)',
                    'border': f"1px solid {'#FF6B35' if tier == 1 else '#FFA500'}",
                    'color': '#FF6B35' if tier == 1 else '#FFA500'
                }

                table_data.append(html.Tr([
                    html.Td(timestamp, style={'color': '#FDB44B'}),
                    html.Td(strategy, style={'color': '#FFD700'}),
                    html.Td(symbol or 'N/A', style={'color': '#FFD700'}),
                    html.Td(html.Span(f'TIER {tier}', style=tier_badge_style)),
                    html.Td(f'{confidence}%', style={'color': '#00ff88', 'fontWeight': 'bold'})
                ]))

            table = html.Table([
                html.Thead(html.Tr([
                    html.Th('Time', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'}),
                    html.Th('Strategy', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'}),
                    html.Th('Symbol', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'}),
                    html.Th('Tier', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'}),
                    html.Th('Confidence', style={'background': 'rgba(255, 165, 0, 0.2)', 'color': '#FFA500', 'padding': '12px', 'border': '1px solid #FFA500'})
                ])),
                html.Tbody(table_data)
            ], style={'width': '100%', 'borderCollapse': 'collapse', 'marginTop': '15px'})

            return html.Div([
                html.Div([
                    html.H3('⚡ Recent Strategy Alerts', style={'color': '#FFA500', 'textAlign': 'center', 'marginBottom': '15px'}),
                    html.P(f'Showing last {len(alerts)} alerts', style={'color': '#FDB44B', 'textAlign': 'center', 'marginBottom': '20px'}),
                    table
                ], className='dash-graph')
            ])

        except Exception as e:
            return html.Div(f"Error loading alerts: {str(e)}", style={'color': '#ff6b6b'})

@app.callback(
    Output('update-time', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_time(n):
    """Update last refresh time"""
    now = datetime.now(timezone.utc)
    # Calculate seconds until next 2-minute interval
    next_refresh = 120 - (now.second + (now.minute % 2) * 60)
    return [
        html.Span('● ', style={'color': '#00ff00'}),
        f"Last Update: {now.strftime('%b %d, %H:%M:%S UTC')} • Auto-refresh in {next_refresh}s"
    ]

if __name__ == '__main__':
    import os

    print("\n🚀 Starting Crypto Perps Dashboard...")
    print("📊 Access at: http://localhost:8050")
    print("⏱️  Auto-refresh: 120 seconds")
    print("\nPress Ctrl+C to stop\n")

    # Use debug mode only in development
    debug_mode = os.getenv('DASH_DEBUG', 'false').lower() == 'true'

    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=8050
    )
