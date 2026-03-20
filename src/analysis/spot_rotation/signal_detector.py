"""
Spot Rotation Signal Detector - 5-Factor Scoring

Detects sector rotation signals in spot markets using a 5-factor scoring model.
Different from perp rotation: no funding/OI, uses market cap momentum instead.

5-Factor Scoring Model:
1. Volume Z-Score (25%) - Unusual volume share relative to history
2. Momentum (25%) - Multi-timeframe price momentum (1h, 24h, 7d weighted)
3. Breadth (20%) - Up/down token ratio, market cap weighted
4. Market Cap Flow (15%) - Sector market cap change relative to market
5. Relative Strength (15%) - Sector RS vs BTC performance
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .storage import (
    SpotSectorSnapshot,
    SpotSectorSignal,
    SpotPerpDivergence,
    SignalStrength,
    SampleSizeFlag,
    SPOT_SECTOR_CONFIG,
    SMALL_SAMPLE_SECTORS,
)

logger = logging.getLogger(__name__)


class SpotSignalDetector:
    """
    Detects sector rotation signals in spot markets using 5-factor scoring.

    Scoring factors and weights:
    - volume_zscore: 0.25 (unusual volume activity)
    - momentum: 0.25 (multi-timeframe momentum)
    - breadth: 0.20 (market cap weighted breadth)
    - market_cap_flow: 0.15 (relative mcap change)
    - relative_strength: 0.15 (RS vs BTC)
    """

    # 5-factor weights (sum = 1.0)
    WEIGHTS = {
        'volume_zscore': 0.25,
        'momentum': 0.25,
        'breadth': 0.20,
        'market_cap_flow': 0.15,
        'relative_strength': 0.15,
    }

    # Signal thresholds
    INFLOW_THRESHOLD = 60.0      # Score >= 60 = inflow signal
    OUTFLOW_THRESHOLD = 40.0     # Score <= 40 = outflow signal
    MODERATE_THRESHOLD = 55.0    # Strength upgrade threshold
    STRONG_THRESHOLD = 70.0      # Strong signal threshold

    # Z-score lookback (in snapshot periods)
    ZSCORE_PERIODS = 42          # ~7 days at 15-min intervals

    def __init__(self):
        """Initialize detector with history storage."""
        # Historical snapshots for z-score calculation
        self._history: Dict[str, List[SpotSectorSnapshot]] = defaultdict(list)

        # Active signals
        self._active_signals: Dict[str, SpotSectorSignal] = {}

        # Signal confirmation tracking
        self._signal_streaks: Dict[str, int] = defaultdict(int)

    def process_snapshots(
        self,
        snapshots: Dict[str, SpotSectorSnapshot]
    ) -> Dict[str, SpotSectorSignal]:
        """
        Process new snapshots and detect signals.

        Args:
            snapshots: Dictionary of sector_code -> SpotSectorSnapshot

        Returns:
            Dictionary of active signals
        """
        now = datetime.utcnow()

        for sector_code, snapshot in snapshots.items():
            # Add to history
            self._history[sector_code].append(snapshot)

            # Trim history to limit
            if len(self._history[sector_code]) > self.ZSCORE_PERIODS * 2:
                self._history[sector_code] = self._history[sector_code][-self.ZSCORE_PERIODS:]

            # Calculate rotation score
            score, factors = self._calculate_rotation_score(snapshot, sector_code)

            # Update snapshot with score
            snapshot.rotation_score = score
            snapshot.signal_strength = self._classify_strength(score)

            # Calculate z-scores for snapshot
            self._update_zscores(snapshot, sector_code)

            # Detect and track signals
            self._process_signal(sector_code, snapshot, score)

        return self._active_signals.copy()

    def _calculate_rotation_score(
        self,
        snapshot: SpotSectorSnapshot,
        sector_code: str
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate 5-factor rotation score (0-100).

        Returns:
            (score, factor_dict) - Score and individual factor contributions
        """
        factors = {}

        # Factor 1: Volume Z-Score (25%)
        volume_zscore = snapshot.volume_share_zscore
        factors['volume_zscore'] = self._zscore_to_score(volume_zscore)

        # Factor 2: Momentum - Multi-timeframe weighted (25%)
        # Weight: 1h=0.2, 24h=0.5, 7d=0.3
        momentum = (
            snapshot.avg_price_change_1h * 0.2 +
            snapshot.avg_price_change_24h * 0.5 +
            snapshot.avg_price_change_7d * 0.3
        )
        factors['momentum'] = self._momentum_to_score(momentum)

        # Factor 3: Breadth - Market cap weighted (20%)
        # Use weighted breadth (market cap weighted % of tokens up)
        breadth = snapshot.weighted_breadth
        factors['breadth'] = self._breadth_to_score(breadth)

        # Factor 4: Market Cap Flow (15%)
        # Compare sector mcap change to overall market
        mcap_flow = snapshot.market_cap_change_24h - snapshot.market_cap_zscore * 0.1
        factors['market_cap_flow'] = self._flow_to_score(mcap_flow)

        # Factor 5: Relative Strength vs BTC (15%)
        rs = snapshot.sector_rs_24h
        factors['relative_strength'] = self._rs_to_score(rs)

        # Calculate weighted score
        score = sum(
            factors[factor] * weight
            for factor, weight in self.WEIGHTS.items()
        )

        # Apply confidence adjustment for small samples
        if sector_code in SMALL_SAMPLE_SECTORS:
            score = self._apply_confidence_adjustment(score, snapshot)

        return score, factors

    def _zscore_to_score(self, zscore: float) -> float:
        """Convert z-score to 0-100 score."""
        # z=0 -> 50, z=2 -> 80, z=-2 -> 20
        score = 50 + (zscore * 15)
        return max(0, min(100, score))

    def _momentum_to_score(self, momentum: float) -> float:
        """Convert momentum percentage to 0-100 score."""
        # momentum=0 -> 50, momentum=5% -> 75, momentum=-5% -> 25
        score = 50 + (momentum * 5)
        return max(0, min(100, score))

    def _breadth_to_score(self, breadth: float) -> float:
        """Convert breadth ratio (0-1) to 0-100 score."""
        # breadth=0.5 -> 50, breadth=0.8 -> 80
        return breadth * 100

    def _flow_to_score(self, flow: float) -> float:
        """Convert market cap flow to 0-100 score."""
        # flow=0 -> 50, flow=3% -> 65
        score = 50 + (flow * 5)
        return max(0, min(100, score))

    def _rs_to_score(self, rs: float) -> float:
        """Convert relative strength to 0-100 score."""
        # rs=0 -> 50, rs=5% -> 75, rs=-5% -> 25
        score = 50 + (rs * 5)
        return max(0, min(100, score))

    def _apply_confidence_adjustment(
        self,
        score: float,
        snapshot: SpotSectorSnapshot
    ) -> float:
        """Apply confidence adjustment for small sample sizes."""
        if snapshot.sample_size_flag == SampleSizeFlag.SMALL.value:
            # Pull score toward 50 by 15%
            return score * 0.85 + 50 * 0.15
        elif snapshot.sample_size_flag == SampleSizeFlag.INSUFFICIENT.value:
            # Pull score toward 50 by 30%
            return score * 0.70 + 50 * 0.30
        return score

    def _classify_strength(self, score: float) -> str:
        """Classify signal strength based on score."""
        if score >= self.STRONG_THRESHOLD or score <= (100 - self.STRONG_THRESHOLD):
            return SignalStrength.STRONG.value
        elif score >= self.MODERATE_THRESHOLD or score <= (100 - self.MODERATE_THRESHOLD):
            return SignalStrength.MODERATE.value
        return SignalStrength.WEAK.value

    def _update_zscores(self, snapshot: SpotSectorSnapshot, sector_code: str):
        """Update z-scores based on historical data."""
        history = self._history.get(sector_code, [])
        if len(history) < 10:
            return

        # Volume share z-score
        volume_shares = [s.volume_share_pct for s in history[-self.ZSCORE_PERIODS:]]
        if volume_shares:
            mean = sum(volume_shares) / len(volume_shares)
            variance = sum((x - mean) ** 2 for x in volume_shares) / len(volume_shares)
            std = variance ** 0.5 if variance > 0 else 1
            snapshot.volume_share_zscore = (snapshot.volume_share_pct - mean) / std if std > 0 else 0

        # Market cap z-score
        mcap_shares = [s.market_cap_share_pct for s in history[-self.ZSCORE_PERIODS:]]
        if mcap_shares:
            mean = sum(mcap_shares) / len(mcap_shares)
            variance = sum((x - mean) ** 2 for x in mcap_shares) / len(mcap_shares)
            std = variance ** 0.5 if variance > 0 else 1
            snapshot.market_cap_zscore = (snapshot.market_cap_share_pct - mean) / std if std > 0 else 0

        # RS z-score
        rs_values = [s.sector_rs_24h for s in history[-self.ZSCORE_PERIODS:]]
        if rs_values:
            mean = sum(rs_values) / len(rs_values)
            variance = sum((x - mean) ** 2 for x in rs_values) / len(rs_values)
            std = variance ** 0.5 if variance > 0 else 1
            snapshot.sector_rs_zscore = (snapshot.sector_rs_24h - mean) / std if std > 0 else 0

    def _process_signal(
        self,
        sector_code: str,
        snapshot: SpotSectorSnapshot,
        score: float
    ):
        """Process score and update signal status."""
        now = datetime.utcnow()
        signal_key = sector_code

        # Determine signal type
        if score >= self.INFLOW_THRESHOLD:
            signal_type = 'inflow'
        elif score <= self.OUTFLOW_THRESHOLD:
            signal_type = 'outflow'
        else:
            signal_type = 'neutral'
            # Reset streak if neutral
            self._signal_streaks[signal_key] = 0
            # Expire existing signal if neutral for too long
            if signal_key in self._active_signals:
                self._expire_signal(signal_key)
            return

        # Check if continuing same signal
        existing = self._active_signals.get(signal_key)
        if existing and existing.signal_type == signal_type:
            # Same signal - increment confirmation
            self._signal_streaks[signal_key] += 1
            existing.last_confirmed = now
            existing.confirmation_count = self._signal_streaks[signal_key]
            existing.rotation_score = score
            existing.signal_strength = snapshot.signal_strength

            # Confirm if 2+ consecutive periods at moderate+ strength
            if (existing.confirmation_count >= 2 and
                existing.signal_strength in [SignalStrength.MODERATE.value, SignalStrength.STRONG.value]):
                existing.is_confirmed = True

        else:
            # New signal or direction change
            self._signal_streaks[signal_key] = 1

            new_signal = SpotSectorSignal(
                sector_code=sector_code,
                signal_type=signal_type,
                signal_strength=snapshot.signal_strength,
                rotation_score=score,
                first_detected=now,
                last_confirmed=now,
                confirmation_count=1,
                is_confirmed=False,
                volume_zscore=snapshot.volume_share_zscore,
                market_cap_zscore=snapshot.market_cap_zscore,
                btc_correlation=snapshot.btc_correlation,
                breadth_24h=snapshot.breadth_ratio_24h,
                breadth_7d=snapshot.breadth_ratio_7d,
                confidence_level=snapshot.data_quality_score,
                is_active=True,
            )

            self._active_signals[signal_key] = new_signal

    def _expire_signal(self, signal_key: str):
        """Expire and remove a signal."""
        if signal_key in self._active_signals:
            signal = self._active_signals[signal_key]
            signal.is_active = False
            signal.expired_at = datetime.utcnow()
            del self._active_signals[signal_key]

    def get_all_active_signals(self) -> List[SpotSectorSignal]:
        """Get all currently active signals."""
        return list(self._active_signals.values())

    def get_confirmed_signals(self) -> List[SpotSectorSignal]:
        """Get only confirmed signals (2+ consecutive periods)."""
        return [s for s in self._active_signals.values() if s.is_confirmed]

    def get_inflow_sectors(self) -> List[str]:
        """Get sectors with active inflow signals."""
        return [
            s.sector_code for s in self._active_signals.values()
            if s.signal_type == 'inflow' and s.is_confirmed
        ]

    def get_outflow_sectors(self) -> List[str]:
        """Get sectors with active outflow signals."""
        return [
            s.sector_code for s in self._active_signals.values()
            if s.signal_type == 'outflow' and s.is_confirmed
        ]

    def get_signal_summary(self) -> Dict:
        """Get summary of current signal state."""
        active = self.get_all_active_signals()
        confirmed = self.get_confirmed_signals()

        return {
            'active_signals': len(active),
            'confirmed_signals': len(confirmed),
            'inflow_sectors': self.get_inflow_sectors(),
            'outflow_sectors': self.get_outflow_sectors(),
            'rotation_pairs': self._detect_rotation_pairs(),
        }

    def _detect_rotation_pairs(self) -> List[Dict]:
        """Detect rotation pairs (inflow + outflow at same time)."""
        pairs = []
        inflows = [s for s in self._active_signals.values()
                   if s.signal_type == 'inflow' and s.is_confirmed]
        outflows = [s for s in self._active_signals.values()
                    if s.signal_type == 'outflow' and s.is_confirmed]

        # Pair highest-scoring inflow with highest-scoring outflow
        if inflows and outflows:
            inflows_sorted = sorted(inflows, key=lambda x: x.rotation_score, reverse=True)
            outflows_sorted = sorted(outflows, key=lambda x: x.rotation_score)

            for inflow in inflows_sorted[:3]:
                for outflow in outflows_sorted[:3]:
                    pairs.append({
                        'from_sector': outflow.sector_code,
                        'to_sector': inflow.sector_code,
                        'score_diff': inflow.rotation_score - outflow.rotation_score,
                        'from_score': outflow.rotation_score,
                        'to_score': inflow.rotation_score,
                    })

        return pairs[:5]  # Top 5 pairs

    def get_market_state(self) -> str:
        """
        Determine overall market state based on signals.

        Returns:
            'risk_on', 'risk_off', or 'neutral'
        """
        confirmed = self.get_confirmed_signals()
        if not confirmed:
            return 'neutral'

        inflow_count = sum(1 for s in confirmed if s.signal_type == 'inflow')
        outflow_count = sum(1 for s in confirmed if s.signal_type == 'outflow')

        if inflow_count > outflow_count * 1.5:
            return 'risk_on'
        elif outflow_count > inflow_count * 1.5:
            return 'risk_off'
        return 'neutral'


