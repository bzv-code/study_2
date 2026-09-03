from __future__ import annotations

import asyncio

from app.services.profinance_fond_service import ProFinanceFondService
from app.services.profinance_fond_article_service import ProFinanceFondArticleService
from app.utils.logger_utils import get_logger

from database.profinance.duplicate_checker_profinance_fond_clickhouse import (
    ProFinanceFondDuplicateChecker,
)
from database.profinance.writer_profinance_fond_clickhouse import (
    ProFinanceFondClickHouseWriter,
)

logger = get_logger(__name__)

# =============================================================================
# PIPELINE
# =============================================================================

async def run_profinance_fond() -> None:
    """
    Полный pipeline обработки ProFinance Fond RSS.

    Этапы:
        1. Скачать RSS ProFinance Fond.
        2. Распарсить RSS в Article.
        3. Проверить статьи в ClickHouse.
        4. Исключить уже существующие статьи.
        5. Получить description_full через Playwright
           только для новых статей.
        6. Загрузить статьи с description_full в ClickHouse.
        7. Вывести итоговую статистику.
    """

    logger.info("=" * 70)
    logger.info("PROFINANCE FOND PIPELINE START")
    logger.info("=" * 70)

    # =========================================================================
    # 1. RSS
    # =========================================================================

    logger.info("PROFINANCE FOND PIPELINE: starting ProFinance Fond RSS service")

    profinance_service = ProFinanceFondService()
    articles = await profinance_service.fetch_articles()

    logger.info(
        "PROFINANCE FOND PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # =========================================================================
    # 2. DUPLICATE CHECK
    # =========================================================================

    duplicate_checker = ProFinanceFondDuplicateChecker()
    duplicate_result = duplicate_checker.check_new_articles(articles)

    stats = duplicate_result.stats
    new_articles = duplicate_result.new_articles

    logger.info(
        "PROFINANCE FOND PIPELINE: articles requiring full description: %s",
        len(new_articles),
    )

    # =========================================================================
    # 3. NO NEW ARTICLES
    # =========================================================================

    if not new_articles:
        logger.info("PROFINANCE FOND PIPELINE: no new articles")

        stats.set_full_description_statistics(received=0, not_received=0)
        stats.set_inserted(0)
        stats.log()

        logger.info("=" * 70)
        logger.info("PROFINANCE FOND PIPELINE FINISHED")
        logger.info("=" * 70)
        return

    # =========================================================================
    # 4. PLAYWRIGHT
    # =========================================================================

    logger.info("PROFINANCE FOND PIPELINE: starting full description parsing")

    article_service = ProFinanceFondArticleService()
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

    logger.info("PROFINANCE FOND PIPELINE: starting ClickHouse writer")

    writer = ProFinanceFondClickHouseWriter()
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
    logger.info("PROFINANCE FOND PIPELINE FINISHED")
    logger.info("=" * 70)

# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    try:
        asyncio.run(run_profinance_fond())
    except KeyboardInterrupt:
        logger.warning("PROFINANCE FOND PIPELINE: interrupted by user")
    except Exception:
        logger.exception("PROFINANCE FOND PIPELINE: fatal error")
        raise

if __name__ == "__main__":
    main()