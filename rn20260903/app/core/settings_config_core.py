from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


class SettingsConfig(BaseSettings):
    """
    Настройки приложения.
    """

    FINAM_RSS_URL: str = (
        "https://www.finam.ru/analysis/conews/rsspoint/"
    )

    PROFINANCE_FOREX_RSS_URL: str = (
        "https://www.profinance.ru/forex.xml"
    )

    PROFINANCE_FOND_RSS_URL: str = (
        "https://www.profinance.ru/fond.xml"
    )

    PROFINANCE_ECONOM_RSS_URL: str = (
        "https://www.profinance.ru/econom.xml"
    )

    INVESTING_STOCK_RSS_URL: str = (
        "https://ru.investing.com/rss/stock.rss"
    )

    INVESTING_FOREX_RSS_URL: str = (
        "https://ru.investing.com/rss/forex.rss"
    )

    INVESTING_COMMODITIES_RSS_URL: str = (
        "https://ru.investing.com/rss/commodities.rss"
    )

    INVESTING_CURRENCY_MARKET_RSS_URL: str = (
        "https://ru.investing.com/rss/news_1.rss"
    )

    INVESTING_FUTURES_AND_COMMODITY_MARKETS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_11.rss"
    )

    INVESTING_STOCK_MARKET_RSS_URL: str = (
        "https://ru.investing.com/rss/news_25.rss"
    )

    INVESTING_ECONOM_RSS_URL: str = (
        "https://ru.investing.com/rss/news_14.rss"
    )

    INVESTING_RUSSIA_AND_NEIGHBORS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_12.rss"
    )

    INVESTING_ECONOMIC_INDICATORS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_95.rss"
    )

    INVESTING_WORLD_NEWS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_287.rss"
    )

    INVESTING_COMPANY_NEWS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_356.rss"
    )

    INVESTING_INSIDER_TRADING_RSS_URL: str = (
        "https://ru.investing.com/rss/news_357.rss"
    )

    INVESTING_MARKET_ANALYSTS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_1061.rss"
    )

    INVESTING_PROFIT_AND_LOSS_STATEMENTS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_1062.rss"
    )

    INVESTING_INCOME_REPORTS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_1063.rss"
    )

    INVESTING_FORMS_SEC_RSS_URL: str = (
        "https://ru.investing.com/rss/news_1064.rss"
    )
    INVESTING_INVESTMENT_IDEAS_RSS_URL: str = (
        "https://ru.investing.com/rss/news_1065.rss"
    )

    REQUEST_TIMEOUT: int = 30

    USER_AGENT: str = "RSSNews/1.0"

    LOG_LEVEL: str = "INFO"

    LOGS_DIR: Path = BASE_DIR / "logs"

    DATA_DIR: Path = BASE_DIR / "data"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = SettingsConfig()


settings.LOGS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

settings.DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)