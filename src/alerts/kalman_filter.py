"""
Kalman Filter for Smoothing Noisy Metrics (Phase 3+)
Reduces noise in funding rates, OI changes, and other volatile metrics
"""
import numpy as np
from typing import Dict, List


class KalmanFilter:
    """
    1D Kalman filter for smoothing time-series metrics
    Helps reduce false alerts from noisy data spikes
    """

    def __init__(self, process_variance: float = 0.01, measurement_variance: float = 0.1):
        """
        Initialize Kalman filter

        Args:
            process_variance: How much we expect the true value to change (Q)
            measurement_variance: How noisy our measurements are (R)
        """
        self.process_variance = process_variance  # Q
        self.measurement_variance = measurement_variance  # R
        self.estimate = None  # Current state estimate
        self.error_covariance = 1.0  # Uncertainty in estimate (P)

    def update(self, measurement: float) -> float:
        """
        Update filter with new measurement and return smoothed estimate

        Args:
            measurement: New raw measurement

        Returns:
            Smoothed estimate
        """
        if self.estimate is None:
            # Initialize with first measurement
            self.estimate = measurement
            return self.estimate

        # Prediction step
        predicted_estimate = self.estimate
        predicted_error_covariance = self.error_covariance + self.process_variance

        # Update step
        kalman_gain = predicted_error_covariance / (predicted_error_covariance + self.measurement_variance)
        self.estimate = predicted_estimate + kalman_gain * (measurement - predicted_estimate)
        self.error_covariance = (1 - kalman_gain) * predicted_error_covariance

        return self.estimate

    def reset(self):
        """Reset filter state"""
        self.estimate = None
        self.error_covariance = 1.0


class MetricsSmoothing:
    """
    Manages Kalman filters for multiple metrics
    Smooths funding rates, OI changes, volume spikes, etc.
    """

    def __init__(self):
        self.filters: Dict[str, KalmanFilter] = {}

        # Different noise characteristics for different metrics
        self.filter_configs = {
            'funding_rate': {'process_variance': 0.001, 'measurement_variance': 0.05},
            'oi_change': {'process_variance': 0.01, 'measurement_variance': 0.1},
            'volume_ratio': {'process_variance': 0.05, 'measurement_variance': 0.2},
            'basis': {'process_variance': 0.002, 'measurement_variance': 0.08},
            'liquidation_risk': {'process_variance': 0.01, 'measurement_variance': 0.15}
        }

    def smooth(self, metric_name: str, value: float, exchange: str = "") -> float:
        """
        Smooth a metric value using Kalman filter

        Args:
            metric_name: Name of metric (e.g., 'funding_rate')
            value: Raw measurement
            exchange: Optional exchange name for per-exchange filtering

        Returns:
            Smoothed value
        """
        # Create unique key for metric + exchange
        key = f"{metric_name}_{exchange}" if exchange else metric_name

        # Initialize filter if needed
        if key not in self.filters:
            config = self.filter_configs.get(metric_name, {
                'process_variance': 0.01,
                'measurement_variance': 0.1
            })
            self.filters[key] = KalmanFilter(**config)

        # Update and return smoothed value
        return self.filters[key].update(value)

    def smooth_funding_rate(self, exchange: str, funding_rate: float) -> float:
        """Smooth funding rate for an exchange"""
        return self.smooth('funding_rate', funding_rate, exchange)

    def smooth_oi_change(self, exchange: str, oi_change_pct: float) -> float:
        """Smooth open interest change percentage"""
        return self.smooth('oi_change', oi_change_pct, exchange)

    def smooth_volume_ratio(self, exchange: str, volume_ratio: float) -> float:
        """Smooth volume ratio (current / average)"""
        return self.smooth('volume_ratio', volume_ratio, exchange)

    def reset_exchange(self, exchange: str):
        """Reset all filters for an exchange (e.g., after extended downtime)"""
        to_remove = [k for k in self.filters.keys() if k.endswith(f"_{exchange}")]
        for key in to_remove:
            del self.filters[key]

    def reset_all(self):
        """Reset all filters"""
        self.filters.clear()


class AdaptiveThresholds:
    """
    Dynamically adjust alert thresholds based on market volatility
    Higher volatility → higher thresholds to reduce noise
    """

    def __init__(self):
        self.volatility_window = []
        self.max_window_size = 20  # Use last 20 measurements

    def calculate_volatility(self, values: List[float]) -> float:
        """Calculate volatility (standard deviation) from recent values"""
        if len(values) < 2:
            return 0.0
        return float(np.std(values))

    def adjust_threshold(self, base_threshold: float, current_value: float,
                        metric_type: str = 'default') -> float:
        """
        Adjust threshold based on recent volatility

        Args:
            base_threshold: Base threshold from config
            current_value: Current metric value
            metric_type: Type of metric for context

        Returns:
            Adjusted threshold
        """
        # Add current value to window
        self.volatility_window.append(current_value)
        if len(self.volatility_window) > self.max_window_size:
            self.volatility_window.pop(0)

        # Need at least 5 samples to adjust
        if len(self.volatility_window) < 5:
            return base_threshold

        # Calculate volatility
        volatility = self.calculate_volatility(self.volatility_window)
        mean_value = np.mean(self.volatility_window)

        # Avoid division by zero
        if mean_value == 0:
            return base_threshold

        # Calculate volatility ratio (coefficient of variation)
        cv = volatility / abs(mean_value) if mean_value != 0 else 0

        # Adjust threshold based on volatility
        # High volatility (cv > 0.5) → increase threshold by up to 2x
        # Low volatility (cv < 0.1) → decrease threshold by up to 0.8x
        if cv > 0.5:
            multiplier = min(2.0, 1.0 + cv)
        elif cv < 0.1:
            multiplier = max(0.8, 1.0 - (0.1 - cv))
        else:
            multiplier = 1.0

        adjusted = base_threshold * multiplier

        return adjusted

    def get_dynamic_funding_threshold(self, base_threshold: float,
                                     current_funding: float) -> float:
        """Get dynamic threshold for funding rate alerts"""
        return self.adjust_threshold(base_threshold, current_funding, 'funding_rate')

    def reset(self):
        """Reset volatility tracking"""
        self.volatility_window.clear()


# Hysteresis for preventing alert oscillation
class Hysteresis:
    """
    Prevent rapid on/off toggling of alerts
    Requires sustained change before triggering opposite signal
    """

    def __init__(self, lower_threshold: float, upper_threshold: float):
        """
        Args:
            lower_threshold: Value must drop below this to deactivate
            upper_threshold: Value must rise above this to activate
        """
        self.lower_threshold = lower_threshold
        self.upper_threshold = upper_threshold
        self.state = False  # Current alert state

    def update(self, value: float) -> bool:
        """
        Update state based on value

        Returns:
            True if alert should be active
        """
        if value > self.upper_threshold:
            self.state = True
        elif value < self.lower_threshold:
            self.state = False
        # else: maintain current state (hysteresis zone)

        return self.state

    def reset(self):
        """Reset to inactive state"""
        self.state = False
