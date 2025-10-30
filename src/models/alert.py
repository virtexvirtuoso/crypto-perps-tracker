"""Alert domain models"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, date
from enum import Enum
from .market import ExchangeType


class AlertType(str, Enum):
    """Types of alerts that can be generated"""
    HIGH_FUNDING = "high_funding"
    LOW_FUNDING = "low_funding"
    VOLUME_SPIKE = "volume_spike"
    VOLUME_DROP = "volume_drop"
    BASIS_DIVERGENCE = "basis_divergence"
    OPEN_INTEREST_SPIKE = "open_interest_spike"
    LIQUIDATION_CASCADE = "liquidation_cascade"
    MARKET_SENTIMENT = "market_sentiment"


class AlertPriority(str, Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(BaseModel):
    """Alert model for trading signals and market events"""

    type: AlertType
    symbol: str
    exchange: ExchangeType
    priority: AlertPriority
    message: str
    value: float
    threshold: float
    confidence: Optional[float] = Field(None, ge=0, le=1, description="ML confidence score if available")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional alert metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def alert_id(self) -> str:
        """Generate unique alert ID for deduplication"""
        date_str = self.timestamp.date().isoformat()
        return f"{self.type.value}_{self.symbol}_{self.exchange.value}_{date_str}"

    def to_discord_embed(self) -> Dict[str, Any]:
        """Convert alert to Discord embed format"""
        color_map = {
            AlertPriority.LOW: 0x3498db,      # Blue
            AlertPriority.MEDIUM: 0xf39c12,   # Orange
            AlertPriority.HIGH: 0xe67e22,     # Dark orange
            AlertPriority.CRITICAL: 0xe74c3c, # Red
        }

        embed = {
            "title": f"🚨 {self.type.value.replace('_', ' ').title()}",
            "description": self.message,
            "color": color_map.get(self.priority, 0x95a5a6),
            "fields": [
                {"name": "Symbol", "value": self.symbol, "inline": True},
                {"name": "Exchange", "value": self.exchange.value, "inline": True},
                {"name": "Priority", "value": self.priority.value.upper(), "inline": True},
                {"name": "Value", "value": f"{self.value:.4f}", "inline": True},
                {"name": "Threshold", "value": f"{self.threshold:.4f}", "inline": True},
            ],
            "timestamp": self.timestamp.isoformat(),
        }

        if self.confidence:
            embed["fields"].append({
                "name": "Confidence",
                "value": f"{self.confidence:.1%}",
                "inline": True
            })

        return embed

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class AlertState(BaseModel):
    """Alert state for tracking sent alerts and preventing duplicates"""

    alert_id: str
    alert_type: AlertType
    symbol: str
    exchange: ExchangeType
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        """Check if alert state has expired"""
        return datetime.utcnow() > self.expires_at

    class Config:
        use_enum_values = True
