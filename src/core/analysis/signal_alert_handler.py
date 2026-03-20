"""
Perpetuals Pulse Signal Alert Handler

Sends Discord notifications when trading signals are generated.
Integrates with Phase 2 signal generation system.
"""

import requests
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum


class SignalAlertConfig:
    """Configuration for signal alerts"""

    # Discord webhook URL
    WEBHOOK_URL = "https://discord.com/api/webhooks/1439697883199705270/4b608XidmYfCV48I1ZArvunQvUEqGGMw2N3rnXt-yJFUFdn3e1OxzRDvWTff-mQK9I5X"

    # Alert thresholds (only send alerts meeting these criteria)
    MIN_CONFIDENCE = 0.5  # Only send signals with 50%+ confidence
    ENABLED_SIGNAL_TYPES = [
        'funding_divergence',
        'ls_extreme',
        'liquidation_risk',
        'momentum'
    ]

    # Strength filtering (which strengths to alert on)
    ALERT_STRENGTHS = ['extreme', 'strong', 'moderate']  # Exclude 'weak'

    # Cooldown to prevent spam (seconds between alerts)
    COOLDOWN_SECONDS = 300  # 5 minutes between alerts


class SignalAlertHandler:
    """
    Handles Discord alerts for trading signals.

    Responsibilities:
    - Format signals into rich Discord embeds
    - Filter signals based on confidence/strength thresholds
    - Send webhook notifications
    - Track cooldowns to prevent spam
    """

    def __init__(
        self,
        webhook_url: str = SignalAlertConfig.WEBHOOK_URL,
        min_confidence: float = SignalAlertConfig.MIN_CONFIDENCE
    ):
        """
        Initialize alert handler.

        Args:
            webhook_url: Discord webhook URL
            min_confidence: Minimum confidence (0-1) to trigger alerts
        """
        self.logger = logging.getLogger(__name__)
        self.webhook_url = webhook_url
        self.min_confidence = min_confidence
        self.last_alert_time = 0

    def should_alert(self, signal: Dict[str, Any]) -> bool:
        """
        Determine if a signal meets alerting criteria.

        Args:
            signal: Signal dictionary from signal generator

        Returns:
            True if signal should trigger an alert
        """
        # Check confidence threshold
        if signal.get('confidence', 0) < self.min_confidence:
            return False

        # Check signal type filter
        if signal.get('signal_type') not in SignalAlertConfig.ENABLED_SIGNAL_TYPES:
            return False

        # Check strength filter
        if signal.get('strength') not in SignalAlertConfig.ALERT_STRENGTHS:
            return False

        # Check cooldown
        import time
        current_time = time.time()
        if current_time - self.last_alert_time < SignalAlertConfig.COOLDOWN_SECONDS:
            self.logger.debug(f"Alert cooldown active, skipping")
            return False

        return True

    def format_signal_embed(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a signal into a Discord embed.

        Args:
            signal: Signal dictionary

        Returns:
            Discord embed dictionary
        """
        # Color based on direction and strength
        direction = signal.get('direction', 'neutral')
        strength = signal.get('strength', 'moderate')

        if direction == 'bullish':
            if strength == 'extreme':
                color = 0x00FF00  # Bright green
            elif strength == 'strong':
                color = 0x00CC00  # Green
            else:
                color = 0x009900  # Dark green
        elif direction == 'bearish':
            if strength == 'extreme':
                color = 0xFF0000  # Bright red
            elif strength == 'strong':
                color = 0xCC0000  # Red
            else:
                color = 0x990000  # Dark red
        else:
            color = 0x808080  # Gray

        # Signal type emoji
        signal_type = signal.get('signal_type', 'unknown')
        emoji_map = {
            'funding_divergence': '💸',
            'ls_extreme': '⚠️',
            'liquidation_risk': '🔥',
            'momentum': '📈'
        }
        emoji = emoji_map.get(signal_type, '🎯')

        # Direction emoji
        direction_emoji = '🟢' if direction == 'bullish' else '🔴' if direction == 'bearish' else '⚪'

        # Build title
        title = f"{emoji} {signal_type.replace('_', ' ').title()} Signal"

        # Build description
        description = signal.get('description', 'No description available')

        # Build fields
        fields = [
            {
                'name': 'Direction',
                'value': f"{direction_emoji} **{direction.upper()}**",
                'inline': True
            },
            {
                'name': 'Strength',
                'value': f"**{strength.upper()}**",
                'inline': True
            },
            {
                'name': 'Confidence',
                'value': f"**{signal.get('confidence', 0):.1%}**",
                'inline': True
            },
            {
                'name': 'Time Horizon',
                'value': f"{signal.get('time_horizon_hours', 'N/A')} hours",
                'inline': True
            }
        ]

        # Add optional fields
        if signal.get('expected_move_pct') is not None:
            fields.append({
                'name': 'Expected Move',
                'value': f"{signal['expected_move_pct']:.2f}%",
                'inline': True
            })

        if signal.get('max_drawdown_risk_pct') is not None:
            fields.append({
                'name': 'Max Risk',
                'value': f"{signal['max_drawdown_risk_pct']:.1f}%",
                'inline': True
            })

        # Build embed
        embed = {
            'title': title,
            'description': description,
            'color': color,
            'fields': fields,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'footer': {
                'text': 'Perpetuals Pulse Signal System'
            }
        }

        return embed

    def send_alert(self, signals: List[Dict[str, Any]]) -> bool:
        """
        Send Discord alert for filtered signals.

        Args:
            signals: List of signal dictionaries

        Returns:
            True if alert sent successfully
        """
        # Filter signals that meet alerting criteria
        alertable_signals = [s for s in signals if self.should_alert(s)]

        if not alertable_signals:
            self.logger.debug(f"No signals meet alert criteria (checked {len(signals)} signals)")
            return False

        try:
            # Build embeds for each signal
            embeds = [self.format_signal_embed(signal) for signal in alertable_signals]

            # Prepare payload
            payload = {
                'username': 'Perpetuals Pulse Bot',
                'avatar_url': 'https://i.imgur.com/4M34hi2.png',  # Optional: trading bot avatar
                'embeds': embeds[:10]  # Discord limit: 10 embeds per message
            }

            # Send webhook
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )

            if response.status_code == 204:
                # Update cooldown timer
                import time
                self.last_alert_time = time.time()

                self.logger.info(f"✅ Sent Discord alert for {len(alertable_signals)} signals")
                return True
            else:
                self.logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {e}", exc_info=True)
            return False

    def send_test_alert(self) -> bool:
        """
        Send a test alert to verify webhook configuration.

        Returns:
            True if test alert sent successfully
        """
        test_signal = {
            'signal_type': 'funding_divergence',
            'direction': 'bearish',
            'strength': 'strong',
            'confidence': 0.78,
            'description': '🧪 Test Alert: Funding rate 1.8σ above mean. This is a test signal.',
            'time_horizon_hours': 24,
            'expected_move_pct': 4.5,
            'max_drawdown_risk_pct': 1.5
        }

        try:
            embed = self.format_signal_embed(test_signal)

            payload = {
                'username': 'Perpetuals Pulse Bot',
                'content': '🧪 **Test Alert** - Signal system operational!',
                'embeds': [embed]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )

            if response.status_code == 204:
                self.logger.info("✅ Test alert sent successfully")
                return True
            else:
                self.logger.error(f"Test alert failed: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Test alert error: {e}")
            return False


# Singleton instance
_alert_handler: Optional[SignalAlertHandler] = None


def get_signal_alert_handler() -> SignalAlertHandler:
    """Get singleton alert handler instance"""
    global _alert_handler
    if _alert_handler is None:
        _alert_handler = SignalAlertHandler()
    return _alert_handler


# Standalone test function
if __name__ == '__main__':
    """Test the alert handler"""
    import logging
    logging.basicConfig(level=logging.INFO)

    handler = SignalAlertHandler()

    print("Sending test alert...")
    success = handler.send_test_alert()

    if success:
        print("✅ Test alert sent! Check your Discord channel.")
    else:
        print("❌ Test alert failed. Check logs for details.")
