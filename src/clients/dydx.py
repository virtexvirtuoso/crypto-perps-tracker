"""dYdX v4 exchange client"""

from typing import Optional
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class DYdXClient(BaseExchangeClient):
    """Client for dYdX v4 API

    Fetches trading volume, open interest, and market data from
    dYdX v4 decentralized perpetual futures exchange.
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.DYDX

    @property
    def base_url(self) -> str:
        """Base URL for dYdX v4 API"""
        return "https://indexer.dydx.trade"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume from dYdX v4

        Returns:
            MarketData object with volume information

        Raises:
            requests.RequestException: If API request fails
        """
        response = self._get("/v4/perpetualMarkets")

        markets = response.get('markets', {})

        if not markets:
            raise ValueError("No markets data returned")

        # Calculate totals
        total_volume = sum(float(m.get('volume24H', 0)) for m in markets.values())

        total_oi = 0
        for market in markets.values():
            oracle_price = float(market.get('oraclePrice', 0))
            oi = float(market.get('openInterest', 0))
            total_oi += oi * oracle_price

        # Get BTC funding rate
        btc_funding = None
        btc_market = markets.get('BTC-USD')
        if btc_market:
            btc_funding = float(btc_market.get('nextFundingRate', 0))

        # Get top pairs by volume
        top_pairs = self._get_top_pairs(markets, limit=10)

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            open_interest=total_oi,
            funding_rate=btc_funding,
            market_count=len(markets),
            top_pairs=top_pairs,
        )

    def _get_top_pairs(self, markets: dict, limit: int = 10) -> list[TradingPair]:
        """Extract top trading pairs by volume"""
        pairs_with_volume = []

        for ticker, market in markets.items():
            volume = float(market.get('volume24H', 0))

            # Parse ticker (e.g., "BTC-USD" -> base: BTC, quote: USD)
            parts = ticker.split('-')
            base = parts[0] if len(parts) > 0 else ticker
            quote = parts[1] if len(parts) > 1 else 'USD'

            pairs_with_volume.append({
                'symbol': ticker,
                'base': base,
                'quote': quote,
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

    def fetch_funding_rate(self, symbol: str = "BTC-USD") -> float:
        """Fetch current funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD", "ETH-USD")

        Returns:
            Current funding rate as decimal

        Raises:
            ValueError: If symbol not found
            requests.RequestException: If API request fails
        """
        response = self._get("/v4/perpetualMarkets")
        markets = response.get('markets', {})

        market = markets.get(symbol)
        if not market:
            raise ValueError(f"Symbol {symbol} not found")

        return float(market.get('nextFundingRate', 0))

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on dYdX v4

        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USD', 'ETH-USD', 'SOL-USD')

        Returns:
            SymbolData object or None if not found
        """
        try:
            response = self._get("/v4/perpetualMarkets")
            markets = response.get('markets', {})

            market = markets.get(symbol)
            if not market:
                return None

            oracle_price = float(market.get('oraclePrice', 0))
            price_change_24h = float(market.get('priceChange24H', 0))

            # Calculate price change percentage
            price_change_pct = None
            if oracle_price > 0:
                price_change_pct = (price_change_24h / oracle_price) * 100

            # Calculate OI
            oi_value = float(market.get('openInterest', 0)) * oracle_price

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=oracle_price,
                volume_24h=float(market.get('volume24H', 0)),
                price_change_24h_pct=price_change_pct,
                open_interest=oi_value,
                funding_rate=float(market.get('nextFundingRate', 0)),
                num_trades=int(market.get('trades24H', 0))
            )

        except Exception:
            return None
