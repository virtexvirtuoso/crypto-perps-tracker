"""Tests for market data models"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from src.models.market import MarketData, ExchangeType, TradingPair, FundingRate


class TestMarketData:
    """Test suite for MarketData model"""

    def test_market_data_creation(self):
        """Test creating valid market data"""
        data = MarketData(
            exchange=ExchangeType.BINANCE,
            volume_24h=1000000000,
            funding_rate=0.0001,
        )

        assert data.exchange == ExchangeType.BINANCE
        assert data.volume_24h == 1000000000
        assert data.funding_rate == 0.0001
        assert isinstance(data.timestamp, datetime)

    def test_market_data_validation_negative_volume(self):
        """Test that negative volume raises validation error"""
        with pytest.raises(ValidationError):
            MarketData(
                exchange=ExchangeType.BINANCE,
                volume_24h=-1000,
            )

    def test_market_data_validation_funding_rate_range(self):
        """Test funding rate must be between -1 and 1"""
        # Valid funding rates
        MarketData(exchange=ExchangeType.BINANCE, volume_24h=1000, funding_rate=0.5)
        MarketData(exchange=ExchangeType.BINANCE, volume_24h=1000, funding_rate=-0.5)

        # Invalid funding rates
        with pytest.raises(ValidationError):
            MarketData(exchange=ExchangeType.BINANCE, volume_24h=1000, funding_rate=1.5)

        with pytest.raises(ValidationError):
            MarketData(exchange=ExchangeType.BINANCE, volume_24h=1000, funding_rate=-1.5)

    def test_market_data_immutable(self):
        """Test that MarketData is immutable"""
        data = MarketData(
            exchange=ExchangeType.BINANCE,
            volume_24h=1000000,
        )

        with pytest.raises(ValidationError):
            data.volume_24h = 2000000

    def test_market_data_exchange_string_conversion(self):
        """Test that exchange string is converted to enum"""
        data = MarketData(
            exchange="binance",  # Lower case string
            volume_24h=1000000,
        )

        assert data.exchange == ExchangeType.BINANCE

    def test_market_data_json_serialization(self):
        """Test JSON serialization"""
        data = MarketData(
            exchange=ExchangeType.BINANCE,
            volume_24h=1000000,
            funding_rate=0.0001,
        )

        json_data = data.json()
        assert 'exchange' in json_data
        assert 'volume_24h' in json_data
        assert 'timestamp' in json_data

    def test_trading_pair_creation(self):
        """Test creating trading pair"""
        pair = TradingPair(
            symbol="BTC/USDT",
            base="BTC",
            quote="USDT",
            volume=1000000,
        )

        assert pair.symbol == "BTC/USDT"
        assert pair.volume == 1000000

    def test_funding_rate_creation(self):
        """Test creating funding rate"""
        rate = FundingRate(
            exchange=ExchangeType.BINANCE,
            symbol="BTC/USDT",
            funding_rate=0.0001,
        )

        assert rate.funding_rate == 0.0001
        assert isinstance(rate.timestamp, datetime)


class TestExchangeType:
    """Test suite for ExchangeType enum"""

    def test_exchange_types(self):
        """Test all exchange types are defined"""
        assert ExchangeType.BINANCE.value == "Binance"
        assert ExchangeType.BYBIT.value == "Bybit"
        assert ExchangeType.GATEIO.value == "Gate.io"
        assert ExchangeType.BITGET.value == "Bitget"
        assert ExchangeType.OKX.value == "OKX"
