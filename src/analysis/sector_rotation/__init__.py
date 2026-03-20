"""
Sector Rotation Analysis - Multi-Exchange Version

This module provides sector rotation analysis across 8 perpetual futures exchanges
covering 91.7% of market volume (Binance, OKX, Bybit, Gate.io, Bitget, HyperLiquid,
AsterDEX, dYdX).

Key Features:
- Multi-exchange data aggregation with volume-weighted metrics
- CEX vs DEX flow analysis for institutional/retail detection
- Cross-exchange funding spread signals
- 8-factor scoring with enhanced signal detection

Usage:
    from src.analysis.sector_rotation import SectorRotationRunner

    # Run analysis
    runner = SectorRotationRunner()
    results = await runner.run_once()

    # Or continuous background task
    await runner.run_forever()
"""

from .storage import (
    # Enums
    SignalStrength,
    OIPriceSignal,
    SampleSizeFlag,
    ExchangeCategory,
    # Config
    EXCHANGE_CONFIG,
    SECTOR_CONFIG,
    SECTOR_METADATA,
    EXCHANGE_SYMBOL_MAP,
    SMALL_SAMPLE_SECTORS,
    CEX_TOTAL_WEIGHT,
    DEX_TOTAL_WEIGHT,
    # Dataclasses
    ExchangeBreakdown,
    SectorSnapshot,
    SectorSignal,
    SectorCorrelation,
    # Helper functions
    get_sector_for_symbol,
    get_all_base_symbols,
    format_symbol_for_exchange,
    get_enabled_exchanges,
    get_cex_exchanges,
    get_dex_exchanges,
    get_exchange_weight,
    get_sector_metadata,
)

from .collector import SectorDataCollector, collect_sectors_async
from .signal_detector import SectorSignalDetector
from .alerter import SectorRotationAlerter
from .runner import SectorRotationRunner
from .db_storage import SectorRotationStorage

__all__ = [
    # Enums
    'SignalStrength',
    'OIPriceSignal',
    'SampleSizeFlag',
    'ExchangeCategory',
    # Config
    'EXCHANGE_CONFIG',
    'SECTOR_CONFIG',
    'SECTOR_METADATA',
    'EXCHANGE_SYMBOL_MAP',
    'SMALL_SAMPLE_SECTORS',
    'CEX_TOTAL_WEIGHT',
    'DEX_TOTAL_WEIGHT',
    # Dataclasses
    'ExchangeBreakdown',
    'SectorSnapshot',
    'SectorSignal',
    'SectorCorrelation',
    # Helper functions
    'get_sector_for_symbol',
    'get_all_base_symbols',
    'format_symbol_for_exchange',
    'get_enabled_exchanges',
    'get_cex_exchanges',
    'get_dex_exchanges',
    'get_exchange_weight',
    'get_sector_metadata',
    # Core components
    'SectorDataCollector',
    'collect_sectors_async',
    'SectorSignalDetector',
    'SectorRotationAlerter',
    'SectorRotationRunner',
    'SectorRotationStorage',
]
