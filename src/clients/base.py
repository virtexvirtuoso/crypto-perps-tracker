"""Base exchange client with common functionality"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import requests
from src.models.market import MarketData, ExchangeType, SymbolData
import time


class BaseExchangeClient(ABC):
    """Abstract base class for all exchange clients

    Provides common functionality for API calls, error handling,
    retry logic, and rate limiting.
    """

    def __init__(
        self,
        timeout: int = 10,
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize base client

        Args:
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts on failure
            retry_delay: Base delay between retries in seconds
        """
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._session = requests.Session()

    @property
    @abstractmethod
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for API endpoints"""
        pass

    @abstractmethod
    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume data

        Returns:
            MarketData object with volume information
        """
        pass

    @abstractmethod
    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific trading symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT', 'BTC-USDT-SWAP')

        Returns:
            SymbolData object with price, volume, funding rate, etc.
            None if symbol not found or error occurs
        """
        pass

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request with retry logic

        Args:
            endpoint: API endpoint (relative to base_url)
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.RequestException: If all retry attempts fail
        """
        url = f"{self.base_url}{endpoint}"
        last_exception = None

        for attempt in range(self.retry_attempts):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    raise

        # Should never reach here, but just in case
        raise last_exception or requests.RequestException("Unknown error")

    def _post(self, endpoint: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request with retry logic

        Args:
            endpoint: API endpoint (relative to base_url)
            json: Optional JSON body
            data: Optional form data

        Returns:
            JSON response as dictionary

        Raises:
            requests.RequestException: If all retry attempts fail
        """
        url = f"{self.base_url}{endpoint}"
        last_exception = None

        for attempt in range(self.retry_attempts):
            try:
                response = self._session.post(
                    url,
                    json=json,
                    data=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    raise

        # Should never reach here, but just in case
        raise last_exception or requests.RequestException("Unknown error")

    def close(self):
        """Close the HTTP session"""
        self._session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __repr__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}(exchange={self.exchange_type.value})"
