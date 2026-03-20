"""Pytest configuration and fixtures"""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
from datetime import datetime, timezone
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config, CacheConfig, DatabaseConfig
from src.models.market import MarketData, ExchangeType, TradingPair
from src.utils.cache import TTLCache
from src.container import Container


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
        cache=CacheConfig(ttl=300, max_size=1000),
        database=DatabaseConfig(
            path=str(test_data_dir / "test_market.db"),
            snapshots_path=str(test_data_dir / "test_snapshots.db")
        ),
        exchanges=['binance', 'bybit'],
        blacklist=[],
        retry_attempts=3,
        retry_delay=1,
        timeout=10
    )


@pytest.fixture
def container(test_config):
    """Provide a container with test configuration"""
    return Container(test_config)


@pytest.fixture
def mock_cache():
    """Mock TTL cache for testing"""
    cache = Mock(spec=TTLCache)
    cache.get.return_value = None  # Default to cache miss
    cache.set.return_value = None
    cache.clear.return_value = None
    cache._hits = 0
    cache._misses = 0
    return cache


@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    return MarketData(
        exchange=ExchangeType.BINANCE,
        total_volume_usd=100_000_000_000,  # $100B
        total_open_interest_usd=10_000_000_000,  # $10B
        num_pairs=150,
        top_pairs=[
            TradingPair(
                symbol="BTCUSDT",
                volume_24h_usd=50_000_000_000,
                price=45000.0,
                funding_rate=0.0001,
                open_interest_usd=5_000_000_000
            ),
            TradingPair(
                symbol="ETHUSDT",
                volume_24h_usd=30_000_000_000,
                price=2500.0,
                funding_rate=0.0002,
                open_interest_usd=3_000_000_000
            )
        ],
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def mock_exchange_client():
    """Mock exchange client for testing"""
    client = Mock()
    client.exchange_type = ExchangeType.BINANCE
    client.fetch_volume = Mock(return_value=MarketData(
        exchange=ExchangeType.BINANCE,
        total_volume_usd=100_000_000_000,
        total_open_interest_usd=10_000_000_000,
        num_pairs=150,
        top_pairs=[],
        timestamp=datetime.now(timezone.utc)
    ))
    return client


@pytest.fixture
def mock_client_factory():
    """Mock client factory for testing"""
    factory = Mock()
    factory.available_exchanges = ['binance', 'bybit']

    # Create mock clients
    binance_client = Mock()
    binance_client.exchange_type = ExchangeType.BINANCE
    binance_client.fetch_volume.return_value = MarketData(
        exchange=ExchangeType.BINANCE,
        total_volume_usd=100_000_000_000,
        total_open_interest_usd=10_000_000_000,
        num_pairs=150,
        top_pairs=[],
        timestamp=datetime.now(timezone.utc)
    )

    bybit_client = Mock()
    bybit_client.exchange_type = ExchangeType.BYBIT
    bybit_client.fetch_volume.return_value = MarketData(
        exchange=ExchangeType.BYBIT,
        total_volume_usd=50_000_000_000,
        total_open_interest_usd=5_000_000_000,
        num_pairs=100,
        top_pairs=[],
        timestamp=datetime.now(timezone.utc)
    )

    factory.create.side_effect = lambda ex: {
        'binance': binance_client,
        'bybit': bybit_client
    }.get(ex)

    factory.create_all.return_value = {
        'binance': binance_client,
        'bybit': bybit_client
    }

    return factory


@pytest.fixture
def mock_repository():
    """Mock repository for testing"""
    repo = Mock()
    repo.save_snapshot.return_value = True
    repo.get_latest_snapshot.return_value = None
    repo.get_snapshots_since.return_value = []
    return repo


@pytest.fixture(autouse=True)
def cleanup_test_databases(test_data_dir):
    """Automatically cleanup test databases after each test"""
    yield
    # Cleanup code runs after test
    if test_data_dir.exists():
        for db_file in test_data_dir.glob("*.db"):
            db_file.unlink()
