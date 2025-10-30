"""Market data domain models"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ExchangeType(str, Enum):
    """Supported cryptocurrency exchanges"""
    BINANCE = "Binance"
    BYBIT = "Bybit"
    GATEIO = "Gate.io"
    BITGET = "Bitget"
    OKX = "OKX"
    HYPERLIQUID = "HyperLiquid"
    DYDX = "dYdX v4"
    COINBASE_INTX = "Coinbase INTX"
    ASTERDEX = "AsterDEX"
    KRAKEN = "Kraken"
    COINBASE = "Coinbase"
    KUCOIN = "KuCoin"


class TradingPair(BaseModel):
    """Trading pair information"""
    symbol: str
    base: Optional[str] = None
    quote: Optional[str] = None
    volume: float = Field(ge=0)

    class Config:
        frozen = True


class MarketData(BaseModel):
    """Market data from a cryptocurrency exchange"""

    exchange: ExchangeType
    symbol: Optional[str] = None
    volume_24h: float = Field(gt=0, description="24-hour trading volume in USD")
    funding_rate: Optional[float] = Field(None, ge=-1, le=1, description="Current funding rate")
    open_interest: Optional[float] = Field(None, ge=0, description="Open interest in USD")
    market_count: Optional[int] = Field(None, ge=0, description="Number of active markets")
    top_pairs: List[TradingPair] = Field(default_factory=list, description="Top trading pairs by volume")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Data fetch timestamp")

    @validator('exchange', pre=True)
    def validate_exchange(cls, v):
        """Convert string to ExchangeType if needed"""
        if isinstance(v, str):
            # Try to match case-insensitively
            for exchange in ExchangeType:
                if exchange.value.lower() == v.lower():
                    return exchange
        return v

    class Config:
        frozen = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class FundingRate(BaseModel):
    """Funding rate information for a perpetual futures contract"""

    exchange: ExchangeType
    symbol: str
    funding_rate: float = Field(ge=-1, le=1)
    next_funding_time: Optional[datetime] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = True
        use_enum_values = True


class OpenInterest(BaseModel):
    """Open interest information"""

    exchange: ExchangeType
    symbol: str
    open_interest: float = Field(ge=0, description="Open interest in USD")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = True
        use_enum_values = True


class SymbolData(BaseModel):
    """Detailed data for a specific trading symbol"""

    exchange: ExchangeType
    symbol: str
    price: float = Field(gt=0, description="Current/last price")
    volume_24h: float = Field(ge=0, description="24-hour trading volume in USD")
    price_change_24h_pct: Optional[float] = Field(None, description="24-hour price change percentage")
    open_interest: Optional[float] = Field(None, ge=0, description="Open interest in USD")
    funding_rate: Optional[float] = Field(None, ge=-1, le=1, description="Current funding rate")
    num_trades: Optional[int] = Field(None, ge=0, description="Number of trades in 24h")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Data fetch timestamp")

    @validator('exchange', pre=True)
    def validate_exchange(cls, v):
        """Convert string to ExchangeType if needed"""
        if isinstance(v, str):
            for exchange in ExchangeType:
                if exchange.value.lower() == v.lower():
                    return exchange
        return v

    class Config:
        frozen = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
