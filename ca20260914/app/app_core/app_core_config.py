"""
app_core_config.py
------------------
Централизованное хранилище настроек приложения.
Загружает переменные из .env и предоставляет их в виде структурированного объекта.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv


# Загружаем .env из корня проекта (на два уровня выше этого файла)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


@dataclass(frozen=True)
class AppConfig:
    """Неизменяемая конфигурация приложения."""

    # Основные настройки
    env: str = os.getenv("APP_ENV", "development")
    name: str = os.getenv("APP_NAME", "calc_aggregator")
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = os.getenv("APP_DEBUG", "true").lower() == "true"

    # Пути к директориям (относительно корня проекта)
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    app_dir: Path = base_dir / "app"
    section_dir: Path = app_dir / "app_section"
    core_dir: Path = app_dir / "app_core"
    utilities_dir: Path = app_dir / "app_utilities"

    @property
    def is_development(self) -> bool:
        """True, если запущен режим разработки."""
        return self.env.lower() == "development"


# Глобальный объект конфигурации (импортируется во все модули)
config = AppConfig()