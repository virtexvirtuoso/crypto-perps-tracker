"""
Sector Rotation Signal Detector - Multi-Exchange 8-Factor Scoring

Enhanced from Virtuoso_ccxt with:
- 8th factor: CEX↔DEX flow (institutional vs retail detection)
- Cross-exchange funding spread analysis
- Exchange consensus scoring
- Multi-timeframe pattern detection

Design Note: Signals require 2+ consecutive snapshots at MODERATE+ strength
before being considered confirmed (avoids false positives from noise).
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

import numpy as np

from .storage import (
    SectorSnapshot,
    SectorSignal,
    SignalStrength,
    OIPriceSignal,
    SampleSizeFlag,
    SECTOR_CONFIG,
    SMALL_SAMPLE_SECTORS,
    get_sector_metadata,
)

logger = logging.getLogger(__name__)


class SectorSignalDetector:
    """
    Detects and confirms sector rotation signals from multi-exchange snapshots.

    Uses an 8-factor composite scoring system with the new CEX↔DEX flow factor:
    1. Volume z-score (18%)
    2. OI-Price signal (15%)
    3. Momentum (15%)
    4. Funding divergence (12%)
    5. Breadth (12%)
    6. Correlation breakdown (10%)
    7. Relative strength (8%)
    8. CEX↔DEX flow (10%) - NEW
    """

    # 8-Factor scoring weights (sum to 1.0)
    SCORING_WEIGHTS = {
        'volume_zscore': 0.18,          # Unusual cross-exchange volume
        'oi_signal': 0.15,              # OI-Price matrix (multi-exchange)
        'momentum': 0.15,               # Price momentum
        'funding_divergence': 0.12,     # Cross-exchange funding spread
        'breadth': 0.12,                # Up/down ratio
        'correlation_breakdown': 0.10,  # BTC correlation z-score
        'relative_strength': 0.08,      # Sector RS vs BTC
        'cex_dex_flow': 0.10,           # NEW: CEX↔DEX volume shift
    }

    # Signal classification thresholds
    INFLOW_THRESHOLD = 65       # Score >= 65 = inflow signal
    OUTFLOW_THRESHOLD = 35      # Score <= 35 = outflow signal
    ROTATION_THRESHOLD = 50     # Used for pair detection

    # Confirmation requirements
    MIN_CONFIRMATION_PERIODS = 2    # Need 2+ consecutive signals
    SIGNAL_EXPIRY_HOURS = 24        # Signals expire if not re-confirmed

    # Z-score thresholds
    EXTREME_ZSCORE = 2.0
    SIGNIFICANT_ZSCORE = 1.5

    # Funding spread thresholds (basis points)
    FUNDING_SPREAD_EXTREME = 0.05   # 5 bps spread = extreme
    FUNDING_SPREAD_SIGNIFICANT = 0.02  # 2 bps spread = significant

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize signal detector.

        Args:
            config: Optional configuration overrides
        """
        self.config = config or {}
        self.logger = logger

        # Apply config overrides
        if 'scoring_weights' in self.config:
            self.SCORING_WEIGHTS.update(self.config['scoring_weights'])

        # Normalize weights to sum to 1.0
        total = sum(self.SCORING_WEIGHTS.values())
        if abs(total - 1.0) > 0.001:
            self.SCORING_WEIGHTS = {
                k: v / total for k, v in self.SCORING_WEIGHTS.items()
            }

        # Track active signals for confirmation logic
        self._active_signals: Dict[str, SectorSignal] = {}

        # Historical snapshots for statistical calculations
        self._snapshot_history: Dict[str, List[SectorSnapshot]] = defaultdict(list)
        self._max_history = 100  # Keep last 100 snapshots per sector

        self.logger.info("SectorSignalDetector initialized with 8-factor scoring")

    def detect_signals(
        self,
        snapshots: Dict[str, SectorSnapshot]
    ) -> List[SectorSignal]:
        """
        Detect rotation signals from a batch of sector snapshots.

        Args:
            snapshots: Dict of sector_code -> SectorSnapshot

        Returns:
            List of detected/updated SectorSignal objects
        """
        if not snapshots:
            return []

        self.logger.debug(f"Processing {len(snapshots)} snapshots for signals")

        # Update history for z-score calculations
        for sector_code, snapshot in snapshots.items():
            self._update_history(sector_code, snapshot)

        detected_signals = []
        timestamp = datetime.utcnow()

        # Step 1: Calculate rotation score for each sector
        scored_sectors = []
        for sector_code, snapshot in snapshots.items():
            # Calculate z-scores from history
            self._calculate_zscores(snapshot)

            # Calculate 8-factor rotation score
            score = self._calculate_rotation_score(snapshot)
            snapshot.rotation_score = score
            snapshot.signal_strength = self._classify_strength(score).value
            scored_sectors.append((snapshot, score))

        # Step 2: Sort by score
        scored_sectors.sort(key=lambda x: x[1], reverse=True)

        # Log top/bottom sectors
        if scored_sectors:
            top = scored_sectors[0]
            bottom = scored_sectors[-1]
            self.logger.info(
                f"Rotation scores: Top={top[0].sector_code}({top[1]:.1f}), "
                f"Bottom={bottom[0].sector_code}({bottom[1]:.1f})"
            )

        # Step 3: Detect individual sector signals
        for snapshot, score in scored_sectors:
            signal = self._detect_sector_signal(snapshot, score, timestamp)
            if signal:
                detected_signals.append(signal)

        # Step 4: Detect rotation pairs
        rotation_pairs = self._detect_rotation_pairs(scored_sectors)
        detected_signals.extend(rotation_pairs)

        # Step 5: Expire old signals
        self._expire_old_signals()

        self.logger.info(f"Detected {len(detected_signals)} rotation signals")

        return detected_signals

    def _update_history(self, sector_code: str, snapshot: SectorSnapshot) -> None:
        """Add snapshot to history, maintaining max size."""
        history = self._snapshot_history[sector_code]
        history.append(snapshot)
        if len(history) > self._max_history:
            self._snapshot_history[sector_code] = history[-self._max_history:]

    def _calculate_zscores(self, snapshot: SectorSnapshot) -> None:
        """
        Calculate z-scores for metrics that require historical context.

        Updates the snapshot in place with calculated z-scores.
        """
        sector_code = snapshot.sector_code
        history = self._snapshot_history.get(sector_code, [])

        if len(history) < 10:
            # Not enough history for meaningful z-scores
            snapshot.volume_share_zscore = 0.0
            snapshot.funding_spread_zscore = 0.0
            snapshot.cex_dex_flow_zscore = 0.0
            snapshot.confidence_level = 0.5
            return

        # Volume share z-score
        volumes = [s.volume_share_pct for s in history if s.volume_share_pct > 0]
        if len(volumes) >= 5:
            mean_vol = np.mean(volumes)
            std_vol = np.std(volumes)
            if std_vol > 0:
                snapshot.volume_share_zscore = (snapshot.volume_share_pct - mean_vol) / std_vol

        # Funding spread z-score
        spreads = [s.funding_spread for s in history if s.funding_spread is not None]
        if len(spreads) >= 5:
            mean_spread = np.mean(spreads)
            std_spread = np.std(spreads)
            if std_spread > 0:
                snapshot.funding_spread_zscore = (snapshot.funding_spread - mean_spread) / std_spread

        # CEX/DEX flow z-score
        flows = [s.cex_dex_flow_score for s in history]
        if len(flows) >= 5:
            mean_flow = np.mean(flows)
            std_flow = np.std(flows)
            if std_flow > 0:
                snapshot.cex_dex_flow_zscore = (snapshot.cex_dex_flow_score - mean_flow) / std_flow

        # Confidence level based on data quality and sample size
        confidence = snapshot.data_quality_score
        if sector_code in SMALL_SAMPLE_SECTORS:
            confidence *= 0.8  # Reduce confidence for small sectors
        if snapshot.exchange_count < 4:
            confidence *= 0.9  # Reduce confidence for few exchanges
        snapshot.confidence_level = max(0.3, min(1.0, confidence))

    def _calculate_rotation_score(self, snapshot: SectorSnapshot) -> float:
        """
        Calculate composite 8-factor rotation score (0-100).

        Higher scores indicate inflow (bullish rotation into sector).
        Lower scores indicate outflow (bearish rotation out of sector).
        """
        scores = {}

        # 1. Volume z-score (normalized to 0-100)
        # z=+2 → 100, z=0 → 50, z=-2 → 0
        vol_z = np.clip(snapshot.volume_share_zscore, -3, 3)
        scores['volume_zscore'] = 50 + (vol_z / 3) * 50

        # 2. OI-Price signal interpretation
        oi_signal_scores = {
            OIPriceSignal.NEW_LONGS.value: 85,
            OIPriceSignal.SHORT_COVER.value: 70,
            OIPriceSignal.NEUTRAL.value: 50,
            OIPriceSignal.NEW_SHORTS.value: 30,
            OIPriceSignal.LONG_LIQUIDATION.value: 15,
        }
        scores['oi_signal'] = oi_signal_scores.get(snapshot.oi_price_signal, 50)

        # 3. Momentum score
        # Price change normalized to score
        price_change = np.clip(snapshot.avg_price_change_24h / 20, -1, 1)  # ±20% max
        scores['momentum'] = 50 + (price_change * 40)

        # 4. Funding divergence (cross-exchange spread)
        # High spread + extreme funding = contrarian signal
        # Normalize spread: 0.05 (5bps) spread → extreme
        spread_score = 50
        if snapshot.funding_spread > 0:
            spread_normalized = min(snapshot.funding_spread / self.FUNDING_SPREAD_EXTREME, 1.0)
            # High spread with positive avg funding → bearish (too crowded long)
            # High spread with negative avg funding → bullish (contrarian)
            if snapshot.avg_funding_rate > 0.0001:
                spread_score = 50 - (spread_normalized * 30)
            elif snapshot.avg_funding_rate < -0.0001:
                spread_score = 50 + (spread_normalized * 30)
        scores['funding_divergence'] = spread_score

        # 5. Breadth
        # Simple breadth ratio (0-1) scaled to 0-100
        scores['breadth'] = snapshot.breadth_ratio * 100

        # 6. Correlation breakdown
        # Lower correlation = more independent = higher rotation signal
        corr_z = snapshot.btc_correlation_zscore if hasattr(snapshot, 'btc_correlation_zscore') else 0
        # Negative z-score means lower-than-usual correlation (divergence)
        scores['correlation_breakdown'] = 50 - np.clip(corr_z, -3, 3) * 16.67

        # 7. Relative strength vs BTC
        rs = snapshot.sector_rs if hasattr(snapshot, 'sector_rs') else 0
        rs_normalized = np.clip(rs / 10, -1, 1)  # ±10% max
        scores['relative_strength'] = 50 + (rs_normalized * 50)

        # 8. NEW: CEX↔DEX Flow Score
        # Positive = CEX favored (institutional), Negative = DEX favored (retail/degen)
        # Unusual shifts are significant
        cex_dex_score = 50
        flow = snapshot.cex_dex_flow_score
        flow_z = snapshot.cex_dex_flow_zscore if hasattr(snapshot, 'cex_dex_flow_zscore') else 0

        # Interpretation:
        # - Unusual CEX inflow (positive flow, high z) → institutional buying → bullish
        # - Unusual DEX inflow (negative flow, high |z|) → retail FOMO → mixed signal
        if abs(flow_z) > self.SIGNIFICANT_ZSCORE:
            if flow > 0:
                # CEX-favored unusual flow → institutional = bullish
                cex_dex_score = 50 + (flow_z / 3) * 25
            else:
                # DEX-favored unusual flow → retail FOMO, less reliable
                cex_dex_score = 50 + (flow_z / 3) * 15
        else:
            # Normal flow distribution
            cex_dex_score = 50 + (flow * 20)

        scores['cex_dex_flow'] = np.clip(cex_dex_score, 0, 100)

        # Calculate weighted sum
        total_score = sum(
            scores.get(factor, 50) * weight
            for factor, weight in self.SCORING_WEIGHTS.items()
        )

        # Apply confidence adjustment for low-confidence sectors
        if snapshot.confidence_level < 1.0:
            # Shrink extreme scores toward 50
            shrink_factor = snapshot.confidence_level
            total_score = 50 + (total_score - 50) * shrink_factor

        return np.clip(total_score, 0, 100)

    def _classify_strength(self, score: float) -> SignalStrength:
        """Classify score into signal strength category."""
        distance = abs(score - 50)

        if distance >= 30:  # Score >= 80 or <= 20
            return SignalStrength.STRONG
        elif distance >= 15:  # Score >= 65 or <= 35
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def _detect_sector_signal(
        self,
        snapshot: SectorSnapshot,
        score: float,
        timestamp: datetime
    ) -> Optional[SectorSignal]:
        """
        Detect and confirm individual sector inflow/outflow signals.
        """
        sector_code = snapshot.sector_code
        strength = self._classify_strength(score)

        # Skip weak signals
        if strength == SignalStrength.WEAK:
            return None

        # Determine signal type
        if score >= self.INFLOW_THRESHOLD:
            signal_type = "inflow"
        elif score <= self.OUTFLOW_THRESHOLD:
            signal_type = "outflow"
        else:
            return None

        # Check for existing signal
        existing_signal = self._active_signals.get(sector_code)

        if existing_signal and existing_signal.signal_type == signal_type:
            # Confirmation - extend the signal
            existing_signal.confirmation_count += 1
            existing_signal.last_confirmed = timestamp
            existing_signal.rotation_score = score
            existing_signal.signal_strength = strength.value

            # Update multi-exchange context
            existing_signal.funding_spread = snapshot.funding_spread
            existing_signal.cex_dex_flow = snapshot.cex_dex_flow_score
            existing_signal.exchange_consensus = self._calculate_exchange_consensus(snapshot)

            # Mark as confirmed after MIN_CONFIRMATION_PERIODS
            if existing_signal.confirmation_count >= self.MIN_CONFIRMATION_PERIODS:
                if not existing_signal.is_confirmed:
                    self.logger.info(
                        f"✅ CONFIRMED {signal_type.upper()} signal for {sector_code} "
                        f"(score={score:.1f}, confirmations={existing_signal.confirmation_count})"
                    )
                existing_signal.is_confirmed = True

            return existing_signal

        else:
            # New signal
            new_signal = SectorSignal(
                sector_code=sector_code,
                signal_type=signal_type,
                signal_strength=strength.value,
                rotation_score=score,
                first_detected=timestamp,
                last_confirmed=timestamp,
                confirmation_count=1,
                is_confirmed=False,
                volume_zscore=snapshot.volume_share_zscore,
                btc_correlation=snapshot.btc_correlation,
                oi_signal=snapshot.oi_price_signal,
                breadth=snapshot.breadth_ratio,
                # Multi-exchange context
                funding_spread=snapshot.funding_spread,
                cex_dex_flow=snapshot.cex_dex_flow_score,
                exchange_consensus=self._calculate_exchange_consensus(snapshot),
                confidence_level=snapshot.confidence_level,
                is_active=True,
            )

            self._active_signals[sector_code] = new_signal

            self.logger.info(
                f"🔍 New {signal_type} signal detected for {sector_code} "
                f"(score={score:.1f}, strength={strength.value})"
            )

            return new_signal

    def _calculate_exchange_consensus(self, snapshot: SectorSnapshot) -> float:
        """
        Calculate what % of exchanges agree on direction.

        Uses exchange breakdown to determine if most exchanges show same trend.
        """
        if not snapshot.exchange_breakdown:
            return 0.5

        # Count exchanges showing positive vs negative price change
        # (Would need price change per exchange, approximating from funding)
        positive_count = sum(
            1 for eb in snapshot.exchange_breakdown
            if eb.avg_funding_rate > 0
        )
        total = len(snapshot.exchange_breakdown)

        if total == 0:
            return 0.5

        # Return ratio in dominant direction
        ratio = positive_count / total
        return max(ratio, 1 - ratio)

    def _detect_rotation_pairs(
        self,
        scored_sectors: List[Tuple[SectorSnapshot, float]]
    ) -> List[SectorSignal]:
        """
        Detect rotation pairs: capital moving from sector A to sector B.
        """
        rotation_signals = []

        if len(scored_sectors) < 2:
            return rotation_signals

        # Find outflow sectors (bottom scores)
        outflow_sectors = [
            (s, score) for s, score in scored_sectors
            if score <= self.OUTFLOW_THRESHOLD
        ]

        # Find inflow sectors (top scores)
        inflow_sectors = [
            (s, score) for s, score in scored_sectors
            if score >= self.INFLOW_THRESHOLD
        ]

        # Create pairs
        for outflow_snap, out_score in outflow_sectors:
            for inflow_snap, in_score in inflow_sectors:
                # Check strength requirements
                out_strength = self._classify_strength(out_score)
                in_strength = self._classify_strength(in_score)

                if out_strength == SignalStrength.WEAK or in_strength == SignalStrength.WEAK:
                    continue

                # Check for significant score differential
                differential = in_score - out_score
                if differential < 40:
                    continue

                # Create rotation pair signal
                pair_key = f"{outflow_snap.sector_code}_to_{inflow_snap.sector_code}"
                existing = self._active_signals.get(pair_key)

                if existing and existing.signal_type == "rotation":
                    # Extend existing rotation signal
                    existing.confirmation_count += 1
                    existing.last_confirmed = datetime.utcnow()
                    existing.rotation_score = differential

                    if existing.confirmation_count >= self.MIN_CONFIRMATION_PERIODS:
                        if not existing.is_confirmed:
                            self.logger.info(
                                f"🔄 CONFIRMED ROTATION: {outflow_snap.sector_code} → "
                                f"{inflow_snap.sector_code} (differential={differential:.1f})"
                            )
                        existing.is_confirmed = True

                    rotation_signals.append(existing)

                else:
                    # New rotation pair
                    pair_signal = SectorSignal(
                        sector_code=pair_key,
                        signal_type="rotation",
                        signal_strength=SignalStrength.MODERATE.value,
                        rotation_score=differential,
                        first_detected=datetime.utcnow(),
                        last_confirmed=datetime.utcnow(),
                        confirmation_count=1,
                        is_confirmed=False,
                        from_sector=outflow_snap.sector_code,
                        to_sector=inflow_snap.sector_code,
                        is_active=True,
                    )

                    self._active_signals[pair_key] = pair_signal

                    self.logger.info(
                        f"🔍 Rotation pair detected: {outflow_snap.sector_code} → "
                        f"{inflow_snap.sector_code} (differential={differential:.1f})"
                    )

                    rotation_signals.append(pair_signal)

        return rotation_signals

    def _expire_old_signals(self) -> None:
        """Expire signals that haven't been confirmed recently."""
        now = datetime.utcnow()
        expiry_threshold = now - timedelta(hours=self.SIGNAL_EXPIRY_HOURS)

        expired_keys = []
        for key, signal in self._active_signals.items():
            if signal.last_confirmed < expiry_threshold:
                signal.is_active = False
                signal.expired_at = now
                expired_keys.append(key)
                self.logger.info(f"Signal expired: {key}")

        for key in expired_keys:
            del self._active_signals[key]

    # =========================================================================
    # Public API Methods
    # =========================================================================

    def get_confirmed_signals(self) -> List[SectorSignal]:
        """Get all currently confirmed and active signals."""
        return [
            signal for signal in self._active_signals.values()
            if signal.is_confirmed and signal.is_active
        ]

    def get_all_active_signals(self) -> List[SectorSignal]:
        """Get all active signals (confirmed and unconfirmed)."""
        return list(self._active_signals.values())

    def get_sector_rankings(
        self,
        snapshots: Dict[str, SectorSnapshot]
    ) -> List[Dict[str, Any]]:
        """
        Get sectors ranked by rotation score for dashboard display.
        """
        rankings = []

        for sector_code, snapshot in snapshots.items():
            # Calculate z-scores if not already done
            self._calculate_zscores(snapshot)
            score = self._calculate_rotation_score(snapshot)
            metadata = get_sector_metadata(sector_code)

            rankings.append({
                'rank': 0,  # Set below
                'sector_code': sector_code,
                'sector_name': metadata['name'],
                'emoji': metadata['emoji'],
                'rotation_score': round(score, 1),
                'signal_strength': self._classify_strength(score).value,
                'signal_type': (
                    'inflow' if score >= self.INFLOW_THRESHOLD else
                    'outflow' if score <= self.OUTFLOW_THRESHOLD else
                    'neutral'
                ),
                # Key metrics
                'volume_zscore': round(snapshot.volume_share_zscore, 2),
                'btc_correlation': round(snapshot.btc_correlation, 2),
                'oi_signal': snapshot.oi_price_signal,
                'breadth': round(snapshot.breadth_ratio * 100, 1),
                'funding_spread': round(snapshot.funding_spread * 10000, 2),  # bps
                'cex_dex_flow': round(snapshot.cex_dex_flow_score, 3),
                # Quality
                'symbol_count': snapshot.symbol_count,
                'exchange_count': snapshot.exchange_count,
                'confidence': round(snapshot.confidence_level * 100, 0),
            })

        # Sort by rotation score descending
        rankings.sort(key=lambda x: x['rotation_score'], reverse=True)

        # Add rank position
        for i, ranking in enumerate(rankings):
            ranking['rank'] = i + 1

        return rankings

    def get_signal_summary(self) -> Dict[str, Any]:
        """Get summary statistics for current signals."""
        confirmed = self.get_confirmed_signals()
        active = self.get_all_active_signals()

        inflows = [s for s in confirmed if s.signal_type == 'inflow']
        outflows = [s for s in confirmed if s.signal_type == 'outflow']
        rotations = [s for s in confirmed if s.signal_type == 'rotation']

        return {
            'active_signals': len(active),
            'confirmed_signals': len(confirmed),
            'inflow_count': len(inflows),
            'outflow_count': len(outflows),
            'rotation_pairs': len(rotations),
            'inflow_sectors': [s.sector_code for s in inflows],
            'outflow_sectors': [s.sector_code for s in outflows],
            'rotation_pairs_list': [
                {'from': s.from_sector, 'to': s.to_sector}
                for s in rotations
            ],
            'sectors_analyzed': len(SECTOR_CONFIG),
            'timestamp': datetime.utcnow().isoformat(),
        }

    def get_market_state(
        self,
        snapshots: Dict[str, SectorSnapshot]
    ) -> str:
        """
        Determine overall market state from sector signals.

        Returns: 'risk_on', 'risk_off', or 'neutral'
        """
        if not snapshots:
            return 'neutral'

        # Calculate average rotation score
        scores = []
        for sector_code, snapshot in snapshots.items():
            self._calculate_zscores(snapshot)
            score = self._calculate_rotation_score(snapshot)
            scores.append(score)

        avg_score = np.mean(scores)

        # Check CEX/DEX flow trend
        avg_cex_flow = np.mean([s.cex_dex_flow_score for s in snapshots.values()])

        if avg_score >= 60 and avg_cex_flow > 0:
            return 'risk_on'
        elif avg_score <= 40 or avg_cex_flow < -0.1:
            return 'risk_off'
        else:
            return 'neutral'
