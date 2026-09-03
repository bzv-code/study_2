
import httpx

from app.core.base_service_core import BaseService
from app.core.settings_config_core import settings
from app.models.article_model import Article
from app.parsers.rss_parser import RssParser
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class FinamService(BaseService):
    """
    Плагин для Finam.ru.
    """

    name = "Finam"

    source_url = settings.FINAM_RSS_URL

    def __init__(self) -> None:
        self.parser = RssParser()

    async def fetch_articles(self) -> list[Article]:
        """
        Скачать и распарсить RSS Finam.
        """

        logger.info(
            "FINAM: downloading RSS: %s",
            self.source_url,
        )

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": (
                "application/rss+xml, "
                "application/atom+xml, "
                "application/xml, "
                "text/xml, "
                "*/*"
            ),
        }

        async with httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:

            response = await client.get(
                self.source_url
            )

            response.raise_for_status()

        logger.info(
            "FINAM: HTTP status: %s",
            response.status_code,
        )

        logger.info(
            "FINAM: RSS size: %s bytes",
            len(response.content),
        )

        articles = self.parser.parse(
            content=response.content,
            source=self.name,
            source_url=self.source_url,
        )

        logger.info(
            "FINAM: parsed articles: %s",
            len(articles),
        )

        return articles

