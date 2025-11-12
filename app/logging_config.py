"""Centralized logging configuration for TALE Pair Finder"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Set up application-wide logging with both console and file handlers.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, uses 'logs/tale.log'
        max_bytes: Maximum size of log file before rotation (default 10MB)
        backup_count: Number of backup files to keep (default 5)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("tale")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (if log file specified or default)
    if log_file is None:
        log_file = "logs/tale.log"

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # Log startup message
    logger.info(f"Logging initialized - Level: {log_level}, File: {log_file}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"tale.{name}")
    return logging.getLogger("tale")
