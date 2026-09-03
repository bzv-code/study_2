from __future__ import annotations

import asyncio

from app.services.investing_commodities_service import InvestingCommoditiesService
from app.services.investing_commodities_article_service import InvestingCommoditiesArticleService
from app.utils.logger_utils import get_logger

from database.investing.duplicate_checker_investing_commodities_clickhouse import (
    InvestingCommoditiesDuplicateChecker,
)
from database.investing.writer_investing_commodities_clickhouse import (
    InvestingCommoditiesClickHouseWriter,
)

logger = get_logger(__name__)


async def run_investing_commodities() -> None:
    """
    Полный pipeline обработки Investing.com Commodities RSS.

    Этапы:
        1. Скачать RSS Investing.com Commodities.
        2. Распарсить RSS в Article.
        3. Проверить статьи в ClickHouse.
        4. Исключить уже существующие статьи.
        5. Получить description_full через curl_cffi + __NEXT_DATA__
           только для новых статей.
        6. Загрузить статьи с description_full в ClickHouse.
        7. Вывести итоговую статистику.
    """

    logger.info("=" * 70)
    logger.info("INVESTING COMMODITIES PIPELINE START")
    logger.info("=" * 70)

    # 1. RSS
    logger.info("INVESTING COMMODITIES PIPELINE: starting Investing.com Commodities RSS service")

    investing_service = InvestingCommoditiesService()
    articles = await investing_service.fetch_articles()

    logger.info(
        "INVESTING COMMODITIES PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # 2. DUPLICATE CHECK
    duplicate_checker = InvestingCommoditiesDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "INVESTING COMMODITIES PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # 3. NO NEW ARTICLES
    if not new_articles:
        logger.info("INVESTING COMMODITIES PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("INVESTING COMMODITIES PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # 4. CURL_CFFI + __NEXT_DATA__
    logger.info("INVESTING COMMODITIES PIPELINE: starting full description parsing")

    article_service = InvestingCommoditiesArticleService()
    enriched_articles = await article_service.enrich_articles(new_articles)

    # 5. FULL DESCRIPTION STATISTICS
    duplicate_checker.update_full_description_statistics(
        stats=stats,
        articles=enriched_articles,
    )

    # 6. CLICKHOUSE
    logger.info("INVESTING COMMODITIES PIPELINE: starting ClickHouse writer")

    writer = InvestingCommoditiesClickHouseWriter()
    inserted_count = writer.write(enriched_articles)

    # 7. INSERT STATISTICS
    duplicate_checker.update_insert_statistics(
        stats=stats,
        inserted_count=inserted_count,
    )

    # 8. FINAL STATISTICS
    stats.log()

    logger.info("=" * 70)
    logger.info("INVESTING COMMODITIES PIPELINE FINISHED")
    logger.info("=" * 70)


def main() -> None:
    try:
        asyncio.run(run_investing_commodities())
    except KeyboardInterrupt:
        logger.warning("INVESTING COMMODITIES PIPELINE: interrupted by user")
    except Exception:
        logger.exception("INVESTING COMMODITIES PIPELINE: fatal error")
        raise


if __name__ == "__main__":
    main()