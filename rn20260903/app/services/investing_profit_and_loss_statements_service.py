import httpx

from app.core.base_service_core import BaseService
from app.core.settings_config_core import settings
from app.models.article_model import Article
from app.parsers.rss_parser import RssParser
from app.utils.logger_utils import get_logger

logger = get_logger(__name__)


class InvestingProfitAndLossStatementsService(BaseService):
    """
    Плагин для Investing.com - раздел Отчеты о прибылях и убытках (Profit and Loss Statements).

    Источник:
        https://ru.investing.com/rss/news_1062.rss
    """

    name = "Investing"

    source_url = settings.INVESTING_PROFIT_AND_LOSS_STATEMENTS_RSS_URL

    def __init__(self) -> None:
        self.parser = RssParser()

    async def fetch_articles(self) -> list[Article]:
        logger.info(
            "INVESTING PROFIT AND LOSS STATEMENTS: downloading RSS: %s",
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
            "INVESTING PROFIT AND LOSS STATEMENTS: HTTP status: %s",
            response.status_code,
        )

        logger.info(
            "INVESTING PROFIT AND LOSS STATEMENTS: RSS size: %s bytes",
            len(response.content),
        )

        articles = self.parser.parse(
            content=response.content,
            source=self.name,
            source_url=self.source_url,
        )

        logger.info(
            "INVESTING PROFIT AND LOSS STATEMENTS: parsed articles: %s",
            len(articles),
        )

        return articles