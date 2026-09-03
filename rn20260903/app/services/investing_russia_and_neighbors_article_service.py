from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from app.models.article_model import Article
from app.utils.logger_utils import get_logger

logger = get_logger(__name__)

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    logger.warning("curl_cffi не установлен. Установите: pip install curl_cffi")


class InvestingRussiaAndNeighborsArticleService:
    """
    Сервис получения полного текста статьи Investing.com Russia and Neighbors.
    """

    REQUEST_TIMEOUT = 30
    REQUEST_DELAY = 2.0
    HOME_URL = "https://ru.investing.com/"
    IMPERSONATE_PROFILE = "chrome124"

    BROWSER_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
    }

    DEBUG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "debug" / "investing_russia_and_neighbors"

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def enrich_articles(
        self,
        articles: list[Article],
    ) -> list[Article]:
        if not articles:
            logger.warning("INVESTING RUSSIA AND NEIGHBORS ARTICLE: no articles to process")
            return articles

        if not CURL_CFFI_AVAILABLE:
            logger.error("INVESTING RUSSIA AND NEIGHBORS ARTICLE: curl_cffi не установлен")
            return articles

        logger.info(
            "INVESTING RUSSIA AND NEIGHBORS ARTICLE: starting parsing: %s articles",
            len(articles),
        )

        self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()

        for index, article in enumerate(articles, start=1):
            logger.info(
                "INVESTING RUSSIA AND NEIGHBORS ARTICLE: processing %s/%s: %s",
                index, len(articles), article.url,
            )

            if not article.author:
                article.author = "Investing.com"

            try:
                save_debug = (index == 1)

                article_data = await loop.run_in_executor(
                    None,
                    self._fetch_article_data_sync,
                    article.url,
                    save_debug,
                )

                if article_data:
                    if article_data.get("title"):
                        article.title = article_data["title"]

                    if article_data.get("description"):
                        article.description = article_data["description"]

                    if article_data.get("description_full"):
                        article.description_full = article_data["description_full"]

                    if article_data.get("published_at"):
                        article.published_at = article_data["published_at"]

                    if article_data.get("author"):
                        article.author = article_data["author"]

                    full_len = len(article_data.get("description_full", ""))
                    logger.info(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: data received: %s/%s, %s chars",
                        index, len(articles), full_len,
                    )
                else:
                    logger.warning(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: data not found: %s/%s",
                        index, len(articles),
                    )

            except Exception:
                logger.exception(
                    "INVESTING RUSSIA AND NEIGHBORS ARTICLE: failed to process %s/%s: %s",
                    index, len(articles), article.url,
                )

            if index < len(articles):
                await asyncio.sleep(self.REQUEST_DELAY)

        return articles

    # =========================================================================
    # SYNC FETCH
    # =========================================================================

    def _fetch_article_data_sync(self, url: str, save_debug: bool = False) -> dict | None:
        try:
            with curl_requests.Session(impersonate=self.IMPERSONATE_PROFILE) as session:
                session.get(
                    self.HOME_URL,
                    timeout=self.REQUEST_TIMEOUT,
                    headers=self.BROWSER_HEADERS,
                )

                response = session.get(
                    url,
                    timeout=self.REQUEST_TIMEOUT,
                    headers={**self.BROWSER_HEADERS, "Referer": self.HOME_URL},
                )

                if response.status_code >= 400:
                    logger.warning(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: HTTP %s for %s",
                        response.status_code, url,
                    )
                    return None

                html = response.text

                logger.info(
                    "INVESTING RUSSIA AND NEIGHBORS ARTICLE: HTML size=%d bytes, status=%d",
                    len(html), response.status_code,
                )

                if save_debug:
                    debug_file = self.DEBUG_DIR / "first_article.html"
                    debug_file.write_text(html, encoding="utf-8")
                    logger.info(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: debug HTML saved: %s",
                        debug_file,
                    )

                if len(html) < 5000:
                    logger.warning(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: HTML слишком короткий (%d байт)",
                        len(html),
                    )
                    return None

                return self._parse_html(html)

        except Exception as e:
            logger.exception(
                "INVESTING RUSSIA AND NEIGHBORS ARTICLE: sync fetch failed for %s: %s",
                url, e,
            )
            return None

    # =========================================================================
    # HTML PARSING
    # =========================================================================

    def _parse_html(self, html: str) -> dict | None:
        result = {}

        # =====================================================================
        # __NEXT_DATA__
        # =====================================================================
        next_data = self._extract_next_data(html)

        if next_data:
            article_json = self._get_article_from_next_data(next_data)

            if article_json:
                body_html = article_json.get("body", "")

                if body_html:
                    cleaned = self._clean_html_body(body_html)
                    if cleaned:
                        cleaned = self._clean_investing_text(cleaned)
                        result["description_full"] = cleaned

                        first_para = self._get_first_paragraph(cleaned)
                        if first_para:
                            result["description"] = self._clean_investing_text(first_para)

                date_str = article_json.get("dateCreated") or article_json.get("datePublished")
                if date_str:
                    parsed_date = self._parse_iso_date(date_str)
                    if parsed_date:
                        result["published_at"] = parsed_date

                author = article_json.get("author")
                if isinstance(author, dict):
                    result["author"] = author.get("name", "")
                elif isinstance(author, str):
                    result["author"] = author

        # =====================================================================
        # JSON-LD fallback
        # =====================================================================
        if not result.get("description_full"):
            json_ld = self._extract_json_ld(html)

            if json_ld:
                article_body = json_ld.get("articleBody")
                if article_body:
                    cleaned = self._clean_html_body(article_body)
                    cleaned = self._clean_investing_text(cleaned)
                    result["description_full"] = cleaned

                    first_para = self._get_first_paragraph(cleaned)
                    if first_para:
                        result["description"] = self._clean_investing_text(first_para)

                if not result.get("published_at"):
                    date_str = json_ld.get("dateCreated") or json_ld.get("datePublished")
                    if date_str:
                        parsed_date = self._parse_iso_date(date_str)
                        if parsed_date:
                            result["published_at"] = parsed_date

                if not result.get("author"):
                    author = json_ld.get("author")
                    if isinstance(author, dict):
                        result["author"] = author.get("name", "")
                    elif isinstance(author, str):
                        result["author"] = author

        # =====================================================================
        # HTML fallback
        # =====================================================================
        if not result.get("description_full"):
            logger.info("INVESTING RUSSIA AND NEIGHBORS ARTICLE: trying HTML fallback parsing")
            html_result = self._parse_html_fallback(html)
            if html_result.get("description_full"):
                cleaned = self._clean_investing_text(html_result["description_full"])
                result["description_full"] = cleaned

                first_para = self._get_first_paragraph(cleaned)
                if first_para:
                    result["description"] = self._clean_investing_text(first_para)

        # =====================================================================
        # Title
        # =====================================================================
        og_title_match = re.search(
            r'<meta\s+property="og:title"\s+content="([^"]*)"',
            html
        )
        if og_title_match:
            title = og_title_match.group(1)
            title = re.sub(r'\s*\|\s*Investing\.com\s*$', '', title)
            result["title"] = self._clean_investing_title(title)

        return result if result else None

    # =========================================================================
    # __NEXT_DATA__ EXTRACTION
    # =========================================================================

    def _extract_next_data(self, html: str) -> dict | None:
        match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL
        )

        if not match:
            logger.warning("INVESTING RUSSIA AND NEIGHBORS ARTICLE: __NEXT_DATA__ не найден")
            return None

        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError as e:
            logger.warning("INVESTING RUSSIA AND NEIGHBORS ARTICLE: ошибка парсинга __NEXT_DATA__: %s", e)
            return None

    def _get_article_from_next_data(self, next_data: dict) -> dict | None:
        page_props = (
            next_data
            .get("props", {})
            .get("pageProps", {})
        )

        logger.info(
            "INVESTING RUSSIA AND NEIGHBORS ARTICLE: pageProps keys: %s",
            list(page_props.keys()),
        )

        analysis_store = page_props.get("analysisStore")
        if isinstance(analysis_store, dict):
            logger.debug(
                "INVESTING RUSSIA AND NEIGHBORS ARTICLE: analysisStore keys: %s",
                list(analysis_store.keys()),
            )

            article = analysis_store.get("_article")
            if isinstance(article, dict):
                logger.debug(
                    "INVESTING RUSSIA AND NEIGHBORS ARTICLE: _article keys: %s",
                    list(article.keys()),
                )

                if article.get("body"):
                    logger.info("INVESTING RUSSIA AND NEIGHBORS ARTICLE: found via analysisStore._article.body")
                    return article

        for key in page_props.keys():
            val = page_props[key]

            if not isinstance(val, dict):
                continue

            if "_article" in val and isinstance(val["_article"], dict):
                article = val["_article"]
                if article.get("body"):
                    logger.info(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: found via pageProps.%s._article.body",
                        key,
                    )
                    return article

            if "article" in val and isinstance(val["article"], dict):
                article = val["article"]
                if article.get("body"):
                    logger.info(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: found via pageProps.%s.article.body",
                        key,
                    )
                    return article

        direct_keys = ["article", "_article", "data", "content", "post"]
        for key in direct_keys:
            val = page_props.get(key)
            if isinstance(val, dict) and val.get("body"):
                logger.info(
                    "INVESTING RUSSIA AND NEIGHBORS ARTICLE: found via pageProps.%s.body",
                    key,
                )
                return val

        for key1, val1 in page_props.items():
            if not isinstance(val1, dict):
                continue

            for key2, val2 in val1.items():
                if not isinstance(val2, dict):
                    continue

                if val2.get("body"):
                    logger.info(
                        "INVESTING RUSSIA AND NEIGHBORS ARTICLE: found via pageProps.%s.%s.body",
                        key1, key2,
                    )
                    return val2

                for key3 in ["_article", "article"]:
                    val3 = val2.get(key3)
                    if isinstance(val3, dict) and val3.get("body"):
                        logger.info(
                            "INVESTING RUSSIA AND NEIGHBORS ARTICLE: found via pageProps.%s.%s.%s.body",
                            key1, key2, key3,
                        )
                        return val3

        logger.warning(
            "INVESTING RUSSIA AND NEIGHBORS ARTICLE: не удалось найти body в __NEXT_DATA__. "
            "Проверьте debug HTML: %s",
            self.DEBUG_DIR / "first_article.html",
        )
        return None

    # =========================================================================
    # JSON-LD EXTRACTION
    # =========================================================================

    def _extract_json_ld(self, html: str) -> dict | None:
        match = re.search(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL
        )

        if not match:
            return None

        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None

    # =========================================================================
    # HTML FALLBACK PARSING
    # =========================================================================

    def _parse_html_fallback(self, html: str) -> dict:
        result = {}

        article_html = None

        match = re.search(
            r'<div[^>]*id="article"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html,
            re.DOTALL
        )
        if match:
            article_html = match.group(1)
            logger.info("INVESTING RUSSIA AND NEIGHBORS ARTICLE: found article via id='article'")

        if not article_html:
            matches = re.findall(
                r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                html,
                re.DOTALL
            )
            for m in matches:
                if len(m) > 1000:
                    article_html = m
                    logger.info("INVESTING RUSSIA AND NEIGHBORS ARTICLE: found article via class with 'article'")
                    break

        if article_html:
            cleaned = self._clean_html_body(article_html)
            if cleaned and len(cleaned) > 200:
                result["description_full"] = cleaned

        return result

    # =========================================================================
    # HTML CLEANING (базовая)
    # =========================================================================

    @staticmethod
    def _clean_html_body(html_body: str) -> str:
        if not html_body:
            return ""

        text = unescape(html_body)

        text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</h[1-6]>', '\n', text, flags=re.IGNORECASE)

        text = re.sub(r'<[^>]+>', '', text)

        lines = []
        for line in text.splitlines():
            line = " ".join(line.split()).strip()
            if line:
                lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def _get_first_paragraph(text: str) -> str:
        if not text:
            return ""

        for line in text.splitlines():
            line = line.strip()
            if line and len(line) > 50:
                if len(line) > 500:
                    line = line[:497] + "..."
                return line

        return ""

    # =========================================================================
    # INVESTING-SPECIFIC CLEANING
    # =========================================================================

    @staticmethod
    def _clean_investing_title(title: str) -> str:
        """
        Очистить title от специфичных Investing.com суффиксов.
        """
        if not title:
            return ""

        patterns = [
            # Investing.com
            r'\s+От\s+Investing\.com\s*$',
            r'\s*\|\s*Investing\.com\s*$',
            r'\s*[-–—]\s*Investing\.com\s*$',
            r'\s+by\s+Investing\.com\s*$',

            # Frankmedia
            r'\s+От\s+Frankmedia\s*$',
            r'\s*\|\s*Frankmedia\s*$',
            r'\s*[-–—]\s*Frankmedia\s*$',
            r'\s+by\s+Frankmedia\s*$',
        ]

        for pattern in patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        return title.strip()

    @classmethod
    def _clean_investing_text(cls, text: str) -> str:
        """
        Очистить description/description_full от специфичных Investing.com элементов.
        """
        if not text:
            return ""

        # 1. Удаляем CSS-блоки
        lines = text.split('\n')
        text_lines = []
        for line in lines:
            if (len(line) > 150 and
                line.count('{') > 3 and
                not re.search(r'[а-яА-ЯёЁ]', line)):
                continue
            text_lines.append(line)
        text = '\n'.join(text_lines)

        # 2. Убираем префиксы источников (с поддержкой множественных тире)
        source_prefixes = [
            r'^Investing\.com\s*[—\-–]+\s*',
            r'^Frankmedia\s*[—\-–]+\s*',
            r'^Reuters\s*[—\-–]+\s*',
            r'^Bloomberg\s*[—\-–]+\s*',
            r'^MarketWatch\s*[—\-–]+\s*',
            r'^CNBC\s*[—\-–]+\s*',
            r'^Forbes\s*[—\-–]+\s*',
            r'^WSJ\s*[—\-–]+\s*',
            r'^FT\s*[—\-–]+\s*',
            r'^РБК\s*[—\-–]+\s*',
            r'^ТАСС\s*[—\-–]+\s*',
            r'^Интерфакс\s*[—\-–]+\s*',
        ]

        for pattern in source_prefixes:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)

        # 3. Защита от одиночного разделителя в начале
        text = re.sub(r'^\s*[—\-–]+\s+', '', text, count=1)

        # 4. Удаляем рекламу и служебные блоки Investing
        ad_patterns = [
            # Реклама InvestingPro
            r'\s*Следите за ценами[^.\n]*InvestingPro[^\n]*',
            r'\s*Инструменты InvestingPro[^\n]*',
            r'\s*Скидка \d+% на InvestingPro[^\n]*',

            # Служебные фразы WarrenAI
            r'\s*Try chart analysis with WarrenAI[^\n]*',
            r'\s*Попробуйте анализ графиков с WarrenAI[^\n]*',

            # Служебные метки обновления
            r'\s*Latest update:[^\n]*',
            r'\s*This article is regularly updated[^\n]*',
            r'\s*Эта статья регулярно обновляется[^\n]*',

            # Frankmedia (НОВОЕ) - ссылки на оригинал статьи
            r'\s*Читайте оригинальную статью на сайте Frankmedia[^\n]*',
            r'\s*Оригинал статьи на Frankmedia[^\n]*',
            r'\s*Источник:\s*Frankmedia[^\n]*',
            r'\s*Читайте также на Frankmedia[^\n]*',
            r'\s*Подробнее на сайте Frankmedia[^\n]*',
        ]

        for pattern in ad_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # 5. Убираем подпись про ИИ-перевод
        ai_signature_patterns = [
            r'\s*Эта статья была переведена с помощью искусственного интеллекта[^\n]*',
            r'\s*Данная статья была автоматически переведена[^\n]*',
            r'\s*This article was translated using artificial intelligence[^\n]*',
            r'\s*Эта статья была переведена с помощью ИИ[^\n]*',
            r'\s*Материал переведен с помощью ИИ[^\n]*',
        ]

        for pattern in ai_signature_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)

        # 6. Финальная очистка
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                lines.append(line)

        return "\n".join(lines)

    # =========================================================================
    # DATE PARSING
    # =========================================================================

    @staticmethod
    def _parse_iso_date(date_str: str) -> datetime | None:
        if not date_str:
            return None

        try:
            clean = re.sub(r'\.\d+', '', date_str)
            clean = re.sub(r'[+-]\d{2}:\d{2}$', '', clean)
            clean = clean.replace('Z', '')

            return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")

        except (ValueError, TypeError) as e:
            logger.warning(
                "INVESTING RUSSIA AND NEIGHBORS ARTICLE: не удалось распарсить дату '%s': %s",
                date_str, e,
            )
            return None