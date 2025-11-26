"""Pytest configuration and fixtures"""

import pytest
from pathlib import Path
from unittest.mock import Mock
from src.models.config import Config
from src.utils.cache import TTLCache
from src.container import Container
from src.models.market import MarketData, SymbolData, ExchangeType


@pytest.fixture
def test_data_dir(tmp_path):
    """Provide a temporary directory for test data"""
    return tmp_path


@pytest.fixture
def cache():
    """Provide a fresh TTL cache for each test"""
    return TTLCache(default_ttl=60)


@pytest.fixture
def test_config(test_data_dir):
    """Provide a test configuration"""
    return Config(
        app_name="Crypto Perps Tracker Test",
        environment="test",
        database={"path": str(test_data_dir / "test_market.db")},
        alert_database={"path": str(test_data_dir / "test_alerts.db")},
    )


@pytest.fixture
def container(test_config):
    """Provide a container with test configuration"""
    return Container(test_config)


@pytest.fixture
def mock_market_data():
    """Provide mock market data for testing"""
    from tests.fixtures.mock_data import MOCK_MARKET_DATA
    return MOCK_MARKET_DATA


@pytest.fixture
def mock_symbol_data():
    """Provide mock symbol data for testing"""
    from tests.fixtures.mock_data import MOCK_SYMBOL_DATA
    return MOCK_SYMBOL_DATA


@pytest.fixture
def mock_exchange_client():
    """Provide a mock exchange client"""
    from tests.fixtures.mock_data import create_mock_market_data, create_mock_symbol_data

    client = Mock()
    client.fetch_volume.return_value = create_mock_market_data()
    client.fetch_symbol.return_value = create_mock_symbol_data()
    client.exchange_type = ExchangeType.BINANCE
    return client
