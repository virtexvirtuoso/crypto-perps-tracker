"""
Sector Rotation Discord Alerter

Sends formatted alerts to Discord when rotation signals are confirmed.
Includes multi-exchange context and CEX/DEX flow indicators.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests

from .storage import (
    SectorSignal,
    SectorSnapshot,
    SignalStrength,
    get_sector_metadata,
)

logger = logging.getLogger(__name__)


class SectorRotationAlerter:
    """
    Sends Discord alerts for confirmed sector rotation signals.

    Features:
    - Rich embeds with sector metadata
    - Multi-exchange context (funding spread, CEX/DEX flow)
    - Rate limiting to avoid spam
    - Configurable alert thresholds
    """

    # Discord webhook is now required via environment variable
    # Set DISCORD_SECTOR_WEBHOOK in your environment or pass webhook_url to constructor
    DEFAULT_WEBHOOK = None  # Removed hardcoded webhook for security

    # Alert cooldowns (seconds) to prevent spam
    SIGNAL_COOLDOWN = 3600  # 1 hour between same signal type for same sector
    ROTATION_PAIR_COOLDOWN = 7200  # 2 hours for rotation pairs

    # Embed colors
    COLORS = {
        'inflow': 0x00D68F,    # Green
        'outflow': 0xFF5252,   # Red
        'rotation': 0xFBBF24,  # Amber
        'neutral': 0x6B7280,   # Gray
    }

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        enabled: bool = True,
    ):
        """
        Initialize alerter.

        Args:
            webhook_url: Discord webhook URL (or set DISCORD_SECTOR_WEBHOOK env var)
            enabled: Whether alerting is enabled
        """
        self.webhook_url = webhook_url or os.getenv('DISCORD_SECTOR_WEBHOOK') or self.DEFAULT_WEBHOOK
        self.enabled = enabled and bool(self.webhook_url)

        # Track last alert times to prevent spam
        self._last_alerts: Dict[str, datetime] = {}

        if self.enabled:
            logger.info("SectorRotationAlerter initialized with Discord webhook")
        else:
            logger.warning("SectorRotationAlerter disabled (no webhook configured)")

    def alert_confirmed_signal(
        self,
        signal: SectorSignal,
        snapshot: Optional[SectorSnapshot] = None,
    ) -> bool:
        """
        Send alert for a confirmed rotation signal.

        Args:
            signal: The confirmed SectorSignal
            snapshot: Optional current snapshot for additional context

        Returns:
            True if alert sent successfully
        """
        if not self.enabled:
            return False

        if not signal.is_confirmed:
            return False

        # Check cooldown
        alert_key = f"{signal.sector_code}_{signal.signal_type}"
        if self._is_on_cooldown(alert_key):
            logger.debug(f"Alert on cooldown: {alert_key}")
            return False

        # Build and send embed
        try:
            embed = self._build_signal_embed(signal, snapshot)
            self._send_webhook(embed)
            self._last_alerts[alert_key] = datetime.utcnow()
            logger.info(f"Sent alert for {signal.signal_type} signal: {signal.sector_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def alert_rotation_pair(
        self,
        signal: SectorSignal,
        from_snapshot: Optional[SectorSnapshot] = None,
        to_snapshot: Optional[SectorSnapshot] = None,
    ) -> bool:
        """
        Send alert for a confirmed rotation pair.

        Args:
            signal: The rotation pair signal
            from_snapshot: Snapshot of source sector
            to_snapshot: Snapshot of destination sector

        Returns:
            True if alert sent successfully
        """
        if not self.enabled:
            return False

        if not signal.is_confirmed or signal.signal_type != 'rotation':
            return False

        # Check cooldown
        alert_key = f"rotation_{signal.from_sector}_{signal.to_sector}"
        if self._is_on_cooldown(alert_key, self.ROTATION_PAIR_COOLDOWN):
            logger.debug(f"Rotation pair alert on cooldown: {alert_key}")
            return False

        try:
            embed = self._build_rotation_pair_embed(signal, from_snapshot, to_snapshot)
            self._send_webhook(embed)
            self._last_alerts[alert_key] = datetime.utcnow()
            logger.info(f"Sent rotation pair alert: {signal.from_sector} → {signal.to_sector}")
            return True
        except Exception as e:
            logger.error(f"Failed to send rotation pair alert: {e}")
            return False

    def alert_market_state_change(
        self,
        new_state: str,
        old_state: str,
        summary: Dict[str, Any],
    ) -> bool:
        """
        Send alert when overall market state changes.

        Args:
            new_state: New market state (risk_on, risk_off, neutral)
            old_state: Previous market state
            summary: Signal summary dict

        Returns:
            True if alert sent successfully
        """
        if not self.enabled:
            return False

        if new_state == old_state:
            return False

        # Check cooldown
        alert_key = f"market_state_{new_state}"
        if self._is_on_cooldown(alert_key, 3600):
            return False

        try:
            embed = self._build_market_state_embed(new_state, old_state, summary)
            self._send_webhook(embed)
            self._last_alerts[alert_key] = datetime.utcnow()
            logger.info(f"Sent market state change alert: {old_state} → {new_state}")
            return True
        except Exception as e:
            logger.error(f"Failed to send market state alert: {e}")
            return False

    def _is_on_cooldown(self, key: str, cooldown: int = None) -> bool:
        """Check if an alert key is still on cooldown."""
        cooldown = cooldown or self.SIGNAL_COOLDOWN
        last_alert = self._last_alerts.get(key)
        if not last_alert:
            return False

        elapsed = (datetime.utcnow() - last_alert).total_seconds()
        return elapsed < cooldown

    def _build_signal_embed(
        self,
        signal: SectorSignal,
        snapshot: Optional[SectorSnapshot],
    ) -> Dict[str, Any]:
        """Build Discord embed for a sector signal."""
        metadata = get_sector_metadata(signal.sector_code)

        # Determine title and color
        if signal.signal_type == 'inflow':
            title = f"🟢 {metadata['emoji']} {metadata['name']} INFLOW Signal"
            color = self.COLORS['inflow']
        else:
            title = f"🔴 {metadata['emoji']} {metadata['name']} OUTFLOW Signal"
            color = self.COLORS['outflow']

        # Build fields
        fields = [
            {
                'name': '📊 Rotation Score',
                'value': f"**{signal.rotation_score:.1f}**/100",
                'inline': True,
            },
            {
                'name': '💪 Signal Strength',
                'value': signal.signal_strength.upper(),
                'inline': True,
            },
            {
                'name': '✅ Confirmations',
                'value': str(signal.confirmation_count),
                'inline': True,
            },
        ]

        # Add multi-exchange context if available
        if signal.funding_spread:
            fields.append({
                'name': '📈 Funding Spread',
                'value': f"{signal.funding_spread * 10000:.2f} bps",
                'inline': True,
            })

        if signal.cex_dex_flow is not None:
            flow_emoji = "🏛️" if signal.cex_dex_flow > 0 else "🌐"
            flow_label = "CEX favored" if signal.cex_dex_flow > 0 else "DEX favored"
            fields.append({
                'name': f'{flow_emoji} CEX/DEX Flow',
                'value': f"{signal.cex_dex_flow:+.3f} ({flow_label})",
                'inline': True,
            })

        if signal.exchange_consensus:
            fields.append({
                'name': '🤝 Exchange Consensus',
                'value': f"{signal.exchange_consensus * 100:.0f}%",
                'inline': True,
            })

        # Add snapshot metrics if available
        if snapshot:
            fields.append({
                'name': '📊 Market Data',
                'value': (
                    f"Volume Z: {snapshot.volume_share_zscore:+.2f}\n"
                    f"Breadth: {snapshot.breadth_ratio * 100:.0f}%\n"
                    f"Exchanges: {snapshot.exchange_count}"
                ),
                'inline': False,
            })

        return {
            'embeds': [{
                'title': title,
                'color': color,
                'fields': fields,
                'footer': {
                    'text': f"Sector Rotation • Multi-Exchange Analysis"
                },
                'timestamp': datetime.utcnow().isoformat(),
            }]
        }

    def _build_rotation_pair_embed(
        self,
        signal: SectorSignal,
        from_snapshot: Optional[SectorSnapshot],
        to_snapshot: Optional[SectorSnapshot],
    ) -> Dict[str, Any]:
        """Build Discord embed for a rotation pair."""
        from_meta = get_sector_metadata(signal.from_sector)
        to_meta = get_sector_metadata(signal.to_sector)

        title = f"🔄 Rotation: {from_meta['emoji']} {from_meta['name']} → {to_meta['emoji']} {to_meta['name']}"

        fields = [
            {
                'name': '📉 From Sector',
                'value': f"{from_meta['emoji']} **{from_meta['name']}**\n(Outflow)",
                'inline': True,
            },
            {
                'name': '➡️',
                'value': '→',
                'inline': True,
            },
            {
                'name': '📈 To Sector',
                'value': f"{to_meta['emoji']} **{to_meta['name']}**\n(Inflow)",
                'inline': True,
            },
            {
                'name': '📊 Score Differential',
                'value': f"**{signal.rotation_score:.1f}** points",
                'inline': True,
            },
            {
                'name': '✅ Confirmations',
                'value': str(signal.confirmation_count),
                'inline': True,
            },
        ]

        return {
            'embeds': [{
                'title': title,
                'description': (
                    "Capital appears to be rotating from one sector to another. "
                    "This pattern has been confirmed across multiple periods."
                ),
                'color': self.COLORS['rotation'],
                'fields': fields,
                'footer': {
                    'text': f"Sector Rotation • Multi-Exchange Analysis"
                },
                'timestamp': datetime.utcnow().isoformat(),
            }]
        }

    def _build_market_state_embed(
        self,
        new_state: str,
        old_state: str,
        summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build Discord embed for market state change."""
        state_emoji = {
            'risk_on': '🟢',
            'risk_off': '🔴',
            'neutral': '⚪',
        }

        state_names = {
            'risk_on': 'Risk-On',
            'risk_off': 'Risk-Off',
            'neutral': 'Neutral',
        }

        title = f"{state_emoji.get(new_state, '⚪')} Market State Change: {state_names.get(new_state, 'Unknown')}"

        fields = [
            {
                'name': '📊 State Change',
                'value': f"{state_names.get(old_state, '?')} → **{state_names.get(new_state, '?')}**",
                'inline': True,
            },
            {
                'name': '📈 Active Signals',
                'value': str(summary.get('active_signals', 0)),
                'inline': True,
            },
            {
                'name': '✅ Confirmed',
                'value': str(summary.get('confirmed_signals', 0)),
                'inline': True,
            },
        ]

        if summary.get('inflow_sectors'):
            fields.append({
                'name': '🟢 Inflow Sectors',
                'value': ', '.join(summary['inflow_sectors'][:5]),
                'inline': False,
            })

        if summary.get('outflow_sectors'):
            fields.append({
                'name': '🔴 Outflow Sectors',
                'value': ', '.join(summary['outflow_sectors'][:5]),
                'inline': False,
            })

        color = {
            'risk_on': self.COLORS['inflow'],
            'risk_off': self.COLORS['outflow'],
            'neutral': self.COLORS['neutral'],
        }.get(new_state, self.COLORS['neutral'])

        return {
            'embeds': [{
                'title': title,
                'color': color,
                'fields': fields,
                'footer': {
                    'text': f"Sector Rotation • Market State Monitor"
                },
                'timestamp': datetime.utcnow().isoformat(),
            }]
        }

    def _send_webhook(self, payload: Dict[str, Any]) -> None:
        """Send payload to Discord webhook."""
        if not self.webhook_url:
            raise ValueError("No webhook URL configured")

        response = requests.post(
            self.webhook_url,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
