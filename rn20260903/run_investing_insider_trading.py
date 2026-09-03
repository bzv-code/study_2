from __future__ import annotations

import asyncio

from app.services.investing_insider_trading_service import InvestingInsiderTradingService
from app.services.investing_insider_trading_article_service import InvestingInsiderTradingArticleService
from app.utils.logger_utils import get_logger

from database.investing.duplicate_checker_investing_insider_trading_clickhouse import (
    InvestingInsiderTradingDuplicateChecker,
)
from database.investing.writer_investing_insider_trading_clickhouse import (
    InvestingInsiderTradingClickHouseWriter,
)

logger = get_logger(__name__)


async def run_investing_insider_trading() -> None:
    """
    Полный pipeline обработки Investing.com Insider Trading RSS.
    """

    logger.info("=" * 70)
    logger.info("INVESTING INSIDER TRADING PIPELINE START")
    logger.info("=" * 70)

    # 1. RSS
    logger.info("INVESTING INSIDER TRADING PIPELINE: starting RSS service")

    investing_service = InvestingInsiderTradingService()
    articles = await investing_service.fetch_articles()

    logger.info(
        "INVESTING INSIDER TRADING PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # 2. DUPLICATE CHECK
    duplicate_checker = InvestingInsiderTradingDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "INVESTING INSIDER TRADING PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # 3. NO NEW ARTICLES
    if not new_articles:
        logger.info("INVESTING INSIDER TRADING PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("INVESTING INSIDER TRADING PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # 4. CURL_CFFI + __NEXT_DATA__
    logger.info("INVESTING INSIDER TRADING PIPELINE: starting full description parsing")

    article_service = InvestingInsiderTradingArticleService()
    enriched_articles = await article_service.enrich_articles(new_articles)

    # 5. FULL DESCRIPTION STATISTICS
    duplicate_checker.update_full_description_statistics(
        stats=stats,
        articles=enriched_articles,
    )

    # 6. CLICKHOUSE
    logger.info("INVESTING INSIDER TRADING PIPELINE: starting ClickHouse writer")

    writer = InvestingInsiderTradingClickHouseWriter()
    inserted_count = writer.write(enriched_articles)

    # 7. INSERT STATISTICS
    duplicate_checker.update_insert_statistics(
        stats=stats,
        inserted_count=inserted_count,
    )

    # 8. FINAL STATISTICS
    stats.log()

    logger.info("=" * 70)
    logger.info("INVESTING INSIDER TRADING PIPELINE FINISHED")
    logger.info("=" * 70)


def main() -> None:
    try:
        asyncio.run(run_investing_insider_trading())
    except KeyboardInterrupt:
        logger.warning("INVESTING INSIDER TRADING PIPELINE: interrupted by user")
    except Exception:
        logger.exception("INVESTING INSIDER TRADING PIPELINE: fatal error")
        raise


if __name__ == "__main__":
    main()