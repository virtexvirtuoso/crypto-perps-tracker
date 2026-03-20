"""Tests for signal fusion"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.signals.fusion import SignalFusion
from src.signals.models import (
    SignalDirection,
    SignalStrength,
    FundingRateSignal,
    OpenInterestSignal,
    LongShortRatioSignal,
    CVDSignal,
    SignalType
)


class TestSignalFusion:
    """Test signal fusion engine"""

    @pytest.fixture
    def fusion_engine(self):
        """Create test fusion engine"""
        return SignalFusion()

    @pytest.fixture
    def mock_strong_long_signals(self):
        """Mock strong long signals"""
        return {
            'funding_rate': FundingRateSignal(
                signal_type=SignalType.FUNDING_RATE,
                symbol='BTCUSDT',
                direction=SignalDirection.LONG,
                strength=SignalStrength.STRONG,
                confidence=72.0,
                timestamp=datetime.utcnow(),
                horizon='4h-24h',
                funding_rate=-0.001,
                funding_rate_8h=-0.003,
                next_funding_time=datetime.utcnow(),
                threshold_crossed='extreme_short',
                price_vs_ema200=0.02
            ),
            'open_interest': OpenInterestSignal(
                signal_type=SignalType.OPEN_INTEREST,
                symbol='BTCUSDT',
                direction=SignalDirection.LONG,
                strength=SignalStrength.STRONG,
                confidence=68.0,
                timestamp=datetime.utcnow(),
                horizon='1h-6h',
                oi_change_pct=35.0,
                oi_current=1350000,
                oi_24h_ago=1000000,
                price_change_pct=-3.0,
                divergence_type='bullish'
            ),
            'long_short_ratio': LongShortRatioSignal(
                signal_type=SignalType.LONG_SHORT_RATIO,
                symbol='BTCUSDT',
                direction=SignalDirection.LONG,
                strength=SignalStrength.MODERATE,
                confidence=65.0,
                timestamp=datetime.utcnow(),
                horizon='30min-2h',
                ratio=0.25,
                long_account_pct=20.0,
                short_account_pct=80.0,
                crowd_side='short'
            ),
            'cvd': CVDSignal(
                signal_type=SignalType.CVD,
                symbol='BTCUSDT',
                direction=SignalDirection.LONG,
                strength=SignalStrength.MODERATE,
                confidence=68.0,
                timestamp=datetime.utcnow(),
                horizon='15min-1h',
                cvd=600000,
                cvd_15min=600000,
                buy_volume=1200000,
                sell_volume=600000,
                hidden_flow='buy'
            )
        }

    def test_fusion_engine_initialization(self, fusion_engine):
        """Test fusion engine initialization"""
        assert fusion_engine.calculator is not None

    @patch('src.signals.calculators.SignalCalculator.calculate_all_signals')
    def test_fusion_signal_strong_long(self, mock_calculate, fusion_engine, mock_strong_long_signals):
        """Test fusion signal with strong long confluence"""
        mock_calculate.return_value = mock_strong_long_signals

        signal = fusion_engine.calculate_fusion_signal('BTCUSDT')

        assert signal.direction == SignalDirection.LONG
        assert signal.strength == SignalStrength.STRONG
        assert signal.score >= 3
        assert signal.entry_recommendation == 'ENTER LONG'
        assert signal.win_rate_estimate >= 75.0

    @patch('src.signals.calculators.SignalCalculator.calculate_all_signals')
    def test_fusion_signal_neutral(self, mock_calculate, fusion_engine):
        """Test fusion signal with neutral signals"""
        neutral_signals = {
            'funding_rate': FundingRateSignal(
                signal_type=SignalType.FUNDING_RATE,
                symbol='BTCUSDT',
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.WEAK,
                confidence=50.0,
                timestamp=datetime.utcnow(),
                horizon='4h-24h',
                funding_rate=0.0001,
                funding_rate_8h=0.0003,
                next_funding_time=datetime.utcnow(),
                threshold_crossed='none',
                price_vs_ema200=0.0
            )
        }
        mock_calculate.return_value = neutral_signals

        signal = fusion_engine.calculate_fusion_signal('BTCUSDT')

        assert signal.direction == SignalDirection.NEUTRAL
        assert signal.entry_recommendation == 'WAIT'
        assert -2 <= signal.score <= 2

    @patch('src.signals.calculators.SignalCalculator.calculate_all_signals')
    def test_fusion_contributions(self, mock_calculate, fusion_engine, mock_strong_long_signals):
        """Test individual signal contributions"""
        mock_calculate.return_value = mock_strong_long_signals

        signal = fusion_engine.calculate_fusion_signal('BTCUSDT')

        # Check contributions
        assert signal.funding_contribution == 2  # Extreme short = strong long signal
        assert signal.oi_contribution == 1  # Bullish divergence
        assert signal.lsr_contribution == 1  # Crowded shorts = fade to long
        assert signal.cvd_contribution == 1  # Buy flow

    @patch('src.signals.calculators.SignalCalculator.calculate_all_signals')
    def test_get_recommendation_summary(self, mock_calculate, fusion_engine, mock_strong_long_signals):
        """Test recommendation summary"""
        mock_calculate.return_value = mock_strong_long_signals

        summary = fusion_engine.get_recommendation_summary('BTCUSDT')

        assert summary['symbol'] == 'BTCUSDT'
        assert summary['recommendation'] == 'ENTER LONG'
        assert 'score_breakdown' in summary
        assert 'interpretation' in summary
        assert 'risk_warning' in summary

    def test_interpret_score(self, fusion_engine):
        """Test score interpretation"""
        interpretation = fusion_engine._interpret_score(4)
        assert 'very strong bullish' in interpretation.lower()

        interpretation = fusion_engine._interpret_score(0)
        assert 'neutral' in interpretation.lower()

        interpretation = fusion_engine._interpret_score(-4)
        assert 'very strong bearish' in interpretation.lower()

    def test_get_risk_warning(self, fusion_engine):
        """Test risk warning generation"""
        # Strong signal
        signal = Mock()
        signal.entry_recommendation = 'ENTER LONG'
        warning = fusion_engine._get_risk_warning(signal)
        assert 'stop losses' in warning.lower()

        # Weak signal
        signal.entry_recommendation = 'WAIT'
        warning = fusion_engine._get_risk_warning(signal)
        assert 'fomo' in warning.lower()
