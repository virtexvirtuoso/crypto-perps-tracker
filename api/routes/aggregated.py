"""Aggregated Signal Routes

API endpoints for multi-exchange aggregated signals:
- Consensus Long/Short Ratio from Bybit, Binance, OKX, Bitget
- Volume-weighted Funding Rates
- Cross-exchange signal validation
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
import logging

from src.signals.aggregator import AggregatedSignalCalculator

logger = logging.getLogger(__name__)

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol to exchange format (e.g., BTC -> BTCUSDT)"""
    s = symbol.upper().strip()
    # Remove common suffixes
    for suffix in ["-PERP", "-SWAP", "/USDT", ":USDT", "-USDT"]:
        s = s.replace(suffix, "")
    # Add USDT if not present
    if not s.endswith("USDT") and not s.endswith("USD"):
        s = s + "USDT"
    return s

router = APIRouter(
    prefix="/api/aggregated",
    tags=["Aggregated Signals"]
)

# Initialize aggregator
aggregator = AggregatedSignalCalculator()


@router.get("/lsr/{symbol}")
async def get_consensus_lsr(
    symbol: str,
    period: str = Query("1h", description="Time period (5m, 15m, 30m, 1h, 4h, 1d)")
):
    """Get consensus Long/Short Ratio from multiple exchanges

    Aggregates LSR from Bybit, Binance, OKX, and Bitget using median
    with outlier rejection for robustness.

    Returns:
        - consensus_lsr: Aggregated ratio
        - agreement_score: How much exchanges agree (0-1)
        - crowd_side: "long", "short", or "balanced"
        - exchange_data: Individual exchange data
    """
    try:
        signal = aggregator.calculate_consensus_lsr(normalize_symbol(symbol), period)

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "consensus_lsr": round(signal.consensus_lsr, 4),
            "agreement_score": round(signal.agreement_score, 3),
            "crowd_side": signal.crowd_side,
            "confidence": round(signal.confidence, 1),
            "sources": {
                "available": signal.sources_available,
                "total": signal.sources_total
            },
            "exchange_data": {
                exchange: {
                    "lsr": round(data.get("long_short_ratio", 0), 4),
                    "long_pct": round(data.get("long_account_pct", 0), 2),
                    "short_pct": round(data.get("short_account_pct", 0), 2)
                }
                for exchange, data in signal.exchange_data.items()
            },
            "interpretation": _interpret_lsr(signal.consensus_lsr, signal.crowd_side)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating consensus LSR: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate consensus LSR")


@router.get("/funding/{symbol}")
async def get_aggregated_funding(symbol: str):
    """Get volume-weighted aggregated funding rate

    Aggregates funding rates from multiple exchanges weighted by volume.

    Returns:
        - weighted_funding_rate: Volume-weighted average
        - divergence_score: How much exchanges diverge (0-1)
        - consensus_direction: "bullish", "bearish", or "neutral"
        - exchange_data: Individual exchange data with weights
    """
    try:
        signal = aggregator.calculate_aggregated_funding(normalize_symbol(symbol))

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "weighted_funding_rate": round(signal.weighted_funding_rate, 6),
            "weighted_funding_rate_pct": round(signal.weighted_funding_rate * 100, 4),
            "divergence_score": round(signal.divergence_score, 3),
            "consensus_direction": signal.consensus_direction,
            "confidence": round(signal.confidence, 1),
            "exchange_data": {
                exchange: {
                    "funding_rate": round(data.get("funding_rate", 0), 6),
                    "funding_rate_pct": round(data.get("funding_rate", 0) * 100, 4),
                    "weight": round(data.get("weight", 0), 3)
                }
                for exchange, data in signal.exchange_data.items()
            },
            "interpretation": _interpret_funding(
                signal.weighted_funding_rate,
                signal.consensus_direction
            )
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating aggregated funding: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate aggregated funding")


@router.get("/summary/{symbol}")
async def get_aggregated_summary(symbol: str):
    """Get comprehensive aggregated signal summary

    Returns all aggregated signals for a symbol including:
    - Consensus LSR
    - Aggregated Funding
    - Overall market assessment
    """
    try:
        summary = aggregator.get_signal_summary(normalize_symbol(symbol))

        # Add overall assessment
        lsr_signal = summary['signals'].get('consensus_lsr', {})
        funding_signal = summary['signals'].get('aggregated_funding', {})

        assessment = _calculate_assessment(lsr_signal, funding_signal)

        return {
            **summary,
            "assessment": assessment
        }
    except Exception as e:
        logger.error(f"Error getting aggregated summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get aggregated summary")


