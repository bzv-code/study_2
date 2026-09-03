from __future__ import annotations

import asyncio

from app.services.investing_russia_and_neighbors_service import InvestingRussiaAndNeighborsService
from app.services.investing_russia_and_neighbors_article_service import InvestingRussiaAndNeighborsArticleService
from app.utils.logger_utils import get_logger

from database.investing.duplicate_checker_investing_russia_and_neighbors_clickhouse import (
    InvestingRussiaAndNeighborsDuplicateChecker,
)
from database.investing.writer_investing_russia_and_neighbors_clickhouse import (
    InvestingRussiaAndNeighborsClickHouseWriter,
)

logger = get_logger(__name__)


async def run_investing_russia_and_neighbors() -> None:
    """
    Полный pipeline обработки Investing.com Russia and Neighbors RSS.
    """

    logger.info("=" * 70)
    logger.info("INVESTING RUSSIA AND NEIGHBORS PIPELINE START")
    logger.info("=" * 70)

    # 1. RSS
    logger.info("INVESTING RUSSIA AND NEIGHBORS PIPELINE: starting RSS service")

    investing_service = InvestingRussiaAndNeighborsService()
    articles = await investing_service.fetch_articles()

    logger.info(
        "INVESTING RUSSIA AND NEIGHBORS PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # 2. DUPLICATE CHECK
    duplicate_checker = InvestingRussiaAndNeighborsDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "INVESTING RUSSIA AND NEIGHBORS PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # 3. NO NEW ARTICLES
    if not new_articles:
        logger.info("INVESTING RUSSIA AND NEIGHBORS PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("INVESTING RUSSIA AND NEIGHBORS PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # 4. CURL_CFFI + __NEXT_DATA__
    logger.info("INVESTING RUSSIA AND NEIGHBORS PIPELINE: starting full description parsing")

    article_service = InvestingRussiaAndNeighborsArticleService()
    enriched_articles = await article_service.enrich_articles(new_articles)

    # 5. FULL DESCRIPTION STATISTICS
    duplicate_checker.update_full_description_statistics(
        stats=stats,
        articles=enriched_articles,
    )

    # 6. CLICKHOUSE
    logger.info("INVESTING RUSSIA AND NEIGHBORS PIPELINE: starting ClickHouse writer")

    writer = InvestingRussiaAndNeighborsClickHouseWriter()
    inserted_count = writer.write(enriched_articles)

    # 7. INSERT STATISTICS
    duplicate_checker.update_insert_statistics(
        stats=stats,
        inserted_count=inserted_count,
    )

    # 8. FINAL STATISTICS
    stats.log()

    logger.info("=" * 70)
    logger.info("INVESTING RUSSIA AND NEIGHBORS PIPELINE FINISHED")
    logger.info("=" * 70)


def main() -> None:
    try:
        asyncio.run(run_investing_russia_and_neighbors())
    except KeyboardInterrupt:
        logger.warning("INVESTING RUSSIA AND NEIGHBORS PIPELINE: interrupted by user")
    except Exception:
        logger.exception("INVESTING RUSSIA AND NEIGHBORS PIPELINE: fatal error")
        raise


if __name__ == "__main__":
    main()