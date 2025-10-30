"""Pytest configuration and fixtures"""

import pytest
from pathlib import Path
from src.models.config import Config
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
        database={"path": str(test_data_dir / "test_market.db")},
        alert_database={"path": str(test_data_dir / "test_alerts.db")},
    )


@pytest.fixture
def container(test_config):
    """Provide a container with test configuration"""
    return Container(test_config)
