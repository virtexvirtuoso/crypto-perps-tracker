"""
Spot Rotation Analysis - CoinGecko Version

This module provides spot market sector rotation analysis using CoinGecko data.
Complements the perp rotation module with spot-specific metrics.

Key Features:
- 5-factor rotation scoring (no funding/OI, uses market cap)
- Multi-timeframe price momentum (1h, 24h, 7d, 30d)
- Market cap tier distribution analysis
- Spot/perp divergence detection

Usage:
    from src.analysis.spot_rotation import SpotRotationRunner

    # Run analysis
    runner = SpotRotationRunner()
    results = await runner.run_once()

    # Or continuous background task
    await runner.run_forever()
"""

from .storage import (
    # Enums
    SignalStrength,
    SampleSizeFlag,
    MarketCapTier,
    # Config
    SPOT_SECTOR_CONFIG,
    SPOT_SECTOR_METADATA,
    SMALL_SAMPLE_SECTORS,
    COINGECKO_RATE_LIMIT,
    COINGECKO_BATCH_SIZE,
    COLLECTION_INTERVAL_SECONDS,
    # Dataclasses
    TokenSnapshot,
    SpotSectorSnapshot,
    SpotSectorSignal,
    SpotPerpDivergence,
    # Helper functions
    get_sector_for_token,
    get_all_token_ids,
    get_sector_metadata,
    classify_market_cap_tier,
    get_sectors_by_tier,
)

from .collector import (
    CoinGeckoClient,
    SpotDataCollector,
    GlobalMarketData,
    collect_spot_sectors,
)

from .signal_detector import (
    SpotSignalDetector,
    detect_spot_perp_divergence,
)

from .runner import (
    SpotRotationRunner,
    initialize_spot_rotation,
    start_spot_rotation_task,
)

__all__ = [
    # Enums
    'SignalStrength',
    'SampleSizeFlag',
    'MarketCapTier',
    # Config
    'SPOT_SECTOR_CONFIG',
    'SPOT_SECTOR_METADATA',
    'SMALL_SAMPLE_SECTORS',
    'COINGECKO_RATE_LIMIT',
    'COINGECKO_BATCH_SIZE',
    'COLLECTION_INTERVAL_SECONDS',
    # Dataclasses
    'TokenSnapshot',
    'SpotSectorSnapshot',
    'SpotSectorSignal',
    'SpotPerpDivergence',
    'GlobalMarketData',
    # Helper functions
    'get_sector_for_token',
    'get_all_token_ids',
    'get_sector_metadata',
    'classify_market_cap_tier',
    'get_sectors_by_tier',
    # Core components
    'CoinGeckoClient',
    'SpotDataCollector',
    'collect_spot_sectors',
    'SpotSignalDetector',
    'detect_spot_perp_divergence',
    'SpotRotationRunner',
    'initialize_spot_rotation',
    'start_spot_rotation_task',
]
