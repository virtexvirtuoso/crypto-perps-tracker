"""Market analysis modules

Provides comprehensive market analysis including:
- Sentiment analysis (funding rates, price momentum, long/short ratios)
- Arbitrage opportunity identification
- Market dominance and concentration metrics
- Spot-futures basis analysis
- Sector rotation (multi-exchange perp and CoinGecko spot)
"""

from src.analysis.sentiment import analyze_market_sentiment, fetch_long_short_ratio
from src.analysis.arbitrage import (
    identify_arbitrage_opportunities,
    analyze_trading_behavior,
    detect_anomalies
)
from src.analysis.dominance import calculate_market_dominance
from src.analysis.basis import analyze_basis_metrics, fetch_spot_and_futures_basis

# Sector rotation modules (import submodules directly)
from src.analysis import sector_rotation
from src.analysis import spot_rotation

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
    # Sector rotation
    'sector_rotation',
    'spot_rotation',
]
