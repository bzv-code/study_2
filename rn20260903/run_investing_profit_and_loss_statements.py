from __future__ import annotations

import asyncio

from app.services.investing_profit_and_loss_statements_service import InvestingProfitAndLossStatementsService
from app.services.investing_profit_and_loss_statements_article_service import InvestingProfitAndLossStatementsArticleService
from app.utils.logger_utils import get_logger

from database.investing.duplicate_checker_investing_profit_and_loss_statements_clickhouse import (
    InvestingProfitAndLossStatementsDuplicateChecker,
)
from database.investing.writer_investing_profit_and_loss_statements_clickhouse import (
    InvestingProfitAndLossStatementsClickHouseWriter,
)

logger = get_logger(__name__)


async def run_investing_profit_and_loss_statements() -> None:
    """
    Полный pipeline обработки Investing.com Profit and Loss Statements RSS.
    """

    logger.info("=" * 70)
    logger.info("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE START")
    logger.info("=" * 70)

    # 1. RSS
    logger.info("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: starting RSS service")

    investing_service = InvestingProfitAndLossStatementsService()
    articles = await investing_service.fetch_articles()

    logger.info(
        "INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # 2. DUPLICATE CHECK
    duplicate_checker = InvestingProfitAndLossStatementsDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # 3. NO NEW ARTICLES
    if not new_articles:
        logger.info("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # 4. CURL_CFFI + __NEXT_DATA__
    logger.info("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: starting full description parsing")

    article_service = InvestingProfitAndLossStatementsArticleService()
    enriched_articles = await article_service.enrich_articles(new_articles)

    # 5. FULL DESCRIPTION STATISTICS
    duplicate_checker.update_full_description_statistics(
        stats=stats,
        articles=enriched_articles,
    )

    # 6. CLICKHOUSE
    logger.info("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: starting ClickHouse writer")

    writer = InvestingProfitAndLossStatementsClickHouseWriter()
    inserted_count = writer.write(enriched_articles)

    # 7. INSERT STATISTICS
    duplicate_checker.update_insert_statistics(
        stats=stats,
        inserted_count=inserted_count,
    )

    # 8. FINAL STATISTICS
    stats.log()

    logger.info("=" * 70)
    logger.info("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE FINISHED")
    logger.info("=" * 70)


def main() -> None:
    try:
        asyncio.run(run_investing_profit_and_loss_statements())
    except KeyboardInterrupt:
        logger.warning("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: interrupted by user")
    except Exception:
        logger.exception("INVESTING PROFIT AND LOSS STATEMENTS PIPELINE: fatal error")
        raise


if __name__ == "__main__":
    main()