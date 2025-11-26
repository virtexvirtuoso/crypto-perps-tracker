"""Structured logging utility for Crypto Perps Tracker

Provides JSON-formatted logging with context support for better
observability and debugging in production environments.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps
import time


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured logs"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ContextLogger:
    """Logger with context support for structured logging

    Example:
        logger = get_logger(__name__)
        logger.info("Fetching data", exchange="binance", symbol="BTCUSDT")
        logger.error("API failed", error=str(e), status_code=500)
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """Log with extra context data"""
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown)",
            0,
            message,
            (),
            None,
        )
        if kwargs:
            record.extra_data = kwargs
        self._logger.handle(record)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context"""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with context"""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with context"""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback and context"""
        self._logger.exception(message, extra={"extra_data": kwargs} if kwargs else {})


# Module-level logger cache
_loggers: Dict[str, ContextLogger] = {}
_configured = False


def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: Optional[str] = None
) -> None:
    """Configure the logging system

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Whether to use JSON format (True for production)
        log_file: Optional file path to write logs to
    """
    global _configured

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        )

    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> ContextLogger:
    """Get or create a context-aware logger

    Args:
        name: Logger name (typically __name__)

    Returns:
        ContextLogger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Processing started", task="fetch_data")
    """
    global _configured

    # Auto-configure with defaults if not configured
    if not _configured:
        configure_logging(json_format=False)

    if name not in _loggers:
        _loggers[name] = ContextLogger(logging.getLogger(name))

    return _loggers[name]


def log_execution_time(logger: Optional[ContextLogger] = None):
    """Decorator to log function execution time

    Args:
        logger: Optional logger instance. If None, creates one based on function module.

    Example:
        @log_execution_time()
        def fetch_data():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logger or get_logger(func.__module__)
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                _logger.info(
                    f"Function completed: {func.__name__}",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="success"
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                _logger.error(
                    f"Function failed: {func.__name__}",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="error",
                    error=str(e)
                )
                raise

        return wrapper
    return decorator


class PerformanceMetrics:
    """Track and log performance metrics

    Example:
        metrics = PerformanceMetrics("exchange_fetch")
        metrics.record("binance", 0.5, success=True)
        metrics.record("bybit", 0.3, success=True)
        metrics.log_summary()
    """

    def __init__(self, operation: str, logger: Optional[ContextLogger] = None):
        self.operation = operation
        self.logger = logger or get_logger(__name__)
        self.records: list = []

    def record(
        self,
        name: str,
        duration_seconds: float,
        success: bool = True,
        **metadata: Any
    ) -> None:
        """Record a performance measurement"""
        self.records.append({
            "name": name,
            "duration_ms": round(duration_seconds * 1000, 2),
            "success": success,
            **metadata
        })

    def log_summary(self) -> None:
        """Log performance summary"""
        if not self.records:
            return

        successful = [r for r in self.records if r["success"]]
        failed = [r for r in self.records if not r["success"]]

        total_duration = sum(r["duration_ms"] for r in self.records)
        avg_duration = total_duration / len(self.records) if self.records else 0

        self.logger.info(
            f"Performance summary: {self.operation}",
            operation=self.operation,
            total_records=len(self.records),
            successful=len(successful),
            failed=len(failed),
            total_duration_ms=round(total_duration, 2),
            avg_duration_ms=round(avg_duration, 2),
            slowest=max((r["duration_ms"] for r in self.records), default=0),
            fastest=min((r["duration_ms"] for r in self.records), default=0)
        )
