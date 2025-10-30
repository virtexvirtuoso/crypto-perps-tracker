"""Tests for Bybit exchange client"""

import pytest
from unittest.mock import patch, Mock
from src.clients.bybit import BybitClient
from src.models.market import ExchangeType


@pytest.fixture
def bybit_client():
    """Create a Bybit client instance"""
    return BybitClient(timeout=5, retry_attempts=2)


@pytest.fixture
def mock_ticker_response():
    """Mock response from Bybit V5 ticker API"""
    return {
        'retCode': 0,
        'retMsg': 'OK',
        'result': {
            'category': 'linear',
            'list': [
                {
                    'symbol': 'BTCUSDT',
                    'turnover24h': '3000000000.50',
                    'openInterest': '1500000000.00',
                    'lastPrice': '45000.00',
                    'fundingRate': '0.0001'
                },
                {
                    'symbol': 'ETHUSDT',
                    'turnover24h': '1500000000.25',
                    'openInterest': '800000000.00',
                    'lastPrice': '3000.00',
                    'fundingRate': '0.00008'
                },
                {
                    'symbol': 'SOLUSDT',
                    'turnover24h': '400000000.75',
                    'openInterest': '200000000.00',
                    'lastPrice': '100.00',
                    'fundingRate': '0.00012'
                },
                # Non-USDT pair (should be filtered out)
                {
                    'symbol': 'BTCUSD',
                    'turnover24h': '200000000.00',
                    'openInterest': '100000000.00',
                    'lastPrice': '45000.00',
                    'fundingRate': '0.0001'
                }
            ]
        }
    }


class TestBybitClient:
    """Test suite for BybitClient"""

    def test_client_initialization(self, bybit_client):
        """Test client is initialized correctly"""
        assert bybit_client.exchange_type == ExchangeType.BYBIT
        assert bybit_client.base_url == "https://api.bybit.com"
        assert bybit_client.timeout == 5
        assert bybit_client.retry_attempts == 2

    def test_fetch_volume_success(self, bybit_client, mock_ticker_response):
        """Test successful volume fetch from Bybit"""
        with patch.object(bybit_client, '_get', return_value=mock_ticker_response):
            market_data = bybit_client.fetch_volume()

            # Verify basic properties
            assert market_data.exchange == ExchangeType.BYBIT
            assert market_data.volume_24h > 0
            assert market_data.market_count == 3  # Only USDT pairs

            # Verify volume calculation
            expected_volume = 3000000000.50 + 1500000000.25 + 400000000.75
            assert abs(market_data.volume_24h - expected_volume) < 1.0

            # Verify funding rate (BTC)
            assert market_data.funding_rate == 0.0001

            # Verify open interest exists
            assert market_data.open_interest is not None
            assert market_data.open_interest > 0

            # Verify top pairs
            assert len(market_data.top_pairs) > 0
            assert market_data.top_pairs[0].symbol == 'BTCUSDT'  # Highest volume

    def test_fetch_volume_filters_non_usdt(self, bybit_client, mock_ticker_response):
        """Test that non-USDT pairs are filtered out"""
        with patch.object(bybit_client, '_get', return_value=mock_ticker_response):
            market_data = bybit_client.fetch_volume()

            # Should only count USDT pairs
            assert market_data.market_count == 3

            # BTCUSD should not be included
            symbols = [pair.symbol for pair in market_data.top_pairs]
            assert 'BTCUSD' not in symbols
            assert 'BTCUSDT' in symbols

    def test_fetch_volume_handles_empty_response(self, bybit_client):
        """Test handling of empty API response"""
        empty_response = {
            'retCode': 0,
            'retMsg': 'OK',
            'result': {
                'category': 'linear',
                'list': []
            }
        }

        with patch.object(bybit_client, '_get', return_value=empty_response):
            market_data = bybit_client.fetch_volume()

            # Should return data with zero values
            assert market_data.volume_24h == 0.0
            assert market_data.market_count == 0
            assert len(market_data.top_pairs) == 0

    def test_top_pairs_sorted_by_volume(self, bybit_client, mock_ticker_response):
        """Test that top pairs are sorted by volume"""
        with patch.object(bybit_client, '_get', return_value=mock_ticker_response):
            market_data = bybit_client.fetch_volume()

            # Verify pairs are sorted by volume (descending)
            volumes = [pair.volume for pair in market_data.top_pairs]
            assert volumes == sorted(volumes, reverse=True)

            # BTC should be first (highest volume)
            assert market_data.top_pairs[0].symbol == 'BTCUSDT'

    def test_open_interest_calculation(self, bybit_client, mock_ticker_response):
        """Test open interest is correctly aggregated"""
        with patch.object(bybit_client, '_get', return_value=mock_ticker_response):
            market_data = bybit_client.fetch_volume()

            # Should aggregate OI from all USDT pairs
            expected_oi = 1500000000.00 + 800000000.00 + 200000000.00
            assert abs(market_data.open_interest - expected_oi) < 1.0

    def test_handles_missing_funding_rate(self, bybit_client):
        """Test handling when funding rate is missing"""
        response_no_funding = {
            'retCode': 0,
            'retMsg': 'OK',
            'result': {
                'category': 'linear',
                'list': [
                    {
                        'symbol': 'ETHUSDT',
                        'turnover24h': '1000000000.00',
                        'openInterest': '500000000.00',
                        'lastPrice': '3000.00',
                        # No fundingRate field
                    }
                ]
            }
        }

        with patch.object(bybit_client, '_get', return_value=response_no_funding):
            market_data = bybit_client.fetch_volume()

            # Should still work, funding rate should be None
            assert market_data.volume_24h > 0
            assert market_data.funding_rate is None

    def test_repr(self, bybit_client):
        """Test string representation"""
        assert "BybitClient" in repr(bybit_client)
        assert "timeout=5s" in repr(bybit_client)

    def test_context_manager(self):
        """Test client works as context manager"""
        with BybitClient() as client:
            assert client.exchange_type == ExchangeType.BYBIT
