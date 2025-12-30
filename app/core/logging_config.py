"""Centralized logging configuration for the application."""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
import pytz


def setup_logging():
    """Configure application-wide logging with file and console handlers."""

    # Ensure logs directory exists
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)

    # Get Korea timezone
    kst = pytz.timezone('Asia/Seoul')

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Custom formatter to use KST timezone
    class KSTFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            dt = datetime.fromtimestamp(record.created, tz=kst)
            if datefmt:
                return dt.strftime(datefmt)
            else:
                return dt.strftime('%Y-%m-%d %H:%M:%S %Z')

    kst_formatter = KSTFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(kst_formatter)
    root_logger.addHandler(console_handler)

    # Main application log file (INFO level, rotating)
    app_file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    app_file_handler.setLevel(logging.INFO)
    app_file_handler.setFormatter(kst_formatter)
    root_logger.addHandler(app_file_handler)

    # Error log file (ERROR level only, rotating)
    error_file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "error.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(kst_formatter)
    root_logger.addHandler(error_file_handler)

    # Trading log file (for strategy execution logs)
    trading_logger = logging.getLogger('trading')
    trading_file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "trading.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=20,
        encoding='utf-8'
    )
    trading_file_handler.setLevel(logging.INFO)
    trading_file_handler.setFormatter(kst_formatter)
    trading_logger.addHandler(trading_file_handler)

    # API log file (for Bithumb API calls)
    api_logger = logging.getLogger('api')
    api_file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "api.log"),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=10,
        encoding='utf-8'
    )
    api_file_handler.setLevel(logging.DEBUG)
    api_file_handler.setFormatter(kst_formatter)
    api_logger.addHandler(api_file_handler)

    logging.info("Logging system initialized - logs saved to 'logs/' directory")