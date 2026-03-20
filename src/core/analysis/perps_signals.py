"""
Perpetuals Pulse Phase 2: Trading Signal Generation

Transforms statistical metrics into actionable trading signals with confidence scores.
Implements:
1. Funding Rate Divergence (contrarian mean reversion)
2. L/S Extreme Detection (crowded trade warnings)
3. Liquidation Cascade Risk (composite risk scoring)
4. Multi-Timeframe Momentum Analysis (trend confirmation)
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import deque
import numpy as np


class SignalStrength(Enum):
    """Signal strength classification based on statistical significance"""
    EXTREME = "extreme"   # >2σ event, rare
    STRONG = "strong"     # 1.5-2σ event
    MODERATE = "moderate" # 1.0-1.5σ event
    WEAK = "weak"         # 0.5-1.0σ event
    NONE = "none"         # <0.5σ, no signal


class SignalDirection(Enum):
    """Trading signal direction"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class TradingSignal:
    """Individual trading signal with metadata"""
    signal_type: str
    direction: SignalDirection
    strength: SignalStrength
    confidence: float  # 0-1 scale
    description: str
    time_horizon_hours: int
    invalidation_level: Optional[float] = None
    expected_move_pct: Optional[float] = None
    max_drawdown_risk_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'signal_type': self.signal_type,
            'direction': self.direction.value,
            'strength': self.strength.value,
            'confidence': round(self.confidence, 3),
            'description': self.description,
            'time_horizon_hours': self.time_horizon_hours,
            'invalidation_level': self.invalidation_level,
            'expected_move_pct': self.expected_move_pct,
            'max_drawdown_risk_pct': self.max_drawdown_risk_pct
        }


