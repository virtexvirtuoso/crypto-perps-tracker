"""Tests for ExchangeService"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from src.services.exchange import ExchangeService
from src.models.market import MarketData, ExchangeType


class TestExchangeService:
    """Test suite for ExchangeService"""

    def test_fetch_all_markets_uses_cache_on_hit(self, mock_cache, mock_client_factory):
        """Test that service returns cached data when available"""
        # Arrange
        cached_data = [MarketData(
            exchange=ExchangeType.BINANCE,
            total_volume_usd=1_000_000_000,
            total_open_interest_usd=100_000_000,
            num_pairs=50,
            top_pairs=[],
            timestamp=datetime.now(timezone.utc)
        )]
        mock_cache.get.return_value = cached_data

        service = ExchangeService(
            cache=mock_cache,
            client_factory=mock_client_factory
        )

        # Act
        result = service.fetch_all_markets(use_cache=True)

        # Assert
        assert result == cached_data
        mock_cache.get.assert_called_once_with("all_markets")
        # Should not call clients on cache hit
        mock_client_factory.create_all.assert_not_called()

    def test_fetch_all_markets_fetches_and_caches_on_miss(self, mock_cache, mock_client_factory):
        """Test that service fetches fresh data on cache miss"""
        # Arrange
        mock_cache.get.return_value = None  # Cache miss

        service = ExchangeService(
            cache=mock_cache,
            client_factory=mock_client_factory
        )

        # Act
        result = service.fetch_all_markets(use_cache=True)

        # Assert
        assert len(result) == 2  # binance and bybit
        assert all(isinstance(m, MarketData) for m in result)

        # Should cache the results
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "all_markets"
        assert len(call_args[0][1]) == 2

    def test_fetch_all_markets_bypasses_cache_when_disabled(self, mock_cache, mock_client_factory):
        """Test that service bypasses cache when use_cache=False"""
        # Arrange
        service = ExchangeService(
            cache=mock_cache,
            client_factory=mock_client_factory
        )

        # Act
        result = service.fetch_all_markets(use_cache=False)

        # Assert
        assert len(result) == 2
        # Should not check cache
        mock_cache.get.assert_not_called()
        # Should still cache the fresh data
        mock_cache.set.assert_called_once()

    def test_get_total_volume_sums_correctly(self, mock_cache, mock_client_factory):
        """Test total volume calculation"""
        # Arrange
        mock_cache.get.return_value = [
            MarketData(
                exchange=ExchangeType.BINANCE,
                total_volume_usd=100_000_000_000,  # $100B
                total_open_interest_usd=10_000_000_000,
                num_pairs=150,
                top_pairs=[],
                timestamp=datetime.now(timezone.utc)
            ),
            MarketData(
                exchange=ExchangeType.BYBIT,
                total_volume_usd=50_000_000_000,  # $50B
                total_open_interest_usd=5_000_000_000,
                num_pairs=100,
                top_pairs=[],
                timestamp=datetime.now(timezone.utc)
            ),
        ]

        service = ExchangeService(mock_cache, mock_client_factory)

        # Act
        total = service.get_total_volume()

        # Assert
        assert total == 150_000_000_000  # $150B

    def test_fetch_handles_client_failures_gracefully(self, mock_cache, mock_client_factory):
        """Test that service handles individual client failures"""
        # Arrange
        mock_cache.get.return_value = None

        # Make one client fail
        binance_client = mock_client_factory.create_all.return_value['binance']
        binance_client.fetch_volume.side_effect = Exception("API Error")

        service = ExchangeService(
            cache=mock_cache,
            client_factory=mock_client_factory
        )

        # Act
        result = service.fetch_all_markets(use_cache=False)

        # Assert - should still get bybit data
        assert len(result) >= 1  # At least bybit should succeed
        # Should still cache partial results
        mock_cache.set.assert_called_once()
