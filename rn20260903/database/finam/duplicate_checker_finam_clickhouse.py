from __future__ import annotations

from dataclasses import dataclass

from app.models.article_model import Article
from app.utils.logger_utils import get_logger

from database.client_clickhouse import ClickHouseClient


logger = get_logger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

TABLE_NAME = "finam_analysis_conews_rsspoint"


# =============================================================================
# STATISTICS
# =============================================================================

@dataclass
class FinamPipelineStats:
    """
    Статистика обработки Finam RSS.

    Используется основным pipeline для отображения
    полной статистики обработки статей.
    """

    rss_articles: int = 0

    already_in_database: int = 0

    need_full_description: int = 0

    full_description_received: int = 0

    full_description_not_received: int = 0

    inserted_into_clickhouse: int = 0

    # =========================================================================
    # CALCULATED
    # =========================================================================

    def set_rss_articles(
        self,
        count: int,
    ) -> None:
        """Установить количество статей, полученных из RSS."""

        self.rss_articles = count

    def set_duplicate_statistics(
        self,
        total_articles: int,
        existing_articles: int,
        new_articles: int,
    ) -> None:
        """
        Записать статистику проверки дубликатов.
        """

        self.rss_articles = total_articles

        self.already_in_database = existing_articles

        self.need_full_description = new_articles

    def set_full_description_statistics(
        self,
        received: int,
        not_received: int,
    ) -> None:
        """
        Записать статистику получения description_full.
        """

        self.full_description_received = received

        self.full_description_not_received = not_received

    def set_inserted(
        self,
        count: int,
    ) -> None:
        """Записать количество загруженных в ClickHouse статей."""

        self.inserted_into_clickhouse = count

    def log(self) -> None:
        """
        Вывести итоговую статистику pipeline.
        """

        logger.info("=" * 70)

        logger.info(
            "FINAM PIPELINE STATISTICS"
        )

        logger.info("=" * 70)

        logger.info(
            "RSS ARTICLES:                 %s",
            self.rss_articles,
        )

        logger.info(
            "ALREADY IN DATABASE:          %s",
            self.already_in_database,
        )

        logger.info(
            "NEED FULL DESCRIPTION:        %s",
            self.need_full_description,
        )

        logger.info(
            "FULL DESCRIPTION RECEIVED:    %s",
            self.full_description_received,
        )

        logger.info(
            "FULL DESCRIPTION NOT RECEIVED: %s",
            self.full_description_not_received,
        )

        logger.info(
            "INSERTED INTO CLICKHOUSE:     %s",
            self.inserted_into_clickhouse,
        )

        logger.info("=" * 70)


# =============================================================================
# RESULT
# =============================================================================

@dataclass
class FinamDuplicateCheckResult:
    """
    Результат проверки статей на наличие в ClickHouse.
    """

    new_articles: list[Article]

    existing_articles: int

    total_articles: int

    stats: FinamPipelineStats

    @property
    def new_count(self) -> int:
        """Количество новых статей."""

        return len(self.new_articles)


# =============================================================================
# DUPLICATE CHECKER
# =============================================================================

