
from __future__ import annotations

import asyncio
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


class FinamArticleService:
    """
    Сервис получения полного текста статьи Finam.

    Использует Playwright и сохранённый браузерный профиль Finam.
    """

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    PAGE_TIMEOUT = 30_000

    REQUEST_DELAY = 1.0

    ARTICLE_SELECTOR = 'div[data-id="text"]'

    # =========================================================================
    # PATHS
    # =========================================================================

    # __file__:
    #
    # app/services/finam_article_service.py
    #
    # parent                -> app/services
    # parent.parent         -> app
    # parent.parent.parent  -> project root
    #
    # Поэтому профиль находится:
    #
    # project/data/browser_profiles/finam

    PROJECT_ROOT = (
        Path(__file__).resolve()
        .parent.parent.parent
    )

    PROFILE_DIR = (
        PROJECT_ROOT
        / "data"
        / "browser_profiles"
        / "finam"
    )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def enrich_articles(
        self,
        articles: list[Article],
    ) -> list[Article]:
        """
        Получить description_full для списка статей.

        Статьи уже должны быть получены из RSS.

        Ошибка одной статьи не останавливает обработку остальных.
        """

        if not articles:
            logger.warning(
                "FINAM ARTICLE: no articles to process"
            )

            return articles

        logger.info(
            "FINAM ARTICLE: starting full description parsing: %s articles",
            len(articles),
        )

        self.PROFILE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            "FINAM ARTICLE: browser profile: %s",
            self.PROFILE_DIR,
        )

        async with async_playwright() as playwright:

            context = await self._create_browser_context(
                playwright
            )

            try:
                page = await context.new_page()

                for index, article in enumerate(
                    articles,
                    start=1,
                ):
                    logger.info(
                        "FINAM ARTICLE: processing %s/%s: %s",
                        index,
                        len(articles),
                        article.url,
                    )

                    try:
                        description_full = (
                            await self._fetch_description_full(
                                page=page,
                                url=article.url,
                            )
                        )

                        if description_full:
                            article.description_full = (
                                description_full
                            )

                            logger.info(
                                "FINAM ARTICLE: full description "
                                "received: %s/%s, %s chars",
                                index,
                                len(articles),
                                len(description_full),
                            )

                        else:
                            logger.warning(
                                "FINAM ARTICLE: full description "
                                "not found: %s/%s",
                                index,
                                len(articles),
                            )

                    except Exception:
                        logger.exception(
                            "FINAM ARTICLE: failed to process article "
                            "%s/%s: %s",
                            index,
                            len(articles),
                            article.url,
                        )

                    if index < len(articles):
                        await asyncio.sleep(
                            self.REQUEST_DELAY
                        )

            finally:
                await context.close()

        logger.info(
            "FINAM ARTICLE: full description parsing finished"
        )

        return articles

    # =========================================================================
    # BROWSER
    # =========================================================================

    async def _create_browser_context(
        self,
        playwright,
    ) -> BrowserContext:
        """
        Создать persistent browser context.

        Используется существующий профиль Finam.
        """

        logger.info(
            "FINAM ARTICLE: launching Chromium"
        )

        logger.info(
            "FINAM ARTICLE: profile exists: %s",
            self.PROFILE_DIR.exists(),
        )

        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.PROFILE_DIR),

            # Используем видимый браузер.
            #
            # Именно в таком режиме ранее удалось получить
            # HTTP 200 от Finam.
            headless=False,

            viewport={
                "width": 1920,
                "height": 1080,
            },

            locale="ru-RU",

            timezone_id="Europe/Moscow",

            java_script_enabled=True,

            accept_downloads=False,

            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        return context

    # =========================================================================
    # ARTICLE
    # =========================================================================

    async def _fetch_description_full(
        self,
        page: Page,
        url: str,
    ) -> str | None:
        """
        Открыть страницу статьи и получить полный текст.

        Из статьи удаляются:

        - рекламные блоки;
        - ссылки, но сохраняется их текст;
        - изображения;
        - SVG;
        - video;
        - iframe;
        - script;
        - style;
        - noscript.

        Абзацы сохраняются.
        """

        logger.debug(
            "FINAM ARTICLE: opening: %s",
            url,
        )

        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self.PAGE_TIMEOUT,
        )

        if response is not None:
            logger.info(
                "FINAM ARTICLE: HTTP status: %s",
                response.status,
            )

        logger.info(
            "FINAM ARTICLE: final URL: %s",
            page.url,
        )

        # ---------------------------------------------------------------------
        # CHECK HTTP STATUS
        # ---------------------------------------------------------------------

        if response is not None and response.status == 403:
            logger.warning(
                "FINAM ARTICLE: HTTP 403 received: %s",
                url,
            )

            return None

        if response is not None and response.status >= 400:
            logger.warning(
                "FINAM ARTICLE: HTTP %s received: %s",
                response.status,
                url,
            )

            return None

        # ---------------------------------------------------------------------
        # WAIT FOR ARTICLE
        # ---------------------------------------------------------------------

        try:
            await page.wait_for_selector(
                self.ARTICLE_SELECTOR,
                state="attached",
                timeout=self.PAGE_TIMEOUT,
            )

        except PlaywrightTimeoutError:
            logger.warning(
                "FINAM ARTICLE: article container not found: %s",
                url,
            )

            return None

        # ---------------------------------------------------------------------
        # WAIT FOR JAVASCRIPT
        # ---------------------------------------------------------------------

        await page.wait_for_timeout(
            1000
        )

        # ---------------------------------------------------------------------
        # EXTRACT ARTICLE
        # ---------------------------------------------------------------------

        description_full = await page.locator(
            self.ARTICLE_SELECTOR
        ).evaluate(
            """
            (container) => {

                // =============================================================
                // REMOVE ADVERTISEMENT BLOCKS
                // =============================================================

                const paragraphs = container.querySelectorAll("p");

                for (const paragraph of paragraphs) {

                    const links = paragraph.querySelectorAll("a");

                    let isAdvertisement = false;

                    for (const link of links) {

                        const href = (
                            link.getAttribute("href") || ""
                        ).toLowerCase();

                        const text = (
                            link.textContent || ""
                        ).toLowerCase();

                        // -----------------------------------------------------
                        // FINAM ADVERTISEMENT URLS
                        // -----------------------------------------------------

                        if (
                            href.includes("broker.finam.ru")
                            || href.includes("/landing/")
                            || href.includes("interest-on-balance")
                        ) {
                            isAdvertisement = true;
                            break;
                        }

                        // -----------------------------------------------------
                        // ADDITIONAL ADVERTISEMENT MARKERS
                        // -----------------------------------------------------

                        if (
                            text.includes("получайте")
                            || text.includes("гарантированным")
                            || text.includes("пассивным доходом")
                            || text.includes("годовых")
                        ) {
                            isAdvertisement = true;
                            break;
                        }
                    }

                    if (isAdvertisement) {
                        paragraph.remove();
                    }
                }

                // =============================================================
                // REMOVE LINKS BUT KEEP THEIR TEXT
                // =============================================================

                const links = container.querySelectorAll("a");

                for (const link of links) {

                    const textNode = document.createTextNode(
                        link.textContent || ""
                    );

                    link.replaceWith(textNode);
                }

                // =============================================================
                // REMOVE IMAGES AND MEDIA
                // =============================================================

                const media = container.querySelectorAll(
                    "img, figure, svg, video, iframe"
                );

                for (const element of media) {
                    element.remove();
                }

                // =============================================================
                // REMOVE TECHNICAL HTML
                // =============================================================

                const unwanted = container.querySelectorAll(
                    "script, style, noscript"
                );

                for (const element of unwanted) {
                    element.remove();
                }

                // =============================================================
                // RETURN TEXT
                // =============================================================

                return container.innerText || "";
            }
            """
        )

        if not description_full:
            return None

        description_full = self._clean_text(
            description_full
        )

        if not description_full:
            return None

        return description_full

    # =========================================================================
    # TEXT CLEANING
    # =========================================================================

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:
        """
        Очистить полный текст статьи.

        Правила:

        1. Удалить пробелы и табуляцию в начале/конце строк.
        2. Сжать последовательности пробелов внутри строки.
        3. Удалить пустые строки.
        4. Сохранить каждый абзац отдельной строкой.
        5. Не оставлять пустую строку между абзацами.
        """

        paragraphs: list[str] = []

        for line in text.splitlines():

            line = " ".join(
                line.split()
            ).strip()

            if not line:
                continue

            paragraphs.append(line)

        return "\n".join(paragraphs)
