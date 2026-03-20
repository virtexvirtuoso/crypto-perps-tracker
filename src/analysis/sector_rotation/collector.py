"""
Sector Rotation Data Collector - Multi-Exchange Aggregation

Collects and aggregates perpetual futures data from 8 exchanges covering
91.7% of market volume. Produces sector snapshots with:
- Volume-weighted price/funding metrics
- Cross-exchange OI aggregation
- CEX vs DEX flow analysis
- Funding spread computation
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from statistics import mean, stdev

from src.clients.factory import ClientFactory
from src.models.market import SymbolData

from .storage import (
    EXCHANGE_CONFIG,
    SECTOR_CONFIG,
    SMALL_SAMPLE_SECTORS,
    ExchangeCategory,
    ExchangeBreakdown,
    SectorSnapshot,
    OIPriceSignal,
    SampleSizeFlag,
    format_symbol_for_exchange,
    get_enabled_exchanges,
    get_cex_exchanges,
    get_dex_exchanges,
    get_exchange_weight,
    get_sector_metadata,
)

logger = logging.getLogger(__name__)


class SectorDataCollector:
    """
    Multi-exchange sector data collector.

    Fetches symbol data from multiple exchanges in parallel,
    aggregates by sector, and produces snapshots with CEX/DEX flow metrics.

    Usage:
        collector = SectorDataCollector()
        snapshots = await collector.collect_all_sectors()
    """

    def __init__(
        self,
        timeout: int = 15,
        retry_attempts: int = 2,
        max_workers: int = 8,
    ):
        """
        Initialize collector.

        Args:
            timeout: API request timeout per exchange
            retry_attempts: Number of retries for failed requests
            max_workers: Thread pool size for parallel fetching
        """
        self.factory = ClientFactory(timeout=timeout, retry_attempts=retry_attempts)
        self.max_workers = max_workers
        self._clients: Dict[str, Any] = {}
        self._price_history: Dict[str, List[float]] = {}  # For 4h change calc

    def _get_client(self, exchange: str):
        """Get or create client for exchange."""
        if exchange not in self._clients:
            try:
                self._clients[exchange] = self.factory.create(exchange)
            except ValueError:
                logger.warning(f"Exchange not supported: {exchange}")
                return None
        return self._clients[exchange]

    def fetch_symbol_from_exchange(
        self,
        base_symbol: str,
        exchange: str,
    ) -> Optional[Tuple[str, str, SymbolData]]:
        """
        Fetch symbol data from a single exchange.

        Args:
            base_symbol: Base symbol like 'ETH', 'BTC'
            exchange: Exchange name

        Returns:
            Tuple of (base_symbol, exchange, SymbolData) or None if failed
        """
        client = self._get_client(exchange)
        if not client:
            return None

        # Format symbol for exchange
        formatted_symbol = format_symbol_for_exchange(base_symbol, exchange)

        try:
            data = client.fetch_symbol(formatted_symbol)
            if data:
                return (base_symbol, exchange, data)
        except Exception as e:
            logger.debug(f"Failed to fetch {formatted_symbol} from {exchange}: {e}")

        return None

    def fetch_symbols_parallel(
        self,
        base_symbols: List[str],
        exchanges: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, SymbolData]]:
        """
        Fetch multiple symbols from multiple exchanges in parallel.

        Args:
            base_symbols: List of base symbols to fetch
            exchanges: Optional list of exchanges (defaults to enabled)

        Returns:
            Nested dict: {base_symbol: {exchange: SymbolData}}
        """
        if exchanges is None:
            exchanges = get_enabled_exchanges()

        results: Dict[str, Dict[str, SymbolData]] = {s: {} for s in base_symbols}

        # Create all fetch tasks
        tasks = [
            (symbol, exchange)
            for symbol in base_symbols
            for exchange in exchanges
        ]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.fetch_symbol_from_exchange, symbol, exchange): (symbol, exchange)
                for symbol, exchange in tasks
            }

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30)
                    if result:
                        base_symbol, exchange, data = result
                        results[base_symbol][exchange] = data
                except Exception as e:
                    symbol, exchange = futures[future]
                    logger.debug(f"Task failed for {symbol}@{exchange}: {e}")

        return results

    def aggregate_sector_data(
        self,
        sector_code: str,
        symbol_data: Dict[str, Dict[str, SymbolData]],
        prior_snapshot: Optional[SectorSnapshot] = None,
    ) -> SectorSnapshot:
        """
        Aggregate symbol data into a sector snapshot.

        Args:
            sector_code: Sector code (e.g., 'DEFI', 'L1')
            symbol_data: Nested dict of symbol -> exchange -> SymbolData
            prior_snapshot: Previous snapshot for 4h change calculation

        Returns:
            SectorSnapshot with aggregated metrics
        """
        timestamp = datetime.utcnow()
        symbols = SECTOR_CONFIG.get(sector_code, [])

        # Per-exchange aggregates
        exchange_volumes: Dict[str, float] = {}
        exchange_oi: Dict[str, float] = {}
        exchange_funding: Dict[str, List[float]] = {}
        exchange_symbol_counts: Dict[str, int] = {}

        # Symbol-level metrics
        all_prices: List[Tuple[float, float]] = []  # (price, weight)
        all_price_changes: List[Tuple[float, float]] = []  # (change, weight)
        all_funding_rates: List[Tuple[float, float]] = []  # (rate, weight)

        symbols_up = 0
        symbols_down = 0
        total_volume = 0.0
        total_oi = 0.0
        exchanges_with_data = set()

        for base_symbol in symbols:
            exchange_data = symbol_data.get(base_symbol, {})
            if not exchange_data:
                continue

            # Aggregate across exchanges for this symbol
            symbol_volume = 0.0
            symbol_oi = 0.0
            symbol_price_changes: List[Tuple[float, float]] = []
            symbol_funding_rates: List[Tuple[float, float]] = []
            best_price = None
            best_price_volume = 0.0

            for exchange, data in exchange_data.items():
                weight = get_exchange_weight(exchange)
                volume = data.volume_24h or 0.0
                oi = data.open_interest or 0.0
                funding = data.funding_rate
                price_change = data.price_change_24h_pct

                # Track exchange totals
                exchange_volumes[exchange] = exchange_volumes.get(exchange, 0) + volume
                exchange_oi[exchange] = exchange_oi.get(exchange, 0) + oi
                exchange_symbol_counts[exchange] = exchange_symbol_counts.get(exchange, 0) + 1

                if funding is not None:
                    if exchange not in exchange_funding:
                        exchange_funding[exchange] = []
                    exchange_funding[exchange].append(funding)

                exchanges_with_data.add(exchange)

                # Accumulate for symbol
                symbol_volume += volume
                symbol_oi += oi

                if price_change is not None:
                    symbol_price_changes.append((price_change, volume))

                if funding is not None:
                    symbol_funding_rates.append((funding, volume))

                # Track best price source (highest volume exchange)
                if volume > best_price_volume and data.price:
                    best_price = data.price
                    best_price_volume = volume

            # Symbol-level aggregation
            total_volume += symbol_volume
            total_oi += symbol_oi

            # Volume-weighted price change for symbol
            if symbol_price_changes:
                total_weight = sum(w for _, w in symbol_price_changes)
                if total_weight > 0:
                    weighted_change = sum(c * w for c, w in symbol_price_changes) / total_weight
                    all_price_changes.append((weighted_change, symbol_volume))

                    if weighted_change >= 0:
                        symbols_up += 1
                    else:
                        symbols_down += 1

            # Volume-weighted funding for symbol
            if symbol_funding_rates:
                total_weight = sum(w for _, w in symbol_funding_rates)
                if total_weight > 0:
                    weighted_funding = sum(r * w for r, w in symbol_funding_rates) / total_weight
                    all_funding_rates.append((weighted_funding, symbol_volume))

        # === Sector-level aggregations ===

        # Volume-weighted average price change
        avg_price_change_24h = 0.0
        if all_price_changes:
            total_weight = sum(w for _, w in all_price_changes)
            if total_weight > 0:
                avg_price_change_24h = sum(c * w for c, w in all_price_changes) / total_weight

        # Volume-weighted average funding rate
        avg_funding_rate = 0.0
        if all_funding_rates:
            total_weight = sum(w for _, w in all_funding_rates)
            if total_weight > 0:
                avg_funding_rate = sum(r * w for r, w in all_funding_rates) / total_weight

        # Funding spread (max - min across exchanges)
        funding_spread = 0.0
        if exchange_funding:
            exchange_avg_funding = {
                ex: mean(rates) for ex, rates in exchange_funding.items() if rates
            }
            if len(exchange_avg_funding) >= 2:
                funding_spread = max(exchange_avg_funding.values()) - min(exchange_avg_funding.values())

        # Breadth ratio
        total_symbols_with_data = symbols_up + symbols_down
        breadth_ratio = symbols_up / total_symbols_with_data if total_symbols_with_data > 0 else 0.5

        # CEX vs DEX metrics
        cex_exchanges = get_cex_exchanges()
        dex_exchanges = get_dex_exchanges()

        cex_volume = sum(exchange_volumes.get(ex, 0) for ex in cex_exchanges)
        dex_volume = sum(exchange_volumes.get(ex, 0) for ex in dex_exchanges)
        cex_oi = sum(exchange_oi.get(ex, 0) for ex in cex_exchanges)
        dex_oi = sum(exchange_oi.get(ex, 0) for ex in dex_exchanges)

        cex_volume_share = cex_volume / total_volume if total_volume > 0 else 0.0
        dex_volume_share = dex_volume / total_volume if total_volume > 0 else 0.0
        cex_oi_share = cex_oi / total_oi if total_oi > 0 else 0.0
        dex_oi_share = dex_oi / total_oi if total_oi > 0 else 0.0

        # CEX/DEX flow score: positive = CEX favored, negative = DEX favored
        # Compares volume share to expected weights
        expected_cex_share = sum(
            EXCHANGE_CONFIG[ex]['weight'] for ex in cex_exchanges
            if ex in EXCHANGE_CONFIG
        )
        cex_dex_flow_score = (cex_volume_share - expected_cex_share) * 2  # Scale to roughly -1 to +1

        # 4h price change (vs prior snapshot)
        volume_change_4h = 0.0
        if prior_snapshot and prior_snapshot.total_volume_24h > 0:
            volume_change_4h = ((total_volume - prior_snapshot.total_volume_24h)
                               / prior_snapshot.total_volume_24h) * 100

        # OI-Price signal
        oi_price_signal = self._determine_oi_price_signal(
            oi_change=0.0,  # Would need prior OI to calculate
            price_change=avg_price_change_24h,
        )

        # Data quality score
        max_symbols = len(symbols)
        data_quality_score = total_symbols_with_data / max_symbols if max_symbols > 0 else 0.0

        # Sample size flag
        if total_symbols_with_data < 3:
            sample_size_flag = SampleSizeFlag.INSUFFICIENT.value
        elif total_symbols_with_data < 5 or sector_code in SMALL_SAMPLE_SECTORS:
            sample_size_flag = SampleSizeFlag.SMALL.value
        else:
            sample_size_flag = SampleSizeFlag.NORMAL.value

        # Build exchange breakdown
        exchange_breakdown = []
        for exchange in exchanges_with_data:
            breakdown = ExchangeBreakdown(
                exchange=exchange,
                volume_24h=exchange_volumes.get(exchange, 0),
                open_interest=exchange_oi.get(exchange, 0),
                avg_funding_rate=mean(exchange_funding.get(exchange, [0])) if exchange in exchange_funding else 0.0,
                symbol_count=exchange_symbol_counts.get(exchange, 0),
                data_quality=exchange_symbol_counts.get(exchange, 0) / max_symbols if max_symbols > 0 else 0.0,
            )
            exchange_breakdown.append(breakdown)

        return SectorSnapshot(
            sector_code=sector_code,
            timestamp=timestamp,
            # Volume
            total_volume_24h=total_volume,
            volume_change_4h=volume_change_4h,
            # Price
            avg_price_change_24h=avg_price_change_24h,
            # OI
            total_oi=total_oi,
            oi_price_signal=oi_price_signal,
            # Funding
            avg_funding_rate=avg_funding_rate,
            funding_spread=funding_spread,
            # Breadth
            symbols_up=symbols_up,
            symbols_down=symbols_down,
            breadth_ratio=breadth_ratio,
            # CEX/DEX
            cex_volume_share=cex_volume_share,
            dex_volume_share=dex_volume_share,
            cex_oi_share=cex_oi_share,
            dex_oi_share=dex_oi_share,
            cex_dex_flow_score=cex_dex_flow_score,
            # Quality
            symbol_count=total_symbols_with_data,
            exchange_count=len(exchanges_with_data),
            data_quality_score=data_quality_score,
            sample_size_flag=sample_size_flag,
            # Breakdown
            exchange_breakdown=exchange_breakdown,
        )

    def _determine_oi_price_signal(
        self,
        oi_change: float,
        price_change: float,
        oi_threshold: float = 2.0,
        price_threshold: float = 1.0,
    ) -> str:
        """
        Determine OI-Price signal from changes.

        Matrix:
            OI Rising + Price Rising = NEW_LONGS
            OI Rising + Price Falling = NEW_SHORTS
            OI Falling + Price Rising = SHORT_COVER
            OI Falling + Price Falling = LONG_LIQUIDATION
        """
        oi_rising = oi_change > oi_threshold
        oi_falling = oi_change < -oi_threshold
        price_rising = price_change > price_threshold
        price_falling = price_change < -price_threshold

        if oi_rising and price_rising:
            return OIPriceSignal.NEW_LONGS.value
        elif oi_rising and price_falling:
            return OIPriceSignal.NEW_SHORTS.value
        elif oi_falling and price_rising:
            return OIPriceSignal.SHORT_COVER.value
        elif oi_falling and price_falling:
            return OIPriceSignal.LONG_LIQUIDATION.value
        else:
            return OIPriceSignal.NEUTRAL.value

    def collect_sector(
        self,
        sector_code: str,
        prior_snapshot: Optional[SectorSnapshot] = None,
    ) -> SectorSnapshot:
        """
        Collect data for a single sector.

        Args:
            sector_code: Sector to collect
            prior_snapshot: Previous snapshot for change calculation

        Returns:
            SectorSnapshot with aggregated data
        """
        symbols = SECTOR_CONFIG.get(sector_code, [])
        if not symbols:
            logger.warning(f"No symbols configured for sector: {sector_code}")
            return SectorSnapshot(sector_code=sector_code)

        logger.info(f"Collecting {len(symbols)} symbols for sector {sector_code}")

        # Fetch all symbols in parallel
        symbol_data = self.fetch_symbols_parallel(symbols)

        # Aggregate into snapshot
        snapshot = self.aggregate_sector_data(sector_code, symbol_data, prior_snapshot)

        logger.info(
            f"Collected {sector_code}: {snapshot.symbol_count} symbols, "
            f"${snapshot.total_volume_24h/1e6:.1f}M volume, "
            f"{snapshot.exchange_count} exchanges"
        )

        return snapshot

    def collect_all_sectors(
        self,
        prior_snapshots: Optional[Dict[str, SectorSnapshot]] = None,
    ) -> Dict[str, SectorSnapshot]:
        """
        Collect data for all configured sectors.

        Args:
            prior_snapshots: Dict of previous snapshots by sector code

        Returns:
            Dict of sector_code -> SectorSnapshot
        """
        if prior_snapshots is None:
            prior_snapshots = {}

        logger.info(f"Starting collection for {len(SECTOR_CONFIG)} sectors")
        start_time = datetime.utcnow()

        # Collect all symbols across all sectors at once for efficiency
        all_symbols = []
        for symbols in SECTOR_CONFIG.values():
            all_symbols.extend(symbols)
        all_symbols = list(set(all_symbols))  # Dedupe

        logger.info(f"Fetching {len(all_symbols)} unique symbols from {len(get_enabled_exchanges())} exchanges")

        # Single parallel fetch for all symbols
        all_data = self.fetch_symbols_parallel(all_symbols)

        # Aggregate by sector
        snapshots = {}
        for sector_code, symbols in SECTOR_CONFIG.items():
            sector_data = {s: all_data.get(s, {}) for s in symbols}
            prior = prior_snapshots.get(sector_code)
            snapshots[sector_code] = self.aggregate_sector_data(sector_code, sector_data, prior)

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Collection complete in {elapsed:.1f}s for {len(snapshots)} sectors")

        return snapshots

    def get_market_totals(
        self,
        snapshots: Dict[str, SectorSnapshot],
    ) -> Dict[str, float]:
        """
        Calculate market-wide totals from sector snapshots.

        Returns:
            Dict with total_volume, total_oi, avg_funding, etc.
        """
        total_volume = sum(s.total_volume_24h for s in snapshots.values())
        total_oi = sum(s.total_oi for s in snapshots.values())

        # Volume-weighted funding
        weighted_funding = sum(
            s.avg_funding_rate * s.total_volume_24h
            for s in snapshots.values()
        )
        avg_funding = weighted_funding / total_volume if total_volume > 0 else 0.0

        # Market-wide CEX/DEX
        cex_volume = sum(
            s.total_volume_24h * s.cex_volume_share
            for s in snapshots.values()
        )
        dex_volume = sum(
            s.total_volume_24h * s.dex_volume_share
            for s in snapshots.values()
        )

        return {
            'total_volume_24h': total_volume,
            'total_oi': total_oi,
            'avg_funding_rate': avg_funding,
            'cex_volume': cex_volume,
            'dex_volume': dex_volume,
            'cex_market_share': cex_volume / total_volume if total_volume > 0 else 0.0,
            'sector_count': len(snapshots),
            'symbol_count': sum(s.symbol_count for s in snapshots.values()),
        }


# Async wrapper for use in FastAPI routes
async def collect_sectors_async(
    collector: Optional[SectorDataCollector] = None,
    prior_snapshots: Optional[Dict[str, SectorSnapshot]] = None,
) -> Dict[str, SectorSnapshot]:
    """
    Async wrapper for sector collection.

    Args:
        collector: Optional pre-configured collector
        prior_snapshots: Previous snapshots for change calculation

    Returns:
        Dict of sector snapshots
    """
    if collector is None:
        collector = SectorDataCollector()

    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        collector.collect_all_sectors,
        prior_snapshots,
    )
