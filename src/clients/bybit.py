"""Bybit exchange client

Bybit is a major cryptocurrency derivatives exchange.
API Documentation: https://bybit-exchange.github.io/docs/v5/intro
"""

from typing import Dict, Any, Optional
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class BybitClient(BaseExchangeClient):
    """Client for Bybit V5 API

    Fetches perpetual futures market data including volume, open interest,
    and funding rates from Bybit's USDT perpetual contracts.

    API Endpoints:
        - /v5/market/tickers - Market tickers for all symbols
        - /v5/market/funding/history - Funding rate history
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Return exchange type"""
        return ExchangeType.BYBIT

    @property
    def base_url(self) -> str:
        """Bybit V5 API base URL"""
        return "https://api.bybit.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h volume and market data from Bybit

        Returns:
            MarketData object with volume, open interest, and top pairs

        Raises:
            requests.RequestException: If API request fails after retries
        """
        # Fetch tickers for linear (USDT) perpetuals
        response = self._get("/v5/market/tickers", params={'category': 'linear'})

        # Bybit V5 API returns data in a nested structure
        result = response.get('result', {})
        tickers = result.get('list', [])

        # Calculate total volume and OI
        total_volume = 0.0
        total_oi = 0.0
        pairs_with_volume = []
        btc_funding = None

        for ticker in tickers:
            symbol = ticker.get('symbol', '')

            # Only include USDT perpetual futures
            if not symbol.endswith('USDT'):
                continue

            # Volume in quote currency (USDT)
            volume = float(ticker.get('turnover24h', 0))
            total_volume += volume

            # Open interest in quote currency
            oi = float(ticker.get('openInterest', 0))
            if oi > 0:
                # Convert to USD value (OI is in contracts, need price)
                price = float(ticker.get('lastPrice', 0))
                if price > 0:
                    # For USDT contracts, OI is already in USDT value
                    total_oi += oi

            # Store pair with volume for top pairs calculation
            if volume > 0:
                pairs_with_volume.append({
                    'symbol': symbol,
                    'volume': volume
                })

            # Get BTC funding rate
            if symbol == 'BTCUSDT':
                funding_rate_str = ticker.get('fundingRate', '0')
                btc_funding = float(funding_rate_str) if funding_rate_str else None

        # Get top 10 pairs by volume
        top_pairs = sorted(pairs_with_volume, key=lambda x: x['volume'], reverse=True)[:10]
        top_pairs_models = [
            TradingPair(
                symbol=pair['symbol'],
                volume=pair['volume']
            )
            for pair in top_pairs
        ]

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            open_interest=total_oi if total_oi > 0 else None,
            funding_rate=btc_funding,
            market_count=len(pairs_with_volume),
            top_pairs=top_pairs_models,
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on Bybit

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            SymbolData object with price, volume, OI, funding rate
            None if symbol not found or error occurs
        """
        try:
            # Fetch ticker for specific symbol
            response = self._get("/v5/market/tickers", params={
                'category': 'linear',
                'symbol': symbol
            })

            result = response.get('result', {})
            tickers = result.get('list', [])

            if not tickers:
                return None

            ticker = tickers[0]

            # Calculate price change percentage
            price_change_pct = None
            price_24h_pcnt = ticker.get('price24hPcnt')
            if price_24h_pcnt:
                price_change_pct = float(price_24h_pcnt) * 100

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=float(ticker.get('lastPrice', 0)),
                volume_24h=float(ticker.get('turnover24h', 0)),
                price_change_24h_pct=price_change_pct,
                open_interest=float(ticker.get('openInterestValue', 0)),
                funding_rate=float(ticker.get('fundingRate', 0)),
                num_trades=None  # Bybit doesn't provide trade count in this endpoint
            )

        except Exception:
            return None

    def __repr__(self) -> str:
        """String representation"""
        return f"BybitClient(timeout={self.timeout}s)"
