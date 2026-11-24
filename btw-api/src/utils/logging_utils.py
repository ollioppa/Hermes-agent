import logging
import os
from src.config import settings


def setup_logging(name: str = "btw_api") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)-22s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Offline example can opt out of file writes; live logging is preserved.
    if os.getenv("BTW_LOG_TO_FILE", "true").lower() != "true":
        return logger
    # File
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    fh = logging.FileHandler(os.path.join(settings.LOG_DIR, f"{name}.log"))
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
