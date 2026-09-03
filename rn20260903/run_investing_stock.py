from __future__ import annotations

import asyncio

from app.services.investing_stock_service import InvestingStockService
from app.services.investing_stock_article_service import InvestingStockArticleService
from app.utils.logger_utils import get_logger

from database.investing.duplicate_checker_investing_stock_clickhouse import (
    InvestingStockDuplicateChecker,
)
from database.investing.writer_investing_stock_clickhouse import (
    InvestingStockClickHouseWriter,
)

logger = get_logger(__name__)


# =============================================================================
# PIPELINE
# =============================================================================

async def run_investing_stock() -> None:
    """
    Полный pipeline обработки Investing.com Stock RSS.

    Этапы:
        1. Скачать RSS Investing.com Stock.
        2. Распарсить RSS в Article.
        3. Проверить статьи в ClickHouse.
        4. Исключить уже существующие статьи.
        5. Получить description_full через curl_cffi + __NEXT_DATA__
           только для новых статей.
        6. Загрузить статьи с description_full в ClickHouse.
        7. Вывести итоговую статистику.
    """

    logger.info("=" * 70)
    logger.info("INVESTING STOCK PIPELINE START")
    logger.info("=" * 70)

    # =========================================================================
    # 1. RSS
    # =========================================================================

    logger.info("INVESTING STOCK PIPELINE: starting Investing.com Stock RSS service")

    investing_service = InvestingStockService()
    articles = await investing_service.fetch_articles()

    logger.info(
        "INVESTING STOCK PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # =========================================================================
    # 2. DUPLICATE CHECK
    # =========================================================================

    duplicate_checker = InvestingStockDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "INVESTING STOCK PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # =========================================================================
    # 3. NO NEW ARTICLES
    # =========================================================================

    if not new_articles:
        logger.info("INVESTING STOCK PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("INVESTING STOCK PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # =========================================================================
    # 4. CURL_CFFI + __NEXT_DATA__
    # =========================================================================

    logger.info("INVESTING STOCK PIPELINE: starting full description parsing")

    article_service = InvestingStockArticleService()
    enriched_articles = await article_service.enrich_articles(new_articles)

    # =========================================================================
    # 5. FULL DESCRIPTION STATISTICS
    # =========================================================================

    duplicate_checker.update_full_description_statistics(
        stats=stats,
        articles=enriched_articles,
    )

    # =========================================================================
    # 6. CLICKHOUSE
    # =========================================================================

    logger.info("INVESTING STOCK PIPELINE: starting ClickHouse writer")

    writer = InvestingStockClickHouseWriter()
    inserted_count = writer.write(enriched_articles)

    # =========================================================================
    # 7. INSERT STATISTICS
    # =========================================================================

    duplicate_checker.update_insert_statistics(
        stats=stats,
        inserted_count=inserted_count,
    )

    # =========================================================================
    # 8. FINAL STATISTICS
    # =========================================================================

    stats.log()

    logger.info("=" * 70)
    logger.info("INVESTING STOCK PIPELINE FINISHED")
    logger.info("=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    try:
        asyncio.run(run_investing_stock())
    except KeyboardInterrupt:
        logger.warning("INVESTING STOCK PIPELINE: interrupted by user")
    except Exception:
        logger.exception("INVESTING STOCK PIPELINE: fatal error")
        raise


if __name__ == "__main__":
    main()