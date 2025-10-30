"""Market analysis modules

Provides comprehensive market analysis including:
- Sentiment analysis (funding rates, price momentum, long/short ratios)
- Arbitrage opportunity identification
- Market dominance and concentration metrics
- Spot-futures basis analysis
"""

from src.analysis.sentiment import analyze_market_sentiment, fetch_long_short_ratio
from src.analysis.arbitrage import (
    identify_arbitrage_opportunities,
    analyze_trading_behavior,
    detect_anomalies
)
from src.analysis.dominance import calculate_market_dominance
from src.analysis.basis import analyze_basis_metrics, fetch_spot_and_futures_basis

__all__ = [
    # Sentiment
    'analyze_market_sentiment',
    'fetch_long_short_ratio',
    # Arbitrage
    'identify_arbitrage_opportunities',
    'analyze_trading_behavior',
    'detect_anomalies',
    # Dominance
    'calculate_market_dominance',
    # Basis
    'analyze_basis_metrics',
    'fetch_spot_and_futures_basis',
]
