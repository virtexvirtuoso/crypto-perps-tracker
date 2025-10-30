"""HyperLiquid exchange client"""

from typing import Optional, List
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class HyperLiquidClient(BaseExchangeClient):
    """Client for HyperLiquid DEX API

    Fetches trading volume, open interest, and market data from
    HyperLiquid decentralized perpetual futures.
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.HYPERLIQUID

    @property
    def base_url(self) -> str:
        """Base URL for HyperLiquid API"""
        return "https://api.hyperliquid.xyz"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume from HyperLiquid

        Returns:
            MarketData object with volume information

        Raises:
            requests.RequestException: If API request fails
        """
        # HyperLiquid uses POST requests with JSON body
        response = self._post(
            "/info",
            json={"type": "metaAndAssetCtxs"}
        )

        if not isinstance(response, list) or len(response) < 2:
            raise ValueError("Unexpected response format from HyperLiquid")

        universe = response[0].get("universe", [])
        asset_ctxs = response[1]

        # Calculate totals
        total_volume = sum(float(ctx.get('dayNtlVlm', 0)) for ctx in asset_ctxs)

        total_oi = 0
        for ctx in asset_ctxs:
            if 'openInterest' in ctx and 'markPx' in ctx:
                oi_val = float(ctx['openInterest']) * float(ctx['markPx'])
                total_oi += oi_val

        # Get BTC funding rate
        btc_funding = None
        for i, ctx in enumerate(asset_ctxs):
            if i < len(universe) and universe[i].get('name') == 'BTC':
                btc_funding = float(ctx.get('funding', 0))
                break

        # Get top pairs by volume
        top_pairs = self._get_top_pairs(universe, asset_ctxs, limit=10)

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            open_interest=total_oi,
            funding_rate=btc_funding,
            market_count=len(asset_ctxs),
            top_pairs=top_pairs,
        )

    def _get_top_pairs(self, universe: list, asset_ctxs: list, limit: int = 10) -> List[TradingPair]:
        """Extract top trading pairs by volume"""
        pairs_with_volume = []

        for i, ctx in enumerate(asset_ctxs):
            if i < len(universe):
                symbol = universe[i].get('name', 'UNKNOWN')
                volume = float(ctx.get('dayNtlVlm', 0))

                pairs_with_volume.append({
                    'symbol': symbol,
                    'base': symbol,
                    'quote': 'USD',
                    'volume': volume
                })

        # Sort by volume
        pairs_with_volume.sort(key=lambda x: x['volume'], reverse=True)

        top_pairs = []
        for p in pairs_with_volume[:limit]:
            top_pairs.append(TradingPair(
                symbol=p['symbol'],
                base=p['base'],
                quote=p['quote'],
                volume=p['volume']
            ))

        return top_pairs

    def fetch_funding_rate(self, symbol: str = "BTC") -> float:
        """Fetch current funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., "BTC", "ETH")

        Returns:
            Current funding rate as decimal

        Raises:
            ValueError: If symbol not found
            requests.RequestException: If API request fails
        """
        response = self._post(
            "/info",
            json={"type": "metaAndAssetCtxs"}
        )

        if not isinstance(response, list) or len(response) < 2:
            raise ValueError("Unexpected response format")

        universe = response[0].get("universe", [])
        asset_ctxs = response[1]

        for i, ctx in enumerate(asset_ctxs):
            if i < len(universe) and universe[i].get('name') == symbol:
                return float(ctx.get('funding', 0))

        raise ValueError(f"Symbol {symbol} not found")

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on HyperLiquid

        Args:
            symbol: Trading pair symbol (e.g., 'BTC', 'ETH', 'SOL')

        Returns:
            SymbolData object or None if not found
        """
        try:
            response = self._post(
                "/info",
                json={"type": "metaAndAssetCtxs"}
            )

            if not isinstance(response, list) or len(response) < 2:
                return None

            universe = response[0].get("universe", [])
            asset_ctxs = response[1]

            # Find the symbol
            for i, ctx in enumerate(asset_ctxs):
                if i < len(universe) and universe[i].get('name') == symbol:
                    mark_price = float(ctx.get('markPx', 0))
                    prev_price = float(ctx.get('prevDayPx', 0))

                    # Calculate price change
                    price_change_pct = None
                    if prev_price > 0:
                        price_change_pct = ((mark_price - prev_price) / prev_price) * 100

                    # Calculate OI
                    oi_value = None
                    if 'openInterest' in ctx and 'markPx' in ctx:
                        oi_value = float(ctx['openInterest']) * mark_price

                    return SymbolData(
                        exchange=self.exchange_type,
                        symbol=symbol,
                        price=mark_price,
                        volume_24h=float(ctx.get('dayNtlVlm', 0)),
                        price_change_24h_pct=price_change_pct,
                        open_interest=oi_value,
                        funding_rate=float(ctx.get('funding', 0)),
                        num_trades=None
                    )

            return None

        except Exception:
            return None
