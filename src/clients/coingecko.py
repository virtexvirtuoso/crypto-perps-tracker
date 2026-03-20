"""CoinGecko API client for aggregated derivatives data

Provides aggregated derivatives data from 120+ exchanges including:
- Funding rates
- Open interest
- 24h volume
- Basis spread

API Documentation: https://docs.coingecko.com/
Free tier: 30 calls/min, derivatives endpoints available
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import os

from src.clients.base import BaseExchangeClient
from src.models.market import ExchangeType


class CoinGeckoClient(BaseExchangeClient):
    """Client for CoinGecko Derivatives API

    Aggregates derivatives data from multiple exchanges.
    Works with or without API key (free tier has rate limits).
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.COINGECKO

    @property
    def base_url(self) -> str:
        """Base URL - uses pro API if key available"""
        if self._api_key:
            return "https://pro-api.coingecko.com/api/v3"
        return "https://api.coingecko.com/api/v3"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        """Initialize CoinGecko client

        Args:
            api_key: Optional Pro API key (uses free tier if not provided)
            timeout: Request timeout in seconds
        """
        super().__init__(timeout=timeout)
        self._api_key = api_key or os.getenv('COINGECKO_API_KEY')
        self._logger = logging.getLogger(self.__class__.__name__)

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Override _get to add API key header if available"""
        headers = {}
        if self._api_key:
            headers['x-cg-pro-api-key'] = self._api_key

        # Use parent's session with custom headers
        import requests
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def fetch_derivatives_tickers(
        self,
        include_tickers: str = "unexpired"
    ) -> List[Dict[str, Any]]:
        """Fetch all derivatives tickers from CoinGecko

        Returns aggregated data from 120+ exchanges.

        Args:
            include_tickers: "all" or "unexpired"

        Returns:
            List of derivative ticker data
        """
        try:
            data = self._get("/derivatives", params={
                "include_tickers": include_tickers
            })

            return data if isinstance(data, list) else []
        except Exception as e:
            self._logger.warning(f"CoinGecko derivatives fetch failed: {e}")
            return []

    def fetch_derivatives_exchanges(self) -> List[Dict[str, Any]]:
        """Fetch list of derivatives exchanges with summary data

        Returns:
            List of exchange data with OI, volume, etc.
        """
        try:
            data = self._get("/derivatives/exchanges", params={
                "per_page": 100,
                "page": 1
            })
            return data if isinstance(data, list) else []
        except Exception as e:
            self._logger.warning(f"CoinGecko exchanges fetch failed: {e}")
            return []

    def fetch_exchange_data(self, exchange_id: str) -> Dict[str, Any]:
        """Fetch detailed data for a specific exchange

        Args:
            exchange_id: Exchange ID (e.g., 'binance_futures', 'bybit')

        Returns:
            Exchange data with tickers
        """
        try:
            return self._get(f"/derivatives/exchanges/{exchange_id}", params={
                "include_tickers": "unexpired"
            })
        except Exception as e:
            self._logger.warning(f"CoinGecko exchange {exchange_id} fetch failed: {e}")
            return {}

    def get_aggregated_funding_rates(
        self,
        symbol: str = "BTC"
    ) -> Dict[str, Any]:
        """Get funding rates aggregated across all exchanges

        Args:
            symbol: Base asset (e.g., 'BTC', 'ETH')

        Returns:
            Aggregated funding rate data
        """
        tickers = self.fetch_derivatives_tickers()

        # Filter for symbol and perpetuals
        symbol_tickers = [
            t for t in tickers
            if t.get('index_id', '').upper() == symbol.upper()
            and t.get('contract_type') == 'perpetual'
            and t.get('funding_rate') is not None
        ]

        if not symbol_tickers:
            return {'error': f'No data for {symbol}'}

        funding_rates = [float(t['funding_rate']) for t in symbol_tickers if t.get('funding_rate')]
        open_interests = [float(t['open_interest']) for t in symbol_tickers if t.get('open_interest')]

        # Volume-weighted average
        total_oi = sum(open_interests) if open_interests else 1
        weighted_funding = sum(
            float(t.get('funding_rate', 0)) * float(t.get('open_interest', 0))
            for t in symbol_tickers
            if t.get('funding_rate') and t.get('open_interest')
        ) / total_oi if total_oi > 0 else 0

        import statistics
        return {
            'symbol': f"{symbol}USDT",
            'weighted_funding_rate': weighted_funding,
            'median_funding_rate': statistics.median(funding_rates) if funding_rates else 0,
            'min_funding_rate': min(funding_rates) if funding_rates else 0,
            'max_funding_rate': max(funding_rates) if funding_rates else 0,
            'exchange_count': len(symbol_tickers),
            'total_open_interest_usd': total_oi,
            'exchanges': [t.get('market') for t in symbol_tickers[:10]],
            'source': 'coingecko_aggregated'
        }

    def get_aggregated_open_interest(
        self,
        symbol: str = "BTC"
    ) -> Dict[str, Any]:
        """Get total open interest aggregated across all exchanges

        Args:
            symbol: Base asset (e.g., 'BTC', 'ETH')

        Returns:
            Aggregated open interest data
        """
        tickers = self.fetch_derivatives_tickers()

        # Filter for symbol perpetuals
        symbol_tickers = [
            t for t in tickers
            if t.get('index_id', '').upper() == symbol.upper()
            and t.get('contract_type') == 'perpetual'
            and t.get('open_interest')
        ]

        if not symbol_tickers:
            return {'error': f'No data for {symbol}'}

        # Aggregate OI by exchange
        exchange_oi = {}
        for t in symbol_tickers:
            market = t.get('market', 'unknown')
            oi = float(t.get('open_interest', 0))
            if market in exchange_oi:
                exchange_oi[market] += oi
            else:
                exchange_oi[market] = oi

        total_oi = sum(exchange_oi.values())

        # Top exchanges by OI
        sorted_exchanges = sorted(exchange_oi.items(), key=lambda x: x[1], reverse=True)

        return {
            'symbol': f"{symbol}USDT",
            'total_open_interest_usd': total_oi,
            'exchange_count': len(exchange_oi),
            'top_exchanges': [
                {'exchange': ex, 'open_interest_usd': oi, 'share_pct': (oi / total_oi) * 100}
                for ex, oi in sorted_exchanges[:10]
            ],
            'source': 'coingecko_aggregated'
        }

    def get_aggregated_basis(
        self,
        symbol: str = "BTC"
    ) -> Dict[str, Any]:
        """Get basis spread aggregated across exchanges

        Args:
            symbol: Base asset (e.g., 'BTC', 'ETH')

        Returns:
            Aggregated basis data
        """
        tickers = self.fetch_derivatives_tickers()

        # Filter for symbol perpetuals with basis data
        symbol_tickers = [
            t for t in tickers
            if t.get('index_id', '').upper() == symbol.upper()
            and t.get('contract_type') == 'perpetual'
            and t.get('basis') is not None
        ]

        if not symbol_tickers:
            return {'error': f'No data for {symbol}'}

        basis_values = [float(t['basis']) for t in symbol_tickers]
        open_interests = [float(t.get('open_interest', 1)) for t in symbol_tickers]

        # Volume-weighted basis
        total_oi = sum(open_interests)
        weighted_basis = sum(
            float(t.get('basis', 0)) * float(t.get('open_interest', 0))
            for t in symbol_tickers
        ) / total_oi if total_oi > 0 else 0

        import statistics
        return {
            'symbol': f"{symbol}USDT",
            'weighted_basis': weighted_basis,
            'median_basis': statistics.median(basis_values) if basis_values else 0,
            'basis_range': {
                'min': min(basis_values) if basis_values else 0,
                'max': max(basis_values) if basis_values else 0
            },
            'sentiment': 'bullish' if weighted_basis > 0 else 'bearish' if weighted_basis < 0 else 'neutral',
            'exchange_count': len(symbol_tickers),
            'source': 'coingecko_aggregated'
        }

    def get_market_dominance(self) -> Dict[str, Any]:
        """Get derivatives market dominance by exchange

        Returns:
            Market share data for top exchanges
        """
        exchanges = self.fetch_derivatives_exchanges()

        if not exchanges:
            return {'error': 'No exchange data'}

        total_oi = sum(float(ex.get('open_interest_btc', 0)) for ex in exchanges)
        total_volume = sum(float(ex.get('trade_volume_24h_btc', 0)) for ex in exchanges)

        return {
            'total_open_interest_btc': total_oi,
            'total_volume_24h_btc': total_volume,
            'exchange_count': len(exchanges),
            'top_by_oi': [
                {
                    'exchange': ex.get('name'),
                    'open_interest_btc': float(ex.get('open_interest_btc', 0)),
                    'share_pct': (float(ex.get('open_interest_btc', 0)) / total_oi * 100) if total_oi > 0 else 0
                }
                for ex in sorted(exchanges, key=lambda x: float(x.get('open_interest_btc', 0)), reverse=True)[:10]
            ],
            'source': 'coingecko'
        }

    def fetch_volume(self):
        """Fetch aggregated volume - required by base class"""
        from src.models.market import MarketData
        exchanges = self.fetch_derivatives_exchanges()
        total_volume = sum(float(ex.get('trade_volume_24h_btc', 0)) for ex in exchanges) * 100000  # BTC to USD estimate
        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            market_count=len(exchanges)
        )
