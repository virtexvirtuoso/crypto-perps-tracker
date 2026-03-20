"""
Spot Rotation Data Collector - CoinGecko Version

Fetches spot market data from CoinGecko API for sector rotation analysis.
Handles rate limiting, batching, and error recovery.

CoinGecko API Endpoints Used:
- /coins/markets - Token prices, volumes, market caps
- /simple/price - Lightweight price checks
- /global - Total market metrics

Rate Limits (free tier):
- 30 requests/minute
- 2.5s delay between requests recommended
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .storage import (
    SpotSectorSnapshot,
    TokenSnapshot,
    SPOT_SECTOR_CONFIG,
    SPOT_SECTOR_METADATA,
    SMALL_SAMPLE_SECTORS,
    COINGECKO_RATE_LIMIT,
    COINGECKO_BATCH_SIZE,
    get_all_token_ids,
    get_sector_for_token,
    classify_market_cap_tier,
    MarketCapTier,
    SampleSizeFlag,
)

logger = logging.getLogger(__name__)


@dataclass
class GlobalMarketData:
    """Global cryptocurrency market data from CoinGecko."""
    total_market_cap: float = 0.0
    total_volume_24h: float = 0.0
    btc_dominance: float = 0.0
    eth_dominance: float = 0.0
    market_cap_change_24h: float = 0.0
    timestamp: datetime = None


class CoinGeckoClient:
    """
    Async CoinGecko API client with rate limiting.

    Handles:
    - Rate limit compliance (30 req/min)
    - Automatic retries with backoff
    - Batch token fetching
    """

    BASE_URL = "https://api.coingecko.com/api/v3"
    RATE_LIMIT_DELAY = 2.5  # seconds between requests

    def __init__(self, api_key: Optional[str] = None):
        """Initialize client.

        Args:
            api_key: Optional CoinGecko API key for higher rate limits
        """
        self.api_key = api_key
        self._last_request_time = 0.0
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {'Accept': 'application/json'}
            if self.api_key:
                headers['x-cg-pro-api-key'] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            await asyncio.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        retries: int = 3
    ) -> Optional[Any]:
        """Make API request with rate limiting and retries."""
        await self._rate_limit()

        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(retries):
            try:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        # Rate limited - exponential backoff
                        wait_time = (2 ** attempt) * 5
                        logger.warning(f"Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"CoinGecko API error: {response.status}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{retries})")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return None

    async def get_global_data(self) -> Optional[GlobalMarketData]:
        """Fetch global market data."""
        data = await self._request("/global")
        if not data or 'data' not in data:
            return None

        market = data['data']
        return GlobalMarketData(
            total_market_cap=market.get('total_market_cap', {}).get('usd', 0),
            total_volume_24h=market.get('total_volume', {}).get('usd', 0),
            btc_dominance=market.get('market_cap_percentage', {}).get('btc', 0),
            eth_dominance=market.get('market_cap_percentage', {}).get('eth', 0),
            market_cap_change_24h=market.get('market_cap_change_percentage_24h_usd', 0),
            timestamp=datetime.utcnow(),
        )

    async def get_coins_markets(
        self,
        token_ids: List[str],
        vs_currency: str = "usd"
    ) -> List[Dict]:
        """
        Fetch market data for multiple tokens.

        Args:
            token_ids: List of CoinGecko token IDs
            vs_currency: Quote currency (default: usd)

        Returns:
            List of token market data dicts
        """
        all_results = []

        # Batch tokens to respect URL length limits
        for i in range(0, len(token_ids), COINGECKO_BATCH_SIZE):
            batch = token_ids[i:i + COINGECKO_BATCH_SIZE]
            ids_str = ",".join(batch)

            params = {
                'vs_currency': vs_currency,
                'ids': ids_str,
                'order': 'market_cap_desc',
                'per_page': len(batch),
                'page': 1,
                'sparkline': 'false',
                'price_change_percentage': '1h,24h,7d,30d',
            }

            data = await self._request("/coins/markets", params)
            if data:
                all_results.extend(data)

        return all_results

    async def get_btc_price(self) -> Dict[str, float]:
        """Get BTC price and 24h change for reference."""
        data = await self._request("/simple/price", params={
            'ids': 'bitcoin',
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
        })
        if data and 'bitcoin' in data:
            return {
                'price': data['bitcoin'].get('usd', 0),
                'change_24h': data['bitcoin'].get('usd_24h_change', 0),
            }
        return {'price': 0, 'change_24h': 0}

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()


class SpotDataCollector:
    """
    Collects and aggregates spot market data by sector.

    Responsibilities:
    - Fetch token data from CoinGecko
    - Aggregate metrics by sector
    - Calculate sector-level statistics
    - Build SpotSectorSnapshot objects
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize collector.

        Args:
            api_key: Optional CoinGecko API key
        """
        self.client = CoinGeckoClient(api_key)
        self._global_data: Optional[GlobalMarketData] = None
        self._btc_data: Dict[str, float] = {}

    async def collect_all_sectors(self) -> Dict[str, SpotSectorSnapshot]:
        """
        Collect data for all sectors.

        Returns:
            Dictionary mapping sector_code to SpotSectorSnapshot
        """
        logger.info("Starting spot sector data collection...")

        # Get global market data first
        self._global_data = await self.client.get_global_data()
        self._btc_data = await self.client.get_btc_price()

        # Get all unique token IDs
        all_tokens = get_all_token_ids()
        logger.info(f"Fetching data for {len(all_tokens)} tokens...")

        # Fetch all token data
        token_data = await self.client.get_coins_markets(all_tokens)
        logger.info(f"Received data for {len(token_data)} tokens")

        # Group by sector
        sector_tokens: Dict[str, List[Dict]] = {sector: [] for sector in SPOT_SECTOR_CONFIG}

        for token in token_data:
            token_id = token.get('id', '')
            sector = get_sector_for_token(token_id)
            if sector:
                sector_tokens[sector].append(token)

        # Build snapshots for each sector
        snapshots = {}
        for sector_code, tokens in sector_tokens.items():
            if tokens:
                snapshot = self._build_sector_snapshot(sector_code, tokens)
                snapshots[sector_code] = snapshot
                logger.debug(f"Built snapshot for {sector_code}: {len(tokens)} tokens")

        logger.info(f"Collection complete: {len(snapshots)} sectors")
        return snapshots

    def _build_sector_snapshot(
        self,
        sector_code: str,
        tokens: List[Dict]
    ) -> SpotSectorSnapshot:
        """Build a sector snapshot from token data."""
        now = datetime.utcnow()
        snapshot = SpotSectorSnapshot(
            sector_code=sector_code,
            timestamp=now,
            token_count=len(tokens),
        )

        if not tokens:
            return snapshot

        # Convert to TokenSnapshots and collect metrics
        token_snapshots = []
        total_mcap = 0.0
        total_volume = 0.0
        mcap_weighted_price_change_1h = 0.0
        mcap_weighted_price_change_24h = 0.0
        mcap_weighted_price_change_7d = 0.0
        mcap_weighted_price_change_30d = 0.0

        tokens_up_1h = 0
        tokens_up_24h = 0
        tokens_up_7d = 0
        tokens_down_24h = 0

        tier_mcaps = {tier: 0.0 for tier in MarketCapTier}

        for t in tokens:
            ts = TokenSnapshot(
                coingecko_id=t.get('id', ''),
                symbol=t.get('symbol', '').upper(),
                name=t.get('name', ''),
                current_price=t.get('current_price', 0) or 0,
                price_change_1h=t.get('price_change_percentage_1h_in_currency', 0) or 0,
                price_change_24h=t.get('price_change_percentage_24h_in_currency', 0) or 0,
                price_change_7d=t.get('price_change_percentage_7d_in_currency', 0) or 0,
                price_change_30d=t.get('price_change_percentage_30d_in_currency', 0) or 0,
                volume_24h=t.get('total_volume', 0) or 0,
                market_cap=t.get('market_cap', 0) or 0,
                market_cap_rank=t.get('market_cap_rank', 0) or 0,
                market_cap_change_24h=t.get('market_cap_change_percentage_24h', 0) or 0,
                circulating_supply=t.get('circulating_supply', 0) or 0,
                total_supply=t.get('total_supply', 0) or 0,
                max_supply=t.get('max_supply'),
                timestamp=now,
            )
            token_snapshots.append(ts)

            # Aggregate metrics
            mcap = ts.market_cap
            total_mcap += mcap
            total_volume += ts.volume_24h

            # Market cap weighted price changes
            mcap_weighted_price_change_1h += ts.price_change_1h * mcap
            mcap_weighted_price_change_24h += ts.price_change_24h * mcap
            mcap_weighted_price_change_7d += ts.price_change_7d * mcap
            mcap_weighted_price_change_30d += ts.price_change_30d * mcap

            # Breadth
            if ts.price_change_1h > 0:
                tokens_up_1h += 1
            if ts.price_change_24h > 0:
                tokens_up_24h += 1
            else:
                tokens_down_24h += 1
            if ts.price_change_7d > 0:
                tokens_up_7d += 1

            # Tier distribution
            tier = classify_market_cap_tier(mcap)
            tier_mcaps[tier] += mcap

        # Calculate weighted averages
        if total_mcap > 0:
            snapshot.avg_price_change_1h = mcap_weighted_price_change_1h / total_mcap
            snapshot.avg_price_change_24h = mcap_weighted_price_change_24h / total_mcap
            snapshot.avg_price_change_7d = mcap_weighted_price_change_7d / total_mcap
            snapshot.avg_price_change_30d = mcap_weighted_price_change_30d / total_mcap

            # Tier percentages
            snapshot.mega_cap_pct = tier_mcaps[MarketCapTier.MEGA] / total_mcap * 100
            snapshot.large_cap_pct = tier_mcaps[MarketCapTier.LARGE] / total_mcap * 100
            snapshot.mid_cap_pct = tier_mcaps[MarketCapTier.MID] / total_mcap * 100
            snapshot.small_cap_pct = tier_mcaps[MarketCapTier.SMALL] / total_mcap * 100
            snapshot.micro_cap_pct = tier_mcaps[MarketCapTier.MICRO] / total_mcap * 100

        # Set basic metrics
        snapshot.total_market_cap = total_mcap
        snapshot.total_volume_24h = total_volume
        snapshot.volume_mcap_ratio = total_volume / total_mcap if total_mcap > 0 else 0

        # Breadth metrics
        n = len(tokens)
        snapshot.tokens_up_1h = tokens_up_1h
        snapshot.tokens_up_24h = tokens_up_24h
        snapshot.tokens_up_7d = tokens_up_7d
        snapshot.tokens_down_24h = tokens_down_24h
        snapshot.breadth_ratio_24h = tokens_up_24h / n if n > 0 else 0
        snapshot.breadth_ratio_7d = tokens_up_7d / n if n > 0 else 0

        # Market cap weighted breadth
        up_mcap = sum(ts.market_cap for ts in token_snapshots if ts.price_change_24h > 0)
        snapshot.weighted_breadth = up_mcap / total_mcap if total_mcap > 0 else 0

        # Momentum (average of 24h and 7d weighted)
        snapshot.momentum_24h = snapshot.avg_price_change_24h
        snapshot.momentum_7d = snapshot.avg_price_change_7d

        # Momentum consistency (% of tokens moving same direction as sector)
        sector_direction = 1 if snapshot.avg_price_change_24h > 0 else -1
        same_dir = sum(1 for ts in token_snapshots
                       if (ts.price_change_24h > 0) == (sector_direction > 0))
        snapshot.momentum_consistency = same_dir / n if n > 0 else 0

        # Market share if global data available
        if self._global_data and self._global_data.total_market_cap > 0:
            snapshot.market_cap_share_pct = (
                total_mcap / self._global_data.total_market_cap * 100
            )
            snapshot.volume_share_pct = (
                total_volume / self._global_data.total_volume_24h * 100
                if self._global_data.total_volume_24h > 0 else 0
            )

        # Relative strength vs BTC
        btc_change_24h = self._btc_data.get('change_24h', 0)
        snapshot.sector_rs_24h = snapshot.avg_price_change_24h - btc_change_24h

        # Data quality
        snapshot.data_quality_score = min(1.0, n / 5)  # Full quality at 5+ tokens

        # Sample size flag
        if n >= 5:
            snapshot.sample_size_flag = SampleSizeFlag.NORMAL.value
        elif n >= 3:
            snapshot.sample_size_flag = SampleSizeFlag.SMALL.value
        else:
            snapshot.sample_size_flag = SampleSizeFlag.INSUFFICIENT.value

        # Store token snapshots
        snapshot.token_snapshots = token_snapshots

        return snapshot

    async def close(self):
        """Clean up resources."""
        await self.client.close()


async def collect_spot_sectors(api_key: Optional[str] = None) -> Dict[str, SpotSectorSnapshot]:
    """
    Convenience function to collect all spot sector data.

    Args:
        api_key: Optional CoinGecko API key

    Returns:
        Dictionary mapping sector_code to SpotSectorSnapshot
    """
    collector = SpotDataCollector(api_key)
    try:
        return await collector.collect_all_sectors()
    finally:
        await collector.close()
