
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# =============================================================================
# PROJECT
# =============================================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class ClickHouseConfig:
    """Настройки подключения к ClickHouse."""

    host: str
    port: int
    user: str
    password: str
    database: str


def get_clickhouse_config() -> ClickHouseConfig:
    """
    Получить настройки ClickHouse из .env.

    Ожидаемые переменные:

        CLICKHOUSE_HOST
        CLICKHOUSE_PORT
        CLICKHOUSE_USER
        CLICKHOUSE_PASSWORD
        CLICKHOUSE_DATABASE
    """

    host = os.getenv(
        "CLICKHOUSE_HOST",
        "",
    ).strip()

    port_raw = os.getenv(
        "CLICKHOUSE_PORT",
        "",
    ).strip()

    user = os.getenv(
        "CLICKHOUSE_USER",
        "",
    ).strip()

    password = os.getenv(
        "CLICKHOUSE_PASSWORD",
        "",
    )

    database = os.getenv(
        "CLICKHOUSE_DATABASE",
        "",
    ).strip()

    if not host:
        raise ValueError(
            "CLICKHOUSE_HOST не задан в .env"
        )

    if not port_raw:
        raise ValueError(
            "CLICKHOUSE_PORT не задан в .env"
        )

    try:
        port = int(port_raw)

    except ValueError as exc:
        raise ValueError(
            "CLICKHOUSE_PORT должен быть целым числом"
        ) from exc

    if port <= 0 or port > 65535:
        raise ValueError(
            "CLICKHOUSE_PORT должен быть в диапазоне 1-65535"
        )

    if not user:
        raise ValueError(
            "CLICKHOUSE_USER не задан в .env"
        )

    if not database:
        raise ValueError(
            "CLICKHOUSE_DATABASE не задан в .env"
        )

    return ClickHouseConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )

