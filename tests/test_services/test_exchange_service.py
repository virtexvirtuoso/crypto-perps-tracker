"""Tests for the ExchangeService

Tests the exchange service's ability to fetch and aggregate data
from multiple exchanges with caching and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import Future

from src.services.exchange import ExchangeService
from src.utils.cache import TTLCache
from src.clients.factory import ClientFactory
from src.models.market import MarketData, ExchangeType, TradingPair
from tests.fixtures.mock_data import (
    MOCK_MARKET_DATA,
    create_mock_market_data,
)


class TestExchangeService:
    """Tests for ExchangeService"""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache"""
        return TTLCache(default_ttl=60)

    @pytest.fixture
    def mock_client_factory(self):
        """Create a mock client factory with mock clients"""
        factory = Mock(spec=ClientFactory)
        factory.available_exchanges = ['binance', 'bybit', 'okx']

        # Create mock clients
        mock_clients = {}
        for exchange_name in factory.available_exchanges:
            mock_client = Mock()
            mock_client.fetch_volume.return_value = MOCK_MARKET_DATA.get(
                exchange_name,
                create_mock_market_data(exchange=ExchangeType.BINANCE)
            )
            mock_clients[exchange_name] = mock_client

        factory.create.side_effect = lambda name: mock_clients.get(name)
        return factory

    @pytest.fixture
    def service(self, mock_cache, mock_client_factory):
        """Create an ExchangeService instance with mocked dependencies"""
        return ExchangeService(
            cache=mock_cache,
            client_factory=mock_client_factory,
            exchanges=['binance', 'bybit', 'okx'],
        )

    def test_fetch_all_markets_returns_list(self, service):
        """Test that fetch_all_markets returns a list of MarketData"""
        results = service.fetch_all_markets(use_cache=False)

        assert isinstance(results, list)
        assert len(results) == 3
        for result in results:
            assert isinstance(result, MarketData)

    def test_fetch_all_markets_uses_cache(self, service, mock_cache):
        """Test that fetch_all_markets uses cache on second call"""
        # First call - should fetch
        results1 = service.fetch_all_markets(use_cache=True)
        assert len(results1) == 3

        # Second call - should use cache
        results2 = service.fetch_all_markets(use_cache=True)
        assert len(results2) == 3

        # Cache should have been hit
        assert mock_cache.get("all_markets") is not None

    def test_fetch_all_markets_handles_exchange_failure(self, service):
        """Test that fetch_all_markets continues when one exchange fails"""
        # Make one client fail
        service.clients['binance'].fetch_volume.side_effect = Exception("API error")

        results = service.fetch_all_markets(use_cache=False)

        # Should still get results from other exchanges
        assert len(results) == 2

    def test_fetch_exchange_returns_market_data(self, service):
        """Test that fetch_exchange returns MarketData for valid exchange"""
        result = service.fetch_exchange('binance', use_cache=False)

        assert isinstance(result, MarketData)
        assert result.exchange == ExchangeType.BINANCE

    def test_fetch_exchange_returns_none_for_invalid(self, service):
        """Test that fetch_exchange returns None for invalid exchange"""
        result = service.fetch_exchange('invalid_exchange', use_cache=False)

        assert result is None

    def test_fetch_exchange_handles_error(self, service):
        """Test that fetch_exchange returns None on error"""
        service.clients['binance'].fetch_volume.side_effect = Exception("API error")

        result = service.fetch_exchange('binance', use_cache=False)

        assert result is None

    def test_get_total_volume(self, service):
        """Test that get_total_volume sums all exchange volumes"""
        total = service.get_total_volume(use_cache=False)

        # Sum of binance (55B) + bybit (25B) + okx (18B)
        expected = 55_000_000_000.0 + 25_000_000_000.0 + 18_000_000_000.0
        assert total == expected

    def test_get_total_open_interest(self, service):
        """Test that get_total_open_interest sums all exchange OI"""
        total = service.get_total_open_interest(use_cache=False)

        # Sum of binance (12B) + bybit (8B) + okx (6B)
        expected = 12_000_000_000.0 + 8_000_000_000.0 + 6_000_000_000.0
        assert total == expected

    def test_get_market_summary(self, service):
        """Test that get_market_summary returns correct structure"""
        summary = service.get_market_summary(use_cache=False)

        assert 'num_exchanges' in summary
        assert 'total_volume_24h' in summary
        assert 'total_open_interest' in summary
        assert 'total_markets' in summary
        assert 'exchanges' in summary

        assert summary['num_exchanges'] == 3
        assert isinstance(summary['exchanges'], list)

    def test_blacklist_filtering(self, mock_cache, mock_client_factory):
        """Test that blacklisted symbols are filtered out"""
        # Create market data with a blacklisted symbol
        market_with_blacklist = create_mock_market_data(
            exchange=ExchangeType.BINANCE,
            top_pairs=[
                TradingPair(symbol="BTCUSDT", volume=1000000),
                TradingPair(symbol="ALPACAUSDT", volume=500000),  # Blacklisted
                TradingPair(symbol="ETHUSDT", volume=800000),
            ]
        )

        mock_client_factory.create.return_value.fetch_volume.return_value = market_with_blacklist

        service = ExchangeService(
            cache=mock_cache,
            client_factory=mock_client_factory,
            exchanges=['binance'],
            blacklist=['ALPACAUSDT'],
        )

        results = service.fetch_all_markets(use_cache=False)

        assert len(results) == 1
        # ALPACAUSDT should be filtered out
        symbols = [pair.symbol for pair in results[0].top_pairs]
        assert 'ALPACAUSDT' not in symbols
        assert 'BTCUSDT' in symbols
        assert 'ETHUSDT' in symbols

    def test_clear_cache(self, service, mock_cache):
        """Test that clear_cache clears the cache"""
        # Populate cache
        service.fetch_all_markets(use_cache=True)
        assert mock_cache.get("all_markets") is not None

        # Clear cache
        service.clear_cache()

        # Cache should be empty
        assert mock_cache.get("all_markets") is None

    def test_repr(self, service):
        """Test string representation"""
        repr_str = repr(service)
        assert "ExchangeService" in repr_str
        assert "exchanges=3" in repr_str
