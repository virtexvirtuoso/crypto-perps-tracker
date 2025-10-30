"""Gate.io exchange client"""

from typing import List, Optional
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class GateioClient(BaseExchangeClient):
    """Client for Gate.io perpetual futures API

    Fetches trading volume, open interest, and market data from
    Gate.io USDT perpetual futures markets.
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.GATEIO

    @property
    def base_url(self) -> str:
        """Base URL for Gate.io API"""
        return "https://api.gateio.ws"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume from Gate.io USDT perpetual futures

        Returns:
            MarketData object with volume information

        Raises:
            requests.RequestException: If API request fails
        """
        # Fetch all USDT perpetual futures tickers
        tickers = self._get("/api/v4/futures/usdt/tickers")

        if not isinstance(tickers, list):
            raise ValueError(f"Unexpected response format: {type(tickers)}")

        # Calculate total volume (volume_24h_settle is in USDT)
        total_volume = sum(
            float(ticker.get('volume_24h_settle', 0))
            for ticker in tickers
        )

        # Calculate total open interest (total_size * mark_price * quanto_multiplier)
        total_oi = sum(
            float(ticker.get('total_size', 0)) *
            float(ticker.get('mark_price', 0)) *
            float(ticker.get('quanto_multiplier', 0.0001))
            for ticker in tickers
        )

        # Get BTC funding rate for reference
        btc_ticker = next(
            (t for t in tickers if t['contract'] == 'BTC_USDT'),
            {}
        )
        btc_funding = (
            float(btc_ticker.get('funding_rate', 0))
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
            key=lambda x: float(x.get('volume_24h_settle', 0)),
            reverse=True
        )

        top_pairs = []
        for ticker in sorted_tickers[:limit]:
            # Extract base/quote from contract (e.g., "BTC_USDT" -> BTC/USDT)
            symbol = ticker['contract']
            parts = symbol.split('_')
            base = parts[0] if len(parts) > 0 else 'UNKNOWN'
            quote = parts[1] if len(parts) > 1 else 'USDT'

            top_pairs.append(TradingPair(
                symbol=symbol,
                base=base,
                quote=quote,
                volume=float(ticker.get('volume_24h_settle', 0))
            ))

        return top_pairs

    def fetch_funding_rate(self, symbol: str = "BTC_USDT") -> float:
        """Fetch current funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., "BTC_USDT")

        Returns:
            Current funding rate as decimal (e.g., 0.0001 = 0.01%)

        Raises:
            ValueError: If symbol not found
            requests.RequestException: If API request fails
        """
        tickers = self._get("/api/v4/futures/usdt/tickers")

        ticker = next(
            (t for t in tickers if t['contract'] == symbol),
            None
        )

        if not ticker:
            raise ValueError(f"Symbol {symbol} not found")

        return float(ticker.get('funding_rate', 0))

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on Gate.io

        Args:
            symbol: Trading pair symbol (e.g., 'BTC_USDT')

        Returns:
            SymbolData object or None if not found
        """
        try:
            # Gate.io expects contract name in path
            response = self._get(f"/api/v4/futures/usdt/contracts/{symbol}")
            if not response:
                return None

            # Get ticker data
            tickers = self._get("/api/v4/futures/usdt/tickers", params={'contract': symbol})
            if not tickers or len(tickers) == 0:
                return None
            ticker = tickers[0]

            price = float(ticker.get('last', 0))
            mark_price = float(ticker.get('mark_price', price))

            # Calculate OI
            total_size = float(ticker.get('total_size', 0))
            quanto_multiplier = float(ticker.get('quanto_multiplier', 0.0001))
            open_interest = total_size * mark_price * quanto_multiplier

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=price,
                volume_24h=float(ticker.get('volume_24h_settle', 0)),
                price_change_24h_pct=float(ticker.get('change_percentage', 0)),
                open_interest=open_interest,
                funding_rate=float(ticker.get('funding_rate', 0)),
                num_trades=None
            )
        except Exception:
            return None
