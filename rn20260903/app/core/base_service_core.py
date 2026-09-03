from abc import ABC, abstractmethod

from app.models.article_model import Article


class BaseService(ABC):
    """
    Базовый класс для RSS/Atom сервисов.

    Каждый сервис должен:
    - иметь name;
    - иметь source_url;
    - реализовать fetch_articles().
    """

    name: str
    source_url: str

    @abstractmethod
    async def fetch_articles(self) -> list[Article]:
        """
        Получить статьи из источника.
        """
        raise NotImplementedError