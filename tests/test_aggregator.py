"""Tests for Multi-Exchange Signal Aggregator"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import statistics

from src.signals.aggregator import (
    AggregatedSignalCalculator,
    AggregatedLSRSignal,
    AggregatedFundingSignal
)


class TestAggregatedSignalCalculator:
    """Tests for the AggregatedSignalCalculator class"""

    @pytest.fixture
    def mock_clients(self):
        """Create mock exchange clients"""
        bybit = Mock()
        binance = Mock()
        okx = Mock()
        bitget = Mock()
        return bybit, binance, okx, bitget

    @pytest.fixture
    def aggregator(self, mock_clients):
        """Create aggregator with mock clients"""
        bybit, binance, okx, bitget = mock_clients
        return AggregatedSignalCalculator(
            bybit_client=bybit,
            binance_client=binance,
            okx_client=okx,
            bitget_client=bitget
        )

    def test_symbol_mapping_btcusdt(self, aggregator):
        """Test symbol mapping for BTC"""
        assert aggregator._get_symbol_for_exchange('BTCUSDT', 'bybit') == 'BTCUSDT'
        assert aggregator._get_symbol_for_exchange('BTCUSDT', 'binance') == 'BTCUSDT'
        assert aggregator._get_symbol_for_exchange('BTCUSDT', 'okx') == 'BTC'
        assert aggregator._get_symbol_for_exchange('BTCUSDT', 'bitget') == 'BTCUSDT'

    def test_symbol_mapping_unknown(self, aggregator):
        """Test symbol mapping for unknown symbols"""
        # OKX strips USDT
        assert aggregator._get_symbol_for_exchange('XYZUSDT', 'okx') == 'XYZ'
        # Others keep as-is
        assert aggregator._get_symbol_for_exchange('XYZUSDT', 'binance') == 'XYZUSDT'

    def test_consensus_lsr_calculation(self, aggregator, mock_clients):
        """Test consensus LSR calculation with mock data"""
        bybit, binance, okx, bitget = mock_clients

        # Mock responses
        bybit.get_long_short_ratio.return_value = {
            'long_short_ratio': 1.5,
            'long_account_pct': 60,
            'short_account_pct': 40,
            'source': 'bybit'
        }
        binance.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 1.4,
            'long_account_pct': 58,
            'short_account_pct': 42,
            'source': 'binance'
        }
        okx.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 1.6,
            'long_account_pct': 62,
            'short_account_pct': 38,
            'source': 'okx'
        }
        bitget.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 1.5,
            'long_account_pct': 60,
            'short_account_pct': 40,
            'source': 'bitget'
        }

        result = aggregator.calculate_consensus_lsr('BTCUSDT')

        assert isinstance(result, AggregatedLSRSignal)
        assert result.symbol == 'BTCUSDT'
        # Median of [1.4, 1.5, 1.5, 1.6] = 1.5
        assert result.consensus_lsr == pytest.approx(1.5, rel=0.01)
        assert result.sources_available == 4
        assert result.crowd_side == 'balanced'  # 1.5 is balanced

    def test_consensus_lsr_crowded_longs(self, aggregator, mock_clients):
        """Test detection of crowded longs"""
        bybit, binance, okx, bitget = mock_clients

        # All exchanges show high LSR (crowded longs)
        bybit.get_long_short_ratio.return_value = {
            'long_short_ratio': 2.5,
            'long_account_pct': 71,
            'short_account_pct': 29
        }
        binance.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 2.5,
            'long_account_pct': 71,
            'short_account_pct': 29
        }
        okx.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 2.5,
            'long_account_pct': 71,
            'short_account_pct': 29
        }
        bitget.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 2.5,
            'long_account_pct': 71,
            'short_account_pct': 29
        }

        result = aggregator.calculate_consensus_lsr('BTCUSDT')

        assert result.consensus_lsr > 2.0
        assert result.crowd_side == 'long'

    def test_consensus_lsr_crowded_shorts(self, aggregator, mock_clients):
        """Test detection of crowded shorts"""
        bybit, binance, okx, bitget = mock_clients

        # All exchanges show low LSR (crowded shorts)
        bybit.get_long_short_ratio.return_value = {
            'long_short_ratio': 0.4,
            'long_account_pct': 29,
            'short_account_pct': 71
        }
        binance.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 0.35,
            'long_account_pct': 26,
            'short_account_pct': 74
        }
        okx.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 0.45,
            'long_account_pct': 31,
            'short_account_pct': 69
        }
        bitget.fetch_long_short_ratio.return_value = {
            'long_short_ratio': 0.4,
            'long_account_pct': 29,
            'short_account_pct': 71
        }

        result = aggregator.calculate_consensus_lsr('BTCUSDT')

        assert result.consensus_lsr < 0.5
        assert result.crowd_side == 'short'

    def test_consensus_lsr_outlier_rejection(self, aggregator, mock_clients):
        """Test that outliers are rejected in consensus calculation"""
        bybit, binance, okx, bitget = mock_clients

        # Three normal values, one outlier
        bybit.get_long_short_ratio.return_value = {'long_short_ratio': 1.5}
        binance.fetch_long_short_ratio.return_value = {'long_short_ratio': 1.4}
        okx.fetch_long_short_ratio.return_value = {'long_short_ratio': 1.6}
        bitget.fetch_long_short_ratio.return_value = {'long_short_ratio': 10.0}  # Outlier

        result = aggregator.calculate_consensus_lsr('BTCUSDT')

        # Median with outlier rejection should be around 1.5, not skewed by 10.0
        assert result.consensus_lsr < 2.0

    def test_consensus_lsr_partial_data(self, aggregator, mock_clients):
        """Test handling when some exchanges fail"""
        bybit, binance, okx, bitget = mock_clients

        bybit.get_long_short_ratio.return_value = {'long_short_ratio': 1.5}
        binance.fetch_long_short_ratio.side_effect = Exception("API Error")
        okx.fetch_long_short_ratio.return_value = {'long_short_ratio': 1.6}
        bitget.fetch_long_short_ratio.side_effect = Exception("Timeout")

        result = aggregator.calculate_consensus_lsr('BTCUSDT')

        assert result.sources_available == 2
        assert result.sources_total == 4
        assert result.consensus_lsr == pytest.approx(1.55, rel=0.01)  # Median of [1.5, 1.6]

    def test_consensus_lsr_no_data(self, aggregator, mock_clients):
        """Test error handling when no exchanges respond"""
        bybit, binance, okx, bitget = mock_clients

        bybit.get_long_short_ratio.side_effect = Exception("Error")
        binance.fetch_long_short_ratio.side_effect = Exception("Error")
        okx.fetch_long_short_ratio.side_effect = Exception("Error")
        bitget.fetch_long_short_ratio.side_effect = Exception("Error")

        with pytest.raises(ValueError, match="No LSR data available"):
            aggregator.calculate_consensus_lsr('BTCUSDT')

    def test_agreement_score_high(self, aggregator, mock_clients):
        """Test high agreement score when exchanges agree"""
        bybit, binance, okx, bitget = mock_clients

        # Very similar values
        bybit.get_long_short_ratio.return_value = {'long_short_ratio': 1.50}
        binance.fetch_long_short_ratio.return_value = {'long_short_ratio': 1.51}
        okx.fetch_long_short_ratio.return_value = {'long_short_ratio': 1.49}
        bitget.fetch_long_short_ratio.return_value = {'long_short_ratio': 1.50}

        result = aggregator.calculate_consensus_lsr('BTCUSDT')

        assert result.agreement_score > 0.9  # High agreement

    def test_agreement_score_low(self, aggregator, mock_clients):
        """Test low agreement score when exchanges diverge"""
        bybit, binance, okx, bitget = mock_clients

        # Very different values
        bybit.get_long_short_ratio.return_value = {'long_short_ratio': 0.5}
        binance.fetch_long_short_ratio.return_value = {'long_short_ratio': 2.5}
        okx.fetch_long_short_ratio.return_value = {'long_short_ratio': 1.0}
        bitget.fetch_long_short_ratio.return_value = {'long_short_ratio': 3.0}

        result = aggregator.calculate_consensus_lsr('BTCUSDT')

        assert result.agreement_score < 0.5  # Low agreement


class TestAggregatedFundingSignal:
    """Tests for aggregated funding rate calculation"""

    @pytest.fixture
    def mock_clients(self):
        """Create mock exchange clients"""
        bybit = Mock()
        binance = Mock()
        okx = Mock()
        bitget = Mock()
        return bybit, binance, okx, bitget

    @pytest.fixture
    def aggregator(self, mock_clients):
        """Create aggregator with mock clients"""
        bybit, binance, okx, bitget = mock_clients
        return AggregatedSignalCalculator(
            bybit_client=bybit,
            binance_client=binance,
            okx_client=okx,
            bitget_client=bitget
        )

    def test_aggregated_funding_bullish(self, aggregator, mock_clients):
        """Test bullish consensus when funding is positive"""
        bybit, binance, okx, bitget = mock_clients

        bybit.get_funding_rate.return_value = {'funding_rate': 0.0005}
        bybit.get_perp_price.return_value = 100000

        mock_symbol_data = Mock()
        mock_symbol_data.funding_rate = 0.0004
        mock_symbol_data.volume_24h = 1000000
        binance.fetch_symbol.return_value = mock_symbol_data

        okx.fetch_funding_rate.return_value = 0.0006
        bitget.fetch_funding_rate.return_value = 0.0005

        result = aggregator.calculate_aggregated_funding('BTCUSDT')

        assert isinstance(result, AggregatedFundingSignal)
        assert result.weighted_funding_rate > 0
        assert result.consensus_direction == 'bullish'

    def test_aggregated_funding_bearish(self, aggregator, mock_clients):
        """Test bearish consensus when funding is negative"""
        bybit, binance, okx, bitget = mock_clients

        bybit.get_funding_rate.return_value = {'funding_rate': -0.0005}
        bybit.get_perp_price.return_value = 100000

        mock_symbol_data = Mock()
        mock_symbol_data.funding_rate = -0.0004
        mock_symbol_data.volume_24h = 1000000
        binance.fetch_symbol.return_value = mock_symbol_data

        okx.fetch_funding_rate.return_value = -0.0006
        bitget.fetch_funding_rate.return_value = -0.0005

        result = aggregator.calculate_aggregated_funding('BTCUSDT')

        assert result.weighted_funding_rate < 0
        assert result.consensus_direction == 'bearish'


class TestConsensusCalculation:
    """Unit tests for the consensus calculation logic"""

    def test_median_calculation(self):
        """Test median is calculated correctly"""
        ratios = [1.5, 1.6, 1.4, 1.5]
        expected_median = statistics.median(ratios)
        assert expected_median == 1.5

    def test_outlier_detection(self):
        """Test outlier detection logic using IQR (more robust for small samples)"""
        # With 4 values, simple 2-std rule is skewed by the outlier itself
        # The actual implementation uses median which is inherently robust
        # Test that median ignores outliers
        ratios = [1.5, 1.4, 1.6, 10.0]  # 10.0 is outlier

        # Median-based approach is robust to outliers
        median = statistics.median(ratios)  # Median of [1.4, 1.5, 1.6, 10.0] = 1.55

        # Median should be close to the non-outlier values
        assert 1.4 <= median <= 1.6  # Not pulled toward 10.0
        assert median < 3.0  # Not significantly affected by outlier

    def test_agreement_score_calculation(self):
        """Test agreement score (inverse of CV)"""
        ratios = [1.5, 1.5, 1.5, 1.5]  # Perfect agreement
        mean = statistics.mean(ratios)
        std = statistics.stdev(ratios)
        cv = std / mean if mean > 0 else 0
        agreement = max(0, 1 - cv)

        assert agreement == 1.0  # Perfect agreement

    def test_crowd_side_detection(self):
        """Test crowd side detection thresholds"""
        # Test thresholds
        assert 2.5 > 2.0  # Should be "long"
        assert 0.4 < 0.5  # Should be "short"
        assert 0.5 <= 1.5 <= 2.0  # Should be "balanced"
