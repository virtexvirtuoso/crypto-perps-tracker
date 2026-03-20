"""Signal data models for derivatives-based predictions"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, SerializeAsAny


class SignalType(str, Enum):
    """Types of trading signals"""
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    LONG_SHORT_RATIO = "long_short_ratio"
    LIQUIDATION = "liquidation"
    BASIS = "basis"
    CVD = "cvd"
    OPTIONS_IV = "options_iv"
    FUSION = "fusion"


class SignalDirection(str, Enum):
    """Trading signal direction"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    """Signal strength levels"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXTREME = "extreme"


class BaseSignal(BaseModel):
    """Base signal model"""
    signal_type: SignalType
    symbol: str
    direction: SignalDirection
    strength: SignalStrength
    confidence: float = Field(ge=0, le=100, description="Confidence percentage (0-100)")
    timestamp: datetime
    horizon: str = Field(description="Expected time horizon (e.g., '4h-24h')")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class FundingRateSignal(BaseSignal):
    """Funding rate extremes signal"""
    funding_rate: float = Field(description="Current funding rate")
    funding_rate_8h: float = Field(description="8-hour equivalent rate")
    next_funding_time: datetime
    threshold_crossed: str = Field(description="Which threshold was crossed")
    price_vs_ema200: Optional[float] = Field(None, description="Price relative to 200 EMA")


class OpenInterestSignal(BaseSignal):
    """Open interest surge with price divergence signal"""
    oi_change_pct: float = Field(description="OI change percentage")
    oi_current: float = Field(description="Current open interest")
    oi_24h_ago: float = Field(description="Open interest 24h ago")
    price_change_pct: float = Field(description="Price change percentage")
    divergence_type: str = Field(description="bullish/bearish divergence")


class LongShortRatioSignal(BaseSignal):
    """Long/Short ratio skew signal"""
    ratio: float = Field(description="Current long/short ratio")
    long_account_pct: float = Field(description="Percentage of long accounts")
    short_account_pct: float = Field(description="Percentage of short accounts")
    crowd_side: str = Field(description="Which side is crowded")


class LiquidationSignal(BaseSignal):
    """Liquidation heatmap/cascade zones signal"""
    liquidation_volume_24h: float = Field(description="24h liquidation volume")
    liquidation_clusters: list[Dict[str, Any]] = Field(description="Price levels with liquidation clusters")
    cascade_risk: str = Field(description="Risk level for liquidation cascade")
    predicted_move_pct: float = Field(description="Predicted price move percentage")


class BasisSignal(BaseSignal):
    """Perp vs Spot basis divergence signal"""
    perp_price: float
    spot_price: float
    basis_pct: float = Field(description="Basis percentage (perp-spot)/spot")
    basis_type: str = Field(description="contango/backwardation")
    arbitrage_opportunity: bool


class CVDSignal(BaseSignal):
    """Cumulative Volume Delta signal"""
    cvd: float = Field(description="Cumulative volume delta in USDT")
    cvd_15min: float = Field(description="15-minute CVD")
    buy_volume: float = Field(description="Aggressive buy volume")
    sell_volume: float = Field(description="Aggressive sell volume")
    hidden_flow: str = Field(description="Hidden order flow direction")


class OptionsIVSignal(BaseSignal):
    """Options implied volatility skew signal"""
    iv_put: float = Field(description="Put option IV")
    iv_call: float = Field(description="Call option IV")
    iv_skew: float = Field(description="IV skew (put - call)")
    market_sentiment: str = Field(description="fear/complacency based on skew")
    predicted_move_pct: float = Field(description="Expected price move")


class FusionSignal(BaseSignal):
    """Composite signal combining multiple indicators"""
    score: float = Field(description="Composite score (-5 to +5, confidence-weighted)")
    component_signals: Dict[str, Any] = Field(description="Individual signal contributions")
    funding_contribution: float = Field(description="Funding rate contribution (confidence-weighted)")
    oi_contribution: float = Field(description="Open interest contribution (confidence-weighted)")
    lsr_contribution: float = Field(description="Long/short ratio contribution (confidence-weighted)")
    cvd_contribution: float = Field(description="CVD contribution (confidence-weighted)")
    win_rate_estimate: float = Field(description="Estimated win rate percentage")
    entry_recommendation: str = Field(description="ENTER LONG/SHORT/WAIT")


class SignalResponse(BaseModel):
    """API response wrapper for signals"""
    success: bool
    signal: Optional[SerializeAsAny[BaseSignal]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MultiSignalResponse(BaseModel):
    """API response for multiple signals"""
    success: bool
    signals: list[SerializeAsAny[BaseSignal]] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
