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


class InvestingStockArticleService:
    """
    Сервис получения полного текста статьи Investing.com Stock.
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

    # Папка для сохранения отладочных HTML
    DEBUG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "debug" / "investing"

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def enrich_articles(
        self,
        articles: list[Article],
    ) -> list[Article]:
        if not articles:
            logger.warning("INVESTING STOCK ARTICLE: no articles to process")
            return articles

        if not CURL_CFFI_AVAILABLE:
            logger.error("INVESTING STOCK ARTICLE: curl_cffi не установлен")
            return articles

        logger.info(
            "INVESTING STOCK ARTICLE: starting parsing: %s articles",
            len(articles),
        )

        self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()

        for index, article in enumerate(articles, start=1):
            logger.info(
                "INVESTING STOCK ARTICLE: processing %s/%s: %s",
                index, len(articles), article.url,
            )

            if not article.author:
                article.author = "Investing.com"

            try:
                # Сохраняем HTML первой статьи для отладки
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
                        "INVESTING STOCK ARTICLE: data received: %s/%s, %s chars",
                        index, len(articles), full_len,
                    )
                else:
                    logger.warning(
                        "INVESTING STOCK ARTICLE: data not found: %s/%s",
                        index, len(articles),
                    )

            except Exception:
                logger.exception(
                    "INVESTING STOCK ARTICLE: failed to process %s/%s: %s",
                    index, len(articles), article.url,
                )

            if index < len(articles):
                await asyncio.sleep(self.REQUEST_DELAY)

        return articles

    # =========================================================================
    # SYNC FETCH
    # =========================================================================

    def _fetch_article_data_sync(self, url: str, save_debug: bool = False) -> dict | None:
        """Синхронный метод для curl_cffi."""
        try:
            with curl_requests.Session(impersonate=self.IMPERSONATE_PROFILE) as session:
                # Pre-flight
                session.get(
                    self.HOME_URL,
                    timeout=self.REQUEST_TIMEOUT,
                    headers=self.BROWSER_HEADERS,
                )

                # Запрос статьи
                response = session.get(
                    url,
                    timeout=self.REQUEST_TIMEOUT,
                    headers={**self.BROWSER_HEADERS, "Referer": self.HOME_URL},
                )

                if response.status_code >= 400:
                    logger.warning(
                        "INVESTING STOCK ARTICLE: HTTP %s for %s",
                        response.status_code, url,
                    )
                    return None

                html = response.text

                logger.info(
                    "INVESTING STOCK ARTICLE: HTML size=%d bytes, status=%d",
                    len(html), response.status_code,
                )

                # Сохраняем для отладки
                if save_debug:
                    debug_file = self.DEBUG_DIR / "first_article.html"
                    debug_file.write_text(html, encoding="utf-8")
                    logger.info(
                        "INVESTING STOCK ARTICLE: debug HTML saved: %s",
                        debug_file,
                    )

                if len(html) < 5000:
                    logger.warning(
                        "INVESTING STOCK ARTICLE: HTML слишком короткий (%d байт) - возможно Cloudflare",
                        len(html),
                    )
                    return None

                return self._parse_html(html)

        except Exception as e:
            logger.exception(
                "INVESTING STOCK ARTICLE: sync fetch failed for %s: %s",
                url, e,
            )
            return None

    # =========================================================================
    # HTML PARSING
    # =========================================================================

    def _parse_html(self, html: str) -> dict | None:
        """
        Извлечь данные статьи из HTML.

        Приоритет:
            1. __NEXT_DATA__ -> различные пути к body
            2. JSON-LD -> articleBody
            3. HTML-парсинг через regex
        """
        result = {}

        # =====================================================================
        # 1. __NEXT_DATA__
        # =====================================================================
        next_data = self._extract_next_data(html)

        if next_data:
            article_json = self._get_article_from_next_data(next_data)

            if article_json:
                body_html = article_json.get("body", "")

                if body_html:
                    cleaned = self._clean_html_body(body_html)
                    if cleaned:
                        # NEW: применяем investing-специфичную очистку
                        cleaned = self._clean_investing_text(cleaned)
                        if cleaned:  # проверяем, что текст не стал пустым
                            result["description_full"] = cleaned
                            result["description"] = self._get_first_paragraph(cleaned)

                # date
                date_str = article_json.get("dateCreated") or article_json.get("datePublished")
                if date_str:
                    parsed_date = self._parse_iso_date(date_str)
                    if parsed_date:
                        result["published_at"] = parsed_date

                # author
                author = article_json.get("author")
                if isinstance(author, dict):
                    result["author"] = author.get("name", "")
                elif isinstance(author, str):
                    result["author"] = author

                logger.debug(
                    "INVESTING STOCK ARTICLE: __NEXT_DATA__ body=%d chars",
                    len(result.get("description_full", "")),
                )

        # =====================================================================
        # 2. JSON-LD (fallback)
        # =====================================================================
        if not result.get("description_full"):
            json_ld = self._extract_json_ld(html)

            if json_ld:
                article_body = json_ld.get("articleBody")
                if article_body:
                    cleaned = self._clean_html_body(article_body)
                    # NEW: применяем investing-специфичную очистку
                    cleaned = self._clean_investing_text(cleaned)
                    if cleaned:
                        result["description_full"] = cleaned
                        result["description"] = self._get_first_paragraph(cleaned)

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
        # 3. HTML-парсинг (fallback, если JSON не сработал)
        # =====================================================================
        if not result.get("description_full"):
            logger.info("INVESTING STOCK ARTICLE: trying HTML fallback parsing")
            html_result = self._parse_html_fallback(html)
            if html_result.get("description_full"):
                # NEW: применяем investing-специфичную очистку
                cleaned = self._clean_investing_text(html_result["description_full"])
                if cleaned:
                    result["description_full"] = cleaned
                    result["description"] = self._get_first_paragraph(cleaned)

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
            # NEW: применяем investing-специфичную очистку заголовка
            title = self._clean_investing_title(title)
            result["title"] = title.strip()

        return result if result else None

    # =========================================================================
    # __NEXT_DATA__ EXTRACTION
    # =========================================================================

    def _extract_next_data(self, html: str) -> dict | None:
        """Извлечь JSON из <script id="__NEXT_DATA__">."""
        match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL
        )

        if not match:
            logger.warning("INVESTING STOCK ARTICLE: __NEXT_DATA__ не найден")
            return None

        try:
            data = json.loads(match.group(1).strip())
            logger.debug(
                "INVESTING STOCK ARTICLE: __NEXT_DATA__ size=%d bytes",
                len(match.group(1)),
            )
            return data
        except json.JSONDecodeError as e:
            logger.warning("INVESTING STOCK ARTICLE: ошибка парсинга __NEXT_DATA__: %s", e)
            return None

    def _get_article_from_next_data(self, next_data: dict) -> dict | None:
        """
        Найти данные статьи в __NEXT_DATA__.

        Пробуем множество путей, так как структура может отличаться.
        """
        page_props = (
            next_data
            .get("props", {})
            .get("pageProps", {})
        )

        # Логируем все ключи для отладки
        logger.info(
            "INVESTING STOCK ARTICLE: pageProps keys: %s",
            list(page_props.keys()),
        )

        # =====================================================================
        # Путь 1: analysisStore._article
        # =====================================================================
        analysis_store = page_props.get("analysisStore")
        if isinstance(analysis_store, dict):
            logger.debug(
                "INVESTING STOCK ARTICLE: analysisStore keys: %s",
                list(analysis_store.keys()),
            )

            article = analysis_store.get("_article")
            if isinstance(article, dict):
                logger.debug(
                    "INVESTING STOCK ARTICLE: _article keys: %s",
                    list(article.keys()),
                )

                if article.get("body"):
                    logger.info("INVESTING STOCK ARTICLE: found via analysisStore._article.body")
                    return article

        # =====================================================================
        # Путь 2: Рекурсивный поиск по всем Store
        # =====================================================================
        for key in page_props.keys():
            val = page_props[key]

            if not isinstance(val, dict):
                continue

            # Ищем _article внутри любого Store
            if "_article" in val and isinstance(val["_article"], dict):
                article = val["_article"]
                if article.get("body"):
                    logger.info(
                        "INVESTING STOCK ARTICLE: found via pageProps.%s._article.body",
                        key,
                    )
                    return article

            # Ищем article внутри любого Store
            if "article" in val and isinstance(val["article"], dict):
                article = val["article"]
                if article.get("body"):
                    logger.info(
                        "INVESTING STOCK ARTICLE: found via pageProps.%s.article.body",
                        key,
                    )
                    return article

        # =====================================================================
        # Путь 3: Прямые ключи в pageProps
        # =====================================================================
        direct_keys = ["article", "_article", "data", "content", "post"]
        for key in direct_keys:
            val = page_props.get(key)
            if isinstance(val, dict) and val.get("body"):
                logger.info(
                    "INVESTING STOCK ARTICLE: found via pageProps.%s.body",
                    key,
                )
                return val

        # =====================================================================
        # Путь 4: Глубокий поиск (до 3 уровней)
        # =====================================================================
        for key1, val1 in page_props.items():
            if not isinstance(val1, dict):
                continue

            for key2, val2 in val1.items():
                if not isinstance(val2, dict):
                    continue

                # Ищем body на 3-м уровне
                if val2.get("body"):
                    logger.info(
                        "INVESTING STOCK ARTICLE: found via pageProps.%s.%s.body",
                        key1, key2,
                    )
                    return val2

                # Ищем _article или article на 3-м уровне
                for key3 in ["_article", "article"]:
                    val3 = val2.get(key3)
                    if isinstance(val3, dict) and val3.get("body"):
                        logger.info(
                            "INVESTING STOCK ARTICLE: found via pageProps.%s.%s.%s.body",
                            key1, key2, key3,
                        )
                        return val3

        logger.warning(
            "INVESTING STOCK ARTICLE: не удалось найти body в __NEXT_DATA__. "
            "Проверьте debug HTML: %s",
            self.DEBUG_DIR / "first_article.html",
        )
        return None

    # =========================================================================
    # JSON-LD EXTRACTION
    # =========================================================================

    def _extract_json_ld(self, html: str) -> dict | None:
        """Извлечь Schema.org JSON-LD."""
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
        """
        Парсить HTML напрямую, если JSON не работает.

        Ищем контейнер статьи и извлекаем текст.
        """
        result = {}

        # Ищем контейнер статьи
        article_html = None

        # Попытка 1: id="article"
        match = re.search(
            r'<div[^>]*id="article"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html,
            re.DOTALL
        )
        if match:
            article_html = match.group(1)
            logger.info("INVESTING STOCK ARTICLE: found article via id='article'")

        # Попытка 2: class с "article" и большой текст
        if not article_html:
            matches = re.findall(
                r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                html,
                re.DOTALL
            )
            for m in matches:
                if len(m) > 1000:
                    article_html = m
                    logger.info("INVESTING STOCK ARTICLE: found article via class with 'article'")
                    break

        if article_html:
            cleaned = self._clean_html_body(article_html)
            if cleaned and len(cleaned) > 200:
                result["description_full"] = cleaned

        return result

    # =========================================================================
    # HTML CLEANING (базовая - не изменена)
    # =========================================================================

    @staticmethod
    def _clean_html_body(html_body: str) -> str:
        """Очистить HTML body статьи."""
        if not html_body:
            return ""

        text = unescape(html_body)

        # Заменяем блочные элементы на переносы строк
        text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</h[1-6]>', '\n', text, flags=re.IGNORECASE)

        # Удаляем все остальные теги
        text = re.sub(r'<[^>]+>', '', text)

        # Чистим пробелы
        lines = []
        for line in text.splitlines():
            line = " ".join(line.split()).strip()
            if line:
                lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def _get_first_paragraph(text: str) -> str:
        """Получить первый непустой абзац."""
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
    # INVESTING-SPECIFIC CLEANING (НОВОЕ - защита от CSS и рекламы)
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

            # Frankmedia (НОВОЕ)
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

        Убирает:
            1. CSS-блоки (длинные строки с фигурными скобками без кириллицы)
            2. Префиксы источников в начале
            3. Рекламу и служебные блоки Investing
            4. Подпись про ИИ-перевод в конце
        """
        if not text:
            return ""

        # =====================================================================
        # 1. Удаляем CSS-блоки
        #    CSS приходит как длинные строки без переносов, содержащие много
        #    фигурных скобок и не содержащие кириллицу
        # =====================================================================
        lines = text.split('\n')
        text_lines = []
        for line in lines:
            # Пропускаем CSS-подобные длинные строки
            # Критерии: длина > 150, много {}, нет кириллицы
            if (len(line) > 150 and
                line.count('{') > 3 and
                not re.search(r'[а-яА-ЯёЁ]', line)):
                continue
            text_lines.append(line)
        text = '\n'.join(text_lines)

        # =====================================================================
        # 2. Убираем префиксы источников (с поддержкой множественных тире)
        # =====================================================================
        source_prefixes = [
            r'^Investing\.com\s*[—\-–]+\s*',
            r'^Frankmedia\s*[—\-–]+\s*',
            r'^Reuters\s*[—\-–]+\s*',
            r'^Bloomberg\s*[—\-–]+\s*',
            r'^MarketWatch\s*[—\-–]+\s*',
            r'^CNBC\s*[—\-–]+\s*',
            r'^Investing\.com\s*-\s*',
            r'^Forbes\s*[—\-–]+\s*',
            r'^WSJ\s*[—\-–]+\s*',
            r'^FT\s*[—\-–]+\s*',
            r'^РБК\s*[—\-–]+\s*',
            r'^ТАСС\s*[—\-–]+\s*',
            r'^Интерфакс\s*[—\-–]+\s*',
        ]

        for pattern in source_prefixes:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)

        # =====================================================================
        # 3. Защита от одиночного разделителя в начале
        # =====================================================================
        text = re.sub(r'^\s*[—\-–]+\s+', '', text, count=1)

        # =====================================================================
        # 4. Удаляем рекламу и служебные блоки Investing
        # =====================================================================
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

        # =====================================================================
        # 5. Убираем подпись про ИИ-перевод в конце текста
        # =====================================================================
        ai_signature_patterns = [
            r'\s*Эта статья была переведена с помощью искусственного интеллекта[^\n]*',
            r'\s*Данная статья была автоматически переведена[^\n]*',
            r'\s*This article was translated using artificial intelligence[^\n]*',
            r'\s*Эта статья была переведена с помощью ИИ[^\n]*',
            r'\s*Материал переведен с помощью ИИ[^\n]*',
        ]

        for pattern in ai_signature_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)

        # =====================================================================
        # 6. Финальная очистка пробелов и пустых строк
        # =====================================================================
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
        """Парсить дату ISO 8601."""
        if not date_str:
            return None

        try:
            clean = re.sub(r'\.\d+', '', date_str)
            clean = re.sub(r'[+-]\d{2}:\d{2}$', '', clean)
            clean = clean.replace('Z', '')

            return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")

        except (ValueError, TypeError) as e:
            logger.warning(
                "INVESTING STOCK ARTICLE: не удалось распарсить дату '%s': %s",
                date_str, e,
            )
            return None