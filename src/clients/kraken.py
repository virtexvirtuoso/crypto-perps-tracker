"""Kraken Futures client for perpetual futures data

Kraken Futures is a regulated perpetual futures exchange offering
BTC, ETH, and various altcoin perpetual contracts.
"""

from typing import Dict, Any, Optional
from src.clients.base import BaseExchangeClient
from src.models.market import ExchangeType, MarketData, TradingPair, SymbolData


class KrakenClient(BaseExchangeClient):
    """Client for Kraken Futures API (v3)

    API Documentation: https://docs.kraken.com/api/docs/futures-api/
    Base URL: https://futures.kraken.com/derivatives/api/v3
    """

    @property
    def exchange_type(self) -> ExchangeType:
        return ExchangeType.KRAKEN

    @property
    def base_url(self) -> str:
        return "https://futures.kraken.com/derivatives/api/v3"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h volume data from Kraken Futures

        Returns:
            MarketData with volume, top pairs, and market count
        """
        # Get ticker data for all perpetual contracts
        response = self._get("/tickers")

        if response.get('result') != 'success':
            raise ValueError(f"Kraken API error: {response.get('error', 'Unknown error')}")

        tickers = response.get('tickers', [])

        if not tickers:
            raise ValueError("No ticker data received from Kraken")

        # Filter for perpetual contracts (symbol starts with 'PI_' or 'PF_')
        perp_tickers = [
            t for t in tickers
            if t.get('symbol', '').startswith(('PI_', 'PF_'))
        ]

        # Calculate total volume (volumeQuote is in USD for USD-settled contracts)
        total_volume = sum(
            float(ticker.get('volumeQuote', 0))
            for ticker in perp_tickers
        )

        # Sort by volume to get top pairs
        sorted_tickers = sorted(
            perp_tickers,
            key=lambda x: float(x.get('volumeQuote', 0)),
            reverse=True
        )

        # Extract top trading pairs
        top_pairs = []
        for ticker in sorted_tickers[:10]:
            symbol = ticker['symbol']
            # Parse symbol: PI_XBTUSD -> BTC/USD
            base = symbol.replace('PI_', '').replace('PF_', '').replace('USD', '')
            top_pairs.append(
                TradingPair(
                    symbol=symbol,
                    base=base,
                    quote='USD',
                    volume=float(ticker.get('volumeQuote', 0))
                )
            )

        # Get BTC perpetual for funding rate (if available)
        btc_perp = next(
            (t for t in perp_tickers if t['symbol'] == 'PI_XBTUSD'),
            {}
        )

        funding_rate = None
        if btc_perp and 'fundingRate' in btc_perp:
            # Kraken returns funding rate as decimal (e.g., 0.0001 = 0.01%)
            funding_rate = float(btc_perp.get('fundingRate', 0)) * 100

        # Calculate total open interest
        total_oi = sum(
            float(ticker.get('openInterest', 0)) * float(ticker.get('markPrice', 0))
            for ticker in perp_tickers
            if 'openInterest' in ticker and 'markPrice' in ticker
        )

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            top_pairs=top_pairs,
            market_count=len(perp_tickers),
            open_interest=total_oi if total_oi > 0 else None,
            funding_rate=funding_rate
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on Kraken Futures

        Args:
            symbol: Trading pair symbol (e.g., 'PI_XBTUSD')

        Returns:
            SymbolData with price, volume, and available metrics
        """
        try:
            # Get all tickers (Kraken doesn't have single-symbol endpoint)
            response = self._get("/tickers")

            if response.get('result') != 'success':
                self._logger.error(f"Kraken API error: {response.get('error')}")
                return None

            tickers = response.get('tickers', [])

            # Find the specific ticker
            ticker = next(
                (t for t in tickers if t['symbol'] == symbol),
                None
            )

            if not ticker:
                self._logger.error(f"Symbol {symbol} not found in Kraken tickers")
                return None

            # Calculate 24h price change
            mark_price = float(ticker.get('markPrice', 0))
            last_price = float(ticker.get('last', mark_price))  # Use mark if last not available

            # Note: Kraken doesn't provide 24h open price in tickers endpoint
            # Would need separate /historicalfundingrates or /ohlc endpoint

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=last_price,
                volume_24h=float(ticker.get('volumeQuote', 0)),
                price_change_24h=None,  # Not available in tickers
                price_change_pct=None,  # Not available in tickers
                high_24h=None,          # Not available in tickers
                low_24h=None,           # Not available in tickers
                trades_24h=None,        # Not available in tickers
                open_interest=float(ticker.get('openInterest', 0)) * mark_price if 'openInterest' in ticker else None,
                funding_rate=float(ticker.get('fundingRate', 0)) * 100 if 'fundingRate' in ticker else None
            )

        except Exception as e:
            self._logger.error(f"Error fetching symbol {symbol}: {e}")
            return None
