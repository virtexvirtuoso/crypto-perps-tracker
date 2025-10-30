"""
ML-Based Alert Scoring and Prioritization (Phase 3+)
Uses Isolation Forest and historical patterns to score alert quality
"""
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path
from datetime import datetime, timedelta


class AlertScorer:
    """
    Machine learning-based alert quality scoring
    Prioritizes alerts based on historical effectiveness
    """

    def __init__(self, model_path: str = 'data/ml_models'):
        self.model_path = Path(model_path)
        self.model_path.mkdir(parents=True, exist_ok=True)

        # Isolation Forest for anomaly detection
        self.anomaly_detector = IsolationForest(
            contamination=0.1,  # Expect 10% of signals to be truly anomalous
            random_state=42,
            n_estimators=100
        )

        self.scaler = StandardScaler()
        self.is_fitted = False

        # Historical alert effectiveness data
        self.alert_history: List[Dict] = []
        self._load_history()

    def _load_history(self):
        """Load historical alert data"""
        history_file = self.model_path / 'alert_history.json'
        if history_file.exists():
            with open(history_file, 'r') as f:
                self.alert_history = json.load(f)

    def _save_history(self):
        """Save historical alert data"""
        history_file = self.model_path / 'alert_history.json'
        with open(history_file, 'w') as f:
            json.dump(self.alert_history[-1000:], f, indent=2)  # Keep last 1000

    def extract_features(self, alert_data: Dict) -> np.ndarray:
        """
        Extract features from alert data for ML scoring

        Features:
        - Confidence level
        - Tier (urgency)
        - Time of day (hour)
        - Day of week
        - Recent alert frequency
        - Metric deviations (funding rate, OI change, volume)
        - Multi-exchange agreement
        """
        features = []

        # Basic alert properties
        features.append(alert_data.get('confidence', 0))
        features.append(alert_data.get('tier', 3))

        # Temporal features
        now = datetime.now()
        features.append(now.hour)  # 0-23
        features.append(now.weekday())  # 0-6

        # Market condition features
        features.append(alert_data.get('funding_rate', 0) * 100)  # Scale to basis points
        features.append(alert_data.get('oi_change_pct', 0))
        features.append(alert_data.get('volume_ratio', 1))
        features.append(alert_data.get('basis_pct', 0))

        # Multi-exchange agreement
        features.append(alert_data.get('exchange_agreement', 0))  # 0-1 ratio

        # Recent alert density
        features.append(alert_data.get('alerts_last_hour', 0))
        features.append(alert_data.get('alerts_last_day', 0))

        return np.array(features).reshape(1, -1)

    def score_alert(self, alert_data: Dict) -> float:
        """
        Score an alert from 0-100 based on predicted quality

        Returns:
            Score (0-100), where higher = more likely to be actionable
        """
        features = self.extract_features(alert_data)

        if not self.is_fitted or len(self.alert_history) < 50:
            # Not enough data yet - use simple heuristic scoring
            return self._heuristic_score(alert_data)

        # Normalize features
        features_scaled = self.scaler.transform(features)

        # Get anomaly score (-1 to 1, where -1 is most anomalous)
        anomaly_score = self.anomaly_detector.score_samples(features_scaled)[0]

        # Convert to 0-100 scale (more anomalous = higher score)
        # Anomaly scores typically range from -0.5 to 0.5
        ml_score = min(100, max(0, (1 - anomaly_score) * 50))

        # Blend with heuristic score
        heuristic_score = self._heuristic_score(alert_data)
        final_score = 0.6 * ml_score + 0.4 * heuristic_score

        return final_score

    def _heuristic_score(self, alert_data: Dict) -> float:
        """
        Simple rule-based scoring when ML model not ready
        """
        score = 50.0  # Base score

        # Confidence boost
        confidence = alert_data.get('confidence', 50)
        score += (confidence - 50) * 0.5  # +/- 25 points

        # Tier urgency boost
        tier = alert_data.get('tier', 3)
        if tier == 1:
            score += 20
        elif tier == 2:
            score += 10

        # Multi-exchange agreement boost
        agreement = alert_data.get('exchange_agreement', 0)
        score += agreement * 15  # Up to +15 for full agreement

        # Extreme values boost
        funding = abs(alert_data.get('funding_rate', 0))
        if funding > 0.001:  # > 0.1%
            score += 10

        oi_change = abs(alert_data.get('oi_change_pct', 0))
        if oi_change > 15:
            score += 10

        # Penalize if too many recent alerts (fatigue factor)
        alerts_last_hour = alert_data.get('alerts_last_hour', 0)
        if alerts_last_hour > 5:
            score -= (alerts_last_hour - 5) * 5

        return min(100, max(0, score))

    def train_model(self, labeled_data: Optional[List[Dict]] = None):
        """
        Train anomaly detection model on historical data

        Args:
            labeled_data: Optional list of alert data with effectiveness labels
        """
        if labeled_data:
            self.alert_history.extend(labeled_data)

        if len(self.alert_history) < 50:
            print(f"Not enough training data ({len(self.alert_history)}/50 minimum)")
            return

        # Extract features from all historical alerts
        X = []
        for alert in self.alert_history[-500:]:  # Use last 500 alerts
            features = self.extract_features(alert)
            X.append(features.flatten())

        X = np.array(X)

        # Fit scaler
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)

        # Train Isolation Forest
        self.anomaly_detector.fit(X_scaled)
        self.is_fitted = True

        print(f"Model trained on {len(X)} samples")

    def record_alert_outcome(self, alert_data: Dict, was_actionable: bool):
        """
        Record whether an alert led to actionable trading opportunity

        Args:
            alert_data: The alert that was sent
            was_actionable: True if alert was useful/accurate
        """
        alert_data['was_actionable'] = was_actionable
        alert_data['timestamp'] = datetime.now().isoformat()

        self.alert_history.append(alert_data)
        self._save_history()

        # Retrain periodically
        if len(self.alert_history) % 50 == 0:
            self.train_model()

    def get_effectiveness_stats(self, days: int = 7) -> Dict:
        """
        Calculate alert effectiveness statistics

        Returns:
            Dict with accuracy, precision metrics
        """
        cutoff = datetime.now() - timedelta(days=days)

        recent_alerts = [
            a for a in self.alert_history
            if 'timestamp' in a and
            datetime.fromisoformat(a['timestamp']) > cutoff and
            'was_actionable' in a
        ]

        if not recent_alerts:
            return {
                'total_alerts': 0,
                'actionable_count': 0,
                'actionable_rate': 0.0
            }

        actionable_count = sum(1 for a in recent_alerts if a['was_actionable'])

        return {
            'total_alerts': len(recent_alerts),
            'actionable_count': actionable_count,
            'actionable_rate': actionable_count / len(recent_alerts) if recent_alerts else 0.0,
            'by_tier': self._stats_by_tier(recent_alerts)
        }

    def _stats_by_tier(self, alerts: List[Dict]) -> Dict:
        """Calculate effectiveness by tier"""
        by_tier = {}
        for tier in [1, 2, 3]:
            tier_alerts = [a for a in alerts if a.get('tier') == tier]
            if tier_alerts:
                actionable = sum(1 for a in tier_alerts if a.get('was_actionable'))
                by_tier[f'tier_{tier}'] = {
                    'count': len(tier_alerts),
                    'actionable_rate': actionable / len(tier_alerts)
                }
        return by_tier


