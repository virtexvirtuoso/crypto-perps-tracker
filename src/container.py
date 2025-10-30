"""Dependency injection container

This module provides a centralized container for managing dependencies
and wiring up services, repositories, and clients.
"""

from dataclasses import dataclass
from typing import Optional
from src.models.config import Config
from src.utils.cache import TTLCache
from src.clients.factory import ClientFactory
from src.services.exchange import ExchangeService
from src.services.analysis import AnalysisService
from src.services.report import ReportService
from src.services.alert import AlertService
from src.repositories.market import MarketRepository
from src.repositories.alert import AlertRepository


@dataclass
class Container:
    """Dependency injection container for application components

    This container manages the lifecycle and dependencies of all
    application services, repositories, and utilities.

    Usage:
        config = Config.from_yaml('config/config.yaml')
        container = Container(config)

        # Access services (recommended)
        markets = container.exchange_service.fetch_all_markets()
        total_volume = container.exchange_service.get_total_volume()

        # Or access clients directly
        gateio = container.client_factory.create('gateio')
    """

    config: Config

    def __post_init__(self):
        """Initialize all dependencies after config is set"""

        # ============================================================
        # Utilities
        # ============================================================
        self.cache = TTLCache(default_ttl=self.config.cache.ttl)

        # ============================================================
        # Clients
        # ============================================================
        self.client_factory = ClientFactory(
            timeout=self.config.exchanges.timeout,
            retry_attempts=self.config.exchanges.retry_attempts
        )

        # ============================================================
        # Repositories
        # ============================================================
        self.market_repo = MarketRepository(self.config.database.path)
        self.alert_repo = AlertRepository(self.config.alert_database.path)

        # ============================================================
        # Services
        # ============================================================
        self.exchange_service = ExchangeService(
            cache=self.cache,
            client_factory=self.client_factory,
            exchanges=self.config.exchanges.enabled,
            blacklist=self.config.blacklist.symbols
        )

        self.analysis_service = AnalysisService(
            exchange_service=self.exchange_service
        )

        self.report_service = ReportService(
            exchange_service=self.exchange_service,
            analysis_service=self.analysis_service
        )

        self.alert_service = AlertService(
            exchange_service=self.exchange_service,
            analysis_service=self.analysis_service,
            alert_repo=self.alert_repo,
            enable_ml=False,  # ML scoring disabled for now
            enable_kalman=False  # Kalman filtering disabled for now
        )

        # ============================================================
        # External Integrations
        # ============================================================
        # if self.config.discord:
        #     self.discord_client = DiscordClient(
        #         webhook_url=self.config.discord.webhook_url,
        #         rate_limit=self.config.discord.rate_limit
        #     )

    def cleanup(self):
        """Cleanup resources on shutdown"""
        # Clear cache
        self.cache.clear()

        # Close database connections
        # self.market_repo.close()
        # self.alert_repo.close()

    def __repr__(self) -> str:
        """String representation"""
        return f"Container(config={self.config.app_name}, cache={self.cache})"
