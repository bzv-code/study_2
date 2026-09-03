import httpx

from app.core.base_service_core import BaseService
from app.core.settings_config_core import settings
from app.models.article_model import Article
from app.parsers.rss_parser import RssParser
from app.utils.logger_utils import get_logger

logger = get_logger(__name__)


class InvestingCommoditiesService(BaseService):
    """
    Плагин для Investing.com - раздел Сырьевые товары (Commodities).

    Источник:
        https://ru.investing.com/rss/commodities.rss
    """

    name = "Investing"

    source_url = settings.INVESTING_COMMODITIES_RSS_URL

    def __init__(self) -> None:
        self.parser = RssParser()

    async def fetch_articles(self) -> list[Article]:
        logger.info(
            "INVESTING COMMODITIES: downloading RSS: %s",
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
            response = await client.get(self.source_url)
            response.raise_for_status()

        logger.info(
            "INVESTING COMMODITIES: HTTP status: %s",
            response.status_code,
        )

        logger.info(
            "INVESTING COMMODITIES: RSS size: %s bytes",
            len(response.content),
        )

        articles = self.parser.parse(
            content=response.content,
            source=self.name,
            source_url=self.source_url,
        )

        logger.info(
            "INVESTING COMMODITIES: parsed articles: %s",
            len(articles),
        )

        return articles