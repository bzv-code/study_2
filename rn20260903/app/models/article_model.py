
from datetime import datetime

from pydantic import BaseModel, Field


class Article(BaseModel):
    """
    Унифицированная модель статьи.

    Модель используется всеми сервисами RSS-агрегатора.
    """

    source: str = Field(
        ...,
        description="Название источника",
    )

    source_url: str = Field(
        ...,
        description="URL RSS/Atom-источника",
    )

    title: str = Field(
        ...,
        description="Заголовок статьи",
    )

    url: str = Field(
        ...,
        description="URL статьи",
    )

    description: str | None = Field(
        default=None,
        description="Краткое описание статьи из RSS/Atom",
    )

    description_full: str | None = Field(
        default=None,
        description="Полное описание или текст статьи",
    )

    author: str | None = Field(
        default=None,
        description="Автор статьи",
    )

    published_at: datetime | None = Field(
        default=None,
        description="Дата и время публикации статьи",
    )

    fetched_at: datetime = Field(
        default_factory=datetime.now,
        description="Дата и время получения статьи агрегатором",
    )

