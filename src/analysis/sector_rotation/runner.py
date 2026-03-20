"""
Sector Rotation Background Runner

Orchestrates periodic collection, signal detection, and alerting.
Can be run as a background task in FastAPI or as a standalone process.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Callable, Any

from .storage import SectorSnapshot, SECTOR_CONFIG
from .collector import SectorDataCollector, collect_sectors_async
from .signal_detector import SectorSignalDetector
from .alerter import SectorRotationAlerter

logger = logging.getLogger(__name__)


class SectorRotationRunner:
    """
    Background runner for sector rotation analysis.

    Manages the collection → detection → alert pipeline on a configurable interval.

    Usage:
        runner = SectorRotationRunner()

        # As async task
        await runner.run_forever()

        # Or single run
        results = await runner.run_once()
    """

    # Collection interval (4 hours for sector rotation)
    DEFAULT_INTERVAL_SECONDS = 4 * 60 * 60  # 4 hours

    def __init__(
        self,
        interval_seconds: int = None,
        discord_webhook: Optional[str] = None,
        alerts_enabled: bool = True,
        on_collection: Optional[Callable[[Dict[str, SectorSnapshot]], None]] = None,
    ):
        """
        Initialize runner.

        Args:
            interval_seconds: Collection interval (default 4 hours)
            discord_webhook: Discord webhook URL for alerts
            alerts_enabled: Whether to send Discord alerts
            on_collection: Optional callback after each collection
        """
        self.interval = interval_seconds or self.DEFAULT_INTERVAL_SECONDS
        self.on_collection = on_collection

        # Initialize components
        self.collector = SectorDataCollector()
        self.detector = SectorSignalDetector()
        self.alerter = SectorRotationAlerter(
            webhook_url=discord_webhook,
            enabled=alerts_enabled,
        )

        # State tracking
        self._running = False
        self._last_run: Optional[datetime] = None
        self._last_snapshots: Dict[str, SectorSnapshot] = {}
        self._last_market_state: str = 'neutral'
        self._run_count = 0

        logger.info(
            f"SectorRotationRunner initialized "
            f"(interval={self.interval}s, alerts={'ON' if alerts_enabled else 'OFF'})"
        )

    async def run_once(self) -> Dict[str, Any]:
        """
        Run a single collection and detection cycle.

        Returns:
            Dict with snapshots, signals, and summary
        """
        start_time = datetime.utcnow()
        logger.info("Starting sector rotation cycle...")

        try:
            # 1. Collect data from all exchanges
            snapshots = await collect_sectors_async(
                collector=self.collector,
                prior_snapshots=self._last_snapshots,
            )

            # 2. Detect signals
            signals = self.detector.detect_signals(snapshots)

            # 3. Get rankings and summary
            rankings = self.detector.get_sector_rankings(snapshots)
            summary = self.detector.get_signal_summary()
            market_state = self.detector.get_market_state(snapshots)

            # 4. Send alerts for confirmed signals
            confirmed_signals = [s for s in signals if s.is_confirmed]
            for signal in confirmed_signals:
                snapshot = snapshots.get(signal.sector_code)

                if signal.signal_type == 'rotation':
                    from_snap = snapshots.get(signal.from_sector)
                    to_snap = snapshots.get(signal.to_sector)
                    self.alerter.alert_rotation_pair(signal, from_snap, to_snap)
                else:
                    self.alerter.alert_confirmed_signal(signal, snapshot)

            # 5. Check for market state change
            if market_state != self._last_market_state:
                self.alerter.alert_market_state_change(
                    market_state,
                    self._last_market_state,
                    summary,
                )
                self._last_market_state = market_state

            # 6. Call optional callback
            if self.on_collection:
                try:
                    self.on_collection(snapshots)
                except Exception as e:
                    logger.error(f"on_collection callback error: {e}")

            # Update state
            self._last_snapshots = snapshots
            self._last_run = start_time
            self._run_count += 1

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Sector rotation cycle complete in {elapsed:.1f}s: "
                f"{len(snapshots)} sectors, {len(signals)} signals, "
                f"{len(confirmed_signals)} confirmed"
            )

            return {
                'success': True,
                'timestamp': start_time.isoformat(),
                'elapsed_seconds': elapsed,
                'snapshots': snapshots,
                'signals': signals,
                'confirmed_signals': confirmed_signals,
                'rankings': rankings,
                'summary': summary,
                'market_state': market_state,
            }

        except Exception as e:
            logger.exception(f"Sector rotation cycle failed: {e}")
            return {
                'success': False,
                'timestamp': start_time.isoformat(),
                'error': str(e),
            }

    async def run_forever(self) -> None:
        """
        Run collection cycles forever at configured interval.

        This method never returns normally - use task cancellation to stop.
        """
        self._running = True
        logger.info(f"Starting sector rotation runner (interval: {self.interval}s)")

        while self._running:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                logger.info("Sector rotation runner cancelled")
                break
            except Exception as e:
                logger.exception(f"Unexpected error in rotation runner: {e}")

            # Wait for next interval
            if self._running:
                logger.debug(f"Sleeping {self.interval}s until next cycle")
                await asyncio.sleep(self.interval)

        logger.info("Sector rotation runner stopped")

    def stop(self) -> None:
        """Stop the runner gracefully."""
        self._running = False
        logger.info("Sector rotation runner stop requested")

    # =========================================================================
    # State Access Methods
    # =========================================================================

    def get_latest_snapshots(self) -> Dict[str, SectorSnapshot]:
        """Get most recent sector snapshots."""
        return self._last_snapshots.copy()

    def get_latest_rankings(self) -> list:
        """Get sector rankings from last run."""
        if not self._last_snapshots:
            return []
        return self.detector.get_sector_rankings(self._last_snapshots)

    def get_confirmed_signals(self) -> list:
        """Get currently confirmed signals."""
        return self.detector.get_confirmed_signals()

    def get_signal_summary(self) -> dict:
        """Get signal summary."""
        return self.detector.get_signal_summary()

    def get_market_state(self) -> str:
        """Get current market state."""
        return self._last_market_state

    def get_status(self) -> Dict[str, Any]:
        """Get runner status."""
        return {
            'running': self._running,
            'last_run': self._last_run.isoformat() if self._last_run else None,
            'run_count': self._run_count,
            'interval_seconds': self.interval,
            'sectors_tracked': len(SECTOR_CONFIG),
            'market_state': self._last_market_state,
            'alerts_enabled': self.alerter.enabled,
        }


# ============================================================================
# Standalone Execution
# ============================================================================

async def main():
    """Run sector rotation as standalone process."""
    import os

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    webhook = os.getenv('DISCORD_SECTOR_WEBHOOK')
    runner = SectorRotationRunner(
        discord_webhook=webhook,
        alerts_enabled=bool(webhook),
    )

    try:
        await runner.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        runner.stop()


if __name__ == '__main__':
    asyncio.run(main())
