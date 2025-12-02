import logging
from enum import Enum
from rich.logging import RichHandler


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def setup_logging(level: LogLevel = LogLevel.INFO):
    """
    Configures the root logger for the application.

    Args:
        level: The minimum logging level to display.
    """
    log_format = "%(name)s - %(message)s"
    logging.basicConfig(
        level=level.value,
        format=log_format,
        handlers=[RichHandler(rich_tracebacks=True)],
    )
