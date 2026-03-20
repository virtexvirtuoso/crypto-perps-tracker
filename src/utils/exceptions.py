"""Custom exceptions for the tracker"""


class TrackerError(Exception):
    """Base exception for all tracker errors"""
    pass


class APIError(TrackerError):
    """
    API request failed - potentially retryable

    Attributes:
        exchange: Name of the exchange
        status_code: HTTP status code (0 if network error)
        message: Error message
    """
    def __init__(self, exchange: str, status_code: int, message: str):
        self.exchange = exchange
        self.status_code = status_code
        self.message = message
        super().__init__(f"{exchange} API error ({status_code}): {message}")

    @property
    def is_retryable(self) -> bool:
        """Check if this error is retryable"""
        # Rate limits and temporary server errors are retryable
        return self.status_code in (429, 502, 503, 504, 0)

    @property
    def is_auth_error(self) -> bool:
        """Check if this is an authentication error"""
        return self.status_code in (401, 403)


class ValidationError(TrackerError):
    """Data validation failed - permanent error"""
    pass


class DatabaseError(TrackerError):
    """Database operation failed - critical error"""
    pass


class CacheError(TrackerError):
    """Cache operation failed - non-critical error"""
    pass


class ConfigError(TrackerError):
    """Configuration error - permanent error"""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded - temporary error"""
    def __init__(self, exchange: str, retry_after: int = None):
        self.retry_after = retry_after
        message = f"Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(exchange, 429, message)
