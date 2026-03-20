"""API Configuration

Manages configuration for the derivatives signals API including
Redis, rate limiting, and signal calculation parameters.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class RedisConfig(BaseModel):
    """Redis configuration"""
    enabled: bool = Field(
        default=True,
        description="Enable Redis caching"
    )
    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    host: str = Field(
        default="localhost",
        description="Redis host"
    )
    port: int = Field(
        default=6379,
        description="Redis port"
    )
    db: int = Field(
        default=0,
        description="Redis database number"
    )


class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    requests_per_minute: int = Field(
        default=60,
        description="Max requests per minute per IP"
    )


class SignalConfig(BaseModel):
    """Signal calculation configuration"""
    funding_extreme_short: float = Field(
        default=-0.0005,
        description="Funding rate extreme short threshold"
    )
    funding_extreme_long: float = Field(
        default=0.001,
        description="Funding rate extreme long threshold"
    )
    oi_surge_threshold: float = Field(
        default=0.30,
        description="OI surge threshold (30%)"
    )
    price_divergence_threshold: float = Field(
        default=0.02,
        description="Price divergence threshold (2%)"
    )
    lsr_crowded_long: float = Field(
        default=3.0,
        description="Long/short ratio crowded long threshold"
    )
    lsr_crowded_short: float = Field(
        default=0.33,
        description="Long/short ratio crowded short threshold"
    )
    basis_contango_discount: float = Field(
        default=-0.005,
        description="Basis contango discount threshold"
    )
    basis_backwardation_premium: float = Field(
        default=0.01,
        description="Basis backwardation premium threshold"
    )
    cvd_threshold: float = Field(
        default=500_000,
        description="CVD threshold in USDT"
    )
    iv_skew_fear: float = Field(
        default=0.15,
        description="IV skew fear threshold"
    )
    iv_skew_complacency: float = Field(
        default=-0.15,
        description="IV skew complacency threshold"
    )


class APIConfig(BaseModel):
    """Complete API configuration"""
    redis: RedisConfig = Field(default_factory=RedisConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    signals: SignalConfig = Field(default_factory=SignalConfig)

    api_host: str = Field(
        default="0.0.0.0",
        description="API host"
    )
    api_port: int = Field(
        default=8000,
        description="API port"
    )
    debug: bool = Field(
        default=False,
        description="Debug mode"
    )
    cors_origins: list[str] = Field(
        default=["*"],
        description="CORS allowed origins"
    )

    @classmethod
    def from_env(cls) -> "APIConfig":
        """Load configuration from environment variables

        Environment variables:
            REDIS_URL: Redis connection URL
            REDIS_ENABLED: Enable Redis (true/false)
            API_HOST: API host
            API_PORT: API port
            DEBUG: Debug mode (true/false)

        Returns:
            APIConfig instance
        """
        redis_config = RedisConfig(
            enabled=os.getenv("REDIS_ENABLED", "true").lower() == "true",
            url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0"))
        )

        rate_limit_config = RateLimitConfig(
            enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            requests_per_minute=int(os.getenv("RATE_LIMIT_RPM", "60"))
        )

        return cls(
            redis=redis_config,
            rate_limit=rate_limit_config,
            signals=SignalConfig(),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            cors_origins=os.getenv("CORS_ORIGINS", "*").split(",")
        )


# Global config instance
_config: Optional[APIConfig] = None


def get_config() -> APIConfig:
    """Get global configuration instance

    Returns:
        APIConfig instance
    """
    global _config

    if _config is None:
        _config = APIConfig.from_env()

    return _config
