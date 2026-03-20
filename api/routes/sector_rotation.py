"""
Sector Rotation API Routes

Exposes sector rotation analysis via REST endpoints.
Includes rankings, signals, and multi-exchange metrics.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from api.rate_limiter import rate_limit_collect, rate_limit_control

from src.analysis.sector_rotation import (
    SectorRotationRunner,
    SectorDataCollector,
    SectorSignalDetector,
    SECTOR_CONFIG,
    SECTOR_METADATA,
    get_sector_metadata,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sector-rotation", tags=["Sector Rotation"])

# Global runner instance (initialized on first use)
_runner: Optional[SectorRotationRunner] = None
_background_task_started = False

# Collection interval: 15 minutes for granular sector rotation tracking
COLLECTION_INTERVAL_SECONDS = 15 * 60  # 15 minutes


def get_runner() -> SectorRotationRunner:
    """Get or create the sector rotation runner."""
    global _runner
    if _runner is None:
        _runner = SectorRotationRunner(
            interval_seconds=COLLECTION_INTERVAL_SECONDS,
            alerts_enabled=True
        )
    return _runner


# ============================================================================
# Rankings & Overview
# ============================================================================

@router.get("/rankings")
async def get_sector_rankings(
    limit: Optional[int] = Query(None, description="Limit number of results"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type (inflow, outflow, neutral)"),
):
    """
    Get sectors ranked by rotation score.

    Returns all sectors sorted by their 8-factor rotation score (0-100).
    Higher scores indicate inflow (bullish rotation into sector).
    Lower scores indicate outflow (bearish rotation out of sector).

    Returns:
        List of sector rankings with scores and key metrics
    """
    try:
        runner = get_runner()
        rankings = runner.get_latest_rankings()

        if not rankings:
            # No data yet - trigger a collection
            raise HTTPException(
                status_code=503,
                detail="No sector data available. System is initializing."
            )

        # Filter by signal type if specified
        if signal_type:
            rankings = [r for r in rankings if r.get('signal_type') == signal_type]

        # Apply limit
        if limit:
            rankings = rankings[:limit]

        return {
            "success": True,
            "rankings": rankings,
            "count": len(rankings),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sector rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_rotation_summary():
    """
    Get summary of current sector rotation signals.

    Returns overview statistics including:
    - Active and confirmed signal counts
    - Inflow/outflow sector lists
    - Rotation pairs
    - Market state (risk_on, risk_off, neutral)

    Returns:
        Signal summary with market state
    """
    try:
        runner = get_runner()
        summary = runner.get_signal_summary()
        market_state = runner.get_market_state()

        return {
            "success": True,
            "market_state": market_state,
            **summary,
        }

    except Exception as e:
        logger.error(f"Failed to get rotation summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_active_signals(
    confirmed_only: bool = Query(False, description="Only return confirmed signals"),
):
    """
    Get active sector rotation signals.

    Signals require 2+ consecutive periods at MODERATE+ strength
    to be confirmed.

    Args:
        confirmed_only: If true, only return confirmed signals

    Returns:
        List of active signals with confirmation status
    """
    try:
        runner = get_runner()

        if confirmed_only:
            signals = runner.get_confirmed_signals()
        else:
            signals = runner.detector.get_all_active_signals()

        return {
            "success": True,
            "signals": [s.to_dict() for s in signals],
            "count": len(signals),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get active signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Sector Details
# ============================================================================

@router.get("/sector/{sector_code}")
async def get_sector_details(sector_code: str):
    """
    Get detailed metrics for a specific sector.

    Args:
        sector_code: Sector code (e.g., DEFI, L1, MEME)

    Returns:
        Detailed sector snapshot with exchange breakdown
    """
    sector_code = sector_code.upper()

    if sector_code not in SECTOR_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown sector: {sector_code}. Available: {list(SECTOR_CONFIG.keys())}"
        )

    try:
        runner = get_runner()
        snapshots = runner.get_latest_snapshots()

        snapshot = snapshots.get(sector_code)
        if not snapshot:
            raise HTTPException(
                status_code=503,
                detail=f"No data available for sector {sector_code}"
            )

        metadata = get_sector_metadata(sector_code)

        return {
            "success": True,
            "sector_code": sector_code,
            "sector_name": metadata['name'],
            "emoji": metadata['emoji'],
            "symbols": SECTOR_CONFIG[sector_code],
            "snapshot": snapshot.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sector details for {sector_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors")
async def list_sectors():
    """
    List all available sectors with metadata.

    Returns:
        List of sector codes with names and symbol counts
    """
    sectors = []
    for code, symbols in SECTOR_CONFIG.items():
        meta = get_sector_metadata(code)
        sectors.append({
            "code": code,
            "name": meta['name'],
            "emoji": meta['emoji'],
            "symbol_count": len(symbols),
            "symbols": symbols,
        })

    return {
        "success": True,
        "sectors": sectors,
        "count": len(sectors),
    }


# ============================================================================
# Multi-Exchange Metrics
# ============================================================================

@router.get("/exchanges")
async def get_exchange_breakdown():
    """
    Get per-exchange breakdown of sector metrics.

    Shows volume, OI, and funding distribution across all exchanges
    for each sector.

    Returns:
        Exchange breakdown by sector
    """
    try:
        runner = get_runner()
        snapshots = runner.get_latest_snapshots()

        if not snapshots:
            raise HTTPException(
                status_code=503,
                detail="No sector data available"
            )

        breakdown = {}
        for sector_code, snapshot in snapshots.items():
            breakdown[sector_code] = {
                "sector_name": get_sector_metadata(sector_code)['name'],
                "exchange_count": snapshot.exchange_count,
                "exchanges": [eb.to_dict() for eb in snapshot.exchange_breakdown],
            }

        return {
            "success": True,
            "breakdown": breakdown,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get exchange breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cex-vs-dex")
async def get_cex_dex_flow():
    """
    Get CEX vs DEX flow analysis.

    Shows the distribution of volume and OI between centralized
    and decentralized exchanges by sector.

    CEX-favored flow often indicates institutional activity.
    DEX-favored flow may indicate retail/degen activity.

    Returns:
        CEX/DEX flow metrics by sector
    """
    try:
        runner = get_runner()
        snapshots = runner.get_latest_snapshots()

        if not snapshots:
            raise HTTPException(
                status_code=503,
                detail="No sector data available"
            )

        flows = []
        for sector_code, snapshot in snapshots.items():
            flows.append({
                "sector_code": sector_code,
                "sector_name": get_sector_metadata(sector_code)['name'],
                "cex_volume_share": round(snapshot.cex_volume_share * 100, 1),
                "dex_volume_share": round(snapshot.dex_volume_share * 100, 1),
                "cex_oi_share": round(snapshot.cex_oi_share * 100, 1),
                "dex_oi_share": round(snapshot.dex_oi_share * 100, 1),
                "flow_score": round(snapshot.cex_dex_flow_score, 3),
                "flow_direction": "CEX" if snapshot.cex_dex_flow_score > 0 else "DEX",
            })

        # Sort by absolute flow score
        flows.sort(key=lambda x: abs(x['flow_score']), reverse=True)

        return {
            "success": True,
            "flows": flows,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get CEX/DEX flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding-spreads")
async def get_funding_spreads():
    """
    Get cross-exchange funding rate spreads.

    High funding spread indicates divergent positioning across exchanges,
    which can signal arbitrage opportunities or market dislocations.

    Returns:
        Funding spread metrics by sector
    """
    try:
        runner = get_runner()
        snapshots = runner.get_latest_snapshots()

        if not snapshots:
            raise HTTPException(
                status_code=503,
                detail="No sector data available"
            )

        spreads = []
        for sector_code, snapshot in snapshots.items():
            spreads.append({
                "sector_code": sector_code,
                "sector_name": get_sector_metadata(sector_code)['name'],
                "avg_funding_rate": round(snapshot.avg_funding_rate * 10000, 2),  # bps
                "funding_spread": round(snapshot.funding_spread * 10000, 2),  # bps
                "spread_significant": snapshot.funding_spread > 0.0002,  # > 2 bps
            })

        # Sort by funding spread descending
        spreads.sort(key=lambda x: x['funding_spread'], reverse=True)

        return {
            "success": True,
            "spreads": spreads,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get funding spreads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# System Status & Control
# ============================================================================

@router.get("/status")
async def get_system_status():
    """
    Get sector rotation system status.

    Returns:
        Runner status with last run time and configuration
    """
    try:
        runner = get_runner()
        return {
            "success": True,
            "status": runner.get_status(),
        }

    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect")
async def trigger_collection(
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_collect),
):
    """
    Manually trigger a sector data collection.

    This runs asynchronously in the background.
    Rate limited: 5 requests per 5 minutes.

    Returns:
        Confirmation that collection was started
    """
    try:
        runner = get_runner()

        async def run_collection():
            await runner.run_once()

        background_tasks.add_task(run_collection)

        return {
            "success": True,
            "message": "Collection started in background",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-background")
async def start_background_runner(
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_control),
):
    """
    Start the background rotation runner.

    The runner will collect data every 4 hours and send alerts
    for confirmed signals.
    Rate limited: 10 requests per minute.

    Returns:
        Confirmation that background runner was started
    """
    global _background_task_started

    if _background_task_started:
        return {
            "success": True,
            "message": "Background runner already started",
        }

    try:
        runner = get_runner()

        background_tasks.add_task(runner.run_forever)
        _background_task_started = True

        return {
            "success": True,
            "message": "Background runner started",
            "interval_hours": runner.interval / 3600,
        }

    except Exception as e:
        logger.error(f"Failed to start background runner: {e}")
        raise HTTPException(status_code=500, detail=str(e))
