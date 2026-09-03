import importlib
import inspect
import pkgutil

from app.core.base_service_core import BaseService
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class PluginLoader:
    """
    Автоматический загрузчик сервисов.

    Сканирует app.services и ищет файлы:

        *_service.py

    После импорта ищет классы-наследники BaseService.
    """

    PACKAGE_NAME = "app.services"

    MODULE_SUFFIX = "_service"

    def discover(self) -> list[type[BaseService]]:
        """
        Найти все сервисы.
        """

        services: list[type[BaseService]] = []

        package = importlib.import_module(
            self.PACKAGE_NAME
        )

        logger.info(
            "PLUGIN DISCOVERY: scanning %s",
            self.PACKAGE_NAME,
        )

        for module_info in pkgutil.iter_modules(
            package.__path__
        ):

            module_name = module_info.name

            if not module_name.endswith(
                self.MODULE_SUFFIX
            ):
                continue

            if module_name.startswith("_"):
                continue

            full_module_name = (
                f"{self.PACKAGE_NAME}.{module_name}"
            )

            logger.info(
                "PLUGIN DISCOVERY: importing %s",
                full_module_name,
            )

            module = importlib.import_module(
                full_module_name
            )

            module_services = self._find_services(
                module
            )

            services.extend(module_services)

        logger.info(
            "PLUGIN DISCOVERY: found %s service(s)",
            len(services),
        )

        return services

    @staticmethod
    def _find_services(
        module,
    ) -> list[type[BaseService]]:
        """
        Найти классы BaseService внутри модуля.
        """

        result: list[type[BaseService]] = []

        for _, obj in inspect.getmembers(
            module,
            inspect.isclass,
        ):

            if obj is BaseService:
                continue

            if not issubclass(
                obj,
                BaseService,
            ):
                continue

            if inspect.isabstract(obj):
                continue

            # Не брать импортированный класс
            # из другого модуля.
            if obj.__module__ != module.__name__:
                continue

            result.append(obj)

            logger.info(
                "PLUGIN DISCOVERY: registered %s",
                obj.__name__,
            )

        return result