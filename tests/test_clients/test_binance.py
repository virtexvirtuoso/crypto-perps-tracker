"""Tests for Binance exchange client"""

import pytest
from unittest.mock import patch, Mock
from src.clients.binance import BinanceClient
from src.models.market import ExchangeType


@pytest.fixture
def binance_client():
    """Create a Binance client instance"""
    return BinanceClient(timeout=5, retry_attempts=2)


@pytest.fixture
def mock_ticker_response():
    """Mock response from Binance ticker API"""
    return [
        {
            'symbol': 'BTCUSDT',
            'quoteVolume': '5000000000.50',
            'lastPrice': '45000.00'
        },
        {
            'symbol': 'ETHUSDT',
            'quoteVolume': '2000000000.25',
            'lastPrice': '3000.00'
        },
        {
            'symbol': 'BNBUSDT',
            'quoteVolume': '500000000.75',
            'lastPrice': '400.00'
        },
        {
            'symbol': 'SOLUSDT',
            'quoteVolume': '300000000.00',
            'lastPrice': '100.00'
        },
        # Non-USDT pair (should be filtered out)
        {
            'symbol': 'BTCBUSD',
            'quoteVolume': '100000000.00',
            'lastPrice': '45000.00'
        }
    ]


@pytest.fixture
def mock_funding_response():
    """Mock response from Binance funding rate API"""
    return {
        'symbol': 'BTCUSDT',
        'lastFundingRate': '0.0001',
        'markPrice': '45000.00'
    }


@pytest.fixture
def mock_oi_response():
    """Mock response from Binance open interest API"""
    return {
        'symbol': 'BTCUSDT',
        'openInterest': '50000.0',
        'time': 1640000000000
    }


class TestBinanceClient:
    """Test suite for BinanceClient"""

    def test_client_initialization(self, binance_client):
        """Test client is initialized correctly"""
        assert binance_client.exchange_type == ExchangeType.BINANCE
        assert binance_client.base_url == "https://fapi.binance.com"
        assert binance_client.timeout == 5
        assert binance_client.retry_attempts == 2

    def test_fetch_volume_success(
        self,
        binance_client,
        mock_ticker_response,
        mock_funding_response,
        mock_oi_response
    ):
        """Test successful volume fetch from Binance"""
        with patch.object(binance_client, '_get') as mock_get:
            # Configure mock to return different responses based on endpoint
            def side_effect(endpoint, params=None):
                if endpoint == '/fapi/v1/ticker/24hr':
                    return mock_ticker_response
                elif endpoint == '/fapi/v1/premiumIndex':
                    return mock_funding_response
                elif endpoint == '/fapi/v1/openInterest':
                    return mock_oi_response
                return {}

            mock_get.side_effect = side_effect

            # Fetch data
            market_data = binance_client.fetch_volume()

            # Verify basic properties
            assert market_data.exchange == ExchangeType.BINANCE
            assert market_data.volume_24h > 0
            assert market_data.market_count == 4  # Only USDT pairs

            # Verify calculations
            expected_volume = 5000000000.50 + 2000000000.25 + 500000000.75 + 300000000.00
            assert abs(market_data.volume_24h - expected_volume) < 1.0

            # Verify funding rate
            assert market_data.funding_rate == 0.0001

            # Verify top pairs exist
            assert len(market_data.top_pairs) > 0
            assert market_data.top_pairs[0].symbol == 'BTCUSDT'  # Highest volume

    def test_fetch_volume_filters_non_usdt(self, binance_client, mock_ticker_response):
        """Test that non-USDT pairs are filtered out"""
        with patch.object(binance_client, '_get', return_value=mock_ticker_response):
            market_data = binance_client.fetch_volume()

            # Should only count USDT pairs
            assert market_data.market_count == 4
            # BTCBUSD should not be included
            symbols = [pair.symbol for pair in market_data.top_pairs]
            assert 'BTCBUSD' not in symbols

    def test_fetch_volume_handles_missing_funding(
        self,
        binance_client,
        mock_ticker_response
    ):
        """Test handling when funding rate endpoint fails"""
        with patch.object(binance_client, '_get') as mock_get:
            def side_effect(endpoint, params=None):
                if endpoint == '/fapi/v1/ticker/24hr':
                    return mock_ticker_response
                # Simulate funding rate endpoint failure
                raise Exception("Funding rate unavailable")

            mock_get.side_effect = side_effect

            market_data = binance_client.fetch_volume()

            # Should still succeed with no funding rate
            assert market_data.volume_24h > 0
            assert market_data.funding_rate is None

    def test_top_pairs_sorted_by_volume(
        self,
        binance_client,
        mock_ticker_response,
    ):
        """Test that top pairs are sorted by volume"""
        with patch.object(binance_client, '_get', return_value=mock_ticker_response):
            market_data = binance_client.fetch_volume()

            # Verify pairs are sorted by volume (descending)
            volumes = [pair.volume for pair in market_data.top_pairs]
            assert volumes == sorted(volumes, reverse=True)

            # BTC should be first (highest volume)
            assert market_data.top_pairs[0].symbol == 'BTCUSDT'

    def test_repr(self, binance_client):
        """Test string representation"""
        assert "BinanceClient" in repr(binance_client)
        assert "timeout=5s" in repr(binance_client)

    def test_context_manager(self):
        """Test client works as context manager"""
        with BinanceClient() as client:
            assert client.exchange_type == ExchangeType.BINANCE
