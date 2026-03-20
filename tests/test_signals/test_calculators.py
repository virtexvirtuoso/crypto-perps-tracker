"""Tests for signal calculators"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.signals.calculators import SignalCalculator
from src.signals.models import SignalDirection, SignalStrength


class TestSignalCalculator:
    """Test signal calculator"""

    @pytest.fixture
    def calculator(self):
        """Create test calculator"""
        return SignalCalculator()

    @pytest.fixture
    def mock_client(self):
        """Create mock Bybit client"""
        client = Mock()
        return client

    def test_calculator_initialization(self, calculator):
        """Test calculator initialization"""
        assert calculator.client is not None
        assert calculator.FUNDING_EXTREME_SHORT == -0.0005
        assert calculator.FUNDING_EXTREME_LONG == 0.001

    @patch('src.signals.bybit_derivatives.BybitDerivativesClient')
    def test_funding_rate_signal_extreme_short(self, mock_client_class):
        """Test funding rate signal with extreme short"""
        mock_client = Mock()
        mock_client.get_funding_rate.return_value = {
            'symbol': 'BTCUSDT',
            'funding_rate': -0.001,  # Extreme short
            'funding_rate_8h': -0.003,
            'next_funding_time': datetime.utcnow(),
            'last_price': 50000.0
        }
        mock_client.get_kline_data.return_value = [
            {'close': 48000.0, 'timestamp': datetime.utcnow()}
            for _ in range(200)
        ]
        mock_client.calculate_ema.return_value = 49000.0

        mock_client_class.return_value = mock_client

        calculator = SignalCalculator(client=mock_client)
        signal = calculator.calculate_funding_rate_signal('BTCUSDT')

        assert signal.symbol == 'BTCUSDT'
        assert signal.direction == SignalDirection.LONG
        assert signal.strength == SignalStrength.STRONG
        assert signal.confidence >= 70.0

    @patch('src.signals.bybit_derivatives.BybitDerivativesClient')
    def test_oi_signal_bullish_divergence(self, mock_client_class):
        """Test OI signal with bullish divergence"""
        mock_client = Mock()

        # OI increased 35%, price decreased 3%
        mock_client.get_open_interest_history.return_value = [
            {'open_interest': 1000000, 'timestamp': datetime.utcnow()}
            for _ in range(24)
        ] + [
            {'open_interest': 1350000, 'timestamp': datetime.utcnow()}
        ]

        mock_client.get_kline_data.return_value = [
            {'close': 50000.0, 'timestamp': datetime.utcnow()}
            for _ in range(24)
        ] + [
            {'close': 48500.0, 'timestamp': datetime.utcnow()}
        ]

        mock_client_class.return_value = mock_client

        calculator = SignalCalculator(client=mock_client)
        signal = calculator.calculate_open_interest_signal('BTCUSDT')

        assert signal.direction == SignalDirection.LONG
        assert signal.divergence_type == 'bullish'
        assert signal.oi_change_pct > 30

    @patch('src.signals.bybit_derivatives.BybitDerivativesClient')
    def test_lsr_signal_crowded_longs(self, mock_client_class):
        """Test LSR signal with crowded longs"""
        mock_client = Mock()
        mock_client.get_long_short_ratio.return_value = {
            'symbol': 'BTCUSDT',
            'long_short_ratio': 3.5,  # Crowded longs
            'long_account_pct': 77.8,
            'short_account_pct': 22.2,
            'timestamp': datetime.utcnow()
        }

        mock_client_class.return_value = mock_client

        calculator = SignalCalculator(client=mock_client)
        signal = calculator.calculate_long_short_ratio_signal('BTCUSDT')

        assert signal.direction == SignalDirection.SHORT  # Fade the crowd
        assert signal.crowd_side == 'long'
        assert signal.ratio > 3.0

    @patch('src.signals.bybit_derivatives.BybitDerivativesClient')
    def test_basis_signal_contango_discount(self, mock_client_class):
        """Test basis signal with contango discount"""
        mock_client = Mock()
        mock_client.get_perp_price.return_value = 49700.0
        mock_client.get_spot_price.return_value = 50000.0

        mock_client_class.return_value = mock_client

        calculator = SignalCalculator(client=mock_client)
        signal = calculator.calculate_basis_signal('BTCUSDT')

        assert signal.direction == SignalDirection.LONG
        assert signal.basis_type == 'contango_discount'
        assert signal.arbitrage_opportunity is True

    @patch('src.signals.bybit_derivatives.BybitDerivativesClient')
    def test_cvd_signal_buy_flow(self, mock_client_class):
        """Test CVD signal with buy flow"""
        mock_client = Mock()

        # Generate trades with net buy flow
        trades = []
        for i in range(100):
            trades.append({
                'timestamp': datetime.utcnow(),
                'price': 50000.0,
                'size': 0.1,
                'side': 'Buy' if i < 70 else 'Sell'
            })

        mock_client.get_recent_trades.return_value = trades

        mock_client_class.return_value = mock_client

        calculator = SignalCalculator(client=mock_client)
        signal = calculator.calculate_cvd_signal('BTCUSDT')

        assert signal.hidden_flow == 'buy'
        assert signal.cvd > 0

    @patch('src.signals.bybit_derivatives.BybitDerivativesClient')
    def test_calculate_all_signals(self, mock_client_class):
        """Test calculating all signals"""
        mock_client = Mock()

        # Mock all necessary methods
        mock_client.get_funding_rate.return_value = {
            'symbol': 'BTCUSDT',
            'funding_rate': 0.0001,
            'funding_rate_8h': 0.0003,
            'next_funding_time': datetime.utcnow(),
            'last_price': 50000.0
        }
        mock_client.get_kline_data.return_value = [
            {'close': 50000.0, 'timestamp': datetime.utcnow()}
            for _ in range(200)
        ]
        mock_client.calculate_ema.return_value = 49000.0
        mock_client.get_open_interest_history.return_value = [
            {'open_interest': 1000000, 'timestamp': datetime.utcnow()}
            for _ in range(25)
        ]
        mock_client.get_long_short_ratio.return_value = {
            'long_short_ratio': 1.5,
            'long_account_pct': 60.0,
            'short_account_pct': 40.0,
            'timestamp': datetime.utcnow()
        }
        mock_client.get_perp_price.return_value = 50000.0
        mock_client.get_spot_price.return_value = 50000.0
        mock_client.get_recent_trades.return_value = []

        mock_client_class.return_value = mock_client

        calculator = SignalCalculator(client=mock_client)
        signals = calculator.calculate_all_signals('BTCUSDT')

        assert 'funding_rate' in signals
        assert 'open_interest' in signals
        assert 'long_short_ratio' in signals
        assert 'basis' in signals
        assert 'cvd' in signals
