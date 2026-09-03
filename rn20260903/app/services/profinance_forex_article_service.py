from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import (
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from app.models.article_model import Article
from app.utils.logger_utils import get_logger

logger = get_logger(__name__)


class ProFinanceForexArticleService:
    """
    Сервис получения метатегов и полного текста статьи ProFinance.
    """

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    PAGE_TIMEOUT = 30_000
    REQUEST_DELAY = 1.0
    ARTICLE_SELECTOR = "#article_content"
    CUT_OFF_MARKER = "Подготовлено ProFinance.Ru"

    # =========================================================================
    # PATHS
    # =========================================================================

    PROJECT_ROOT = (
        Path(__file__).resolve()
        .parent.parent.parent
    )

    PROFILE_DIR = (
        PROJECT_ROOT
        / "data"
        / "browser_profiles"
        / "profinance"
    )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def enrich_articles(
        self,
        articles: list[Article],
    ) -> list[Article]:
        if not articles:
            logger.warning("PROFINANCE ARTICLE: no articles to process")
            return articles

        logger.info(
            "PROFINANCE ARTICLE: starting parsing: %s articles",
            len(articles),
        )

        self.PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            context = await self._create_browser_context(playwright)

            try:
                page = await context.new_page()

                for index, article in enumerate(articles, start=1):
                    logger.info(
                        "PROFINANCE ARTICLE: processing %s/%s: %s",
                        index, len(articles), article.url,
                    )

                    # ---------------------------------------------------------
                    # АВТОМАТИЧЕСКИ ПРОСТАВЛЯЕМ AUTHOR
                    # ---------------------------------------------------------
                    if not article.author:
                        article.author = "ProFinance"

                    try:
                        article_data = await self._fetch_article_data(
                            page=page,
                            url=article.url,
                        )

                        if article_data:
                            # Обновляем полный текст
                            if article_data.get("description_full"):
                                article.description_full = article_data["description_full"]

                            # Обновляем title из og:title
                            if article_data.get("title"):
                                article.title = article_data["title"]

                            # Обновляем description из og:description
                            if article_data.get("description"):
                                article.description = article_data["description"]

                            # Парсим дату из article:published_time
                            if article_data.get("published_at_raw"):
                                try:
                                    # Формат на сайте: 10.08.2026 16:05:24
                                    dt = datetime.strptime(
                                        article_data["published_at_raw"],
                                        "%d.%m.%Y %H:%M:%S"
                                    )
                                    article.published_at = dt
                                except ValueError:
                                    logger.warning(
                                        "PROFINANCE ARTICLE: invalid date format: %s",
                                        article_data.get("published_at_raw"),
                                    )

                            logger.info(
                                "PROFINANCE ARTICLE: data received: %s/%s, %s chars",
                                index, len(articles),
                                len(article_data.get("description_full", "")),
                            )
                        else:
                            logger.warning(
                                "PROFINANCE ARTICLE: data not found: %s/%s",
                                index, len(articles),
                            )

                    except Exception:
                        logger.exception(
                            "PROFINANCE ARTICLE: failed to process %s/%s: %s",
                            index, len(articles), article.url,
                        )

                    if index < len(articles):
                        await asyncio.sleep(self.REQUEST_DELAY)

            finally:
                await context.close()

        return articles

    # =========================================================================
    # BROWSER
    # =========================================================================

    async def _create_browser_context(
        self,
        playwright,
    ) -> BrowserContext:
        return await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.PROFILE_DIR),
            headless=False,
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            java_script_enabled=True,
            accept_downloads=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

    # =========================================================================
    # ARTICLE PARSING
    # =========================================================================

    async def _fetch_article_data(
        self,
        page: Page,
        url: str,
    ) -> dict | None:
        """
        Открыть страницу и извлечь meta-теги и полный текст.
        """
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self.PAGE_TIMEOUT,
        )

        if response is not None and response.status >= 400:
            logger.warning(
                "PROFINANCE ARTICLE: HTTP %s received: %s",
                response.status, url,
            )
            return None

        try:
            await page.wait_for_selector(
                self.ARTICLE_SELECTOR,
                state="attached",
                timeout=self.PAGE_TIMEOUT,
            )
        except PlaywrightTimeoutError:
            logger.warning("PROFINANCE ARTICLE: container not found: %s", url)
            return None

        await page.wait_for_timeout(1000)

        meta_data = {}

        # 1. TITLE (из og:title)
        try:
            og_title = await page.locator('meta[property="og:title"]').get_attribute("content")
            if og_title:
                meta_data["title"] = og_title.strip()
        except Exception:
            pass

        # 2. DESCRIPTION (из og:description)
        try:
            og_desc = await page.locator('meta[property="og:description"]').get_attribute("content")
            if og_desc:
                meta_data["description"] = og_desc.strip()
        except Exception:
            pass

        # 3. PUBLISHED_AT (из article:published_time)
        try:
            pub_time = await page.locator('meta[name="article:published_time"]').get_attribute("content")
            if pub_time:
                meta_data["published_at_raw"] = pub_time.strip()
        except Exception:
            pass

        # 4. FULL TEXT
        try:
            description_full = await page.locator(self.ARTICLE_SELECTOR).inner_text()
            cleaned_text = self._clean_text(description_full)
            if cleaned_text:
                meta_data["description_full"] = cleaned_text
        except Exception:
            logger.exception("PROFINANCE ARTICLE: failed to get text: %s", url)

        return meta_data if meta_data else None

    # =========================================================================
    # TEXT CLEANING
    # =========================================================================

    @classmethod
    def _clean_text(cls, text: str) -> str:
        paragraphs = []
        for line in text.splitlines():
            line = " ".join(line.split()).strip()
            if line:
                paragraphs.append(line)

        cleaned_text = "\n".join(paragraphs)

        marker = cls.CUT_OFF_MARKER
        marker_position = cleaned_text.find(marker)
        if marker_position != -1:
            cleaned_text = cleaned_text[:marker_position].rstrip()

        return cleaned_text