class FinamDuplicateChecker:
    """
    Проверка существования статей Finam в ClickHouse.

    Основной идентификатор статьи:
        url

    URL предварительно очищается в RssParser.

    Поэтому одна и та же статья с различными
    query-параметрами не должна создавать дубликаты.

    Проверка выполняется ДО запуска Playwright.

    Это позволяет не открывать в браузере статьи,
    которые уже были успешно загружены в ClickHouse.
    """

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def check_new_articles(
        self,
        articles: list[Article],
    ) -> FinamDuplicateCheckResult:
        """
        Проверить статьи и вернуть новые вместе со статистикой.

        :param articles:
            статьи, полученные из RSS

        :return:
            FinamDuplicateCheckResult
        """

        stats = FinamPipelineStats()

        stats.set_rss_articles(
            len(articles)
        )

        if not articles:

            logger.warning(
                "CLICKHOUSE FINAM DUPLICATE: no articles to check"
            )

            return FinamDuplicateCheckResult(
                new_articles=[],
                existing_articles=0,
                total_articles=0,
                stats=stats,
            )

        logger.info(
            "CLICKHOUSE FINAM DUPLICATE: checking %s articles",
            len(articles),
        )

        existing_urls = self._get_existing_urls(
            articles
        )

        existing_count = sum(
            1
            for article in articles
            if article.url in existing_urls
        )

        new_articles = [
            article
            for article in articles
            if article.url not in existing_urls
        ]

        stats.set_duplicate_statistics(
            total_articles=len(articles),
            existing_articles=existing_count,
            new_articles=len(new_articles),
        )

        logger.info(
            "CLICKHOUSE FINAM DUPLICATE: RSS articles: %s",
            len(articles),
        )

        logger.info(
            "CLICKHOUSE FINAM DUPLICATE: already in database: %s",
            existing_count,
        )

        logger.info(
            "CLICKHOUSE FINAM DUPLICATE: need full description: %s",
            len(new_articles),
        )

        return FinamDuplicateCheckResult(
            new_articles=new_articles,
            existing_articles=existing_count,
            total_articles=len(articles),
            stats=stats,
        )

    # =========================================================================
    # BACKWARD COMPATIBILITY
    # =========================================================================

    def filter_new_articles(
        self,
        articles: list[Article],
    ) -> list[Article]:
        """
        Вернуть только статьи, которых ещё нет в ClickHouse.

        Метод сохранён для совместимости с существующим кодом.

        Для нового pipeline рекомендуется использовать:

            check_new_articles()

        поскольку он дополнительно возвращает статистику.
        """

        result = self.check_new_articles(
            articles
        )

        return result.new_articles

    # =========================================================================
    # FULL DESCRIPTION STATISTICS
    # =========================================================================

    @staticmethod
    def update_full_description_statistics(
        stats: FinamPipelineStats,
        articles: list[Article],
    ) -> None:
        """
        Обновить статистику после работы Playwright.

        Статья считается успешно обработанной,
        если description_full содержит непустой текст.

        :param stats:
            статистика текущего pipeline

        :param articles:
            статьи после enrich_articles()
        """

        received = sum(
            1
            for article in articles
            if article.description_full
            and article.description_full.strip()
        )

        not_received = (
            len(articles) - received
        )

        stats.set_full_description_statistics(
            received=received,
            not_received=not_received,
        )

        logger.info(
            "CLICKHOUSE FINAM DUPLICATE: full description received: %s",
            received,
        )

        logger.info(
            "CLICKHOUSE FINAM DUPLICATE: full description not received: %s",
            not_received,
        )

    # =========================================================================
    # INSERT STATISTICS
    # =========================================================================

    @staticmethod
    def update_insert_statistics(
        stats: FinamPipelineStats,
        inserted_count: int,
    ) -> None:
        """
        Обновить количество реально загруженных статей.
        """

        stats.set_inserted(
            inserted_count
        )

        logger.info(
            "CLICKHOUSE FINAM DUPLICATE: inserted into ClickHouse: %s",
            inserted_count,
        )

    # =========================================================================
    # DATABASE
    # =========================================================================

    def _get_existing_urls(
        self,
        articles: list[Article],
    ) -> set[str]:
        """
        Получить из ClickHouse URL статей,
        которые уже существуют в базе.
        """

        urls = {
            article.url
            for article in articles
            if article.url
        }

        if not urls:
            return set()

        escaped_urls = [
            self._escape_sql_string(url)
            for url in urls
        ]

        urls_sql = ", ".join(
            f"'{url}'"
            for url in escaped_urls
        )

        query = f"""
        SELECT DISTINCT url
        FROM {TABLE_NAME}
        WHERE url IN ({urls_sql})
        """

        logger.debug(
            "CLICKHOUSE FINAM DUPLICATE: checking URLs in database"
        )

        with ClickHouseClient() as client:

            result = client.query(
                query
            )

        existing_urls = {
            row[0]
            for row in result.result_rows
            if row and row[0]
        }

        return existing_urls

    # =========================================================================
    # SQL
    # =========================================================================

    @staticmethod
    def _escape_sql_string(
        value: str,
    ) -> str:
        """
        Безопасно экранировать строковое значение
        для SQL-запроса ClickHouse.
        """

        return (
            value
            .replace(
                "\\",
                "\\\\",
            )
            .replace(
                "'",
                "\\'",
            )
        )