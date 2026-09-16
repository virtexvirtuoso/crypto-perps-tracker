"""Bitget exchange client"""

from typing import List, Dict, Any
from datetime import datetime
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class BitgetClient(BaseExchangeClient):
    """Client for Bitget perpetual futures API

    Fetches trading volume, open interest, and market data from
    Bitget USDT-margined perpetual futures markets.

    API Endpoints:
        - /api/v2/mix/market/tickers - Ticker data (v2)
        - /api/v2/mix/market/long-short - Long/short account ratio
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
        # Fetch all USDT-margined perpetual tickers (v2)
        response = self._get(
            "/api/v2/mix/market/tickers",
            params={"productType": "USDT-FUTURES"}
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
            float(ticker.get('holdingAmount', 0)) * float(ticker.get('lastPr', 0))
            for ticker in tickers
        )

        # Get BTC funding rate for reference
        btc_ticker = next(
            (t for t in tickers if t['symbol'] == 'BTCUSDT'),
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
            # v2 symbols are already plain (e.g., BTCUSDT, no _UMCBL suffix)
            symbol = ticker['symbol']

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

    def fetch_funding_rate(self, symbol: str = "BTCUSDT") -> float:
        """Fetch current funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            Current funding rate as decimal (e.g., 0.0001 = 0.01%)

        Raises:
            ValueError: If symbol not found or API error
            requests.RequestException: If API request fails
        """
        response = self._get(
            "/api/v2/mix/market/tickers",
            params={"productType": "USDT-FUTURES"}
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
        try:
            response = self._get(
                "/api/v2/mix/market/ticker",
                params={"symbol": symbol, "productType": "USDT-FUTURES"}
            )
            if response.get('code') != '00000' or not response.get('data'):
                return None

            # v2 returns data as a list; v1 returned an object. Handle both.
            data = response['data']
            if isinstance(data, list):
                if not data:
                    return None
                ticker = data[0]
            else:
                ticker = data

            last_price = float(ticker.get('lastPr', 0))

            # v2 'change24h' is already a decimal fraction (e.g. -0.01132 = -1.132%)
            change_raw = ticker.get('change24h')
            price_change_pct = float(change_raw) * 100 if change_raw is not None else None

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=last_price,
                volume_24h=float(ticker.get('usdtVolume', 0)),
                price_change_24h_pct=price_change_pct,
                open_interest=float(ticker.get('holdingAmount', 0)) * last_price,
                funding_rate=float(ticker.get('fundingRate', 0)),
                num_trades=None
            )
        except Exception:
            return None

    def fetch_long_short_ratio(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1h"
    ) -> Dict[str, Any]:
        """Fetch long/short account ratio from Bitget

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            period: Time period (5m, 15m, 30m, 1h, 4h, 1Dutc)

        Returns:
            Dict with long/short ratio data:
                - symbol: Trading pair
                - long_short_ratio: Ratio of longs to shorts
                - long_account_pct: Percentage of long accounts
                - short_account_pct: Percentage of short accounts
                - timestamp: Data timestamp

        Raises:
            ValueError: If API returns error
            requests.RequestException: If request fails
        """
        # Bitget V2 API for long/short ratio
        response = self._get(
            "/api/v2/mix/market/long-short",
            params={
                "symbol": symbol,
                "period": period,
                "productType": "USDT-FUTURES"
            }
        )

        if response.get('code') != '00000':
            raise ValueError(f"API error: {response.get('msg', 'Unknown error')}")

        data = response.get('data', [])
        if not data:
            raise ValueError(f"No long/short ratio data for {symbol}")

        # Get most recent data point
        latest = data[0] if isinstance(data, list) else data

        long_ratio = float(latest.get('longRatio', 0))
        short_ratio = float(latest.get('shortRatio', 0))

        # Calculate L/S ratio
        lsr = long_ratio / short_ratio if short_ratio > 0 else float('inf')

        return {
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(int(latest.get('ts', 0)) / 1000),
            'long_short_ratio': lsr,
            'long_account_pct': long_ratio * 100,
            'short_account_pct': short_ratio * 100,
            'source': 'bitget'
        }
