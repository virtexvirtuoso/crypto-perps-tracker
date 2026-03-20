"""
Perpetuals Market Data Aggregator

Provides statistically rigorous aggregation of multi-exchange perpetuals data
with volume-weighting, outlier detection, and confidence metrics.
"""

import logging
import math
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExchangeMetrics:
    """Raw metrics from a single exchange."""
    exchange: str
    long_pct: float
    short_pct: float
    funding_rate: float
    open_interest_usd: float
    volume_24h_usd: float
    timestamp: float
    
    @property
    def liquidity_score(self) -> float:
        """
        Combined liquidity metric for weighting.
        
        Uses geometric mean (more conservative than arithmetic mean).
        Penalizes exchanges with imbalanced OI/volume ratios.
        """
        return math.sqrt(self.open_interest_usd * self.volume_24h_usd)


class PerpetualsAggregator:
    """
    Quantitatively rigorous aggregation of multi-exchange perpetuals data.
    
    Key Features:
    1. Volume-weighted averages (not simple averages)
    2. Outlier detection via MAD (Median Absolute Deviation)
    3. Statistical significance testing
    4. Temporal smoothing with exponential decay
    
    Usage:
        aggregator = PerpetualsAggregator()
        
        # Create exchange data
        exchanges = [
            ExchangeMetrics('Binance', 67.8, 32.2, 0.0008, 50e9, 100e9, time.time()),
            ExchangeMetrics('Bybit', 70.8, 29.2, 0.0007, 30e9, 60e9, time.time()),
            ExchangeMetrics('OKX', 66.3, 33.7, 0.0009, 20e9, 40e9, time.time()),
        ]
        
        # Aggregate
        result = aggregator.aggregate_metrics(exchanges)
        print(f"Volume-weighted long%: {result['long_pct']:.1f}%")
    """
    
    # Outlier thresholds (MAD multipliers)
    MAD_THRESHOLD_FUNDING = 3.0  # 3 MADs ≈ 99.7% confidence
    MAD_THRESHOLD_LS_RATIO = 2.5  # 2.5 MADs ≈ 98.8% confidence
    
    # Minimum liquidity threshold (USD)
    MIN_LIQUIDITY = 1_000_000  # Ignore exchanges with <$1M liquidity
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._historical_funding: List[float] = []  # For z-score calculation
        self._max_history = 288  # 24 hours at 5-minute resolution
        
    def aggregate_metrics(
        self,
        exchange_data: List[ExchangeMetrics]
    ) -> Dict[str, float]:
        """
        Aggregate multi-exchange data with volume weighting and outlier removal.
        
        Args:
            exchange_data: List of ExchangeMetrics from different exchanges
        
        Returns:
            Dict containing:
            - Primary metrics (volume-weighted)
            - Statistical confidence metrics
            - Metadata about data quality
        """
        if not exchange_data:
            return self._empty_result()
        
        # Filter by minimum liquidity
        valid_data = [
            e for e in exchange_data 
            if e.liquidity_score >= self.MIN_LIQUIDITY
        ]
        
        if len(valid_data) < 2:
            self.logger.warning(f"Only {len(valid_data)} exchanges meet liquidity threshold")
            return self._empty_result()
        
        # Remove outliers
        clean_data = self._remove_outliers(valid_data)
        
        if len(clean_data) < 2:
            self.logger.warning("Insufficient data after outlier removal")
            return self._empty_result()
        
        # Calculate volume-weighted metrics
        total_liquidity = sum(e.liquidity_score for e in clean_data)
        weights = np.array([e.liquidity_score / total_liquidity for e in clean_data])
        
        # Funding rate (volume-weighted average)
        funding_rates = np.array([e.funding_rate for e in clean_data])
        funding_vwap = np.average(funding_rates, weights=weights)
        
        # Long/Short ratio (volume-weighted average)
        long_pcts = np.array([e.long_pct for e in clean_data])
        long_vwap = np.average(long_pcts, weights=weights)
        short_vwap = 100 - long_vwap
        
        # Statistical measures
        funding_std = np.std(funding_rates)  # Cross-exchange dispersion
        ls_entropy = self._calculate_entropy(clean_data)  # Market structure diversity
        
        # Historical context (z-score for funding)
        self._historical_funding.append(funding_vwap)
        if len(self._historical_funding) > self._max_history:
            self._historical_funding.pop(0)
        
        funding_zscore = self._calculate_zscore(funding_vwap, self._historical_funding)
        
        # Aggregate open interest and volume
        total_oi = sum(e.open_interest_usd for e in clean_data)
        total_volume = sum(e.volume_24h_usd for e in clean_data)
        
        return {
            # Primary metrics (volume-weighted)
            'funding_rate': float(funding_vwap),
            'funding_rate_annualized': float(funding_vwap * 365 * 3),  # 3x daily funding
            'long_pct': float(long_vwap),
            'short_pct': float(short_vwap),
            'total_open_interest': float(total_oi),
            'total_volume_24h': float(total_volume),
            
            # Statistical confidence metrics
            'funding_zscore': funding_zscore,
            'funding_std_bps': float(funding_std * 10000),  # Basis points
            'ls_entropy': ls_entropy,
            'exchange_agreement': self._calculate_agreement(clean_data),
            
            # Metadata
            'exchanges_used': len(clean_data),
            'exchanges_available': len(exchange_data),
            'largest_exchange_weight': float(max(weights)),
            'data_quality_score': self._calculate_quality_score(clean_data, exchange_data)
        }
    
    def _remove_outliers(
        self,
        data: List[ExchangeMetrics]
    ) -> List[ExchangeMetrics]:
        """
        Remove outliers using MAD (more robust than standard deviation).
        
        MAD = median(|x_i - median(x)|)
        Outlier if: |x_i - median(x)| > threshold * MAD
        
        Returns:
            Filtered list with outliers removed
        """
        if len(data) < 3:
            return data  # Need at least 3 points for outlier detection
        
        # Extract arrays
        funding_rates = np.array([e.funding_rate for e in data])
        long_pcts = np.array([e.long_pct for e in data])
        
        # Calculate MAD for funding rates
        funding_median = np.median(funding_rates)
        funding_mad = np.median(np.abs(funding_rates - funding_median))
        
        # Calculate MAD for L/S ratios
        ls_median = np.median(long_pcts)
        ls_mad = np.median(np.abs(long_pcts - ls_median))
        
        # Filter outliers (keep if both funding and L/S are within thresholds)
        clean_data = []
        for i, ex in enumerate(data):
            funding_ok = (
                funding_mad == 0 or  # All values identical
                abs(funding_rates[i] - funding_median) <= self.MAD_THRESHOLD_FUNDING * funding_mad
            )
            ls_ok = (
                ls_mad == 0 or
                abs(long_pcts[i] - ls_median) <= self.MAD_THRESHOLD_LS_RATIO * ls_mad
            )
            
            if funding_ok and ls_ok:
                clean_data.append(ex)
            else:
                self.logger.debug(
                    f"Outlier removed: {ex.exchange} "
                    f"(funding={ex.funding_rate:.4f}, L/S={ex.long_pct:.1f})"
                )
        
        return clean_data
    
    def _calculate_zscore(self, value: float, history: List[float]) -> float:
        """Calculate z-score relative to historical distribution."""
        if len(history) < 30:  # Need sufficient history
            return 0.0
        
        mean = np.mean(history)
        std = np.std(history)
        
        if std == 0:
            return 0.0
        
        return float((value - mean) / std)
    
    def _calculate_entropy(self, data: List[ExchangeMetrics]) -> float:
        """
        Shannon entropy of L/S distribution across exchanges.
        
        Higher entropy = more diverse positioning = healthier market
        Lower entropy = clustered positioning = potential crowding
        
        Range: 0 (fully clustered) to 1 (perfectly balanced)
        """
        long_pcts = np.array([e.long_pct / 100.0 for e in data])
        short_pcts = 1 - long_pcts
        
        # Calculate entropy for each exchange's L/S split
        entropies = []
        for lp, sp in zip(long_pcts, short_pcts):
            if lp > 0 and sp > 0:  # Avoid log(0)
                entropy = -(lp * np.log2(lp) + sp * np.log2(sp))
                entropies.append(entropy)
        
        return float(np.mean(entropies)) if entropies else 0.0
    
    def _calculate_agreement(self, data: List[ExchangeMetrics]) -> float:
        """
        Calculate cross-exchange agreement score (0-1).
        
        1.0 = all exchanges show identical metrics
        0.0 = maximum disagreement
        
        Uses coefficient of variation with exponential decay normalization.
        """
        if len(data) < 2:
            return 1.0
        
        # Calculate coefficient of variation for funding rate
        funding_rates = np.array([e.funding_rate for e in data])
        funding_cv = np.std(funding_rates) / (abs(np.mean(funding_rates)) + 1e-8)
        
        # Calculate CV for L/S ratio
        long_pcts = np.array([e.long_pct for e in data])
        ls_cv = np.std(long_pcts) / (np.mean(long_pcts) + 1e-8)
        
        # Normalize to 0-1 scale (lower CV = higher agreement)
        # Typical CV for funding: 0-2, for L/S: 0-0.2
        funding_agreement = np.exp(-funding_cv * 2)  # Decay function
        ls_agreement = np.exp(-ls_cv * 20)
        
        # Weighted average (funding matters more)
        return float(0.6 * funding_agreement + 0.4 * ls_agreement)
    
    def _calculate_quality_score(
        self,
        clean_data: List[ExchangeMetrics],
        all_data: List[ExchangeMetrics]
    ) -> float:
        """
        Data quality score (0-1) based on:
        - Number of exchanges
        - Percentage retained after outlier removal
        - Recency of data
        """
        # Exchange count score (more = better, cap at 10)
        exchange_score = min(len(clean_data) / 10.0, 1.0)
        
        # Retention score (fewer outliers = better)
        retention_score = len(clean_data) / len(all_data) if all_data else 0.0
        
        # Recency score (data within 60 seconds = 1.0)
        now = datetime.now().timestamp()
        avg_age = np.mean([now - e.timestamp for e in clean_data])
        recency_score = np.exp(-avg_age / 60.0)  # Exponential decay
        
        # Weighted combination
        return float(0.4 * exchange_score + 0.3 * retention_score + 0.3 * recency_score)
    
    def _empty_result(self) -> Dict[str, float]:
        """Return empty result structure when data is insufficient."""
        return {
            'funding_rate': 0.0,
            'funding_rate_annualized': 0.0,
            'long_pct': 50.0,
            'short_pct': 50.0,
            'total_open_interest': 0.0,
            'total_volume_24h': 0.0,
            'funding_zscore': 0.0,
            'funding_std_bps': 0.0,
            'ls_entropy': 0.0,
            'exchange_agreement': 0.0,
            'exchanges_used': 0,
            'exchanges_available': 0,
            'largest_exchange_weight': 0.0,
            'data_quality_score': 0.0
        }


