"""Logging configuration utilities"""

import logging
import logging.config
import yaml
from pathlib import Path
from typing import Optional


def setup_logging(config_path: Optional[str] = None, log_level: Optional[str] = None):
    """
    Initialize logging from config file

    Args:
        config_path: Path to logging config YAML file
        log_level: Optional override for log level (DEBUG, INFO, WARNING, ERROR)
    """
    if config_path is None:
        # Default to config/logging.yaml
        config_path = Path(__file__).parent.parent.parent / "config" / "logging.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        # Fallback to basic config if file doesn't exist
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.warning(f"Logging config not found at {config_path}, using basic config")
        return

    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Load config
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Apply config
    logging.config.dictConfig(config)

    # Override log level if specified
    if log_level:
        log_level_value = getattr(logging, log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level_value)

    logging.info(f"Logging configured from {config_path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
