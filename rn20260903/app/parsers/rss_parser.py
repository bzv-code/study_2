
from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import feedparser

from app.models.article_model import Article


class RssParser:
    """
    Универсальный RSS/Atom parser.

    Преобразует RSS/Atom feed в список Article.
    """

    def parse(
        self,
        content: bytes,
        source: str,
        source_url: str,
    ) -> list[Article]:
        """
        Распарсить RSS/Atom.

        :param content: содержимое RSS/Atom
        :param source: название источника
        :param source_url: URL RSS/Atom источника
        :return: список статей
        """

        feed = feedparser.parse(content)

        articles: list[Article] = []

        for entry in feed.entries:

            title = entry.get(
                "title",
                "",
            ).strip()

            raw_url = (
                entry.get("link")
                or entry.get("url")
                or ""
            ).strip()

            if not title or not raw_url:
                continue

            url = self._clean_url(
                raw_url
            )

            description = (
                entry.get("summary")
                or entry.get("description")
                or None
            )

            description = self._clean_description(
                description
            )

            author = entry.get("author")

            if author:
                author = author.strip()

            published_at = self._parse_date(
                entry
            )

            article = Article(
                source=source,
                source_url=source_url,
                title=title,
                url=url,
                description=description,
                description_full=None,
                author=author,
                published_at=published_at,
            )

            articles.append(article)

        return articles

    # =========================================================================
    # URL
    # =========================================================================

    @staticmethod
    def _clean_url(
        url: str,
    ) -> str:
        """
        Очистить URL статьи.

        Удаляет query-параметры после '?' и fragment
        после '#'.

        Например:

        https://www.finam.ru/publications/item/news/?utm_source=rss

        превращается в:

        https://www.finam.ru/publications/item/news/
        """

        if not url:
            return url

        try:
            parsed_url = urlsplit(url)

            return urlunsplit(
                (
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    "",
                    "",
                )
            )

        except ValueError:
            return url

    # =========================================================================
    # DESCRIPTION
    # =========================================================================

    @staticmethod
    def _clean_description(
        description: str | None,
    ) -> str | None:
        """
        Очистить краткое описание RSS.

        Для Finam RSS характерен формат:

            Текст краткого описания...
            <a ...>Далее</a>

        Выполняется:

        1. удаление HTML-ссылки и всего текста после первого <a;
        2. удаление пробелов по краям;
        3. удаление завершающего "...".

        Примеры:

            "Индекс МосБиржи вырос на 0,51%..."
            ->
            "Индекс МосБиржи вырос на 0,51%"

            "Рынок продолжает расти..."
            ->
            "Рынок продолжает расти"

        Многоточия внутри текста не изменяются.
        """

        if not description:
            return None

        description = description.strip()

        # ---------------------------------------------------------------------
        # REMOVE "ДАЛЕЕ" LINK
        # ---------------------------------------------------------------------

        description_lower = description.lower()

        anchor_position = description_lower.find(
            "<a"
        )

        if anchor_position != -1:
            description = description[
                :anchor_position
            ].strip()

        # ---------------------------------------------------------------------
        # REMOVE TRAILING THREE DOTS
        # ---------------------------------------------------------------------

        if description.endswith("..."):
            description = description[:-3].rstrip()

        return description or None

    # =========================================================================
    # DATE
    # =========================================================================

    @staticmethod
    def _parse_date(
        entry: Any,
    ) -> datetime | None:
        """
        Извлечь дату публикации.

        Сначала используется уже разобранная
        feedparser дата, затем строковое значение.
        """

        parsed_time = (
            entry.get("published_parsed")
            or entry.get("updated_parsed")
        )

        if parsed_time:

            try:
                return datetime(
                    *parsed_time[:6]
                )

            except (
                TypeError,
                ValueError,
            ):
                pass

        for field in (
            "published",
            "updated",
        ):

            value = entry.get(field)

            if not value:
                continue

            try:
                return parsedate_to_datetime(
                    value
                ).replace(
                    tzinfo=None
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

        return None