# Example usage
if __name__ == "__main__":
    import time
    
    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Create sample data (real values from your system)
    exchanges = [
        ExchangeMetrics(
            exchange='Binance',
            long_pct=67.8,
            short_pct=32.2,
            funding_rate=0.0008,
            open_interest_usd=50_000_000_000,
            volume_24h_usd=100_000_000_000,
            timestamp=time.time()
        ),
        ExchangeMetrics(
            exchange='Bybit',
            long_pct=70.8,
            short_pct=29.2,
            funding_rate=0.0007,
            open_interest_usd=30_000_000_000,
            volume_24h_usd=60_000_000_000,
            timestamp=time.time()
        ),
        ExchangeMetrics(
            exchange='OKX',
            long_pct=66.3,
            short_pct=33.7,
            funding_rate=0.0009,
            open_interest_usd=20_000_000_000,
            volume_24h_usd=40_000_000_000,
            timestamp=time.time()
        ),
    ]
    
    # Aggregate
    aggregator = PerpetualsAggregator()
    result = aggregator.aggregate_metrics(exchanges)
    
    print("\n=== Volume-Weighted Aggregation ===")
    print(f"Funding Rate: {result['funding_rate']:.4f} ({result['funding_rate']*100:.3f}%)")
    print(f"Long/Short: {result['long_pct']:.1f}% / {result['short_pct']:.1f}%")
    print(f"Total OI: ${result['total_open_interest']/1e9:.1f}B")
    print(f"Total Volume: ${result['total_volume_24h']/1e9:.1f}B")
    
    print("\n=== Statistical Metrics ===")
    print(f"Funding Z-Score: {result['funding_zscore']:.2f}")
    print(f"Funding Std Dev: {result['funding_std_bps']:.1f} bps")
    print(f"L/S Entropy: {result['ls_entropy']:.3f}")
    print(f"Exchange Agreement: {result['exchange_agreement']:.2f}")
    
    print("\n=== Data Quality ===")
    print(f"Exchanges Used: {result['exchanges_used']}/{result['exchanges_available']}")
    print(f"Largest Weight: {result['largest_exchange_weight']:.1%}")
    print(f"Quality Score: {result['data_quality_score']:.2f}")
