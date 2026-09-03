from app.core.plugin_loader_core import PluginLoader
from app.storages.json_storage import JsonStorage
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def main() -> None:

    logger.info("=" * 60)
    logger.info("RSS NEWS")
    logger.info("=" * 60)

    loader = PluginLoader()

    service_classes = loader.discover()

    if not service_classes:
        logger.warning(
            "No services found"
        )
        return

    storage = JsonStorage()

    for service_class in service_classes:

        logger.info(
            "SERVICE: starting %s",
            service_class.__name__,
        )

        service = service_class()

        try:

            articles = await service.fetch_articles()

            logger.info(
                "SERVICE: %s returned %s articles",
                service.name,
                len(articles),
            )

            if articles:
                storage.save(
                    articles
                )

                for article in articles:
                    logger.info(
                        "ARTICLE: [%s] %s",
                        article.source,
                        article.title,
                    )

        except Exception:

            logger.exception(
                "SERVICE ERROR: %s",
                service_class.__name__,
            )

    logger.info("=" * 60)
    logger.info("RSS NEWS FINISHED")
    logger.info("=" * 60)