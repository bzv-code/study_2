from __future__ import annotations

import asyncio

from app.services.investing_forms_sec_service import InvestingFormsSecService
from app.services.investing_forms_sec_article_service import InvestingFormsSecArticleService
from app.utils.logger_utils import get_logger

from database.investing.duplicate_checker_investing_forms_sec_clickhouse import (
    InvestingFormsSecDuplicateChecker,
)
from database.investing.writer_investing_forms_sec_clickhouse import (
    InvestingFormsSecClickHouseWriter,
)

logger = get_logger(__name__)


async def run_investing_forms_sec() -> None:
    """
    Полный pipeline обработки Investing.com Forms SEC RSS.
    """

    logger.info("=" * 70)
    logger.info("INVESTING FORMS SEC PIPELINE START")
    logger.info("=" * 70)

    # 1. RSS
    logger.info("INVESTING FORMS SEC PIPELINE: starting RSS service")

    investing_service = InvestingFormsSecService()
    articles = await investing_service.fetch_articles()

    logger.info(
        "INVESTING FORMS SEC PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # 2. DUPLICATE CHECK
    duplicate_checker = InvestingFormsSecDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "INVESTING FORMS SEC PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # 3. NO NEW ARTICLES
    if not new_articles:
        logger.info("INVESTING FORMS SEC PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("INVESTING FORMS SEC PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # 4. CURL_CFFI + __NEXT_DATA__
    logger.info("INVESTING FORMS SEC PIPELINE: starting full description parsing")

    article_service = InvestingFormsSecArticleService()
    enriched_articles = await article_service.enrich_articles(new_articles)

    # 5. FULL DESCRIPTION STATISTICS
    duplicate_checker.update_full_description_statistics(
        stats=stats,
        articles=enriched_articles,
    )

    # 6. CLICKHOUSE
    logger.info("INVESTING FORMS SEC PIPELINE: starting ClickHouse writer")

    writer = InvestingFormsSecClickHouseWriter()
    inserted_count = writer.write(enriched_articles)

    # 7. INSERT STATISTICS
    duplicate_checker.update_insert_statistics(
        stats=stats,
        inserted_count=inserted_count,
    )

    # 8. FINAL STATISTICS
    stats.log()

    logger.info("=" * 70)
    logger.info("INVESTING FORMS SEC PIPELINE FINISHED")
    logger.info("=" * 70)


def main() -> None:
    try:
        asyncio.run(run_investing_forms_sec())
    except KeyboardInterrupt:
        logger.warning("INVESTING FORMS SEC PIPELINE: interrupted by user")
    except Exception:
        logger.exception("INVESTING FORMS SEC PIPELINE: fatal error")
        raise


if __name__ == "__main__":
    main()