"""
app_core_logger.py
------------------
Единая настройка логирования для всего проекта.
Все модули импортируют `logger` отсюда, чтобы логи были единообразными.
"""

import logging
import sys
from app.app_core.app_core_config import config


def _setup_logger() -> logging.Logger:
    """Создает и настраивает корневой логгер проекта."""

    logger = logging.getLogger(config.name)
    logger.setLevel(logging.DEBUG if config.debug else logging.INFO)

    # Очищаем существующие обработчики (защита от дублирования при reload)
    if logger.handlers:
        logger.handlers.clear()

    # Формат вывода: время | уровень | модуль | сообщение
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Вывод в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Отключаем проброс в корневой логгер Python (чтобы не было дублей)
    logger.propagate = False

    return logger


# Глобальный логгер — импортируется как: `from app.app_core.app_core_logger import logger`
logger = _setup_logger()