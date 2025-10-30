"""Factory for creating exchange clients"""

from typing import Dict, Optional, List
from src.clients.base import BaseExchangeClient
from src.clients.gateio import GateioClient
from src.clients.bitget import BitgetClient
from src.clients.okx import OKXClient
from src.clients.binance import BinanceClient
from src.clients.bybit import BybitClient
from src.clients.hyperliquid import HyperLiquidClient
from src.clients.dydx import DYdXClient
from src.clients.coinbase_intx import CoinbaseINTXClient
from src.clients.asterdex import AsterDEXClient
from src.clients.kraken import KrakenClient
from src.clients.kucoin import KuCoinClient
from src.clients.coinbase import CoinbaseClient


class ClientFactory:
    """Factory for creating exchange API clients

    Provides a centralized way to create and manage exchange clients
    with consistent configuration.

    Usage:
        factory = ClientFactory()
        gateio = factory.create('gateio')
        all_clients = factory.create_all()
    """

    # Registry of available clients
    _CLIENTS = {
        'binance': BinanceClient,
        'bybit': BybitClient,
        'gateio': GateioClient,
        'bitget': BitgetClient,
        'okx': OKXClient,
        'hyperliquid': HyperLiquidClient,
        'dydx': DYdXClient,
        'coinbase_intx': CoinbaseINTXClient,
        'asterdex': AsterDEXClient,
        'kraken': KrakenClient,
        'kucoin': KuCoinClient,
        'coinbase': CoinbaseClient,
    }

    def __init__(self, timeout: int = 10, retry_attempts: int = 3):
        """Initialize client factory

        Args:
            timeout: Default timeout for API requests in seconds
            retry_attempts: Default number of retry attempts
        """
        self.timeout = timeout
        self.retry_attempts = retry_attempts

    def create(self, exchange: str) -> BaseExchangeClient:
        """Create a single exchange client

        Args:
            exchange: Exchange name (e.g., 'gateio', 'binance')

        Returns:
            Exchange client instance

        Raises:
            ValueError: If exchange is not supported
        """
        exchange_lower = exchange.lower()
        client_class = self._CLIENTS.get(exchange_lower)

        if not client_class:
            available = ', '.join(self._CLIENTS.keys())
            raise ValueError(
                f"Unknown exchange: {exchange}. "
                f"Available exchanges: {available}"
            )

        return client_class(
            timeout=self.timeout,
            retry_attempts=self.retry_attempts
        )

    def create_all(self, exchanges: Optional[List[str]] = None) -> Dict[str, BaseExchangeClient]:
        """Create clients for all or selected exchanges

        Args:
            exchanges: Optional list of exchange names to create.
                      If None, creates clients for all available exchanges.

        Returns:
            Dictionary mapping exchange names to client instances

        Example:
            # Create all clients
            clients = factory.create_all()

            # Create specific clients
            clients = factory.create_all(['gateio', 'binance'])
        """
        if exchanges is None:
            exchanges = list(self._CLIENTS.keys())

        clients = {}
        for exchange in exchanges:
            try:
                clients[exchange] = self.create(exchange)
            except ValueError:
                # Skip unsupported exchanges silently
                continue

        return clients

    @property
    def available_exchanges(self) -> List[str]:
        """Get list of available exchanges

        Returns:
            List of exchange names that can be created
        """
        return list(self._CLIENTS.keys())

    def is_supported(self, exchange: str) -> bool:
        """Check if an exchange is supported

        Args:
            exchange: Exchange name to check

        Returns:
            True if exchange is supported, False otherwise
        """
        return exchange.lower() in self._CLIENTS

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ClientFactory(exchanges={len(self._CLIENTS)}, "
            f"timeout={self.timeout}s, "
            f"retry_attempts={self.retry_attempts})"
        )
