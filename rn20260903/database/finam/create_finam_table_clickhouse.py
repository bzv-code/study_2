
from __future__ import annotations

from app.utils.logger_utils import get_logger
from database.client_clickhouse import (
    ClickHouseClient,
)


logger = get_logger(__name__)


# =============================================================================
# TABLE
# =============================================================================

TABLE_NAME = "finam_analysis_conews_rsspoint"

MOSCOW_TIMEZONE = "Europe/Moscow"


# =============================================================================
# SQL
# =============================================================================

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME}
(
    source String,

    source_url String,

    title String,

    url String,

    description String DEFAULT '',

    description_full String DEFAULT '',

    author String DEFAULT '',

    published_at DateTime('{MOSCOW_TIMEZONE}')
        DEFAULT toDateTime(
            '1970-01-01 00:00:00',
            '{MOSCOW_TIMEZONE}'
        )
)
ENGINE = MergeTree
ORDER BY
(
    source,
    published_at,
    url
)
"""


# =============================================================================
# CREATE TABLE
# =============================================================================

def create_table() -> None:
    """
    Создать таблицу Finam в ClickHouse.

    published_at хранится с часовым поясом Europe/Moscow.
    """

    logger.info(
        "CLICKHOUSE: creating table: %s",
        TABLE_NAME,
    )

    logger.info(
        "CLICKHOUSE: table timezone: %s",
        MOSCOW_TIMEZONE,
    )

    with ClickHouseClient() as client:

        client.execute(
            CREATE_TABLE_SQL
        )

    logger.info(
        "CLICKHOUSE: table created or already exists: %s",
        TABLE_NAME,
    )


# =============================================================================
# CHECK TABLE
# =============================================================================

def check_table() -> None:
    """
    Проверить структуру таблицы.
    """

    logger.info(
        "CLICKHOUSE: checking table: %s",
        TABLE_NAME,
    )

    query = f"""
    DESCRIBE TABLE {TABLE_NAME}
    """

    with ClickHouseClient() as client:

        result = client.query(
            query
        )

    logger.info(
        "CLICKHOUSE: table structure:"
    )

    for row in result.result_rows:

        logger.info(
            "  %s | %s | default=%s",
            row[0],
            row[1],
            row[3],
        )


# =============================================================================
# CHECK TIMEZONE
# =============================================================================

def check_timezone() -> None:
    """
    Проверить часовой пояс колонки published_at.
    """

    logger.info(
        "CLICKHOUSE: checking published_at timezone"
    )

    query = f"""
    SELECT
        toTypeName(published_at) AS published_type
    FROM {TABLE_NAME}
    LIMIT 1
    """

    with ClickHouseClient() as client:

        result = client.query(
            query
        )

    if not result.result_rows:

        logger.info(
            "CLICKHOUSE: published_at type: DateTime('%s')",
            MOSCOW_TIMEZONE,
        )

        return

    published_type = result.result_rows[0][0]

    logger.info(
        "CLICKHOUSE: published_at type: %s",
        published_type,
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    logger.info(
        "=" * 70
    )

    logger.info(
        "FINAM CLICKHOUSE TABLE CREATION"
    )

    logger.info(
        "=" * 70
    )

    try:

        create_table()

        check_table()

        check_timezone()

    except Exception:

        logger.exception(
            "CLICKHOUSE: failed to create Finam table"
        )

        raise

    logger.info(
        "=" * 70
    )

    logger.info(
        "FINAM CLICKHOUSE TABLE CREATION FINISHED"
    )

    logger.info(
        "=" * 70
    )


if __name__ == "__main__":
    main()

