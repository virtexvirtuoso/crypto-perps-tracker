"""
Spot Rotation API Routes - CoinGecko Spot Market Analysis

Exposes spot sector rotation analysis via REST endpoints.
Uses CoinGecko data with 5-factor scoring model.

5-Factor Scoring:
- Volume Z-Score (25%): Unusual volume share relative to history
- Momentum (25%): Multi-timeframe price momentum (1h, 24h, 7d)
- Breadth (20%): Up/down ratio, market cap weighted
- Market Cap Flow (15%): Sector mcap change vs market
- Relative Strength (15%): Sector RS vs BTC
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from api.rate_limiter import rate_limit_collect, rate_limit_control

from src.analysis.spot_rotation import (
    SpotRotationRunner,
    SpotSignalDetector,
    SPOT_SECTOR_CONFIG,
    SPOT_SECTOR_METADATA,
    get_sector_metadata,
    detect_spot_perp_divergence,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spot-rotation", tags=["Spot Rotation"])

# Global runner instance (initialized on first use)
_runner: Optional[SpotRotationRunner] = None
_background_task_started = False


def get_runner() -> SpotRotationRunner:
    """Get or create the spot rotation runner."""
    global _runner
    if _runner is None:
        _runner = SpotRotationRunner()
    return _runner


# ============================================================================
# Rankings & Overview
# ============================================================================

@router.get("/rankings")
async def get_spot_rankings(
    limit: Optional[int] = Query(None, description="Limit number of results"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type (inflow, outflow, neutral)"),
    tier: Optional[str] = Query(None, description="Filter by sector tier (core, defi, narrative, infra, ecosystem, other)"),
):
    """
    Get spot sectors ranked by rotation score (CoinGecko data).

    Returns all sectors sorted by their 5-factor rotation score (0-100).
    Higher scores indicate inflow (capital entering sector).
    Lower scores indicate outflow (capital leaving sector).

    Scoring factors:
    - Volume Z-Score (25%): Unusual volume activity
    - Momentum (25%): Multi-timeframe price momentum
    - Breadth (20%): Market cap weighted breadth
    - Market Cap Flow (15%): Relative mcap change
    - Relative Strength (15%): RS vs BTC

    Returns:
        List of sector rankings with scores and metrics
    """
    try:
        runner = get_runner()
        rankings = runner.get_latest_rankings()

        if not rankings:
            raise HTTPException(
                status_code=503,
                detail="No spot data available. System is initializing or CoinGecko API unavailable."
            )

        # Filter by tier if specified
        if tier:
            tier_sectors = [
                code for code, meta in SPOT_SECTOR_METADATA.items()
                if meta.get('tier') == tier
            ]
            rankings = [r for r in rankings if r.get('sector_code') in tier_sectors]

        # Filter by signal type if specified
        if signal_type:
            rankings = [r for r in rankings if r.get('signal_type') == signal_type]

        # Apply limit
        if limit:
            rankings = rankings[:limit]

        return {
            "success": True,
            "source": "coingecko",
            "rankings": rankings,
            "count": len(rankings),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get spot rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_spot_summary():
    """
    Get summary of current spot sector rotation signals.

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
            "source": "coingecko",
            "market_state": market_state,
            **summary,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get spot summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_spot_signals(
    confirmed_only: bool = Query(False, description="Only return confirmed signals"),
):
    """
    Get active spot sector rotation signals.

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
            "source": "coingecko",
            "signals": [s.to_dict() for s in signals],
            "count": len(signals),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get spot signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Sector Details
# ============================================================================

@router.get("/sector/{sector_code}")
async def get_spot_sector_details(sector_code: str):
    """
    Get detailed metrics for a specific spot sector.

    Includes multi-timeframe price changes, market cap distribution,
    and token-level breakdown.

    Args:
        sector_code: Sector code (e.g., DEFI, L1, MEME, GAMING)

    Returns:
        Detailed sector snapshot with token breakdown
    """
    sector_code = sector_code.upper()

    if sector_code not in SPOT_SECTOR_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown sector: {sector_code}. Available: {list(SPOT_SECTOR_CONFIG.keys())}"
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
            "source": "coingecko",
            "sector_code": sector_code,
            "sector_name": metadata['name'],
            "emoji": metadata['emoji'],
            "tier": metadata['tier'],
            "token_ids": SPOT_SECTOR_CONFIG[sector_code],
            "snapshot": snapshot.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get spot sector details for {sector_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors")
async def list_spot_sectors():
    """
    List all available spot sectors with metadata.

    Returns:
        List of sector codes with names, emojis, tiers, and token counts
    """
    sectors = []
    for code, tokens in SPOT_SECTOR_CONFIG.items():
        meta = get_sector_metadata(code)
        sectors.append({
            "code": code,
            "name": meta['name'],
            "emoji": meta['emoji'],
            "tier": meta['tier'],
            "token_count": len(tokens),
            "tokens": tokens,
        })

    # Group by tier
    tiers = {}
    for sector in sectors:
        tier = sector['tier']
        if tier not in tiers:
            tiers[tier] = []
        tiers[tier].append(sector)

    return {
        "success": True,
        "source": "coingecko",
        "sectors": sectors,
        "by_tier": tiers,
        "count": len(sectors),
    }


# ============================================================================
# Market Cap Tiers
# ============================================================================

@router.get("/market-cap-tiers")
async def get_market_cap_tiers():
    """
    Get market cap tier distribution for each sector.

    Shows the percentage of sector market cap in:
    - MEGA: >$50B
    - LARGE: $10B-$50B
    - MID: $1B-$10B
    - SMALL: $100M-$1B
    - MICRO: <$100M

    Returns:
        Market cap tier breakdown by sector
    """
    try:
        runner = get_runner()
        snapshots = runner.get_latest_snapshots()

        if not snapshots:
            raise HTTPException(
                status_code=503,
                detail="No spot data available"
            )

        tiers = []
        for sector_code, snapshot in snapshots.items():
            meta = get_sector_metadata(sector_code)
            tiers.append({
                "sector_code": sector_code,
                "sector_name": meta['name'],
                "emoji": meta['emoji'],
                "total_market_cap": snapshot.total_market_cap,
                "mega_cap_pct": round(snapshot.mega_cap_pct, 1),
                "large_cap_pct": round(snapshot.large_cap_pct, 1),
                "mid_cap_pct": round(snapshot.mid_cap_pct, 1),
                "small_cap_pct": round(snapshot.small_cap_pct, 1),
                "micro_cap_pct": round(snapshot.micro_cap_pct, 1),
            })

        # Sort by total market cap
        tiers.sort(key=lambda x: x['total_market_cap'], reverse=True)

        return {
            "success": True,
            "source": "coingecko",
            "tier_breakdown": tiers,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get market cap tiers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Spot/Perp Comparison (when both systems are running)
# ============================================================================

@router.get("/comparison")
async def get_spot_perp_comparison():
    """
    Get spot vs perp rotation comparison.

    Compares CoinGecko spot data with multi-exchange perp data
    to detect divergences that may indicate:
    - Smart money accumulation (spot leading perps)
    - Retail speculation (perps leading spot)
    - Funding arbitrage opportunities

    Note: Requires both spot and perp rotation systems to be running.

    Returns:
        Spot/perp divergence analysis by sector
    """
    try:
        runner = get_runner()
        spot_snapshots = runner.get_latest_snapshots()

        if not spot_snapshots:
            raise HTTPException(
                status_code=503,
                detail="No spot data available"
            )

        # Try to get perp snapshots if available
        perp_snapshots = {}
        try:
            from api.routes.sector_rotation import get_runner as get_perp_runner
            perp_runner = get_perp_runner()
            perp_snapshots = perp_runner.get_latest_snapshots()
        except ImportError:
            logger.warning("Perp rotation module not available for comparison")
        except Exception as e:
            logger.warning(f"Could not fetch perp snapshots: {e}")

        if not perp_snapshots:
            # Return spot-only data
            return {
                "success": True,
                "source": "coingecko",
                "perp_available": False,
                "message": "Perp rotation data not available for comparison",
                "spot_sectors": len(spot_snapshots),
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Detect divergences
        divergences = detect_spot_perp_divergence(spot_snapshots, perp_snapshots)

        # Sort by divergence score (most divergent first)
        divergences.sort(key=lambda x: abs(x.divergence_score), reverse=True)

        return {
            "success": True,
            "perp_available": True,
            "divergences": [d.to_dict() for d in divergences],
            "divergent_sectors": [
                d.sector_code for d in divergences if d.is_divergent
            ],
            "aligned_sectors": [
                d.sector_code for d in divergences if not d.is_divergent
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get spot/perp comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# System Status & Control
# ============================================================================

@router.get("/status")
async def get_spot_system_status():
    """
    Get spot rotation system status.

    Returns:
        Runner status with last collection time, error count, and config
    """
    try:
        runner = get_runner()
        return {
            "success": True,
            "source": "coingecko",
            "status": runner.get_status(),
        }

    except Exception as e:
        logger.error(f"Failed to get spot system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect")
async def trigger_spot_collection(
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_collect),
):
    """
    Manually trigger a spot data collection from CoinGecko.

    This runs asynchronously in the background.
    Respects CoinGecko rate limits (30 req/min).
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
            "message": "Spot collection started in background",
            "note": "Respects CoinGecko rate limits (30 req/min)",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger spot collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-background")
async def start_spot_background_runner(
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_control),
):
    """
    Start the background spot rotation runner.

    The runner will collect data every 15 minutes from CoinGecko.
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
            "message": "Spot background runner started",
            "interval_minutes": runner.interval / 60,
        }

    except Exception as e:
        logger.error(f"Failed to start spot background runner: {e}")
        raise HTTPException(status_code=500, detail=str(e))
