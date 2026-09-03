from __future__ import annotations

import asyncio

from app.services.profinance_forex_service import ProFinanceForexService
from app.services.profinance_forex_article_service import ProFinanceForexArticleService
from app.utils.logger_utils import get_logger

from database.profinance.duplicate_checker_profinance_forex_clickhouse import (
    ProFinanceForexDuplicateChecker,
)
from database.profinance.writer_profinance_forex_clickhouse import (
    ProFinanceForexClickHouseWriter,
)

logger = get_logger(__name__)

# =============================================================================
# PIPELINE
# =============================================================================

async def run_profinance() -> None:
    """
    Полный pipeline обработки ProFinance RSS.

    Этапы:
        1. Скачать RSS ProFinance.
        2. Распарсить RSS в Article.
        3. Проверить статьи в ClickHouse.
        4. Исключить уже существующие статьи.
        5. Получить description_full через Playwright
           только для новых статей.
        6. Загрузить статьи с description_full в ClickHouse.
        7. Вывести итоговую статистику.
    """

    logger.info("=" * 70)
    logger.info("PROFINANCE PIPELINE START")
    logger.info("=" * 70)

    # =========================================================================
    # 1. RSS
    # =========================================================================

    logger.info("PROFINANCE PIPELINE: starting ProFinance RSS service")

    profinance_service = ProFinanceForexService()
    articles = await profinance_service.fetch_articles()

    logger.info(
        "PROFINANCE PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # =========================================================================
    # 2. DUPLICATE CHECK
    # =========================================================================

    duplicate_checker = ProFinanceForexDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "PROFINANCE PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # =========================================================================
    # 3. NO NEW ARTICLES
    # =========================================================================

    if not new_articles:
        logger.info("PROFINANCE PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("PROFINANCE PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # =========================================================================
    # 4. PLAYWRIGHT
    # =========================================================================

    logger.info("PROFINANCE PIPELINE: starting full description parsing")

    article_service = ProFinanceForexArticleService()
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

    logger.info("PROFINANCE PIPELINE: starting ClickHouse writer")

    writer = ProFinanceForexClickHouseWriter()
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
    logger.info("PROFINANCE PIPELINE FINISHED")
    logger.info("=" * 70)

# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    try:
        asyncio.run(run_profinance())
    except KeyboardInterrupt:
        logger.warning("PROFINANCE PIPELINE: interrupted by user")
    except Exception:
        logger.exception("PROFINANCE PIPELINE: fatal error")
        raise

if __name__ == "__main__":
    main()