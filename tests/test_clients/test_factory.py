"""Tests for ClientFactory"""

import pytest
from src.clients.factory import ClientFactory
from src.clients.gateio import GateioClient
from src.clients.binance import BinanceClient
from src.clients.bybit import BybitClient
from src.clients.base import BaseExchangeClient


class TestClientFactory:
    """Test suite for ClientFactory"""

    @pytest.fixture
    def factory(self):
        """Create factory instance"""
        return ClientFactory()

    def test_create_gateio_client(self, factory):
        """Test creating Gate.io client"""
        client = factory.create('gateio')

        assert isinstance(client, GateioClient)
        assert isinstance(client, BaseExchangeClient)

    def test_create_binance_client(self, factory):
        """Test creating Binance client"""
        client = factory.create('binance')

        assert isinstance(client, BinanceClient)
        assert isinstance(client, BaseExchangeClient)

    def test_create_bybit_client(self, factory):
        """Test creating Bybit client"""
        client = factory.create('bybit')

        assert isinstance(client, BybitClient)
        assert isinstance(client, BaseExchangeClient)

    def test_create_case_insensitive(self, factory):
        """Test that exchange names are case-insensitive"""
        client1 = factory.create('gateio')
        client2 = factory.create('GATEIO')
        client3 = factory.create('GateIO')

        assert all(isinstance(c, GateioClient) for c in [client1, client2, client3])

    def test_create_unknown_exchange(self, factory):
        """Test creating client for unknown exchange raises error"""
        with pytest.raises(ValueError, match="Unknown exchange: unknown"):
            factory.create('unknown')

    def test_create_all_clients(self, factory):
        """Test creating all available clients"""
        clients = factory.create_all()

        assert isinstance(clients, dict)
        assert 'gateio' in clients
        assert isinstance(clients['gateio'], GateioClient)

    def test_create_selected_clients(self, factory):
        """Test creating specific clients"""
        clients = factory.create_all(['gateio'])

        assert len(clients) == 1
        assert 'gateio' in clients
        assert isinstance(clients['gateio'], GateioClient)

    def test_create_all_with_invalid_exchange(self, factory):
        """Test that invalid exchanges are skipped silently"""
        clients = factory.create_all(['gateio', 'invalid_exchange'])

        # Should only contain valid exchanges
        assert len(clients) == 1
        assert 'gateio' in clients
        assert 'invalid_exchange' not in clients

    def test_available_exchanges(self, factory):
        """Test getting list of available exchanges"""
        exchanges = factory.available_exchanges

        assert isinstance(exchanges, list)
        assert len(exchanges) == 5
        assert 'gateio' in exchanges
        assert 'binance' in exchanges
        assert 'bybit' in exchanges
        assert 'bitget' in exchanges
        assert 'okx' in exchanges

    def test_is_supported(self, factory):
        """Test checking if exchange is supported"""
        assert factory.is_supported('gateio')
        assert factory.is_supported('GATEIO')  # Case insensitive
        assert not factory.is_supported('unknown')

    def test_custom_timeout(self):
        """Test creating factory with custom timeout"""
        factory = ClientFactory(timeout=20, retry_attempts=5)

        client = factory.create('gateio')

        assert client.timeout == 20
        assert client.retry_attempts == 5

    def test_repr(self, factory):
        """Test string representation"""
        repr_str = repr(factory)

        assert 'ClientFactory' in repr_str
        assert 'timeout=10s' in repr_str
        assert 'retry_attempts=3' in repr_str
