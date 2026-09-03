
from __future__ import annotations

from typing import Any, Iterable, Sequence

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from database.config_clickhouse import (
    ClickHouseConfig,
    get_clickhouse_config,
)


class ClickHouseClient:
    """
    Общий клиент для работы с ClickHouse.

    Настройки подключения загружаются из .env.
    """

    def __init__(
        self,
        config: ClickHouseConfig | None = None,
    ) -> None:
        self.config = (
            config
            or get_clickhouse_config()
        )

        self._client: Client | None = None

    # =========================================================================
    # CONNECTION
    # =========================================================================

    def connect(self) -> Client:
        """
        Создать подключение к ClickHouse.

        Если подключение уже создано,
        возвращается существующий клиент.
        """

        if self._client is None:
            self._client = (
                clickhouse_connect.get_client(
                    host=self.config.host,
                    port=self.config.port,
                    username=self.config.user,
                    password=self.config.password,
                    database=self.config.database,
                )
            )

        return self._client

    def close(self) -> None:
        """Закрыть подключение к ClickHouse."""

        if self._client is not None:
            self._client.close()
            self._client = None

    # =========================================================================
    # COMMAND
    # =========================================================================

    def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> Any:
        """
        Выполнить SQL-команду.

        Используется для:

        - CREATE TABLE
        - DROP TABLE
        - ALTER TABLE
        - INSERT
        - других команд.
        """

        client = self.connect()

        return client.command(
            query,
            parameters=parameters,
        )

    # =========================================================================
    # SELECT
    # =========================================================================

    def query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> Any:
        """
        Выполнить SELECT-запрос.
        """

        client = self.connect()

        return client.query(
            query,
            parameters=parameters,
        )

    # =========================================================================
    # INSERT
    # =========================================================================

    def insert(
        self,
        table: str,
        rows: Iterable[Sequence[Any]],
        column_names: Sequence[str],
    ) -> Any:
        """
        Вставить строки в ClickHouse.

        :param table:
            Имя таблицы.

        :param rows:
            Последовательность строк.

        :param column_names:
            Названия колонок.
        """

        client = self.connect()

        data = list(rows)

        if not data:
            return None

        return client.insert(
            table=table,
            data=data,
            column_names=list(column_names),
        )

    # =========================================================================
    # PING
    # =========================================================================

    def ping(self) -> bool:
        """
        Проверить соединение с ClickHouse.
        """

        try:
            result = self.query(
                "SELECT 1"
            )

            return bool(
                result.result_rows
                and result.result_rows[0][0] == 1
            )

        except Exception:
            return False

    # =========================================================================
    # CONTEXT MANAGER
    # =========================================================================

    def __enter__(
        self,
    ) -> ClickHouseClient:
        self.connect()

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()