@router.get("/oi/{symbol}")
async def get_aggregated_oi(symbol: str):
    """Get aggregated Open Interest from multiple exchanges

    Aggregates OI from Bybit, Binance, and OKX.

    Returns:
        - total_oi_usd: Total open interest in USD
        - exchange_data: Individual exchange OI
        - trend: OI trend direction
    """
    try:
        signal = aggregator.calculate_aggregated_oi(normalize_symbol(symbol))

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "total_oi_usd": round(signal.total_oi_usd, 2),
            "total_oi_formatted": _format_usd(signal.total_oi_usd),
            "trend": signal.oi_trend,
            "confidence": round(signal.confidence, 1),
            "exchange_data": {
                exchange: {
                    "oi_usd": round(data.get("open_interest_usd", 0), 2),
                    "oi_formatted": _format_usd(data.get("open_interest_usd", 0))
                }
                for exchange, data in signal.exchange_data.items()
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating aggregated OI: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate aggregated OI")


@router.get("/taker/{symbol}")
async def get_aggregated_taker(symbol: str):
    """Get aggregated Taker Buy/Sell volume

    Shows who is the aggressor (buyers or sellers).

    Returns:
        - consensus_ratio: Buy/Sell ratio (>1 = buyers, <1 = sellers)
        - aggressor: "buyers", "sellers", or "neutral"
        - buy_volume: Total buy volume
        - sell_volume: Total sell volume
    """
    try:
        signal = aggregator.calculate_aggregated_taker(normalize_symbol(symbol))

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "consensus_ratio": round(signal.consensus_ratio, 4),
            "aggressor": signal.aggressor,
            "buy_volume": round(signal.total_buy_volume, 2),
            "sell_volume": round(signal.total_sell_volume, 2),
            "net_volume": round(signal.total_buy_volume - signal.total_sell_volume, 2),
            "confidence": round(signal.confidence, 1),
            "interpretation": _interpret_taker(signal.consensus_ratio, signal.aggressor),
            "exchange_data": signal.exchange_data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating aggregated taker: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate aggregated taker flow")


@router.get("/basis/{symbol}")
async def get_aggregated_basis(symbol: str):
    """Get aggregated Basis Spread (perp - spot)

    Positive basis = perp trading at premium = bullish sentiment.
    Negative basis = perp trading at discount = bearish sentiment.

    Returns:
        - weighted_basis_pct: Volume-weighted basis percentage
        - annualized_basis_pct: Annualized basis (for carry trade analysis)
        - sentiment: "bullish", "bearish", or "neutral"
    """
    try:
        signal = aggregator.calculate_aggregated_basis(normalize_symbol(symbol))

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "basis_pct": round(signal.weighted_basis_pct, 4),
            "annualized_basis_pct": round(signal.annualized_basis_pct, 2),
            "sentiment": signal.sentiment,
            "confidence": round(signal.confidence, 1),
            "interpretation": _interpret_basis(signal.weighted_basis_pct, signal.sentiment),
            "exchange_data": signal.exchange_data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating aggregated basis: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate aggregated basis")


@router.get("/liquidations/{symbol}")
async def get_aggregated_liquidations(symbol: str):
    """Get aggregated Liquidation data

    Tracks liquidations across exchanges to detect cascade risk.

    Returns:
        - total_long_liquidations_usd: Long positions liquidated
        - total_short_liquidations_usd: Short positions liquidated
        - liquidation_ratio: Long/Short liquidation ratio
        - cascade_risk: "high", "medium", or "low"
    """
    try:
        signal = aggregator.calculate_aggregated_liquidations(normalize_symbol(symbol))

        total_liq = signal.total_long_liquidations_usd + signal.total_short_liquidations_usd

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "total_liquidations_usd": round(total_liq, 2),
            "total_formatted": _format_usd(total_liq),
            "long_liquidations_usd": round(signal.total_long_liquidations_usd, 2),
            "short_liquidations_usd": round(signal.total_short_liquidations_usd, 2),
            "liquidation_ratio": round(signal.liquidation_ratio, 4),
            "cascade_risk": signal.cascade_risk,
            "confidence": round(signal.confidence, 1),
            "interpretation": _interpret_liquidations(signal.liquidation_ratio, signal.cascade_risk),
            "exchange_data": signal.exchange_data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating aggregated liquidations: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate aggregated liquidations")


@router.get("/smart-money/{symbol}")
async def get_smart_money_divergence(symbol: str):
    """Get Top Trader vs Retail divergence

    Compares top 20% traders by margin with retail positioning.
    Divergence signals potential market reversal.

    Returns:
        - retail_lsr: Retail Long/Short ratio
        - top_trader_lsr: Top trader Long/Short ratio
        - divergence: Difference (positive = smart money more long)
        - signal: "smart_money_long", "smart_money_short", or "aligned"
    """
    try:
        signal = aggregator.calculate_top_trader_divergence(normalize_symbol(symbol))

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "retail_lsr": round(signal.retail_lsr, 4),
            "top_trader_lsr": round(signal.top_trader_lsr, 4),
            "divergence": round(signal.divergence, 4),
            "signal": signal.signal,
            "confidence": round(signal.confidence, 1),
            "interpretation": _interpret_smart_money(signal.divergence, signal.signal)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating smart money divergence: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate smart money divergence")


@router.get("/cex-dex-divergence/{symbol}")
async def get_cex_dex_divergence(symbol: str):
    """Get CEX vs DEX funding rate divergence

    Compares centralized exchange (Binance, Bybit, OKX, Bitget) funding rates
    with decentralized exchange (HyperLiquid, dYdX) funding rates.

    When DEX funding leads CEX by >0.02%, price tends to follow DEX direction.
    DEX traders often lead during FOMO/panic events.

    Returns:
        - cex_weighted_funding: Volume-weighted CEX funding rate
        - dex_weighted_funding: OI-weighted DEX funding rate
        - divergence: CEX - DEX (negative = DEX more bullish)
        - signal: "dex_bullish", "dex_bearish", or "aligned"
    """
    try:
        signal = aggregator.calculate_cex_dex_divergence(normalize_symbol(symbol))

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "cex_weighted_funding": round(signal.cex_weighted_funding, 6),
            "cex_funding_pct": round(signal.cex_weighted_funding * 100, 4),
            "dex_weighted_funding": round(signal.dex_weighted_funding, 6),
            "dex_funding_pct": round(signal.dex_weighted_funding * 100, 4),
            "divergence": round(signal.divergence, 6),
            "divergence_pct": round(signal.divergence * 100, 4),
            "signal": signal.signal,
            "confidence": round(signal.confidence, 1),
            "sources": {
                "cex_count": signal.cex_sources,
                "dex_count": signal.dex_sources
            },
            "cex_data": {
                exchange: {
                    "funding_rate": round(data.get("funding_rate", 0), 6),
                    "weight": round(data.get("weight", 0), 3)
                }
                for exchange, data in signal.cex_data.items()
            },
            "dex_data": {
                exchange: {
                    "funding_rate": round(data.get("funding_rate", 0), 6),
                    "open_interest": round(data.get("open_interest", 0), 2),
                    "weight": round(data.get("weight", 0), 3)
                }
                for exchange, data in signal.dex_data.items()
            },
            "interpretation": _interpret_cex_dex_divergence(signal.divergence, signal.signal)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating CEX-DEX divergence: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate CEX-DEX divergence")


@router.get("/degen-sentiment/{symbol}")
async def get_degen_sentiment(symbol: str):
    """Get DEX-only sentiment (retail/degen flow)

    Tracks sentiment from HyperLiquid, dYdX, and AsterDEX traders,
    who tend to be more retail/degen oriented.

    Returns:
        - hyperliquid_funding: HyperLiquid funding rate
        - dydx_funding: dYdX funding rate
        - asterdex_funding: AsterDEX funding rate
        - dex_consensus_funding: OI-weighted average DEX funding
        - sentiment_score: -100 to +100 scale
        - signal: "degen_fomo", "degen_panic", or "neutral"
    """
    try:
        signal = aggregator.calculate_degen_sentiment(normalize_symbol(symbol))

        return {
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "hyperliquid_funding": round(signal.hyperliquid_funding, 6) if signal.hyperliquid_funding else None,
            "dydx_funding": round(signal.dydx_funding, 6) if signal.dydx_funding else None,
            "asterdex_funding": round(signal.asterdex_funding, 6) if signal.asterdex_funding else None,
            "dex_consensus_funding": round(signal.dex_consensus_funding, 6),
            "dex_consensus_funding_pct": round(signal.dex_consensus_funding * 100, 4),
            "dex_oi_total": round(signal.dex_oi_total, 2),
            "dex_oi_formatted": _format_usd(signal.dex_oi_total),
            "sentiment_score": round(signal.sentiment_score, 1),
            "signal": signal.signal,
            "confidence": round(signal.confidence, 1),
            "dex_data": {
                name: {
                    "funding_rate": round(data.get("funding_rate", 0), 6),
                    "funding_rate_pct": round(data.get("funding_rate", 0) * 100, 4),
                    "open_interest": round(data.get("open_interest", 0), 2),
                    "oi_formatted": _format_usd(data.get("open_interest", 0))
                }
                for name, data in signal.dex_data.items()
            },
            "interpretation": _interpret_degen_sentiment(signal.sentiment_score, signal.signal)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating degen sentiment: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate degen sentiment")


@router.get("/market-lsr")
async def get_market_wide_lsr(
    period: str = Query("1h", description="Time period (5m, 15m, 30m, 1h, 4h, 1d)")
):
    """Get market-wide aggregated Long/Short positioning

    Aggregates L/S ratios across BTC, ETH, and SOL from all tracked exchanges
    (Bybit, Binance, OKX, Bitget) to provide overall market positioning.

    This is the REAL L/S positioning from exchange account ratio APIs,
    not derived from funding rates or other indirect measures.

    Returns:
        - market_long_pct: Overall market percentage in long positions
        - market_short_pct: Overall market percentage in short positions
        - market_lsr: Market-wide long/short ratio
        - crowd_side: "long", "short", or "balanced"
        - symbols: Per-symbol breakdown with exchange data
        - sources: Exchange availability info
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Symbols to aggregate for market-wide view
    MARKET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    # Weight by typical market dominance (BTC > ETH > SOL)
    SYMBOL_WEIGHTS = {
        "BTCUSDT": 0.50,  # BTC is ~50% of crypto market
        "ETHUSDT": 0.30,  # ETH is ~30%
        "SOLUSDT": 0.20   # SOL and others ~20%
    }

    symbols_data = {}
    total_long_pct = 0
    total_short_pct = 0
    total_weight = 0
    total_sources = 0
    max_sources = 0

    def fetch_symbol_lsr(symbol: str):
        """Fetch L/S for a single symbol"""
        try:
            signal = aggregator.calculate_consensus_lsr(symbol, period)
            return symbol, signal, None
        except Exception as e:
            return symbol, None, str(e)

    # Fetch all symbols in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(fetch_symbol_lsr, sym)
            for sym in MARKET_SYMBOLS
        ]

        for future in as_completed(futures):
            symbol, signal, error = future.result()

            if signal:
                weight = SYMBOL_WEIGHTS.get(symbol, 0.1)

                # Calculate long/short percentages from L/S ratio
                lsr = signal.consensus_lsr
                long_pct = (lsr / (1 + lsr)) * 100 if lsr > 0 else 50
                short_pct = 100 - long_pct

                symbols_data[symbol] = {
                    "consensus_lsr": round(lsr, 4),
                    "long_pct": round(long_pct, 2),
                    "short_pct": round(short_pct, 2),
                    "crowd_side": signal.crowd_side,
                    "agreement_score": round(signal.agreement_score, 3),
                    "confidence": round(signal.confidence, 1),
                    "exchanges": list(signal.exchange_data.keys()),
                    "sources_available": signal.sources_available,
                    "weight": weight
                }

                total_long_pct += long_pct * weight
                total_short_pct += short_pct * weight
                total_weight += weight
                total_sources += signal.sources_available
                max_sources += signal.sources_total
            else:
                symbols_data[symbol] = {"error": error}

    if total_weight == 0:
        raise HTTPException(status_code=500, detail="No L/S data available for any symbol")

    # Normalize to 100%
    market_long_pct = total_long_pct / total_weight
    market_short_pct = total_short_pct / total_weight

    # Calculate market-wide L/S ratio
    market_lsr = market_long_pct / market_short_pct if market_short_pct > 0 else 1.0

    # Determine market crowd side
    if market_lsr > 2.0:
        market_crowd_side = "long"
        crowd_interpretation = "Market heavily positioned LONG - potential squeeze risk"
    elif market_lsr < 0.5:
        market_crowd_side = "short"
        crowd_interpretation = "Market heavily positioned SHORT - potential squeeze risk"
    elif market_lsr > 1.2:
        market_crowd_side = "lean_long"
        crowd_interpretation = "Market leaning LONG - moderate bullish positioning"
    elif market_lsr < 0.83:
        market_crowd_side = "lean_short"
        crowd_interpretation = "Market leaning SHORT - moderate bearish positioning"
    else:
        market_crowd_side = "balanced"
        crowd_interpretation = "Market balanced - no extreme positioning"

    # Calculate overall confidence
    symbols_with_data = sum(1 for s in symbols_data.values() if "consensus_lsr" in s)
    data_coverage = symbols_with_data / len(MARKET_SYMBOLS)
    source_coverage = total_sources / max_sources if max_sources > 0 else 0
    overall_confidence = (data_coverage * 0.5 + source_coverage * 0.5) * 100

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "period": period,

        # Main metrics for widget display
        "market_long_pct": round(market_long_pct, 2),
        "market_short_pct": round(market_short_pct, 2),
        "market_lsr": round(market_lsr, 4),
        "crowd_side": market_crowd_side,

        # Visual formatting helpers
        "display": {
            "long": f"{market_long_pct:.1f}%",
            "short": f"{market_short_pct:.1f}%",
            "bar_long_width": round(market_long_pct),
            "bar_short_width": round(market_short_pct)
        },

        # Interpretation
        "interpretation": crowd_interpretation,
        "contrarian_signal": _get_contrarian_signal(market_lsr, market_crowd_side),

        # Confidence and sources
        "confidence": round(overall_confidence, 1),
        "sources": {
            "symbols_available": symbols_with_data,
            "symbols_total": len(MARKET_SYMBOLS),
            "exchanges_available": total_sources,
            "exchanges_total": max_sources
        },

        # Per-symbol breakdown
        "symbols": symbols_data,

        # Data source info
        "data_source": "real_exchange_account_ratios",
        "exchanges": ["bybit", "binance", "okx", "bitget"],
        "note": "Real L/S positioning from exchange account ratio APIs (not derived from funding)"
    }


def _get_contrarian_signal(lsr: float, crowd_side: str) -> dict:
    """Generate contrarian trading signal based on crowd positioning"""
    if crowd_side == "long" and lsr > 3.0:
        return {
            "signal": "SHORT",
            "strength": "strong",
            "reason": "Extremely crowded longs - high squeeze probability"
        }
    elif crowd_side == "long":
        return {
            "signal": "SHORT",
            "strength": "moderate",
            "reason": "Crowded longs - potential for reversal"
        }
    elif crowd_side == "short" and lsr < 0.33:
        return {
            "signal": "LONG",
            "strength": "strong",
            "reason": "Extremely crowded shorts - high squeeze probability"
        }
    elif crowd_side == "short":
        return {
            "signal": "LONG",
            "strength": "moderate",
            "reason": "Crowded shorts - potential for reversal"
        }
    else:
        return {
            "signal": "WAIT",
            "strength": "none",
            "reason": "No clear crowd bias - wait for confirmation"
        }


@router.get("/exchanges")
async def get_supported_exchanges():
    """List supported exchanges for aggregation"""
    return {
        "exchanges": {
            "cex": [
                {
                    "name": "bybit",
                    "display_name": "Bybit",
                    "endpoints": ["lsr", "funding", "oi", "taker", "basis", "liquidations"],
                    "status": "active"
                },
                {
                    "name": "binance",
                    "display_name": "Binance",
                    "endpoints": ["lsr", "funding", "oi", "taker", "liquidations", "smart_money"],
                    "status": "active"
                },
                {
                    "name": "okx",
                    "display_name": "OKX",
                    "endpoints": ["lsr", "funding", "oi", "taker", "liquidations"],
                    "status": "active"
                },
                {
                    "name": "bitget",
                    "display_name": "Bitget",
                    "endpoints": ["lsr", "funding"],
                    "status": "active"
                }
            ],
            "dex": [
                {
                    "name": "hyperliquid",
                    "display_name": "HyperLiquid",
                    "endpoints": ["funding", "oi", "cex_dex_divergence", "degen_sentiment"],
                    "status": "active",
                    "note": "Leading DEX for perps"
                },
                {
                    "name": "dydx",
                    "display_name": "dYdX v4",
                    "endpoints": ["funding", "oi", "cex_dex_divergence", "degen_sentiment"],
                    "status": "active",
                    "note": "Cosmos-based DEX"
                },
                {
                    "name": "asterdex",
                    "display_name": "AsterDEX",
                    "endpoints": ["funding", "oi", "cex_dex_divergence", "degen_sentiment"],
                    "status": "active",
                    "note": "Highest volume perp DEX ($41B+ daily)"
                }
            ],
            "meta": [
                {
                    "name": "coingecko",
                    "display_name": "CoinGecko (Aggregated)",
                    "endpoints": ["oi", "funding", "basis"],
                    "status": "optional",
                    "note": "Aggregates 120+ exchanges"
                }
            ]
        },
        "aggregation_methods": {
            "lsr": "Median with outlier rejection",
            "market_lsr": "Market-wide L/S weighted by BTC/ETH/SOL dominance",
            "funding": "Volume-weighted average",
            "oi": "Sum across exchanges",
            "taker": "Buy/Sell volume aggregation",
            "basis": "Volume-weighted average",
            "liquidations": "Sum with cascade detection",
            "smart_money": "Top trader vs retail divergence",
            "cex_dex_divergence": "CEX vs DEX funding comparison",
            "degen_sentiment": "DEX-only retail/degen flow"
        },
        "new_endpoints": {
            "market_lsr": "/api/aggregated/market-lsr - Market-wide L/S positioning (BTC+ETH+SOL)"
        }
    }


def _interpret_lsr(lsr: float, crowd_side: str) -> str:
    """Generate human-readable LSR interpretation"""
    if crowd_side == "long":
        if lsr > 3.0:
            return f"Extremely crowded longs (LSR: {lsr:.2f}). High probability of long squeeze. Consider SHORT."
        else:
            return f"Crowded longs (LSR: {lsr:.2f}). Potential for reversal. Fade the crowd."
    elif crowd_side == "short":
        if lsr < 0.33:
            return f"Extremely crowded shorts (LSR: {lsr:.2f}). High probability of short squeeze. Consider LONG."
        else:
            return f"Crowded shorts (LSR: {lsr:.2f}). Potential for reversal. Fade the crowd."
    else:
        return f"Balanced positioning (LSR: {lsr:.2f}). No clear crowd bias. Wait for confirmation."


def _interpret_funding(rate: float, direction: str) -> str:
    """Generate human-readable funding rate interpretation"""
    rate_pct = rate * 100
    if direction == "bullish":
        if rate > 0.001:
            return f"Very high funding ({rate_pct:.4f}%). Longs paying shorts heavily. Potential top signal."
        else:
            return f"Positive funding ({rate_pct:.4f}%). Bullish market sentiment."
    elif direction == "bearish":
        if rate < -0.0005:
            return f"Very negative funding ({rate_pct:.4f}%). Shorts paying longs. Potential bottom signal."
        else:
            return f"Negative funding ({rate_pct:.4f}%). Bearish market sentiment."
    else:
        return f"Neutral funding ({rate_pct:.4f}%). No strong directional bias."


def _calculate_assessment(lsr_signal: dict, funding_signal: dict) -> dict:
    """Calculate overall market assessment from aggregated signals"""
    score = 0
    factors = []

    # LSR contribution
    if 'value' in lsr_signal:
        lsr = lsr_signal['value']
        crowd_side = lsr_signal.get('crowd_side', 'balanced')

        if crowd_side == 'short':
            score += 1
            factors.append("Crowded shorts → bullish")
        elif crowd_side == 'long':
            score -= 1
            factors.append("Crowded longs → bearish")

    # Funding contribution
    if 'value' in funding_signal:
        direction = funding_signal.get('direction', 'neutral')

        if direction == 'bearish':
            score += 0.5  # Negative funding = bullish contrarian
            factors.append("Negative funding → bullish contrarian")
        elif direction == 'bullish' and funding_signal['value'] > 0.0005:
            score -= 0.5  # Very high funding = bearish contrarian
            factors.append("High funding → bearish contrarian")

    # Determine recommendation
    if score >= 1:
        recommendation = "BULLISH"
        action = "Consider LONG positions"
    elif score <= -1:
        recommendation = "BEARISH"
        action = "Consider SHORT positions"
    else:
        recommendation = "NEUTRAL"
        action = "Wait for clearer signals"

    return {
        "score": round(score, 2),
        "recommendation": recommendation,
        "action": action,
        "factors": factors,
        "confidence": "HIGH" if abs(score) >= 1.5 else "MEDIUM" if abs(score) >= 0.5 else "LOW"
    }


def _format_usd(value: float) -> str:
    """Format USD value with appropriate suffix"""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.2f}K"
    else:
        return f"${value:.2f}"


def _interpret_taker(ratio: float, aggressor: str) -> str:
    """Generate human-readable taker flow interpretation"""
    if aggressor == "buyers":
        if ratio > 1.5:
            return f"Strong buying pressure (ratio: {ratio:.2f}). Aggressive buyers dominating. Bullish short-term."
        else:
            return f"Moderate buying pressure (ratio: {ratio:.2f}). Buyers slightly more aggressive."
    elif aggressor == "sellers":
        if ratio < 0.67:
            return f"Strong selling pressure (ratio: {ratio:.2f}). Aggressive sellers dominating. Bearish short-term."
        else:
            return f"Moderate selling pressure (ratio: {ratio:.2f}). Sellers slightly more aggressive."
    else:
        return f"Neutral flow (ratio: {ratio:.2f}). No clear aggressor. Market in equilibrium."


def _interpret_basis(basis_pct: float, sentiment: str) -> str:
    """Generate human-readable basis interpretation"""
    if sentiment == "bullish":
        if basis_pct > 0.1:
            return f"High premium ({basis_pct:.4f}%). Strong bullish sentiment. Potential for mean reversion down."
        else:
            return f"Slight premium ({basis_pct:.4f}%). Mildly bullish sentiment."
    elif sentiment == "bearish":
        if basis_pct < -0.1:
            return f"High discount ({basis_pct:.4f}%). Strong bearish sentiment. Potential for mean reversion up."
        else:
            return f"Slight discount ({basis_pct:.4f}%). Mildly bearish sentiment."
    else:
        return f"Flat basis ({basis_pct:.4f}%). Neutral market. Perp tracking spot closely."


def _interpret_liquidations(ratio: float, cascade_risk: str) -> str:
    """Generate human-readable liquidation interpretation"""
    if cascade_risk == "high":
        side = "longs" if ratio > 1 else "shorts"
        return f"HIGH CASCADE RISK! Heavy {side} liquidations. Potential for further cascading liquidations."
    elif cascade_risk == "medium":
        return f"Moderate liquidation activity (L/S ratio: {ratio:.2f}). Monitor for acceleration."
    else:
        return f"Low liquidation activity (L/S ratio: {ratio:.2f}). Market relatively stable."


def _interpret_smart_money(divergence: float, signal: str) -> str:
    """Generate human-readable smart money interpretation"""
    if signal == "smart_money_long":
        return f"Smart money MORE LONG than retail (divergence: +{divergence:.2f}). Consider following smart money."
    elif signal == "smart_money_short":
        return f"Smart money MORE SHORT than retail (divergence: {divergence:.2f}). Consider following smart money."
    else:
        return f"Smart money ALIGNED with retail (divergence: {divergence:.2f}). No contrarian signal."


def _interpret_cex_dex_divergence(divergence: float, signal: str) -> str:
    """Generate human-readable CEX vs DEX divergence interpretation"""
    divergence_pct = divergence * 100
    if signal == "dex_bullish":
        return f"DEX traders MORE BULLISH than CEX (divergence: {divergence_pct:.4f}%). DEX often leads during FOMO. Consider LONG."
    elif signal == "dex_bearish":
        return f"DEX traders MORE BEARISH than CEX (divergence: {divergence_pct:.4f}%). DEX often leads during panic. Consider SHORT."
    else:
        return f"CEX and DEX ALIGNED (divergence: {divergence_pct:.4f}%). No divergence signal."


def _interpret_degen_sentiment(sentiment_score: float, signal: str) -> str:
    """Generate human-readable degen sentiment interpretation"""
    if signal == "degen_fomo":
        return f"DEGEN FOMO detected (score: {sentiment_score:.1f}). Retail traders heavily long. Potential contrarian SHORT."
    elif signal == "degen_panic":
        return f"DEGEN PANIC detected (score: {sentiment_score:.1f}). Retail traders heavily short. Potential contrarian LONG."
    else:
        return f"Neutral DEX sentiment (score: {sentiment_score:.1f}). No extreme retail positioning."
