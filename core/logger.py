"""
Central logging configuration for meme-beta.5.

All subsystems should acquire loggers through `get_logger` so we emit messages
to a single rotating file instead of spamming the terminal.  This keeps the
dashboard stable while still capturing detailed traces for later analysis.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "meme-beta.log")


def _ensure_log_dir():
    os.makedirs(_LOG_DIR, exist_ok=True)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Return a configured logger that writes to the shared rotating log file.
    """
    _ensure_log_dir()

    logger = logging.getLogger(f"meme_beta.{name}")
    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger
