"""Bitget exchange client"""

from typing import List
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class BitgetClient(BaseExchangeClient):
    """Client for Bitget perpetual futures API

    Fetches trading volume, open interest, and market data from
    Bitget USDT-margined perpetual futures markets.
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.BITGET

    @property
    def base_url(self) -> str:
        """Base URL for Bitget API"""
        return "https://api.bitget.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume from Bitget USDT-M perpetual futures

        Returns:
            MarketData object with volume information

        Raises:
            requests.RequestException: If API request fails
            ValueError: If API returns error response
        """
        # Fetch all USDT-margined perpetual tickers
        response = self._get(
            "/api/mix/v1/market/tickers",
            params={"productType": "umcbl"}
        )

        # Check for API error
        if response.get('code') != '00000':
            raise ValueError(f"API error: {response.get('msg', 'Unknown error')}")

        tickers = response['data']

        # Calculate total volume
        total_volume = sum(
            float(ticker.get('usdtVolume', 0))
            for ticker in tickers
        )

        # Calculate total open interest (holdingAmount * last price)
        total_oi = sum(
            float(ticker.get('holdingAmount', 0)) * float(ticker.get('last', 0))
            for ticker in tickers
        )

        # Get BTC funding rate for reference
        btc_ticker = next(
            (t for t in tickers if t['symbol'] == 'BTCUSDT_UMCBL'),
            {}
        )
        btc_funding = (
            float(btc_ticker.get('fundingRate', 0))
            if btc_ticker else None
        )

        # Get top pairs by volume
        top_pairs = self._get_top_pairs(tickers, limit=10)

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            open_interest=total_oi,
            funding_rate=btc_funding,
            market_count=len(tickers),
            top_pairs=top_pairs,
        )

    def _get_top_pairs(self, tickers: List[dict], limit: int = 10) -> List[TradingPair]:
        """Extract top trading pairs by volume

        Args:
            tickers: List of ticker data from API
            limit: Number of top pairs to return

        Returns:
            List of TradingPair objects sorted by volume
        """
        # Sort by volume
        sorted_tickers = sorted(
            tickers,
            key=lambda x: float(x.get('usdtVolume', 0)),
            reverse=True
        )

        top_pairs = []
        for ticker in sorted_tickers[:limit]:
            # Extract symbol (remove _UMCBL suffix)
            symbol = ticker['symbol'].replace('_UMCBL', '')

            # Extract base/quote (e.g., "BTCUSDT" -> BTC/USDT)
            if symbol.endswith('USDT'):
                base = symbol[:-4]  # Remove USDT
                quote = 'USDT'
            else:
                base = symbol
                quote = 'UNKNOWN'

            top_pairs.append(TradingPair(
                symbol=symbol,
                base=base,
                quote=quote,
                volume=float(ticker.get('usdtVolume', 0))
            ))

        return top_pairs

    def fetch_funding_rate(self, symbol: str = "BTCUSDT_UMCBL") -> float:
        """Fetch current funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT_UMCBL")

        Returns:
            Current funding rate as decimal (e.g., 0.0001 = 0.01%)

        Raises:
            ValueError: If symbol not found or API error
            requests.RequestException: If API request fails
        """
        response = self._get(
            "/api/mix/v1/market/tickers",
            params={"productType": "umcbl"}
        )

        if response.get('code') != '00000':
            raise ValueError(f"API error: {response.get('msg', 'Unknown error')}")

        tickers = response['data']
        ticker = next(
            (t for t in tickers if t['symbol'] == symbol),
            None
        )

        if not ticker:
            raise ValueError(f"Symbol {symbol} not found")

        return float(ticker.get('fundingRate', 0))

    def fetch_symbol(self, symbol: str):
        """Fetch data for a specific symbol on Bitget"""
        from typing import Optional
        try:
            response = self._get("/api/mix/v1/market/ticker", params={"symbol": symbol, "productType": "umcbl"})
            if response.get('code') != '00000' or not response.get('data'):
                return None
            ticker = response['data']
            
            last_price = float(ticker.get('last', 0))
            
            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=last_price,
                volume_24h=float(ticker.get('usdtVolume', 0)),
                price_change_24h_pct=float(ticker.get('priceChangePercent', 0)) * 100 if ticker.get('priceChangePercent') else None,
                open_interest=float(ticker.get('holdingAmount', 0)) * last_price,
                funding_rate=float(ticker.get('fundingRate', 0)),
                num_trades=None
            )
        except Exception:
            return None
