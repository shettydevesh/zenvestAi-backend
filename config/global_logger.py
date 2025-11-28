import logging
import sys
from datetime import datetime
# from pathlib import Path
# from logging.handlers import RotatingFileHandler
import json


class JSONFormatter(logging.Formatter):

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "endpoint"):
            log_data["endpoint"] = record.endpoint
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }

    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for future use
        record.levelname = levelname

        return formatted


def setup_logger(
    name: str = "zenvest_ai",
    log_level: str = "INFO",
    log_file: str = "logs/app.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_console: bool = True,
    enable_file: bool = True,
    json_logs: bool = False
) -> logging.Logger:
    """
    Set up and configure logger with console and file handlers

    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        enable_console: Enable console logging
        enable_file: Enable file logging
        json_logs: Use JSON format for file logs

    Returns:
        Configured logger instance
    """

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()  # Clear existing handlers

    # Console Handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        # Use colored formatter for console
        console_format = ColoredFormatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

    # File Handler -> Save logs in a file
    # if enable_file:
    #     # Create logs directory if it doesn't exist
    #     log_path = Path(log_file)
    #     log_path.parent.mkdir(parents=True, exist_ok=True)

    #     file_handler = RotatingFileHandler(
    #         log_file,
    #         maxBytes=max_bytes,
    #         backupCount=backup_count,
    #         encoding='utf-8'
    #     )
    #     file_handler.setLevel(logging.INFO)

    #     # Use JSON formatter or standard formatter for file
    #     if json_logs:
    #         file_format = JSONFormatter()
    #     else:
    #         file_format = logging.Formatter(
    #             fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
    #             datefmt='%Y-%m-%d %H:%M:%S'
    #         )

    #     file_handler.setFormatter(file_format)
    #     logger.addHandler(file_handler)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"zenvest_ai.{name}")
    return logging.getLogger("zenvest_ai")


# Initialize default logger
default_logger = setup_logger(
    name="zenvest_ai",
    log_level="INFO",
    log_file="logs/app.log",
    enable_console=True,
    enable_file=True,
    json_logs=False
)
