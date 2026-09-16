"""FastAPI Application for Derivatives Signals

REST API providing derivatives-based predictive trading signals from Bybit V5.
Includes endpoints for individual signals and fusion signals.
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging
from datetime import datetime

from src.signals.calculators import SignalCalculator
from src.signals.fusion import SignalFusion
from src.signals.models import (
    SignalResponse,
    MultiSignalResponse,
    BaseSignal,
)
from api.websocket import handle_websocket_connection
from api.cache import signal_cache
from api.routes.sector_rotation import router as sector_rotation_router, get_runner as get_sector_runner
from api.routes.spot_rotation import router as spot_rotation_router, get_runner as get_spot_runner
from api.routes.aggregated import router as aggregated_router

def _normalize_symbol(symbol: str) -> str:
    """Ensure symbol has USDT suffix for Bybit API compatibility."""
    s = symbol.upper().strip()
    if not s.endswith('USDT'):
        s = s + 'USDT'
    return s


import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Derivatives Signals API",
    description="Advanced trading signals from derivatives market data (Bybit V5)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sector_rotation_router)
app.include_router(spot_rotation_router)
app.include_router(aggregated_router)

# Initialize signal calculator and fusion engine
calculator = SignalCalculator()
fusion_engine = SignalFusion(calculator)

# Differentiated cache TTLs by signal update frequency
CACHE_TTLS = {
    'funding_rate': 300,      # 5min (changes every 8 hours)
    'open_interest': 90,      # 90s (moderate)
    'long_short_ratio': 60,   # 1min (changes frequently)
    'basis': 90,              # 90s (moderate)
    'cvd': 30,                # 30s (fast-moving order flow)
    'options_iv': 300,        # 5min (changes slowly)
    'fusion': 90,             # 90s (composite signal)
    'recommendation': 90,     # 90s (retail endpoint)
    'all_signals': 90,        # 90s (comprehensive)
}

# Cache for symbols list (5 minutes for consistency with signal cache)
_symbols_cache = {
    "symbols": None,
    "timestamp": None,
    "ttl": 300  # 5 minutes
}


@app.on_event("startup")
async def warm_cache():
    """Pre-warm cache for top symbols on startup"""
    # Top 20 symbols by volume (from Bybit)
    top_symbols = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "ADAUSDT", "DOGEUSDT", "MATICUSDT", "DOTUSDT", "AVAXUSDT",
        "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "APTUSDT",
        "ARBUSDT", "OPUSDT", "SUIUSDT", "NEARUSDT", "TONUSDT"
    ]

    logger.info("🔥 Starting cache warming for top 20 symbols...")

    warmed = 0
    failed = 0

    for symbol in top_symbols:
        try:
            # Calculate and cache recommendation
            summary = fusion_engine.get_recommendation_summary(symbol)
            cache_key = f"recommendation:{symbol}"
            signal_cache.set(cache_key, summary, ttl=CACHE_TTLS['recommendation'])
            warmed += 1
            logger.debug(f"Pre-warmed cache for {symbol}")
        except Exception as e:
            failed += 1
            logger.warning(f"Failed to warm cache for {symbol}: {e}")

    logger.info(f"✅ Cache warming complete: {warmed} symbols warmed, {failed} failed")

    # Auto-start sector rotation background runner
    try:
        runner = get_sector_runner()
        asyncio.create_task(runner.run_forever())
        logger.info("🔄 Sector rotation background runner started automatically")
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-start sector rotation runner: {e}")

    # Auto-start spot rotation background runner
    try:
        spot_runner = get_spot_runner()
        asyncio.create_task(spot_runner.run_forever())
        logger.info("🔄 Spot rotation background runner started automatically")
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-start spot rotation runner: {e}")


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Derivatives Signals API",
        "version": "1.0.0",
        "description": "Advanced trading signals from Bybit V5 derivatives data",
        "endpoints": {
            "funding_rate": "/signals/funding-rate/{symbol}",
            "open_interest": "/signals/open-interest/{symbol}",
            "long_short_ratio": "/signals/long-short-ratio/{symbol}",
            "basis": "/signals/basis/{symbol}",
            "cvd": "/signals/cvd/{symbol}",
            "options_iv": "/signals/options-iv/{base_coin}",
            "fusion": "/signals/fusion/{symbol}",
            "all_signals": "/signals/all/{symbol}",
            "recommendation": "/recommendation/{symbol}",
            "cache_stats": "/cache/stats",
            "sector_rotation": {
                "description": "Multi-exchange perp rotation (8 exchanges, 91.7% coverage)",
                "rankings": "/api/sector-rotation/rankings",
                "summary": "/api/sector-rotation/summary",
                "signals": "/api/sector-rotation/signals",
                "sectors": "/api/sector-rotation/sectors",
                "cex_vs_dex": "/api/sector-rotation/cex-vs-dex",
                "funding_spreads": "/api/sector-rotation/funding-spreads",
            },
            "spot_rotation": {
                "description": "CoinGecko spot rotation (5-factor scoring)",
                "rankings": "/api/spot-rotation/rankings",
                "summary": "/api/spot-rotation/summary",
                "signals": "/api/spot-rotation/signals",
                "sectors": "/api/spot-rotation/sectors",
                "market_cap_tiers": "/api/spot-rotation/market-cap-tiers",
                "comparison": "/api/spot-rotation/comparison",
            }
        },
        "docs": "/docs",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/signals/funding-rate/{symbol}")
async def get_funding_rate_signal(symbol: str = "BTCUSDT"):
    """Get funding rate extremes signal

    **Buy** if FR < -0.05% and price > 200-EMA
    **Sell** if FR > +0.10% and price < 200-EMA

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        FundingRateSignal with direction, confidence, and metadata
    """
    try:
        symbol = _normalize_symbol(symbol)
        signal = calculator.calculate_funding_rate_signal(symbol)
        return SignalResponse(success=True, signal=signal)
    except Exception as e:
        logger.error(f"Funding rate signal failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/open-interest/{symbol}")
async def get_open_interest_signal(symbol: str = "BTCUSDT"):
    """Get open interest surge + price divergence signal

    **Bullish** if ΔOI% > +30% and price falls < -2%
    **Bearish** if ΔOI% > +30% and price rises > +2%

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        OpenInterestSignal with divergence analysis
    """
    try:
        symbol = _normalize_symbol(symbol)
        signal = calculator.calculate_open_interest_signal(symbol)
        return SignalResponse(success=True, signal=signal)
    except Exception as e:
        logger.error(f"Open interest signal failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/long-short-ratio/{symbol}")
async def get_long_short_ratio_signal(symbol: str = "BTCUSDT"):
    """Get long/short ratio skew signal

    **Fade** when LSR > 3.0 (crowded longs) or < 0.33 (crowded shorts)

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        LongShortRatioSignal with crowd positioning
    """
    try:
        symbol = _normalize_symbol(symbol)
        signal = calculator.calculate_long_short_ratio_signal(symbol)
        return SignalResponse(success=True, signal=signal)
    except Exception as e:
        logger.error(f"Long/short ratio signal failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/basis/{symbol}")
async def get_basis_signal(symbol: str = "BTCUSDT"):
    """Get perp vs spot basis divergence signal

    **Buy** if Basis < -0.5% (contango discount)
    **Sell** if Basis > +1% (backwardation premium)

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        BasisSignal with arbitrage opportunity analysis
    """
    try:
        symbol = _normalize_symbol(symbol)
        signal = calculator.calculate_basis_signal(symbol)
        return SignalResponse(success=True, signal=signal)
    except Exception as e:
        logger.error(f"Basis signal failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/cvd/{symbol}")
async def get_cvd_signal(symbol: str = "BTCUSDT"):
    """Get Cumulative Volume Delta signal

    **Bullish** if CVD > +500k USDT
    **Bearish** if CVD < -500k USDT

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        CVDSignal with hidden order flow analysis
    """
    try:
        symbol = _normalize_symbol(symbol)
        signal = calculator.calculate_cvd_signal(symbol)
        return SignalResponse(success=True, signal=signal)
    except Exception as e:
        logger.error(f"CVD signal failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/options-iv/{base_coin}")
async def get_options_iv_signal(base_coin: str = "BTC"):
    """Get options implied volatility skew signal

    **Buy** if IV_Skew > +15% (fear)
    **Sell** if IV_Skew < -15% (complacency)

    Args:
        base_coin: Base coin (default: BTC)

    Returns:
        OptionsIVSignal with market sentiment analysis
    """
    try:
        signal = calculator.calculate_options_iv_signal(base_coin)
        if signal is None:
            raise HTTPException(
                status_code=404,
                detail=f"Options data not available for {base_coin}"
            )
        return SignalResponse(success=True, signal=signal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Options IV signal failed for {base_coin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/fusion/{symbol}")
async def get_fusion_signal(symbol: str = "BTCUSDT"):
    """Get composite fusion signal (HIGHEST EDGE)

    Combines Funding + OI + LSR + CVD → 78% win-rate

    **Score >= +3**: ENTER LONG
    **Score <= -3**: ENTER SHORT
    **Score -2 to +2**: WAIT

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        FusionSignal with composite score and entry recommendation
    """
    try:
        symbol = _normalize_symbol(symbol)
        signal = fusion_engine.calculate_fusion_signal(symbol)
        return SignalResponse(success=True, signal=signal)
    except Exception as e:
        logger.error(f"Fusion signal failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/all/{symbol}")
async def get_all_signals(symbol: str = "BTCUSDT"):
    """Get all available signals for a symbol

    Returns all individual signals plus fusion signal.

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        MultiSignalResponse with all signals
    """
    try:
        symbol = _normalize_symbol(symbol)
        # Get all individual signals
        signals_dict = calculator.calculate_all_signals(symbol)

        # Add fusion signal
        signals_dict['fusion'] = fusion_engine.calculate_fusion_signal(symbol)

        # Convert to list
        signals_list = [s for s in signals_dict.values() if s is not None]

        return MultiSignalResponse(success=True, signals=signals_list)
    except Exception as e:
        logger.error(f"Get all signals failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendation/{symbol}")
async def get_recommendation(symbol: str = "BTCUSDT"):
    """Get human-readable trading recommendation

    Returns a simplified, actionable recommendation with risk warnings.

    Args:
        symbol: Trading pair (default: BTCUSDT)

    Returns:
        Dict with recommendation summary
    """
    try:
        symbol = _normalize_symbol(symbol)
        # Check cache first
        cache_key = f"recommendation:{symbol}"
        cached = signal_cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for recommendation:{symbol}")
            return {
                "success": True,
                "data": cached,
                "cached": True
            }

        # Calculate if not cached
        summary = fusion_engine.get_recommendation_summary(symbol)

        # Cache with appropriate TTL
        signal_cache.set(cache_key, summary, ttl=CACHE_TTLS['recommendation'])
        logger.debug(f"Cached recommendation:{symbol} (TTL: {CACHE_TTLS['recommendation']}s)")

        return {
            "success": True,
            "data": summary,
            "cached": False
        }
    except Exception as e:
        logger.error(f"Get recommendation failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/symbols")
async def get_supported_symbols():
    """Get list of supported trading symbols (dynamically fetched from Bybit)

    Returns:
        List of all available USDT perpetual symbols on Bybit
    """
    from time import time

    # Check cache first
    now = time()
    if (_symbols_cache["symbols"] is not None and
        _symbols_cache["timestamp"] is not None and
        now - _symbols_cache["timestamp"] < _symbols_cache["ttl"]):
        logger.info("Returning cached symbols list")
        return {
            "success": True,
            "symbols": _symbols_cache["symbols"],
            "count": len(_symbols_cache["symbols"]),
            "note": "Cached - dynamically fetched from Bybit",
            "cache_age_seconds": int(now - _symbols_cache["timestamp"])
        }

    try:
        # Fetch active USDT perpetual symbols from Bybit
        from src.signals.bybit_derivatives import BybitDerivativesClient
        client = BybitDerivativesClient()

        logger.info("Fetching symbols list from Bybit API...")

        # Get tickers to check 24h volume
        tickers_data = client._get("/v5/market/tickers", params={'category': 'linear'})

        # Create volume map
        volume_map = {}
        for ticker in tickers_data['result']['list']:
            symbol = ticker['symbol']
            if symbol.endswith('USDT'):
                try:
                    volume_24h = float(ticker.get('turnover24h', 0))
                    volume_map[symbol] = volume_24h
                except (ValueError, TypeError):
                    volume_map[symbol] = 0

        # Filter for high-volume USDT perpetuals
        MIN_VOLUME_24H = 5_000_000  # $5M minimum 24h volume
        symbols = []

        for symbol, volume in volume_map.items():
            # Only include high-volume symbols
            if volume >= MIN_VOLUME_24H:
                symbols.append((symbol, volume))

        # Sort by volume (highest first)
        symbols.sort(key=lambda x: x[1], reverse=True)

        # Extract just symbol names (already sorted by volume)
        sorted_symbols = [sym for sym, vol in symbols]

        # Update cache
        _symbols_cache["symbols"] = sorted_symbols
        _symbols_cache["timestamp"] = now

        logger.info(f"Fetched {len(sorted_symbols)} symbols from Bybit")

        return {
            "success": True,
            "symbols": sorted_symbols,
            "count": len(sorted_symbols),
            "note": f"Dynamically fetched from Bybit - filtered by volume (min $5M/24h), sorted by liquidity"
        }
    except Exception as e:
        logger.error(f"Error fetching symbols from Bybit: {e}")
        # Fallback to default list if API fails
        fallback_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "ADAUSDT", "DOGEUSDT", "MATICUSDT", "DOTUSDT", "AVAXUSDT",
            "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "APTUSDT"
        ]
        return {
            "success": True,
            "symbols": fallback_symbols,
            "count": len(fallback_symbols),
            "note": "Fallback list - Bybit API unavailable"
        }


@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics for monitoring

    Returns cache performance metrics including hit rate, size, and efficiency.
    """
    try:
        stats = signal_cache.stats()
        return {
            "success": True,
            "cache": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/signals/{symbol}")
async def websocket_signals_endpoint(
    websocket: WebSocket,
    symbol: str,
    signal_type: str = "fusion",
    interval: int = 60
):
    """WebSocket endpoint for real-time signal streaming

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        signal_type: Type of signal (fusion, funding_rate, open_interest, etc.)
        interval: Update interval in seconds (default: 60)

    Example:
        ws://localhost:8000/ws/signals/BTCUSDT?signal_type=fusion&interval=30
    """
    await handle_websocket_connection(websocket, symbol, signal_type, interval)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
