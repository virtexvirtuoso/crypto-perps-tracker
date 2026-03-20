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
            SymbolData with price, volume, funding rate, and open interest
        """
        try:
            # Get ticker data for specific symbol
            response = self._get("/fapi/v1/ticker/24hr", params={"symbol": symbol})
            ticker = response if isinstance(response, dict) else response[0]

            # Get funding rate and open interest from dedicated endpoints
            funding_rate = None
            open_interest_usd = None

            try:
                premium_data = self.fetch_premium_index(symbol)
                if premium_data:
                    funding_rate = premium_data.get('funding_rate')
            except Exception:
                pass

            try:
                oi_data = self.fetch_open_interest(symbol)
                if oi_data:
                    # Convert OI from base asset to USD
                    price = float(ticker.get('lastPrice', 0))
                    oi_base = float(oi_data.get('open_interest', 0))
                    open_interest_usd = oi_base * price
            except Exception:
                pass

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=float(ticker.get('lastPrice', 0)),
                volume_24h=float(ticker.get('quoteVolume', 0)),
                price_change_24h_pct=float(ticker.get('priceChangePercent', 0)),
                open_interest=open_interest_usd,
                funding_rate=funding_rate,
                num_trades=int(ticker.get('count', 0))
            )
        except Exception:
            return None

    def fetch_premium_index(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch premium index and funding rate for a symbol

        Uses Binance-compatible /fapi/v1/premiumIndex endpoint.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Dict with mark price, index price, funding rate, and next funding time
        """
        try:
            response = self._get("/fapi/v1/premiumIndex", params={"symbol": symbol})

            return {
                'symbol': response.get('symbol'),
                'mark_price': float(response.get('markPrice', 0)),
                'index_price': float(response.get('indexPrice', 0)),
                'funding_rate': float(response.get('lastFundingRate', 0)),
                'next_funding_time': response.get('nextFundingTime'),
                'interest_rate': float(response.get('interestRate', 0)),
                'timestamp': response.get('time')
            }
        except Exception:
            return None

    def fetch_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch open interest for a symbol

        Uses Binance-compatible /fapi/v1/openInterest endpoint.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Dict with open interest in base asset
        """
        try:
            response = self._get("/fapi/v1/openInterest", params={"symbol": symbol})

            return {
                'symbol': response.get('symbol'),
                'open_interest': float(response.get('openInterest', 0)),
                'timestamp': response.get('time')
            }
        except Exception:
            return None

    def fetch_funding_rate_history(
        self,
        symbol: str,
        limit: int = 1
    ) -> Optional[list]:
        """Fetch funding rate history for a symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            limit: Number of records to fetch (default: 1)

        Returns:
            List of funding rate records
        """
        try:
            response = self._get(
                "/fapi/v1/fundingRate",
                params={"symbol": symbol, "limit": limit}
            )

            if isinstance(response, list):
                return [
                    {
                        'symbol': r.get('symbol'),
                        'funding_rate': float(r.get('fundingRate', 0)),
                        'funding_time': r.get('fundingTime')
                    }
                    for r in response
                ]
            return None
        except Exception:
            return None
