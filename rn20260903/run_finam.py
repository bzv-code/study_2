
from __future__ import annotations

import asyncio

from app.services.finam_article_service import FinamArticleService
from app.services.finam_service import FinamService
from app.utils.logger_utils import get_logger

from database.finam.duplicate_checker_finam_clickhouse import (
    FinamDuplicateChecker,
)
from database.finam.writer_finam_clickhouse import (
    FinamClickHouseWriter,
)


logger = get_logger(__name__)


# =============================================================================
# PIPELINE
# =============================================================================

async def run_finam() -> None:
    """
    Полный pipeline обработки Finam RSS.

    Этапы:

        1. Скачать RSS Finam.
        2. Распарсить RSS в Article.
        3. Проверить статьи в ClickHouse.
        4. Исключить уже существующие статьи.
        5. Получить description_full через Playwright
           только для новых статей.
        6. Загрузить статьи с description_full в ClickHouse.
        7. Вывести итоговую статистику.
    """

    logger.info("=" * 70)
    logger.info("FINAM PIPELINE START")
    logger.info("=" * 70)

    # =========================================================================
    # 1. RSS
    # =========================================================================

    logger.info(
        "FINAM PIPELINE: starting Finam RSS service"
    )

    finam_service = FinamService()

    articles = await finam_service.fetch_articles()

    logger.info(
        "FINAM PIPELINE: RSS articles received: %s",
        len(articles),
    )

    # =========================================================================
    # 2. DUPLICATE CHECK
    # =========================================================================

    duplicate_checker = FinamDuplicateChecker()

    duplicate_result = (
        duplicate_checker.check_new_articles(
            articles
        )
    )

    stats = duplicate_result.stats

    new_articles = duplicate_result.new_articles

    logger.info(
        "FINAM PIPELINE: articles requiring "
        "full description: %s",
        len(new_articles),
    )

    # =========================================================================
    # 3. NO NEW ARTICLES
    # =========================================================================

    if not new_articles:

        logger.info(
            "FINAM PIPELINE: no new articles"
        )

        stats.set_full_description_statistics(
            received=0,
            not_received=0,
        )

        stats.set_inserted(
            0
        )

        stats.log()

        logger.info("=" * 70)
        logger.info("FINAM PIPELINE FINISHED")
        logger.info("=" * 70)

        return

    # =========================================================================
    # 4. PLAYWRIGHT
    # =========================================================================

    logger.info(
        "FINAM PIPELINE: starting full description parsing"
    )

    article_service = FinamArticleService()

    enriched_articles = (
        await article_service.enrich_articles(
            new_articles
        )
    )

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

    logger.info(
        "FINAM PIPELINE: starting ClickHouse writer"
    )

    writer = FinamClickHouseWriter()

    inserted_count = writer.write(
        enriched_articles
    )

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
    logger.info("FINAM PIPELINE FINISHED")
    logger.info("=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """
    Точка входа для запуска Finam pipeline.
    """

    try:

        asyncio.run(
            run_finam()
        )

    except KeyboardInterrupt:

        logger.warning(
            "FINAM PIPELINE: interrupted by user"
        )

    except Exception:

        logger.exception(
            "FINAM PIPELINE: fatal error"
        )

        raise


if __name__ == "__main__":
    main()

