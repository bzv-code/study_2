import json
from pathlib import Path

from app.models.article_model import Article
from app.core.settings_config_core import settings
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class JsonStorage:
    """
    Простое хранилище статей в JSON.
    """

    def __init__(
        self,
        file_path: Path | None = None,
    ) -> None:

        self.file_path = (
            file_path
            or settings.DATA_DIR / "articles.json"
        )

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(
        self,
        articles: list[Article],
    ) -> None:

        data = [
            article.model_dump(mode="json")
            for article in articles
        ]

        with self.file_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=4,
            )

        logger.info(
            "JSON STORAGE: saved %s articles to %s",
            len(articles),
            self.file_path,
        )