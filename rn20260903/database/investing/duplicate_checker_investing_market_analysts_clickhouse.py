from __future__ import annotations

from dataclasses import dataclass

from app.models.article_model import Article
from app.utils.logger_utils import get_logger

from database.client_clickhouse import ClickHouseClient

logger = get_logger(__name__)

TABLE_NAME = "investing_market_analysts"


@dataclass
class InvestingMarketAnalystsPipelineStats:
    rss_articles: int = 0
    already_in_database: int = 0
    need_full_description: int = 0
    full_description_received: int = 0
    full_description_not_received: int = 0
    inserted_into_clickhouse: int = 0

    def set_rss_articles(self, count: int) -> None:
        self.rss_articles = count

    def set_duplicate_statistics(
        self,
        total_articles: int,
        existing_articles: int,
        new_articles: int,
    ) -> None:
        self.rss_articles = total_articles
        self.already_in_database = existing_articles
        self.need_full_description = new_articles

    def set_full_description_statistics(
        self,
        received: int,
        not_received: int,
    ) -> None:
        self.full_description_received = received
        self.full_description_not_received = not_received

    def set_inserted(self, count: int) -> None:
        self.inserted_into_clickhouse = count

    def log(self) -> None:
        logger.info("=" * 70)
        logger.info("INVESTING MARKET ANALYSTS PIPELINE STATISTICS")
        logger.info("=" * 70)

        logger.info("RSS ARTICLES:                 %s", self.rss_articles)
        logger.info("ALREADY IN DATABASE:          %s", self.already_in_database)
        logger.info("NEED FULL DESCRIPTION:        %s", self.need_full_description)
        logger.info("FULL DESCRIPTION RECEIVED:    %s", self.full_description_received)
        logger.info("FULL DESCRIPTION NOT RECEIVED: %s", self.full_description_not_received)
        logger.info("INSERTED INTO CLICKHOUSE:     %s", self.inserted_into_clickhouse)
        logger.info("=" * 70)


@dataclass
class InvestingMarketAnalystsDuplicateCheckResult:
    new_articles: list[Article]
    existing_articles: int
    total_articles: int
    stats: InvestingMarketAnalystsPipelineStats

    @property
    def new_count(self) -> int:
        return len(self.new_articles)


class InvestingMarketAnalystsDuplicateChecker:
    """Проверка существования статей Investing.com Market Analysts в ClickHouse."""

    def check_new_articles(
        self,
        articles: list[Article],
    ) -> InvestingMarketAnalystsDuplicateCheckResult:
        stats = InvestingMarketAnalystsPipelineStats()
        stats.set_rss_articles(len(articles))

        if not articles:
            logger.warning("CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: no articles to check")
            return InvestingMarketAnalystsDuplicateCheckResult(
                new_articles=[],
                existing_articles=0,
                total_articles=0,
                stats=stats,
            )

        logger.info(
            "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: checking %s articles",
            len(articles),
        )

        existing_urls = self._get_existing_urls(articles)

        existing_count = sum(
            1 for article in articles if article.url in existing_urls
        )

        new_articles = [
            article for article in articles if article.url not in existing_urls
        ]

        stats.set_duplicate_statistics(
            total_articles=len(articles),
            existing_articles=existing_count,
            new_articles=len(new_articles),
        )

        logger.info(
            "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: RSS articles: %s",
            len(articles),
        )
        logger.info(
            "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: already in database: %s",
            existing_count,
        )
        logger.info(
            "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: need full description: %s",
            len(new_articles),
        )

        return InvestingMarketAnalystsDuplicateCheckResult(
            new_articles=new_articles,
            existing_articles=existing_count,
            total_articles=len(articles),
            stats=stats,
        )

    def filter_new_articles(self, articles: list[Article]) -> list[Article]:
        result = self.check_new_articles(articles)
        return result.new_articles

    @staticmethod
    def update_full_description_statistics(
        stats: InvestingMarketAnalystsPipelineStats,
        articles: list[Article],
    ) -> None:
        received = sum(
            1 for article in articles
            if article.description_full and article.description_full.strip()
        )
        not_received = len(articles) - received

        stats.set_full_description_statistics(
            received=received,
            not_received=not_received,
        )

        logger.info(
            "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: full description received: %s",
            received,
        )
        logger.info(
            "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: full description not received: %s",
            not_received,
        )

    @staticmethod
    def update_insert_statistics(
        stats: InvestingMarketAnalystsPipelineStats,
        inserted_count: int,
    ) -> None:
        stats.set_inserted(inserted_count)
        logger.info(
            "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: inserted into ClickHouse: %s",
            inserted_count,
        )

    def _get_existing_urls(self, articles: list[Article]) -> set[str]:
        urls = {article.url for article in articles if article.url}

        if not urls:
            return set()

        escaped_urls = [self._escape_sql_string(url) for url in urls]
        urls_sql = ", ".join(f"'{url}'" for url in escaped_urls)

        query = f"""
        SELECT DISTINCT url
        FROM {TABLE_NAME}
        WHERE url IN ({urls_sql})
        """

        logger.debug("CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: checking URLs in database")

        try:
            with ClickHouseClient() as client:
                result = client.query(query)

            if not result or not hasattr(result, 'result_rows') or result.result_rows is None:
                logger.warning(
                    "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: query returned no result"
                )
                return set()

            existing_urls = {row[0] for row in result.result_rows if row and row[0]}
            return existing_urls

        except Exception as e:
            logger.error(
                "CLICKHOUSE INVESTING MARKET ANALYSTS DUPLICATE: failed to query database: %s",
                str(e),
            )
            return set()

    @staticmethod
    def _escape_sql_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")