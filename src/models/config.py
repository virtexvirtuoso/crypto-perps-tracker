"""Configuration models"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml
import os


class CacheConfig(BaseModel):
    """Cache configuration"""
    ttl: int = Field(300, description="Cache TTL in seconds")
    max_size: int = Field(1000, description="Maximum cache entries")


class DatabaseConfig(BaseModel):
    """Database configuration"""
    path: str = Field("data/market_history.db", description="SQLite database path")

    @validator('path')
    def ensure_parent_dir(cls, v):
        """Ensure parent directory exists"""
        Path(v).parent.mkdir(parents=True, exist_ok=True)
        return v


class ExchangeConfig(BaseModel):
    """Exchange API configuration"""
    enabled: List[str] = Field(default_factory=lambda: [
        # CEX (Centralized Exchanges)
        "binance", "bybit", "okx", "gateio", "bitget",
        "coinbase_intx", "kraken", "kucoin", "coinbase",
        # DEX (Decentralized Exchanges)
        "hyperliquid", "dydx", "asterdex"
    ])
    timeout: int = Field(10, description="API timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")


class DiscordConfig(BaseModel):
    """Discord webhook configuration"""
    webhook_url: str = Field(..., description="Discord webhook URL")
    rate_limit: int = Field(30, description="Max messages per minute")

    @validator('webhook_url')
    def validate_webhook_url(cls, v):
        """Validate webhook URL format"""
        if not v.startswith('https://discord.com/api/webhooks/'):
            raise ValueError("Invalid Discord webhook URL")
        return v


class AlertConfig(BaseModel):
    """Alert system configuration"""
    enabled: bool = Field(True, description="Enable alert system")
    deduplication_window: int = Field(3600, description="Deduplication window in seconds")

    # Alert thresholds
    funding_rate_high: float = Field(0.01, description="High funding rate threshold")
    funding_rate_low: float = Field(-0.01, description="Low funding rate threshold")
    volume_spike_multiplier: float = Field(2.0, description="Volume spike multiplier")

    # ML/Kalman settings
    enable_ml_scoring: bool = Field(False, description="Enable ML-based alert scoring")
    enable_kalman_filter: bool = Field(False, description="Enable Kalman filtering")
    enable_websocket: bool = Field(False, description="Enable WebSocket monitoring")


class BlacklistConfig(BaseModel):
    """Blacklist configuration for filtering symbols"""
    symbols: List[str] = Field(default_factory=list, description="List of blacklisted symbols")
    reasons: Dict[str, str] = Field(default_factory=dict, description="Reasons for blacklisting")


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field("INFO", description="Logging level")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )


class Config(BaseModel):
    """Main application configuration"""

    app_name: str = Field("Crypto Perps Tracker", description="Application name")
    environment: str = Field("production", description="Environment (dev/staging/production)")

    cache: CacheConfig = Field(default_factory=CacheConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    alert_database: DatabaseConfig = Field(
        default_factory=lambda: DatabaseConfig(path="data/alert_state.db")
    )
    exchanges: ExchangeConfig = Field(default_factory=ExchangeConfig)
    blacklist: BlacklistConfig = Field(default_factory=BlacklistConfig)
    discord: Optional[DiscordConfig] = None
    alerts: AlertConfig = Field(default_factory=AlertConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str) -> 'Config':
        """Load configuration from YAML file"""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        # Substitute environment variables in strings
        data = cls._substitute_env_vars(data)

        return cls(**data)

    @staticmethod
    def _substitute_env_vars(data: Any) -> Any:
        """Recursively substitute environment variables in config"""
        if isinstance(data, dict):
            return {k: Config._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [Config._substitute_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith('${') and data.endswith('}'):
            # Extract env var name
            env_var = data[2:-1]
            value = os.getenv(env_var)
            if value is None:
                raise ValueError(f"Environment variable {env_var} not set")
            return value
        return data

    class Config:
        extra = 'allow'  # Allow extra fields from YAML
