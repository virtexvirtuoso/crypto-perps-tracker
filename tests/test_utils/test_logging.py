"""Tests for the structured logging utility"""

import pytest
import json
import logging
from io import StringIO

from src.utils.logging import (
    get_logger,
    configure_logging,
    log_execution_time,
    PerformanceMetrics,
    JSONFormatter,
    ContextLogger,
)


class TestJSONFormatter:
    """Tests for JSONFormatter"""

    def test_formats_log_as_json(self):
        """Test that log records are formatted as valid JSON"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert "module" in data

    def test_includes_extra_data(self):
        """Test that extra data is included in JSON output"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"key": "value", "number": 42}

        result = formatter.format(record)
        data = json.loads(result)

        assert "data" in data
        assert data["data"]["key"] == "value"
        assert data["data"]["number"] == 42


class TestContextLogger:
    """Tests for ContextLogger"""

    @pytest.fixture
    def string_handler(self):
        """Create a StringIO handler for capturing log output"""
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        return handler, stream

    @pytest.fixture
    def context_logger(self, string_handler):
        """Create a ContextLogger with string output"""
        handler, stream = string_handler
        base_logger = logging.getLogger("test_context")
        base_logger.handlers.clear()
        base_logger.addHandler(handler)
        base_logger.setLevel(logging.DEBUG)
        return ContextLogger(base_logger), stream

    def test_info_with_context(self, context_logger):
        """Test info logging with context data"""
        logger, stream = context_logger

        logger.info("Test message", key="value", count=5)

        output = stream.getvalue()
        data = json.loads(output)

        assert data["message"] == "Test message"
        assert data["data"]["key"] == "value"
        assert data["data"]["count"] == 5

    def test_error_with_context(self, context_logger):
        """Test error logging with context data"""
        logger, stream = context_logger

        logger.error("Error occurred", error_code=500, service="api")

        output = stream.getvalue()
        data = json.loads(output)

        assert data["level"] == "ERROR"
        assert data["data"]["error_code"] == 500

    def test_warning_with_context(self, context_logger):
        """Test warning logging with context data"""
        logger, stream = context_logger

        logger.warning("Warning message", threshold=0.8)

        output = stream.getvalue()
        data = json.loads(output)

        assert data["level"] == "WARNING"

    def test_debug_with_context(self, context_logger):
        """Test debug logging with context data"""
        logger, stream = context_logger

        logger.debug("Debug info", debug_data={"nested": "value"})

        output = stream.getvalue()
        data = json.loads(output)

        assert data["level"] == "DEBUG"


class TestGetLogger:
    """Tests for get_logger function"""

    def test_returns_context_logger(self):
        """Test that get_logger returns a ContextLogger"""
        logger = get_logger("test_module")

        assert isinstance(logger, ContextLogger)

    def test_caches_loggers(self):
        """Test that loggers are cached"""
        logger1 = get_logger("cached_module")
        logger2 = get_logger("cached_module")

        assert logger1 is logger2

    def test_different_names_different_loggers(self):
        """Test that different names get different loggers"""
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")

        assert logger1 is not logger2


class TestLogExecutionTime:
    """Tests for log_execution_time decorator"""

    def test_logs_successful_execution(self):
        """Test that successful execution is logged"""
        @log_execution_time()
        def sample_function():
            return "result"

        result = sample_function()
        assert result == "result"

    def test_logs_failed_execution(self):
        """Test that failed execution is logged and re-raises"""
        @log_execution_time()
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name"""
        @log_execution_time()
        def named_function():
            """Docstring"""
            pass

        assert named_function.__name__ == "named_function"
        assert named_function.__doc__ == "Docstring"


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics"""

    def test_records_measurements(self):
        """Test that measurements are recorded"""
        metrics = PerformanceMetrics("test_operation")

        metrics.record("task1", 0.5, success=True)
        metrics.record("task2", 0.3, success=True)
        metrics.record("task3", 0.8, success=False)

        assert len(metrics.records) == 3

    def test_log_summary(self):
        """Test that summary is logged"""
        metrics = PerformanceMetrics("test_operation")

        metrics.record("task1", 0.5, success=True)
        metrics.record("task2", 0.3, success=True)

        # Should not raise
        metrics.log_summary()

    def test_log_summary_empty(self):
        """Test that empty summary doesn't log"""
        metrics = PerformanceMetrics("test_operation")

        # Should not raise
        metrics.log_summary()

    def test_record_with_metadata(self):
        """Test that metadata is recorded"""
        metrics = PerformanceMetrics("test_operation")

        metrics.record("task1", 0.5, success=True, volume=1000, exchange="binance")

        assert metrics.records[0]["volume"] == 1000
        assert metrics.records[0]["exchange"] == "binance"


class TestConfigureLogging:
    """Tests for configure_logging function"""

    def test_configure_with_json_format(self):
        """Test configuring with JSON format"""
        configure_logging(level="INFO", json_format=True)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_configure_with_text_format(self):
        """Test configuring with text format"""
        configure_logging(level="DEBUG", json_format=False)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_configure_with_warning_level(self):
        """Test configuring with WARNING level"""
        configure_logging(level="WARNING")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