def detect_spot_perp_divergence(
    spot_snapshots: Dict[str, SpotSectorSnapshot],
    perp_snapshots: Dict,  # From sector_rotation module
) -> List[SpotPerpDivergence]:
    """
    Detect divergences between spot and perp sector signals.

    Useful for:
    - Smart money detection (spot leading perps = accumulation)
    - Retail speculation (perps leading spot = speculation)
    - Funding arbitrage opportunities

    Args:
        spot_snapshots: Spot sector snapshots
        perp_snapshots: Perp sector snapshots (from sector_rotation)

    Returns:
        List of divergence records
    """
    divergences = []
    now = datetime.utcnow()

    # Map spot sectors to perp sectors (handle naming differences)
    SECTOR_MAP = {
        'DEFI': 'DEFI',
        'DEX': 'DEX',
        'L1': 'L1',
        'L2': 'L2',
        'MEME': 'MEME',
        'AI': 'AI',
        'GAMING': 'GAMING',
        'RWA': 'RWA',
        'DEPIN': 'DEPIN',
        'RESTAKING': 'RESTAKING',
        'MODULAR': 'MODULAR',
        'BTC_ECOSYSTEM': 'BTC_ECOSYSTEM',
        'PRIVACY': 'PRIVACY',
    }

    for spot_code, perp_code in SECTOR_MAP.items():
        spot = spot_snapshots.get(spot_code)
        perp = perp_snapshots.get(perp_code)

        if not spot or not perp:
            continue

        # Get scores
        spot_score = spot.rotation_score
        perp_score = getattr(perp, 'rotation_score', 50)  # Default to neutral

        # Classify signals
        def classify(score):
            if score >= 60:
                return 'inflow'
            elif score <= 40:
                return 'outflow'
            return 'neutral'

        spot_signal = classify(spot_score)
        perp_signal = classify(perp_score)

        # Calculate divergence
        divergence_score = spot_score - perp_score

        # Determine if divergent
        is_divergent = False
        divergence_type = 'aligned'

        if spot_signal != perp_signal and spot_signal != 'neutral' and perp_signal != 'neutral':
            is_divergent = True
            divergence_type = 'opposite_signals'
        elif abs(divergence_score) > 20:
            is_divergent = True
            if divergence_score > 0:
                divergence_type = 'spot_leading'
            else:
                divergence_type = 'perp_leading'

        div = SpotPerpDivergence(
            sector_code=spot_code,
            timestamp=now,
            spot_rotation_score=spot_score,
            perp_rotation_score=perp_score,
            divergence_score=divergence_score,
            spot_signal_type=spot_signal,
            perp_signal_type=perp_signal,
            is_divergent=is_divergent,
            divergence_type=divergence_type,
            spot_volume_zscore=spot.volume_share_zscore,
            perp_volume_zscore=getattr(perp, 'volume_share_zscore', 0),
            perp_funding_rate=getattr(perp, 'avg_funding_rate', 0),
        )
        divergences.append(div)

    return divergences
