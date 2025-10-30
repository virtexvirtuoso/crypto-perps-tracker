"""Market analysis service

This service provides market analysis functionality including:
- Market sentiment calculation
- Funding rate analysis
- Volume anomaly detection
- OI/Volume ratio analysis
"""

from typing import Dict, List, Optional
from enum import Enum
from src.services.exchange import ExchangeService
from src.models.market import MarketData


class MarketSentiment(str, Enum):
    """Market sentiment classifications"""
    EXTREME_BULLISH = "extreme_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    EXTREME_BEARISH = "extreme_bearish"


class AnalysisService:
    """Service for market analysis and sentiment calculation

    This service analyzes market data from multiple exchanges to:
    - Calculate aggregate market sentiment
    - Detect anomalies and opportunities
    - Identify arbitrage opportunities
    - Score market conditions

    Usage:
        analysis_service = AnalysisService(exchange_service)
        sentiment = analysis_service.calculate_market_sentiment()
        anomalies = analysis_service.detect_volume_anomalies()
    """

    def __init__(self, exchange_service: ExchangeService):
        """Initialize analysis service

        Args:
            exchange_service: ExchangeService instance for fetching market data
        """
        self.exchange_service = exchange_service

    def calculate_market_sentiment(self, use_cache: bool = True) -> Dict:
        """Calculate overall market sentiment based on funding rates

        Analyzes funding rates across all exchanges to determine if the
        market is bullish (longs paying shorts) or bearish (shorts paying longs).

        Args:
            use_cache: Whether to use cached exchange data

        Returns:
            Dictionary with sentiment analysis:
            {
                'sentiment': MarketSentiment enum,
                'score': float (-1 to 1, negative=bearish, positive=bullish),
                'avg_funding_rate': float,
                'bullish_exchanges': int,
                'bearish_exchanges': int,
                'exchanges': List of exchange sentiment details
            }

        Example:
            >>> sentiment = service.calculate_market_sentiment()
            >>> print(f"Market is {sentiment['sentiment']}")
            >>> print(f"Score: {sentiment['score']:.2f}")
        """
        markets = self.exchange_service.fetch_all_markets(use_cache=use_cache)

        # Filter markets with funding rate data
        markets_with_funding = [
            m for m in markets
            if m.funding_rate is not None
        ]

        if not markets_with_funding:
            return {
                'sentiment': MarketSentiment.NEUTRAL,
                'score': 0.0,
                'avg_funding_rate': 0.0,
                'bullish_exchanges': 0,
                'bearish_exchanges': 0,
                'exchanges': []
            }

        # Calculate average funding rate
        avg_funding = sum(m.funding_rate for m in markets_with_funding) / len(markets_with_funding)

        # Count bullish/bearish exchanges
        bullish_count = sum(1 for m in markets_with_funding if m.funding_rate > 0.0001)
        bearish_count = sum(1 for m in markets_with_funding if m.funding_rate < -0.0001)

        # Calculate sentiment score (-1 to 1)
        # Based on average funding rate, scaled
        score = avg_funding * 1000  # Scale to reasonable range
        score = max(-1.0, min(1.0, score))  # Clamp to [-1, 1]

        # Determine sentiment classification
        if score > 0.5:
            sentiment = MarketSentiment.EXTREME_BULLISH
        elif score > 0.15:
            sentiment = MarketSentiment.BULLISH
        elif score < -0.5:
            sentiment = MarketSentiment.EXTREME_BEARISH
        elif score < -0.15:
            sentiment = MarketSentiment.BEARISH
        else:
            sentiment = MarketSentiment.NEUTRAL

        # Build exchange details
        exchange_details = []
        for market in markets_with_funding:
            exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)
            funding_pct = market.funding_rate * 100

            exchange_details.append({
                'exchange': exchange_name,
                'funding_rate': market.funding_rate,
                'funding_rate_pct': funding_pct,
                'sentiment': 'bullish' if market.funding_rate > 0.0001 else 'bearish' if market.funding_rate < -0.0001 else 'neutral'
            })

        return {
            'sentiment': sentiment,
            'score': score,
            'avg_funding_rate': avg_funding,
            'avg_funding_rate_pct': avg_funding * 100,
            'bullish_exchanges': bullish_count,
            'bearish_exchanges': bearish_count,
            'neutral_exchanges': len(markets_with_funding) - bullish_count - bearish_count,
            'total_exchanges': len(markets_with_funding),
            'exchanges': sorted(exchange_details, key=lambda x: x['funding_rate'], reverse=True)
        }

    def detect_volume_anomalies(
        self,
        threshold_multiplier: float = 2.0,
        use_cache: bool = True
    ) -> List[Dict]:
        """Detect exchanges with unusually high volume

        Identifies exchanges where 24h volume is significantly higher than
        the average, which may indicate increased market activity or
        specific trading opportunities.

        Args:
            threshold_multiplier: Volume must be this many times the average
            use_cache: Whether to use cached exchange data

        Returns:
            List of anomalies with exchange details

        Example:
            >>> anomalies = service.detect_volume_anomalies(threshold_multiplier=2.5)
            >>> for anomaly in anomalies:
            ...     print(f"{anomaly['exchange']}: {anomaly['volume_ratio']:.2f}x average")
        """
        markets = self.exchange_service.fetch_all_markets(use_cache=use_cache)

        if not markets:
            return []

        # Calculate average volume
        avg_volume = sum(m.volume_24h for m in markets) / len(markets)

        # Find anomalies
        anomalies = []
        for market in markets:
            volume_ratio = market.volume_24h / avg_volume if avg_volume > 0 else 0

            if volume_ratio >= threshold_multiplier:
                exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)

                anomalies.append({
                    'exchange': exchange_name,
                    'volume_24h': market.volume_24h,
                    'avg_volume': avg_volume,
                    'volume_ratio': volume_ratio,
                    'deviation_pct': (volume_ratio - 1.0) * 100
                })

        # Sort by volume ratio (highest first)
        return sorted(anomalies, key=lambda x: x['volume_ratio'], reverse=True)

    def analyze_oi_volume_ratios(self, use_cache: bool = True) -> Dict:
        """Analyze Open Interest to Volume ratios across exchanges

        The OI/Volume ratio indicates whether traders are:
        - High ratio: Holding positions (more conviction)
        - Low ratio: Day trading (less conviction)

        Args:
            use_cache: Whether to use cached exchange data

        Returns:
            Dictionary with OI/Volume analysis

        Example:
            >>> analysis = service.analyze_oi_volume_ratios()
            >>> print(f"Market average: {analysis['avg_ratio']:.2f}x")
        """
        markets = self.exchange_service.fetch_all_markets(use_cache=use_cache)

        # Filter markets with both OI and volume
        markets_with_oi = [
            m for m in markets
            if m.open_interest and m.volume_24h > 0
        ]

        if not markets_with_oi:
            return {
                'avg_ratio': 0.0,
                'total_oi': 0.0,
                'total_volume': 0.0,
                'exchanges': []
            }

        # Calculate ratios
        exchange_ratios = []
        total_oi = 0.0
        total_volume = 0.0

        for market in markets_with_oi:
            ratio = market.open_interest / market.volume_24h
            total_oi += market.open_interest
            total_volume += market.volume_24h

            exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)

            # Classify ratio
            if ratio > 2.0:
                classification = "very_high"  # Strong holding
                interpretation = "Strong position holding - high conviction"
            elif ratio > 1.0:
                classification = "high"  # Holding bias
                interpretation = "More holding than day trading"
            elif ratio > 0.5:
                classification = "moderate"  # Balanced
                interpretation = "Balanced holding and trading"
            else:
                classification = "low"  # Day trading bias
                interpretation = "Heavy day trading - low conviction"

            exchange_ratios.append({
                'exchange': exchange_name,
                'oi_volume_ratio': ratio,
                'open_interest': market.open_interest,
                'volume_24h': market.volume_24h,
                'classification': classification,
                'interpretation': interpretation
            })

        # Calculate market average
        avg_ratio = total_oi / total_volume if total_volume > 0 else 0.0

        return {
            'avg_ratio': avg_ratio,
            'total_oi': total_oi,
            'total_volume': total_volume,
            'exchanges': sorted(exchange_ratios, key=lambda x: x['oi_volume_ratio'], reverse=True)
        }

    def find_funding_arbitrage_opportunities(
        self,
        min_spread: float = 0.01,
        use_cache: bool = True
    ) -> List[Dict]:
        """Find potential funding rate arbitrage opportunities

        Identifies exchanges with significant funding rate differences,
        which could present arbitrage opportunities (long on low funding
        exchange, short on high funding exchange).

        Args:
            min_spread: Minimum funding rate spread (as percentage) to report
            use_cache: Whether to use cached exchange data

        Returns:
            List of arbitrage opportunities

        Example:
            >>> opportunities = service.find_funding_arbitrage_opportunities(min_spread=0.02)
            >>> for opp in opportunities:
            ...     print(f"Long {opp['long_exchange']}, Short {opp['short_exchange']}")
            ...     print(f"Spread: {opp['spread_pct']:.4f}%")
        """
        markets = self.exchange_service.fetch_all_markets(use_cache=use_cache)

        # Filter markets with funding rates
        markets_with_funding = [
            m for m in markets
            if m.funding_rate is not None
        ]

        if len(markets_with_funding) < 2:
            return []

        # Find opportunities
        opportunities = []

        for i, market_low in enumerate(markets_with_funding):
            for market_high in markets_with_funding[i+1:]:
                # Calculate spread
                spread = abs(market_high.funding_rate - market_low.funding_rate)
                spread_pct = spread * 100

                if spread_pct >= min_spread:
                    # Determine which is higher
                    if market_high.funding_rate > market_low.funding_rate:
                        long_market = market_low
                        short_market = market_high
                    else:
                        long_market = market_high
                        short_market = market_low

                    long_name = long_market.exchange.value if hasattr(long_market.exchange, 'value') else str(long_market.exchange)
                    short_name = short_market.exchange.value if hasattr(short_market.exchange, 'value') else str(short_market.exchange)

                    opportunities.append({
                        'long_exchange': long_name,
                        'short_exchange': short_name,
                        'long_funding_rate': long_market.funding_rate,
                        'short_funding_rate': short_market.funding_rate,
                        'spread': spread,
                        'spread_pct': spread_pct,
                        'annual_return_estimate': spread_pct * 365 * 3  # 3 funding periods per day
                    })

        # Sort by spread (highest first)
        return sorted(opportunities, key=lambda x: x['spread_pct'], reverse=True)

    def calculate_composite_score(self, use_cache: bool = True) -> Dict:
        """Calculate composite market health score

        Combines multiple metrics into a single score (0-100) indicating
        overall market health and activity.

        Factors considered:
        - Total volume (higher = better)
        - OI/Volume ratio (moderate = better)
        - Funding rate spread (lower = better, more efficient market)
        - Number of active exchanges

        Args:
            use_cache: Whether to use cached exchange data

        Returns:
            Dictionary with composite score and breakdown

        Example:
            >>> score = service.calculate_composite_score()
            >>> print(f"Market Health: {score['composite_score']:.1f}/100")
        """
        markets = self.exchange_service.fetch_all_markets(use_cache=use_cache)

        if not markets:
            return {'composite_score': 0.0, 'components': {}}

        # Component 1: Volume score (0-25 points)
        total_volume = sum(m.volume_24h for m in markets)
        # Score based on billions of volume (capped at $500B = 25 points)
        volume_score = min(25.0, (total_volume / 1e9) / 20)

        # Component 2: Market depth score (0-25 points)
        markets_with_oi = [m for m in markets if m.open_interest]
        if markets_with_oi:
            total_oi = sum(m.open_interest for m in markets_with_oi)
            avg_oi_volume = total_oi / total_volume if total_volume > 0 else 0
            # Optimal ratio is around 1.0, score decreases as we deviate
            oi_deviation = abs(avg_oi_volume - 1.0)
            depth_score = max(0, 25.0 - (oi_deviation * 25))
        else:
            depth_score = 0.0

        # Component 3: Market efficiency score (0-25 points)
        markets_with_funding = [m for m in markets if m.funding_rate is not None]
        if len(markets_with_funding) >= 2:
            funding_rates = [m.funding_rate for m in markets_with_funding]
            funding_spread = max(funding_rates) - min(funding_rates)
            # Lower spread = more efficient market
            # 0.01% spread = 25 points, 0.05% spread = 0 points
            efficiency_score = max(0, 25.0 - (funding_spread * 100 * 500))
        else:
            efficiency_score = 0.0

        # Component 4: Exchange diversity score (0-25 points)
        # More exchanges = better
        diversity_score = min(25.0, len(markets) * 3)

        # Composite score
        composite_score = volume_score + depth_score + efficiency_score + diversity_score

        return {
            'composite_score': composite_score,
            'components': {
                'volume_score': volume_score,
                'depth_score': depth_score,
                'efficiency_score': efficiency_score,
                'diversity_score': diversity_score
            },
            'metrics': {
                'total_volume': total_volume,
                'total_oi': sum(m.open_interest or 0 for m in markets),
                'avg_oi_volume_ratio': (sum(m.open_interest or 0 for m in markets) / total_volume) if total_volume > 0 else 0,
                'num_exchanges': len(markets)
            },
            'rating': self._get_score_rating(composite_score)
        }

    def _get_score_rating(self, score: float) -> str:
        """Convert numerical score to rating

        Args:
            score: Score from 0-100

        Returns:
            Rating string
        """
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 40:
            return "Poor"
        else:
            return "Very Poor"

    def __repr__(self) -> str:
        """String representation"""
        return f"AnalysisService(exchange_service={self.exchange_service})"
