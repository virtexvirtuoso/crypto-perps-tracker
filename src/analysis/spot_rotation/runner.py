"""
Spot Rotation Runner - Background Task Orchestration

Manages the spot rotation analysis lifecycle:
- Periodic data collection from CoinGecko
- Signal detection and tracking
- Alert dispatching
- State management
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any

from .storage import (
    SpotSectorSnapshot,
    SPOT_SECTOR_CONFIG,
    COLLECTION_INTERVAL_SECONDS,
)
from .collector import SpotDataCollector, collect_spot_sectors
from .signal_detector import SpotSignalDetector

logger = logging.getLogger(__name__)


class SpotRotationRunner:
    """
    Orchestrates spot sector rotation analysis.

    Responsibilities:
    - Periodic data collection (15-min intervals by default)
    - Signal detection and confirmation
    - State management
    - Integration with perp rotation for divergence detection
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        interval: int = COLLECTION_INTERVAL_SECONDS,
        alerts_enabled: bool = False,
    ):
        """
        Initialize spot rotation runner.

        Args:
            api_key: Optional CoinGecko API key for higher rate limits
            interval: Collection interval in seconds (default: 900 = 15 min)
            alerts_enabled: Whether to send Discord alerts
        """
        self.api_key = api_key
        self.interval = interval
        self.alerts_enabled = alerts_enabled

        # Components
        self.collector = SpotDataCollector(api_key)
        self.detector = SpotSignalDetector()

        # State
        self._latest_snapshots: Dict[str, SpotSectorSnapshot] = {}
        self._is_running = False
        self._last_collection: Optional[datetime] = None
        self._collection_count = 0
        self._error_count = 0

    async def run_once(self) -> Dict[str, SpotSectorSnapshot]:
        """
        Run a single collection and analysis cycle.

        Returns:
            Dictionary of sector snapshots
        """
        logger.info("Starting spot rotation collection cycle...")
        start_time = datetime.utcnow()

        try:
            # Collect data from CoinGecko
            snapshots = await self.collector.collect_all_sectors()

            if not snapshots:
                logger.warning("No spot data collected")
                self._error_count += 1
                return {}

            # Process through signal detector
            signals = self.detector.process_snapshots(snapshots)

            # Update state
            self._latest_snapshots = snapshots
            self._last_collection = datetime.utcnow()
            self._collection_count += 1

            # Log summary
            duration = (datetime.utcnow() - start_time).total_seconds()
            confirmed_count = len(self.detector.get_confirmed_signals())
            logger.info(
                f"Spot rotation cycle complete: "
                f"{len(snapshots)} sectors, "
                f"{len(signals)} active signals, "
                f"{confirmed_count} confirmed, "
                f"{duration:.1f}s"
            )

            return snapshots

        except Exception as e:
            logger.error(f"Spot rotation collection failed: {e}")
            self._error_count += 1
            raise

    async def run_forever(self):
        """
        Run continuous collection loop.

        Collects data at specified intervals until stopped.
        """
        logger.info(
            f"Starting spot rotation runner "
            f"(interval: {self.interval}s, alerts: {self.alerts_enabled})"
        )
        self._is_running = True

        while self._is_running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Collection error (will retry): {e}")

            # Wait for next interval
            await asyncio.sleep(self.interval)

        logger.info("Spot rotation runner stopped")

    def stop(self):
        """Stop the runner loop."""
        self._is_running = False

    # ============================================================================
    # Data Access Methods
    # ============================================================================

    def get_latest_snapshots(self) -> Dict[str, SpotSectorSnapshot]:
        """Get the most recent snapshots for all sectors."""
        return self._latest_snapshots.copy()

    def get_latest_rankings(self) -> list:
        """Get sectors ranked by rotation score."""
        rankings = []
        for sector_code, snapshot in self._latest_snapshots.items():
            rankings.append({
                'sector_code': sector_code,
                'rotation_score': snapshot.rotation_score,
                'signal_strength': snapshot.signal_strength,
                'avg_price_change_24h': snapshot.avg_price_change_24h,
                'avg_price_change_7d': snapshot.avg_price_change_7d,
                'total_market_cap': snapshot.total_market_cap,
                'total_volume_24h': snapshot.total_volume_24h,
                'breadth_ratio_24h': snapshot.breadth_ratio_24h,
                'sector_rs_24h': snapshot.sector_rs_24h,
                'token_count': snapshot.token_count,
                'signal_type': (
                    'inflow' if snapshot.rotation_score >= 60
                    else 'outflow' if snapshot.rotation_score <= 40
                    else 'neutral'
                ),
            })

        return sorted(rankings, key=lambda x: x['rotation_score'], reverse=True)

    def get_confirmed_signals(self) -> list:
        """Get confirmed signals from detector."""
        return self.detector.get_confirmed_signals()

    def get_signal_summary(self) -> Dict[str, Any]:
        """Get signal summary from detector."""
        return self.detector.get_signal_summary()

    def get_market_state(self) -> str:
        """Get overall market state."""
        return self.detector.get_market_state()

    def get_status(self) -> Dict[str, Any]:
        """Get runner status for monitoring."""
        return {
            'is_running': self._is_running,
            'last_collection': self._last_collection.isoformat() if self._last_collection else None,
            'collection_count': self._collection_count,
            'error_count': self._error_count,
            'sectors_tracked': len(SPOT_SECTOR_CONFIG),
            'sectors_with_data': len(self._latest_snapshots),
            'active_signals': len(self.detector.get_all_active_signals()),
            'confirmed_signals': len(self.detector.get_confirmed_signals()),
            'interval_seconds': self.interval,
            'alerts_enabled': self.alerts_enabled,
        }

    async def close(self):
        """Clean up resources."""
        await self.collector.close()


# ============================================================================
# Convenience Functions
# ============================================================================

async def initialize_spot_rotation(
    api_key: Optional[str] = None,
) -> SpotRotationRunner:
    """
    Initialize spot rotation runner.

    Args:
        api_key: Optional CoinGecko API key

    Returns:
        Initialized SpotRotationRunner
    """
    runner = SpotRotationRunner(api_key=api_key)
    return runner


async def start_spot_rotation_task(
    runner: SpotRotationRunner
) -> asyncio.Task:
    """
    Start spot rotation as background task.

    Args:
        runner: SpotRotationRunner instance

    Returns:
        asyncio Task running the runner
    """
    return asyncio.create_task(runner.run_forever())
