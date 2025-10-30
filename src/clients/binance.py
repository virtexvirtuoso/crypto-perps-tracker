"""Binance exchange client

Binance is one of the largest cryptocurrency exchanges globally.
API Documentation: https://binance-docs.github.io/apidocs/futures/en/
"""

from typing import Dict, Any, Optional
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class BinanceClient(BaseExchangeClient):
    """Client for Binance Futures API

    Fetches perpetual futures market data including volume, open interest,
    and funding rates from Binance USDⓈ-M Futures.

    API Endpoints:
        - /fapi/v1/ticker/24hr - 24h ticker data
        - /fapi/v1/fundingRate - Funding rate history
        - /fapi/v1/openInterest - Open interest data
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Return exchange type"""
        return ExchangeType.BINANCE

    @property
    def base_url(self) -> str:
        """Binance Futures API base URL"""
        return "https://fapi.binance.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h volume and market data from Binance

        Returns:
            MarketData object with volume, open interest, and top pairs

        Raises:
            requests.RequestException: If API request fails after retries
        """
        # Fetch 24h ticker data for all symbols
        tickers = self._get("/fapi/v1/ticker/24hr")

        # Calculate total volume (in USDT)
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
            volume = float(ticker.get('quoteVolume', 0))
            total_volume += volume

            # Store pair with volume for top pairs calculation
            if volume > 0:
                pairs_with_volume.append({
                    'symbol': symbol,
                    'volume': volume
                })

        # Get BTC funding rate
        try:
            funding_data = self._get("/fapi/v1/premiumIndex", params={'symbol': 'BTCUSDT'})
            if funding_data:
                btc_funding = float(funding_data.get('lastFundingRate', 0))
        except Exception:
            # Funding rate is optional, continue without it
            pass

        # Get total open interest
        try:
            oi_data = self._get("/fapi/v1/openInterest", params={'symbol': 'BTCUSDT'})
            if oi_data:
                # This is just BTC OI, we'd need to aggregate all symbols for total
                # For now, fetch a few major symbols
                major_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
                for symbol in major_symbols:
                    try:
                        oi_response = self._get("/fapi/v1/openInterest", params={'symbol': symbol})
                        # Get current price to convert to USD
                        price_data = next((t for t in tickers if t.get('symbol') == symbol), None)
                        if oi_response and price_data:
                            oi_contracts = float(oi_response.get('openInterest', 0))
                            price = float(price_data.get('lastPrice', 0))
                            total_oi += oi_contracts * price
                    except Exception:
                        continue
        except Exception:
            # OI is optional
            pass

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
        """Fetch data for a specific symbol on Binance

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            SymbolData object with price, volume, OI, funding rate
            None if symbol not found or error occurs
        """
        try:
            # Get ticker data
            ticker = self._get("/fapi/v1/ticker/24hr", params={'symbol': symbol})

            if not ticker:
                return None

            # Get funding rate
            funding_rate = None
            try:
                funding_data = self._get("/fapi/v1/premiumIndex", params={'symbol': symbol})
                if funding_data:
                    funding_rate = float(funding_data.get('lastFundingRate', 0))
            except Exception:
                pass

            # Get open interest
            open_interest = None
            try:
                oi_data = self._get("/fapi/v1/openInterest", params={'symbol': symbol})
                if oi_data:
                    oi_contracts = float(oi_data.get('openInterest', 0))
                    price = float(ticker.get('lastPrice', 0))
                    open_interest = oi_contracts * price
            except Exception:
                pass

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=float(ticker.get('lastPrice', 0)),
                volume_24h=float(ticker.get('quoteVolume', 0)),
                price_change_24h_pct=float(ticker.get('priceChangePercent', 0)),
                open_interest=open_interest,
                funding_rate=funding_rate,
                num_trades=int(ticker.get('count', 0))
            )

        except Exception as e:
            # Return None if symbol not found or any error occurs
            return None

    def __repr__(self) -> str:
        """String representation"""
        return f"BinanceClient(timeout={self.timeout}s)"
