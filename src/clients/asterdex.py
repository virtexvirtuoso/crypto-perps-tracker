"""AsterDEX client for perpetual futures data

AsterDEX is a decentralized perpetual futures exchange with a
Binance-compatible API structure.
"""

from typing import Dict, Any, Optional
from src.clients.base import BaseExchangeClient
from src.models.market import ExchangeType, MarketData, TradingPair, SymbolData


class AsterDEXClient(BaseExchangeClient):
    """Client for AsterDEX perpetual futures API

    API Documentation: https://docs.asterdex.com
    Base URL: https://fapi.asterdex.com
    """

    @property
    def exchange_type(self) -> ExchangeType:
        return ExchangeType.ASTERDEX

    @property
    def base_url(self) -> str:
        return "https://fapi.asterdex.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h volume data from AsterDEX

        Returns:
            MarketData with volume, top pairs, and market count
        """
        # Get 24hr ticker data for all perpetual pairs
        response = self._get("/fapi/v1/ticker/24hr")

        if not isinstance(response, list):
            raise ValueError(f"Unexpected response format: {type(response)}")

        # Calculate total volume in USD
        total_volume = sum(float(ticker.get('quoteVolume', 0)) for ticker in response)

        # Get top trading pairs by volume
        sorted_tickers = sorted(
            response,
            key=lambda x: float(x.get('quoteVolume', 0)),
            reverse=True
        )

        top_pairs = [
            TradingPair(
                symbol=ticker['symbol'],
                base=ticker['symbol'].replace('USDT', ''),  # Simple extraction
                quote='USDT',
                volume=float(ticker.get('quoteVolume', 0))
            )
            for ticker in sorted_tickers[:10]
        ]

        # Get BTC ticker for funding rate reference (if available)
        btc_ticker = next(
            (t for t in response if t['symbol'] == 'BTCUSDT'),
            {}
        )

        # Note: AsterDEX ticker endpoint doesn't include funding rate
        # Would need separate endpoint for that

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            top_pairs=top_pairs,
            market_count=len(response),
            open_interest=None,  # Not available in ticker endpoint
            funding_rate=None    # Not available in ticker endpoint
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on AsterDEX

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            SymbolData with price, volume, and available metrics
        """
        try:
            # Get ticker data for specific symbol
            response = self._get("/fapi/v1/ticker/24hr", params={"symbol": symbol})

            # Response can be a single object or list with one item
            ticker = response if isinstance(response, dict) else response[0]

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=float(ticker.get('lastPrice', 0)),
                volume_24h=float(ticker.get('quoteVolume', 0)),
                price_change_24h=float(ticker.get('priceChange', 0)),
                price_change_pct=float(ticker.get('priceChangePercent', 0)),
                high_24h=float(ticker.get('highPrice', 0)),
                low_24h=float(ticker.get('lowPrice', 0)),
                trades_24h=int(ticker.get('count', 0)),
                open_interest=None,  # Not in ticker endpoint
                funding_rate=None    # Not in ticker endpoint
            )
        except Exception as e:
            self._logger.error(f"Error fetching symbol {symbol}: {e}")
            return None
