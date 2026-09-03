from __future__ import annotations

from typing import Any

from app.models.article_model import Article
from app.utils.logger_utils import get_logger

from database.client_clickhouse import ClickHouseClient

logger = get_logger(__name__)

TABLE_NAME = "investing_econom"
DEFAULT_BATCH_SIZE = 100
DEFAULT_AUTHOR = "Investing.com"

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


class InvestingEconomClickHouseWriter:
    """Writer для записи статей Investing.com Econom в ClickHouse."""

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        self.batch_size = batch_size

    def write(self, articles: list[Article]) -> int:
        if not articles:
            logger.warning("CLICKHOUSE INVESTING ECONOM: no articles to write")
            return 0

        logger.info(
            "CLICKHOUSE INVESTING ECONOM: starting write: %s articles",
            len(articles),
        )

        valid_articles = [
            article for article in articles
            if self._has_description_full(article)
        ]

        skipped_count = len(articles) - len(valid_articles)

        if skipped_count:
            logger.warning(
                "CLICKHOUSE INVESTING ECONOM: skipped %s articles without description_full",
                skipped_count,
            )

        if not valid_articles:
            logger.warning("CLICKHOUSE INVESTING ECONOM: no valid articles to write")
            return 0

        logger.info(
            "CLICKHOUSE INVESTING ECONOM: valid articles: %s",
            len(valid_articles),
        )

        rows: list[tuple[Any, ...]] = []
        conversion_errors = 0

        for article in valid_articles:
            try:
                row = self._article_to_row(article)
                rows.append(row)
            except ValueError as exc:
                conversion_errors += 1
                logger.warning(
                    "CLICKHOUSE INVESTING ECONOM: article skipped: %s | reason: %s",
                    article.url, exc,
                )

        if conversion_errors:
            logger.warning(
                "CLICKHOUSE INVESTING ECONOM: %s articles skipped during conversion",
                conversion_errors,
            )

        if not rows:
            logger.warning("CLICKHOUSE INVESTING ECONOM: no rows to write")
            return 0

        total_written = 0

        with ClickHouseClient() as client:
            for batch_start in range(0, len(rows), self.batch_size):
                batch = rows[batch_start:batch_start + self.batch_size]

                if not batch:
                    continue

                client.insert(
                    table=TABLE_NAME,
                    rows=batch,
                    column_names=COLUMN_NAMES,
                )

                batch_size = len(batch)
                total_written += batch_size

                logger.info(
                    "CLICKHOUSE INVESTING ECONOM: batch written: %s-%s/%s",
                    total_written - batch_size + 1,
                    total_written,
                    len(rows),
                )

        logger.info(
            "CLICKHOUSE INVESTING ECONOM: write finished: %s articles",
            total_written,
        )

        return total_written

    @staticmethod
    def _has_description_full(article: Article) -> bool:
        description_full = article.description_full

        if description_full is None:
            return False

        if not isinstance(description_full, str):
            return False

        return bool(description_full.strip())

    @classmethod
    def _article_to_row(cls, article: Article) -> tuple[Any, ...]:
        if not cls._has_description_full(article):
            raise ValueError("description_full is empty")

        description_full = article.description_full.strip()
        author = article.author if article.author else DEFAULT_AUTHOR
        published_at = article.published_at

        return (
            article.source or "",
            article.source_url or "",
            article.title or "",
            article.url or "",
            article.description or "",
            description_full,
            author,
            published_at,
        )