class PerpetualsSignalGenerator:
    """
    Phase 2: Generate trading signals from statistical metrics

    Signal Types:
    1. Funding Divergence - Mean reversion on extreme funding rates
    2. L/S Extremes - Contrarian signals on crowded positioning
    3. Liquidation Risk - Cascade vulnerability detection
    4. Momentum - Multi-timeframe trend confirmation
    """

    def __init__(self, max_history: int = 288):
        """
        Args:
            max_history: Maximum samples to store (288 = 24h at 5-min intervals)
        """
        self.logger = logging.getLogger(__name__)
        self.max_history = max_history

        # Historical buffers for multi-timeframe analysis
        self._funding_history = deque(maxlen=max_history)
        self._ls_history = deque(maxlen=max_history)
        self._oi_history = deque(maxlen=max_history)
        self._timestamp_history = deque(maxlen=max_history)

    def generate_signals(self, metrics: Dict[str, Any]) -> List[TradingSignal]:
        """
        Generate all trading signals from current metrics.

        Args:
            metrics: Dictionary from PerpetualsAggregator containing:
                - funding_rate, funding_zscore, funding_std_bps
                - long_pct, short_pct, ls_entropy
                - exchange_agreement, data_quality_score
                - total_open_interest, total_volume_24h

        Returns:
            List of TradingSignal objects
        """
        signals = []

        # Update historical buffers
        self._update_history(metrics)

        # 1. Funding Rate Divergence Signal
        funding_signal = self._generate_funding_divergence_signal(metrics)
        if funding_signal:
            signals.append(funding_signal)

        # 2. L/S Extreme Detection Signal
        ls_signal = self._generate_ls_extreme_signal(metrics)
        if ls_signal:
            signals.append(ls_signal)

        # 3. Liquidation Cascade Risk Signal
        cascade_signal = self._generate_liquidation_cascade_signal(metrics)
        if cascade_signal:
            signals.append(cascade_signal)

        # 4. Multi-Timeframe Momentum Signal (if enough history)
        if len(self._funding_history) >= 48:  # Need 4h of data minimum
            momentum_signal = self._generate_momentum_signal(metrics)
            if momentum_signal:
                signals.append(momentum_signal)

        return signals

    def _update_history(self, metrics: Dict[str, Any]) -> None:
        """Update historical buffers with current metrics"""
        import time

        self._funding_history.append(metrics.get('funding_rate', 0.0))
        self._ls_history.append(metrics.get('long_pct', 50.0))
        self._oi_history.append(metrics.get('total_open_interest', 0.0))
        self._timestamp_history.append(time.time())

    def _generate_funding_divergence_signal(
        self,
        metrics: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """
        Generate contrarian signal based on funding rate z-score.

        Logic:
        - Positive funding (longs pay shorts) → Too many longs → BEARISH
        - Negative funding (shorts pay longs) → Too many shorts → BULLISH
        - Only trigger when |z_score| > 1.0 (at least moderate signal)
        """
        z_score = metrics.get('funding_zscore', 0.0)
        funding_rate = metrics.get('funding_rate', 0.0)
        exchange_agreement = metrics.get('exchange_agreement', 0.5)

        # No signal if z-score is weak
        if abs(z_score) < 0.5:
            return None

        # Determine strength
        abs_z = abs(z_score)
        if abs_z >= 2.0:
            strength = SignalStrength.EXTREME
        elif abs_z >= 1.5:
            strength = SignalStrength.STRONG
        elif abs_z >= 1.0:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Determine direction (contrarian)
        # Positive funding = too many longs = bearish
        # Negative funding = too many shorts = bullish
        direction = SignalDirection.BEARISH if funding_rate > 0 else SignalDirection.BULLISH

        # Calculate confidence
        # Base: z-score magnitude (capped at 3σ = 100%)
        base_confidence = min(abs_z / 3.0, 1.0)

        # Boost: exchange agreement adds confidence
        agreement_boost = exchange_agreement * 0.5
        final_confidence = base_confidence * (0.5 + agreement_boost)

        # Expected reversion
        # Rule of thumb: funding tends to revert 30-50% toward mean within 24h
        expected_reversion_pct = abs(funding_rate) * 0.4

        # Invalidation: if funding moves further away from mean
        invalidation_level = funding_rate * 1.5

        # Risk: max 1.5% drawdown before invalidation
        max_drawdown_risk = 1.5

        description = (
            f"Funding rate {abs_z:.1f}σ {'above' if funding_rate > 0 else 'below'} mean "
            f"({funding_rate*100:.3f}%). {'Longs' if funding_rate > 0 else 'Shorts'} overextended."
        )

        return TradingSignal(
            signal_type="funding_divergence",
            direction=direction,
            strength=strength,
            confidence=final_confidence,
            description=description,
            time_horizon_hours=24,
            invalidation_level=invalidation_level,
            expected_move_pct=expected_reversion_pct * 100,
            max_drawdown_risk_pct=max_drawdown_risk
        )

    def _generate_ls_extreme_signal(
        self,
        metrics: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """
        Generate contrarian signal based on extreme L/S positioning.

        Thresholds:
        - long_pct > 75%: EXTREME bearish
        - long_pct > 70%: STRONG bearish
        - long_pct > 65%: MODERATE bearish
        - short_pct > 75%: EXTREME bullish
        - short_pct > 70%: STRONG bullish
        - short_pct > 65%: MODERATE bullish
        """
        long_pct = metrics.get('long_pct', 50.0)
        short_pct = metrics.get('short_pct', 50.0)
        entropy = metrics.get('ls_entropy', 1.0)

        # Determine if we have an extreme
        if long_pct >= 65:
            # Too many longs → bearish signal
            direction = SignalDirection.BEARISH
            extreme_pct = long_pct

            if long_pct >= 75:
                strength = SignalStrength.EXTREME
            elif long_pct >= 70:
                strength = SignalStrength.STRONG
            else:
                strength = SignalStrength.MODERATE

        elif short_pct >= 65:
            # Too many shorts → bullish signal
            direction = SignalDirection.BULLISH
            extreme_pct = short_pct

            if short_pct >= 75:
                strength = SignalStrength.EXTREME
            elif short_pct >= 70:
                strength = SignalStrength.STRONG
            else:
                strength = SignalStrength.MODERATE
        else:
            # No extreme
            return None

        # Calculate confidence using entropy
        # Low entropy = clustered positioning = higher confidence in reversal
        clustering_factor = 1 - entropy
        confidence = 0.5 + 0.5 * clustering_factor

        description = (
            f"{'Long' if direction == SignalDirection.BEARISH else 'Short'} positioning "
            f"extreme at {extreme_pct:.1f}%. Crowded trade vulnerable to reversal."
        )

        # Expected move: 5-10% unwind of extreme positioning
        expected_move = (extreme_pct - 50) * 0.15  # 15% of deviation from 50%

        return TradingSignal(
            signal_type="ls_extreme",
            direction=direction,
            strength=strength,
            confidence=confidence,
            description=description,
            time_horizon_hours=48,  # Positioning extremes take longer to unwind
            expected_move_pct=expected_move,
            max_drawdown_risk_pct=2.0
        )

    def _generate_liquidation_cascade_signal(
        self,
        metrics: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """
        Generate signal based on liquidation cascade risk.

        Combines:
        1. Crowd risk (one-sided positioning)
        2. Leverage risk (extreme funding)
        3. Clustering risk (low entropy)
        """
        long_pct = metrics.get('long_pct', 50.0) / 100
        funding_rate = metrics.get('funding_rate', 0.0)
        entropy = metrics.get('ls_entropy', 1.0)

        # 1. Crowd risk (0-1)
        crowd_risk = max(long_pct - 0.5, 0.5 - long_pct) * 2

        # 2. Leverage risk (0-1)
        # High funding indicates high leverage
        leverage_risk = min(abs(funding_rate) / 0.01, 1.0)

        # 3. Clustering risk (0-1)
        # Low entropy = high clustering
        clustering_risk = 1 - entropy

        # Composite risk score
        composite_risk = (
            0.4 * crowd_risk +
            0.3 * leverage_risk +
            0.3 * clustering_risk
        )

        # Only signal if risk is significant
        if composite_risk < 0.6:
            return None

        # Determine strength
        if composite_risk >= 0.8:
            strength = SignalStrength.EXTREME
        elif composite_risk >= 0.7:
            strength = SignalStrength.STRONG
        else:
            strength = SignalStrength.MODERATE

        # Direction: which side would cascade?
        if long_pct > 0.5:
            direction = SignalDirection.BEARISH  # Long cascade risk
            cascade_side = "long"
        else:
            direction = SignalDirection.BULLISH  # Short cascade risk
            cascade_side = "short"

        # Confidence = composite risk itself
        confidence = composite_risk

        description = (
            f"Liquidation cascade risk: {composite_risk:.2f}. "
            f"{cascade_side.capitalize()} positions vulnerable to rapid unwinding."
        )

        return TradingSignal(
            signal_type="liquidation_risk",
            direction=direction,
            strength=strength,
            confidence=confidence,
            description=description,
            time_horizon_hours=12,  # Cascades happen fast
            expected_move_pct=5.0,  # Cascades typically 5-15%
            max_drawdown_risk_pct=3.0
        )

    def _generate_momentum_signal(
        self,
        metrics: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """
        Generate momentum signal from multi-timeframe analysis.

        Requires at least 48 samples (4 hours) of history.
        """
        if len(self._funding_history) < 48:
            return None

        # Calculate 4h trends
        funding_4h = list(self._funding_history)[-48:]
        ls_4h = list(self._ls_history)[-48:]
        oi_4h = list(self._oi_history)[-48:]

        # 1. Funding trend (linear regression)
        x = np.arange(len(funding_4h))
        funding_slope = np.polyfit(x, funding_4h, 1)[0]

        # 2. L/S trend
        ls_slope = np.polyfit(x, ls_4h, 1)[0]

        # 3. OI change
        oi_change_pct = ((oi_4h[-1] - oi_4h[0]) / oi_4h[0] * 100) if oi_4h[0] > 0 else 0

        # Composite momentum score (-1 to +1)
        # Funding momentum (inverted: negative funding = bullish)
        funding_momentum = -funding_slope * 1000  # Scale to reasonable range

        # L/S momentum (normalized)
        ls_ma = np.mean(ls_4h)
        ls_momentum = (ls_ma - 50) / 50

        # OI factor (tanh normalizes)
        oi_factor = np.tanh(oi_change_pct / 20)

        # Weighted combination
        momentum_score = (
            0.4 * funding_momentum +
            0.4 * ls_momentum +
            0.2 * oi_factor
        )

        # Clamp to -1 to +1
        momentum_score = np.clip(momentum_score, -1, 1)

        # No signal if momentum is weak
        if abs(momentum_score) < 0.3:
            return None

        # Determine direction and strength
        direction = SignalDirection.BULLISH if momentum_score > 0 else SignalDirection.BEARISH

        abs_momentum = abs(momentum_score)
        if abs_momentum >= 0.7:
            strength = SignalStrength.STRONG
        elif abs_momentum >= 0.5:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Confidence = momentum magnitude
        confidence = abs_momentum

        description = (
            f"4h momentum {'bullish' if momentum_score > 0 else 'bearish'} "
            f"(score: {momentum_score:.2f}). "
            f"Funding trend: {funding_slope*100:.5f}%/interval, "
            f"L/S: {ls_ma:.1f}%, OI: {oi_change_pct:+.1f}%"
        )

        return TradingSignal(
            signal_type="momentum",
            direction=direction,
            strength=strength,
            confidence=confidence,
            description=description,
            time_horizon_hours=8,
            expected_move_pct=abs_momentum * 3,  # Rule of thumb
            max_drawdown_risk_pct=2.0
        )


# Singleton instance
_signal_generator: Optional[PerpetualsSignalGenerator] = None


def get_signal_generator() -> PerpetualsSignalGenerator:
    """Get singleton signal generator instance"""
    global _signal_generator
    if _signal_generator is None:
        _signal_generator = PerpetualsSignalGenerator()
    return _signal_generator
