import logging
from datetime import datetime

from app.core.settings_config_core import settings


_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(
    name: str,
) -> logging.Logger:

    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)

    logger.setLevel(
        getattr(
            logging,
            settings.LOG_LEVEL.upper(),
            logging.INFO,
        )
    )

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    )

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        console_handler
    )

    log_file = (
        settings.LOGS_DIR
        / f"rss_{datetime.now().strftime('%Y_%m_%d')}.log"
    )

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
    )

    file_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        file_handler
    )

    logger.propagate = False

    _LOGGERS[name] = logger

    return logger