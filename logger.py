"""
Structured logging for the Setup Agent.

Replaces all print() calls with proper logging.
- Console: colored, human-readable
- File: rotating log file at logs/agent.log
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


# ── Log directory ────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "agent.log"


# ── Colors for console output ────────────────────────────────────────────────
class ColorFormatter(logging.Formatter):
    """Adds ANSI colors to console log output."""

    COLORS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[1;31m", # bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Create a named logger with console + file handlers.

    Usage:
        from logger import get_logger
        log = get_logger(__name__)
        log.info("Something happened")
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Console handler (colored) ────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(ColorFormatter(
        fmt="%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S"
    ))

    # ── File handler (rotating, 5MB, keep 3 backups) ────────────────
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger
