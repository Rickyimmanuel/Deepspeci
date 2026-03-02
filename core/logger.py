"""
DeepSpeci Centralized Logger
All modules import from here so logging config is applied once.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


_CONFIGURED = False


def get_logger(name: str = "deepspeci") -> logging.Logger:
    """
    Return a logger configured with a consistent format.
    Safe to call multiple times — configuration is applied only once.
    """
    global _CONFIGURED

    logger = logging.getLogger(name)

    if not _CONFIGURED:
        # Attempt to read log level from environment / config
        try:
            from config.loader import get_config
            level_name = get_config().log_level
        except Exception:
            level_name = "INFO"

        level = getattr(logging, level_name.upper(), logging.INFO)
        fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)

        # File handler (logs/ directory relative to project root)
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "deepspeci.log", encoding="utf-8")
        fh.setFormatter(fmt)

        root = logging.getLogger("deepspeci")
        root.setLevel(level)
        root.addHandler(ch)
        root.addHandler(fh)
        root.propagate = False

        _CONFIGURED = True

    return logger
