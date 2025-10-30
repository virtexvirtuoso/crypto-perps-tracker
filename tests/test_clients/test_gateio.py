"""Tests for Gate.io client"""

import pytest
from unittest.mock import Mock, patch
from src.clients.gateio import GateioClient
from src.models.market import ExchangeType, MarketData


class TestGateioClient:
    """Test suite for GateioClient"""

    @pytest.fixture
    def client(self):
        """Create Gate.io client instance"""
        return GateioClient()

    @pytest.fixture
    def mock_tickers_response(self):
        """Mock API response with ticker data"""
        return [
            {
                'contract': 'BTC_USDT',
                'volume_24h_settle': '1000000000',
                'total_size': '50000',
                'mark_price': '50000',
                'quanto_multiplier': '0.0001',
                'funding_rate': '0.0001',
                'change_percentage': '2.5',
            },
            {
                'contract': 'ETH_USDT',
                'volume_24h_settle': '500000000',
                'total_size': '100000',
                'mark_price': '3000',
                'quanto_multiplier': '0.0001',
                'funding_rate': '0.0002',
                'change_percentage': '1.8',
            },
            {
                'contract': 'SOL_USDT',
                'volume_24h_settle': '250000000',
                'total_size': '200000',
                'mark_price': '100',
                'quanto_multiplier': '0.0001',
                'funding_rate': '-0.0001',
                'change_percentage': '-1.2',
            },
        ]

    def test_exchange_type(self, client):
        """Test exchange type property"""
        assert client.exchange_type == ExchangeType.GATEIO

    def test_base_url(self, client):
        """Test base URL property"""
        assert client.base_url == "https://api.gateio.ws"

    @patch.object(GateioClient, '_get')
    def test_fetch_volume(self, mock_get, client, mock_tickers_response):
        """Test fetching volume data"""
        mock_get.return_value = mock_tickers_response

        data = client.fetch_volume()

        # Verify API call
        mock_get.assert_called_once_with("/api/v4/futures/usdt/tickers")

        # Verify returned data type
        assert isinstance(data, MarketData)
        assert data.exchange == ExchangeType.GATEIO

        # Verify volume calculation (sum of all volumes)
        expected_volume = 1000000000 + 500000000 + 250000000
        assert data.volume_24h == expected_volume

        # Verify open interest calculation
        assert data.open_interest > 0

        # Verify BTC funding rate extracted
        assert data.funding_rate == 0.0001

        # Verify market count
        assert data.market_count == 3

        # Verify top pairs
        assert len(data.top_pairs) == 3
        assert data.top_pairs[0].symbol == 'BTC_USDT'
        assert data.top_pairs[0].volume == 1000000000

    @patch.object(GateioClient, '_get')
    def test_fetch_funding_rate(self, mock_get, client, mock_tickers_response):
        """Test fetching funding rate for specific symbol"""
        mock_get.return_value = mock_tickers_response

        funding_rate = client.fetch_funding_rate('BTC_USDT')

        assert funding_rate == 0.0001

    @patch.object(GateioClient, '_get')
    def test_fetch_funding_rate_symbol_not_found(self, mock_get, client, mock_tickers_response):
        """Test funding rate fetch with invalid symbol"""
        mock_get.return_value = mock_tickers_response

        with pytest.raises(ValueError, match="Symbol INVALID_USDT not found"):
            client.fetch_funding_rate('INVALID_USDT')

    @patch.object(GateioClient, '_get')
    def test_fetch_volume_invalid_response(self, mock_get, client):
        """Test handling of invalid API response"""
        mock_get.return_value = {"error": "Invalid response"}

        with pytest.raises(ValueError, match="Unexpected response format"):
            client.fetch_volume()

    def test_get_top_pairs(self, client, mock_tickers_response):
        """Test extracting top trading pairs"""
        top_pairs = client._get_top_pairs(mock_tickers_response, limit=2)

        assert len(top_pairs) == 2
        # Should be sorted by volume (BTC first, then ETH)
        assert top_pairs[0].symbol == 'BTC_USDT'
        assert top_pairs[0].base == 'BTC'
        assert top_pairs[0].quote == 'USDT'
        assert top_pairs[0].volume == 1000000000

        assert top_pairs[1].symbol == 'ETH_USDT'
        assert top_pairs[1].volume == 500000000

    def test_context_manager(self, client):
        """Test using client as context manager"""
        with client as c:
            assert c.exchange_type == ExchangeType.GATEIO

    def test_repr(self, client):
        """Test string representation"""
        repr_str = repr(client)
        assert 'GateioClient' in repr_str
        assert 'Gate.io' in repr_str