class AlertPrioritizer:
    """
    Prioritizes and ranks multiple simultaneous alerts
    """

    def __init__(self, scorer: AlertScorer):
        self.scorer = scorer

    def prioritize(self, alerts: List[Dict], max_alerts: int = 5) -> List[Dict]:
        """
        Rank and filter alerts by priority

        Args:
            alerts: List of alert candidates
            max_alerts: Maximum number to return

        Returns:
            Top N alerts sorted by priority
        """
        if not alerts:
            return []

        # Score each alert
        scored_alerts = []
        for alert in alerts:
            score = self.scorer.score_alert(alert)
            alert['ml_score'] = score
            scored_alerts.append(alert)

        # Sort by score (descending)
        scored_alerts.sort(key=lambda x: x['ml_score'], reverse=True)

        # Return top N
        return scored_alerts[:max_alerts]

    def should_bundle(self, alerts: List[Dict]) -> bool:
        """
        Determine if alerts should be bundled into digest

        Returns:
            True if alerts should be batched together
        """
        # Bundle if:
        # - More than 3 alerts in same time window
        # - All are same tier
        # - All are lower priority (score < 70)

        if len(alerts) < 3:
            return False

        # Check if all same tier
        tiers = set(a.get('tier', 3) for a in alerts)
        if len(tiers) > 1:
            return False

        # Check if all lower priority
        avg_score = np.mean([a.get('ml_score', 50) for a in alerts])
        return avg_score < 70
