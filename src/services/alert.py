"""Alert service for trading strategy detection and notification

This service analyzes market conditions and generates alerts when
optimal trading strategies are detected. It integrates with the
ExchangeService for market data, AnalysisService for analysis,
and AlertRepository for state management.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from src.services.exchange import ExchangeService
from src.services.analysis import AnalysisService
from src.repositories.alert import AlertRepository
from src.models.alert import Alert, AlertType, AlertPriority


@dataclass
class StrategyAlert:
    """Represents a detected trading strategy alert"""
    strategy_name: str
    confidence: int  # 0-100
    direction: str  # LONG, SHORT, NEUTRAL
    tier: int  # 1 = CRITICAL, 2 = HIGH, 3-4 = BACKGROUND
    reasoning: str
    metrics: Dict
    timestamp: datetime


class AlertService:
    """Service for trading strategy detection and alerting

    Coordinates market analysis, strategy detection, and alert
    management. Uses the repository pattern for state persistence.

    Usage:
        alert_service = container.alert_service
        alerts = alert_service.detect_all_strategies()
        filtered = alert_service.filter_by_tier(alerts, tiers=[1, 2])
    """

    # Strategy tier classifications
    STRATEGY_TIERS = {
        # Tier 1 - CRITICAL (immediate action required)
        'Liquidation Cascade Risk': 1,
        'Momentum Breakout': 1,
        'Institutional-Retail Divergence': 1,

        # Tier 2 - HIGH PRIORITY (act within 1-4 hours)
        'Contrarian Play': 2,
        'Breakout Trading': 2,
        'Volatility Expansion': 2,
        'Trend Following': 2,

        # Tier 3-4 - BACKGROUND (scheduled reports only)
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

    # Cooldown periods (hours) by tier
    COOLDOWN_HOURS = {
        1: 2,   # Critical: 2 hour cooldown
        2: 4,   # High: 4 hour cooldown
        3: 8,   # Background: 8 hour cooldown
    }

    def __init__(
        self,
        exchange_service: ExchangeService,
        analysis_service: AnalysisService,
        alert_repo: AlertRepository,
        enable_ml: bool = False,
        enable_kalman: bool = False
    ):
        """Initialize AlertService

        Args:
            exchange_service: Service for fetching market data
            analysis_service: Service for market analysis
            alert_repo: Repository for alert state management
            enable_ml: Enable ML-based scoring (optional)
            enable_kalman: Enable Kalman filtering (optional)
        """
        self.exchange_service = exchange_service
        self.analysis_service = analysis_service
        self.alert_repo = alert_repo
        self.enable_ml = enable_ml
        self.enable_kalman = enable_kalman

    def get_strategy_tier(self, strategy_name: str) -> int:
        """Get the tier (urgency level) of a strategy

        Args:
            strategy_name: Name of the strategy

        Returns:
            1 = CRITICAL, 2 = HIGH PRIORITY, 3-4 = BACKGROUND
        """
        # Try exact match first
        if strategy_name in self.STRATEGY_TIERS:
            return self.STRATEGY_TIERS[strategy_name]

        # Try partial match (handles variations)
        for key, tier in self.STRATEGY_TIERS.items():
            if key in strategy_name or strategy_name.startswith(key):
                return tier

        # Default to tier 3 if unknown
        return 3

    def should_alert(
        self,
        strategy_name: str,
        confidence: int,
        direction: str,
        min_confidence_delta: int = 20,
        max_alerts_per_day: int = 3,
        max_alerts_per_hour: int = 10
    ) -> Tuple[bool, str]:
        """Determine if an alert should be sent

        Uses the AlertRepository to check:
        - Cooldown periods
        - Confidence deltas
        - Daily/hourly limits

        Args:
            strategy_name: Name of the strategy
            confidence: Alert confidence (0-100)
            direction: Alert direction (LONG/SHORT/NEUTRAL)
            min_confidence_delta: Minimum confidence change to trigger
            max_alerts_per_day: Maximum alerts per strategy per day
            max_alerts_per_hour: Maximum total alerts per hour

        Returns:
            Tuple of (should_alert: bool, reason: str)
        """
        tier = self.get_strategy_tier(strategy_name)

        return self.alert_repo.should_alert(
            strategy_name=strategy_name,
            confidence=confidence,
            direction=direction,
            tier=tier,
            cooldown_hours=self.COOLDOWN_HOURS,
            min_confidence_delta=min_confidence_delta,
            max_alerts_per_day=max_alerts_per_day,
            max_alerts_per_hour=max_alerts_per_hour
        )

    def record_alert(
        self,
        strategy_name: str,
        confidence: int,
        direction: str,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        price: Optional[float] = None,
        metadata: Optional[str] = None
    ) -> int:
        """Record an alert in the repository

        Args:
            strategy_name: Name of the strategy
            confidence: Alert confidence (0-100)
            direction: Alert direction (LONG/SHORT/NEUTRAL)
            exchange: Exchange name (optional)
            symbol: Trading symbol (optional)
            price: Price at alert time (optional)
            metadata: Additional metadata as JSON string (optional)

        Returns:
            Alert ID
        """
        tier = self.get_strategy_tier(strategy_name)
        cooldown = self.COOLDOWN_HOURS.get(tier, 8)

        return self.alert_repo.record_alert(
            strategy_name=strategy_name,
            confidence=confidence,
            direction=direction,
            tier=tier,
            cooldown_hours=cooldown,
            exchange=exchange,
            symbol=symbol,
            price=price,
            metadata=metadata
        )

    def detect_trend_following(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect trend following setup

        Strong trending market with momentum.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use avg_funding_rate_pct from AnalysisService
        weighted_funding = sentiment.get('avg_funding_rate_pct', 0)

        # Strong positive trend (bulls paying bears)
        if weighted_funding > 0.05:
            confidence = min(100, int(weighted_funding * 1000))
            return StrategyAlert(
                strategy_name="Trend Following",
                confidence=confidence,
                direction="LONG",
                tier=self.get_strategy_tier("Trend Following"),
                reasoning=f"Strong bullish momentum with {weighted_funding:.3f}% funding rate",
                metrics={'funding_rate': weighted_funding},
                timestamp=datetime.now(timezone.utc)
            )

        # Strong negative trend (bears paying bulls)
        elif weighted_funding < -0.05:
            confidence = min(100, int(abs(weighted_funding) * 1000))
            return StrategyAlert(
                strategy_name="Trend Following",
                confidence=confidence,
                direction="SHORT",
                tier=self.get_strategy_tier("Trend Following"),
                reasoning=f"Strong bearish momentum with {weighted_funding:.3f}% funding rate",
                metrics={'funding_rate': weighted_funding},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_contrarian_play(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect contrarian trading setup

        Extreme funding rates suggest potential reversal.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use avg_funding_rate_pct from AnalysisService
        weighted_funding = sentiment.get('avg_funding_rate_pct', 0)

        # Extreme positive funding (longs overcrowded)
        if weighted_funding > 0.15:
            confidence = min(100, int((weighted_funding - 0.15) * 500) + 60)
            return StrategyAlert(
                strategy_name="Contrarian Play",
                confidence=confidence,
                direction="SHORT",
                tier=self.get_strategy_tier("Contrarian Play"),
                reasoning=f"Extreme positive funding ({weighted_funding:.3f}%) suggests overcrowded longs",
                metrics={'funding_rate': weighted_funding},
                timestamp=datetime.now(timezone.utc)
            )

        # Extreme negative funding (shorts overcrowded)
        elif weighted_funding < -0.15:
            confidence = min(100, int((abs(weighted_funding) - 0.15) * 500) + 60)
            return StrategyAlert(
                strategy_name="Contrarian Play",
                confidence=confidence,
                direction="LONG",
                tier=self.get_strategy_tier("Contrarian Play"),
                reasoning=f"Extreme negative funding ({weighted_funding:.3f}%) suggests overcrowded shorts",
                metrics={'funding_rate': weighted_funding},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_funding_arbitrage(self, arb_opportunities: List[Dict]) -> Optional[StrategyAlert]:
        """Detect funding rate arbitrage opportunities

        Significant funding rate differences between exchanges.

        Args:
            arb_opportunities: List of arbitrage opportunities

        Returns:
            StrategyAlert if detected, None otherwise
        """
        if not arb_opportunities:
            return None

        # Get best opportunity - use spread_pct from AnalysisService
        best = max(arb_opportunities, key=lambda x: x.get('spread_pct', 0))
        spread_pct = best.get('spread_pct', 0)
        profit_bps = spread_pct * 100  # Convert percentage to basis points

        if profit_bps >= 5:  # At least 5 basis points profit
            confidence = min(100, int(profit_bps * 10))

            return StrategyAlert(
                strategy_name="Funding Rate Arbitrage",
                confidence=confidence,
                direction="NEUTRAL",
                tier=self.get_strategy_tier("Funding Rate Arbitrage"),
                reasoning=f"Funding arbitrage: Long {best.get('long_exchange', '?')} / Short {best.get('short_exchange', '?')} "
                         f"({profit_bps:.1f} bps profit)",
                metrics=best,
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_breakout_setup(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect breakout trading setup

        Price breaking out of consolidation with momentum.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use 'score' field from AnalysisService
        score = sentiment.get('score', 0)

        # Breakout: strong directional shift (score > 0.4 is > 40% sentiment)
        breakout = abs(score) > 40.0  # score is 0-100 scale

        if breakout:
            direction = "LONG" if score > 0 else "SHORT"
            confidence = min(100, int(abs(score)))

            return StrategyAlert(
                strategy_name="Breakout Trading",
                confidence=confidence,
                direction=direction,
                tier=self.get_strategy_tier("Breakout Trading"),
                reasoning=f"Breakout detected: {direction} momentum with {abs(score):.1f} sentiment score",
                metrics={'score': score},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_momentum_breakout(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect momentum breakout setup

        Strong momentum with accelerating price action.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use 'score' field from AnalysisService
        score = sentiment.get('score', 0)

        # Extreme momentum breakout (score > 70 is very strong)
        extreme_momentum = abs(score) > 70.0  # score is 0-100 scale

        if extreme_momentum:
            direction = "LONG" if score > 0 else "SHORT"
            confidence = min(100, int(abs(score)))

            return StrategyAlert(
                strategy_name="Momentum Breakout",
                confidence=confidence,
                direction=direction,
                tier=self.get_strategy_tier("Momentum Breakout"),
                reasoning=f"CRITICAL: Extreme {direction.lower()} momentum with {abs(score):.1f} sentiment score",
                metrics={'score': score},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_mean_reversion(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect mean reversion setup

        Funding rate extended, likely to revert to mean.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use avg_funding_rate_pct from AnalysisService
        weighted_funding = sentiment.get('avg_funding_rate_pct', 0)

        # Mean reversion: moderate funding rate extension (not extreme)
        extended = 0.08 < abs(weighted_funding) < 0.15

        if extended:
            # Contrarian: if funding is positive, expect price reversion down
            direction = "SHORT" if weighted_funding > 0 else "LONG"
            confidence = min(100, int(abs(weighted_funding) * 500))

            return StrategyAlert(
                strategy_name="Mean Reversion",
                confidence=confidence,
                direction=direction,
                tier=self.get_strategy_tier("Mean Reversion"),
                reasoning=f"Funding extended {weighted_funding:.3f}%, expecting reversion",
                metrics={'funding_rate': weighted_funding},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_volatility_expansion(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect volatility expansion setup

        Funding rate volatility indicates market activity pickup.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use avg_funding_rate_pct from AnalysisService
        weighted_funding = sentiment.get('avg_funding_rate_pct', 0)
        score = sentiment.get('score', 0)

        # Volatility expansion: moderate to high funding rate movement
        high_volatility = abs(weighted_funding) > 0.06

        if high_volatility:
            direction = "LONG" if weighted_funding > 0 else "SHORT" if weighted_funding < 0 else "NEUTRAL"
            confidence = min(100, int(abs(weighted_funding) * 800))

            return StrategyAlert(
                strategy_name="Volatility Expansion",
                confidence=confidence,
                direction=direction,
                tier=self.get_strategy_tier("Volatility Expansion"),
                reasoning=f"Volatility expanding: {weighted_funding:.3f}% funding, expect continuation",
                metrics={'funding_rate': weighted_funding, 'score': score},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_range_trading(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect range trading setup

        Neutral market with low funding rate volatility.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use avg_funding_rate_pct from AnalysisService
        weighted_funding = sentiment.get('avg_funding_rate_pct', 0)

        # Range: very neutral funding rate (market in equilibrium)
        in_range = abs(weighted_funding) < 0.02

        if in_range:
            confidence = 70  # Base confidence for range

            return StrategyAlert(
                strategy_name="Range Trading",
                confidence=confidence,
                direction="NEUTRAL",
                tier=self.get_strategy_tier("Range Trading"),
                reasoning=f"Market ranging: {weighted_funding:.4f}% funding rate (neutral)",
                metrics={'funding_rate': weighted_funding},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_scalping_setup(self, sentiment: Dict, total_volume: float) -> Optional[StrategyAlert]:
        """Detect scalping setup

        Ultra-tight ranges with high liquidity.

        Args:
            sentiment: Market sentiment data
            total_volume: Total 24h volume across all exchanges

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use avg_funding_rate_pct from AnalysisService
        weighted_funding = sentiment.get('avg_funding_rate_pct', 0)

        # Scalping: very neutral funding, very high liquidity
        optimal_scalp = (
            abs(weighted_funding) < 0.01 and  # Ultra-neutral
            total_volume > 10_000_000_000  # $10B+
        )

        if optimal_scalp:
            confidence = 80

            return StrategyAlert(
                strategy_name="Scalping",
                confidence=confidence,
                direction="NEUTRAL",
                tier=self.get_strategy_tier("Scalping"),
                reasoning=f"Optimal scalping: {weighted_funding:.4f}% funding, ${total_volume/1e9:.1f}B liquidity",
                metrics={'funding_rate': weighted_funding, 'volume': total_volume},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_liquidation_cascade_risk(self, sentiment: Dict) -> Optional[StrategyAlert]:
        """Detect liquidation cascade risk

        Extreme funding rate indicates crowded positioning and liquidation risk.

        Args:
            sentiment: Market sentiment data

        Returns:
            StrategyAlert if detected, None otherwise
        """
        # Use avg_funding_rate_pct from AnalysisService
        weighted_funding = sentiment.get('avg_funding_rate_pct', 0)

        # Liquidation risk: extreme funding rate (overcrowded positioning)
        cascade_risk = abs(weighted_funding) > 0.20  # 0.20% is very extreme

        if cascade_risk:
            direction = "SHORT" if weighted_funding > 0 else "LONG"  # Fade the overcrowded side
            confidence = min(100, int(abs(weighted_funding) * 400))

            return StrategyAlert(
                strategy_name="Liquidation Cascade Risk",
                confidence=confidence,
                direction=direction,
                tier=self.get_strategy_tier("Liquidation Cascade Risk"),
                reasoning=f"CRITICAL: Cascade risk! {weighted_funding:.3f}% funding indicates overcrowded positioning",
                metrics={'funding_rate': weighted_funding},
                timestamp=datetime.now(timezone.utc)
            )

        return None

    def detect_all_strategies(self) -> List[StrategyAlert]:
        """Detect all trading strategies

        Fetches market data, performs analysis, and detects all
        applicable trading strategies.

        Returns:
            List of detected strategy alerts
        """
        alerts = []

        # Fetch market data
        markets = self.exchange_service.fetch_all_markets(use_cache=True)

        if not markets:
            return alerts

        # Analyze market sentiment
        sentiment = self.analysis_service.calculate_market_sentiment(markets)

        # Calculate total volume for scalping detector
        total_volume = sum(m.volume_24h for m in markets if m.volume_24h)

        # Analyze arbitrage opportunities
        arb_opportunities = self.analysis_service.find_funding_arbitrage_opportunities(use_cache=True)

        # Detect all strategies (ordered by priority/tier)

        # Tier 1 - CRITICAL
        alert = self.detect_liquidation_cascade_risk(sentiment)
        if alert:
            alerts.append(alert)

        alert = self.detect_momentum_breakout(sentiment)
        if alert:
            alerts.append(alert)

        # Tier 2 - HIGH PRIORITY
        alert = self.detect_contrarian_play(sentiment)
        if alert:
            alerts.append(alert)

        alert = self.detect_breakout_setup(sentiment)
        if alert:
            alerts.append(alert)

        alert = self.detect_volatility_expansion(sentiment)
        if alert:
            alerts.append(alert)

        alert = self.detect_trend_following(sentiment)
        if alert:
            alerts.append(alert)

        # Tier 3 - BACKGROUND
        alert = self.detect_range_trading(sentiment)
        if alert:
            alerts.append(alert)

        alert = self.detect_scalping_setup(sentiment, total_volume)
        if alert:
            alerts.append(alert)

        alert = self.detect_mean_reversion(sentiment)
        if alert:
            alerts.append(alert)

        alert = self.detect_funding_arbitrage(arb_opportunities)
        if alert:
            alerts.append(alert)

        return alerts

    def filter_by_tier(
        self,
        alerts: List[StrategyAlert],
        tiers: List[int] = None,
        min_confidence: int = 50
    ) -> List[StrategyAlert]:
        """Filter alerts by tier and confidence

        Args:
            alerts: List of strategy alerts
            tiers: List of tiers to include (e.g., [1, 2] for critical and high)
            min_confidence: Minimum confidence threshold

        Returns:
            Filtered list of alerts
        """
        if tiers is None:
            tiers = [1, 2]  # Default to critical and high priority

        filtered = []
        for alert in alerts:
            if alert.tier in tiers and alert.confidence >= min_confidence:
                filtered.append(alert)

        return filtered

    def get_alert_statistics(self, days: int = 7) -> Dict:
        """Get alert statistics for the last N days

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with alert statistics
        """
        return self.alert_repo.get_daily_stats(days=days)
