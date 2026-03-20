"""Tests for Bybit derivatives data client"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.signals.bybit_derivatives import BybitDerivativesClient


class TestBybitDerivativesClient:
    """Test Bybit derivatives client"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return BybitDerivativesClient(timeout=5)

    @pytest.fixture
    def mock_funding_response(self):
        """Mock funding rate response"""
        return {
            'retCode': 0,
            'result': {
                'list': [{
                    'symbol': 'BTCUSDT',
                    'fundingRate': '0.0001',
                    'nextFundingTime': '1640000000000',
                    'lastPrice': '50000.0'
                }]
            }
        }

    @pytest.fixture
    def mock_oi_response(self):
        """Mock open interest response"""
        return {
            'retCode': 0,
            'result': {
                'list': [
                    {'timestamp': '1640000000000', 'openInterest': '1000000'},
                    {'timestamp': '1640003600000', 'openInterest': '1100000'}
                ]
            }
        }

    def test_client_initialization(self, client):
        """Test client initialization"""
        assert client.timeout == 5
        assert client.BASE_URL == "https://api.bybit.com"
        assert client._session is not None

    @patch('requests.Session.get')
    def test_get_funding_rate(self, mock_get, client, mock_funding_response):
        """Test funding rate fetching"""
        mock_response = Mock()
        mock_response.json.return_value = mock_funding_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client.get_funding_rate('BTCUSDT')

        assert result['symbol'] == 'BTCUSDT'
        assert result['funding_rate'] == 0.0001
        assert result['funding_rate_8h'] == 0.0003
        assert result['last_price'] == 50000.0

    @patch('requests.Session.get')
    def test_get_open_interest_history(self, mock_get, client, mock_oi_response):
        """Test OI history fetching"""
        mock_response = Mock()
        mock_response.json.return_value = mock_oi_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client.get_open_interest_history('BTCUSDT', interval='1h', limit=2)

        assert len(result) == 2
        assert result[0]['open_interest'] == 1000000
        assert result[1]['open_interest'] == 1100000

    @patch('requests.Session.get')
    def test_rate_limit_check(self, mock_get, client):
        """Test rate limiting"""
        mock_response = Mock()
        mock_response.json.return_value = {'retCode': 0, 'result': {'list': []}}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Make multiple requests
        for _ in range(5):
            client._get('/v5/market/tickers', params={'category': 'linear'})

        assert len(client._request_times) == 5

    @patch('requests.Session.get')
    def test_api_error_handling(self, mock_get, client):
        """Test API error handling"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'retCode': 10001,
            'retMsg': 'Invalid parameter'
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            client._get('/v5/market/tickers')

        assert 'Invalid parameter' in str(exc_info.value)

    def test_calculate_ema(self, client):
        """Test EMA calculation"""
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
        ema = client.calculate_ema(prices, period=5)

        assert ema is not None
        assert isinstance(ema, float)
        assert ema > 100

    def test_calculate_ema_insufficient_data(self, client):
        """Test EMA with insufficient data"""
        prices = [100.0, 102.0]
        ema = client.calculate_ema(prices, period=10)

        assert ema is None
