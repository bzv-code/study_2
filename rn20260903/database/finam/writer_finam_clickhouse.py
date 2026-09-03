
from __future__ import annotations

from typing import Any

from app.models.article_model import Article
from app.utils.logger_utils import get_logger

from database.client_clickhouse import ClickHouseClient


logger = get_logger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

TABLE_NAME = "finam_analysis_conews_rsspoint"

DEFAULT_BATCH_SIZE = 100

COLUMN_NAMES = [
    "source",
    "source_url",
    "title",
    "url",
    "description",
    "description_full",
    "author",
    "published_at",
]


# =============================================================================
# WRITER
# =============================================================================

class FinamClickHouseWriter:
    """
    Writer для записи статей Finam в ClickHouse.

    Важное правило:

        article.description_full

    является обязательным условием загрузки.

    Статья с пустым или отсутствующим description_full
    никогда не должна попасть в ClickHouse.
    """

    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than 0"
            )

        self.batch_size = batch_size

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def write(
        self,
        articles: list[Article],
    ) -> int:
        """
        Записать статьи Finam в ClickHouse.

        Статьи без description_full автоматически исключаются.

        :param articles:
            список объектов Article

        :return:
            количество реально записанных статей
        """

        if not articles:

            logger.warning(
                "CLICKHOUSE FINAM: no articles to write"
            )

            return 0

        logger.info(
            "CLICKHOUSE FINAM: starting write: %s articles",
            len(articles),
        )

        # ---------------------------------------------------------------------
        # FILTER ARTICLES WITHOUT FULL DESCRIPTION
        # ---------------------------------------------------------------------

        valid_articles = [
            article
            for article in articles
            if self._has_description_full(article)
        ]

        skipped_count = (
            len(articles) - len(valid_articles)
        )

        if skipped_count:

            logger.warning(
                "CLICKHOUSE FINAM: skipped %s articles "
                "without description_full",
                skipped_count,
            )

        if not valid_articles:

            logger.warning(
                "CLICKHOUSE FINAM: no valid articles to write"
            )

            return 0

        logger.info(
            "CLICKHOUSE FINAM: valid articles: %s",
            len(valid_articles),
        )

        # ---------------------------------------------------------------------
        # CONVERT ARTICLES TO ROWS
        # ---------------------------------------------------------------------

        rows: list[tuple[Any, ...]] = []

        for article in valid_articles:

            try:

                row = self._article_to_row(
                    article
                )

                rows.append(row)

            except ValueError as exc:

                logger.warning(
                    "CLICKHOUSE FINAM: article skipped: "
                    "%s | reason: %s",
                    article.url,
                    exc,
                )

        if not rows:

            logger.warning(
                "CLICKHOUSE FINAM: no rows to write"
            )

            return 0

        # ---------------------------------------------------------------------
        # INSERT INTO CLICKHOUSE
        # ---------------------------------------------------------------------

        total_written = 0

        with ClickHouseClient() as client:

            for batch_start in range(
                0,
                len(rows),
                self.batch_size,
            ):

                batch = rows[
                    batch_start:
                    batch_start + self.batch_size
                ]

                if not batch:
                    continue

                # ВАЖНО:
                #
                # ClickHouseClient.insert() принимает:
                #
                #     table
                #     rows
                #     column_names
                #
                # а не data.
                #
                client.insert(
                    table=TABLE_NAME,
                    rows=batch,
                    column_names=COLUMN_NAMES,
                )

                batch_size = len(batch)

                total_written += batch_size

                logger.info(
                    "CLICKHOUSE FINAM: batch written: "
                    "%s-%s/%s",
                    total_written - batch_size + 1,
                    total_written,
                    len(rows),
                )

        logger.info(
            "CLICKHOUSE FINAM: write finished: %s articles",
            total_written,
        )

        return total_written

    # =========================================================================
    # VALIDATION
    # =========================================================================

    @staticmethod
    def _has_description_full(
        article: Article,
    ) -> bool:
        """
        Проверить наличие полного описания.

        Пустая строка, None или строка,
        состоящая только из пробелов,
        считаются отсутствующим description_full.
        """

        description_full = (
            article.description_full
        )

        if description_full is None:

            return False

        if not isinstance(
            description_full,
            str,
        ):

            return False

        return bool(
            description_full.strip()
        )

    # =========================================================================
    # CONVERSION
    # =========================================================================

    @classmethod
    def _article_to_row(
        cls,
        article: Article,
    ) -> tuple[Any, ...]:
        """
        Преобразовать Article в строку ClickHouse.

        Порядок полей соответствует COLUMN_NAMES.

        Дополнительно выполняется обязательная
        проверка description_full.

        Если description_full отсутствует,
        ValueError предотвращает формирование
        строки для INSERT.
        """

        # ---------------------------------------------------------------------
        # HARD PROTECTION
        # ---------------------------------------------------------------------

        if not cls._has_description_full(
            article
        ):

            raise ValueError(
                "description_full is empty"
            )

        # ---------------------------------------------------------------------
        # NORMALIZE FULL DESCRIPTION
        # ---------------------------------------------------------------------

        description_full = (
            article.description_full.strip()
        )

        # ---------------------------------------------------------------------
        # ROW
        # ---------------------------------------------------------------------

        return (
            article.source or "",
            article.source_url or "",
            article.title or "",
            article.url or "",
            article.description or "",
            description_full,
            article.author or "",
            article.published_at,
        )

