"""Derivatives-based predictive signals module

This module provides advanced trading signals derived from derivatives market data,
including funding rates, open interest, long/short ratios, liquidations, and more.

Includes multi-exchange signal aggregation for higher confidence signals.
"""

from src.signals.models import (
    SignalType,
    SignalDirection,
    SignalStrength,
    BaseSignal,
    FundingRateSignal,
    OpenInterestSignal,
    LongShortRatioSignal,
    LiquidationSignal,
    BasisSignal,
    CVDSignal,
    OptionsIVSignal,
    FusionSignal,
)

from src.signals.aggregator import (
    AggregatedSignalCalculator,
    AggregatedLSRSignal,
    AggregatedFundingSignal,
)

__all__ = [
    # Signal types and models
    'SignalType',
    'SignalDirection',
    'SignalStrength',
    'BaseSignal',
    'FundingRateSignal',
    'OpenInterestSignal',
    'LongShortRatioSignal',
    'LiquidationSignal',
    'BasisSignal',
    'CVDSignal',
    'OptionsIVSignal',
    'FusionSignal',
    # Aggregated signals
    'AggregatedSignalCalculator',
    'AggregatedLSRSignal',
    'AggregatedFundingSignal',
]
