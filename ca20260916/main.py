"""
main.py
-------
Точка входа в приложение "Агрегатор Калькуляторов".
Инициализирует FastAPI, подключает ядро, разделы и запускает локальный сервер.
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Импорт ядра
from app.app_core.app_core_config import config
from app.app_core.app_core_logger import logger

# =========================================================================
# 🚨 ВАЖНО: Импорт роутера главной страницы
# =========================================================================
from app.app_section_general.app_section_general_routes import router as general_router

# =========================================================================
# 🚨 ВАЖНО: Импорт роутера раздела "Налоги"
# =========================================================================
from app.app_section_calc.app_section_calc_taxes.app_section_calc_taxes_routes import router as calc_taxes_router

# =========================================================================
# 🚨 ВАЖНО: Импорт роутера раздела "Инвестиции"
# =========================================================================
from app.app_section_calc.app_section_calc_investment.app_section_calc_investment_routes import router as calc_investment_router


# =============================================================================
# 1. УПРАВЛЕНИЕ ЖИЗНЕННЫМ ЦИКЛОМ (Lifespan)
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Выполняется при запуске и завершении работы приложения."""
    logger.info("=" * 60)
    logger.info(f"🚀 Запуск приложения: {config.name}")
    logger.info(f"📍 Режим: {config.env} | Debug: {config.debug}")
    logger.info(f"🌐 Сервер: http://{config.host}:{config.port}")
    if config.is_development:
        logger.info(f"📖 Swagger UI: http://{config.host}:{config.port}/docs")
    logger.info("=" * 60)

    yield  # Здесь приложение работает и обрабатывает запросы

    logger.info("🛑 Остановка приложения...")


# =============================================================================
# 2. ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
# =============================================================================
app = FastAPI(
    title="Агрегатор Калькуляторов",
    description="Универсальная платформа для финансовых и налоговых расчетов",
    version="0.1.0",
    docs_url="/docs" if config.is_development else None,
    redoc_url="/redoc" if config.is_development else None,
    lifespan=lifespan,
)


# =============================================================================
# 3. ПОДКЛЮЧЕНИЕ РОУТЕРОВ РАЗДЕЛОВ
# =========================================================================
# 🚨 ВАЖНО: Главная страница подключается первой, разделы калькуляторов — следом
app.include_router(general_router)
app.include_router(calc_taxes_router)
app.include_router(calc_investment_router)


# =============================================================================
# 4. ПОДКЛЮЧЕНИЕ СТАТИКИ
# =============================================================================
# Статика главной страницы (app_section_general): /static/app_section_general/...
# 🚨 ВАЖНО: этот mount должен быть подключён РАНЬШЕ общего "/static" ниже,
# иначе более широкий префикс "/static" перехватит запрос первым.
_general_static_dir = config.app_dir / "app_section_general" / "app_section_general_static"
if _general_static_dir.exists():
    app.mount(
        "/static/app_section_general",
        StaticFiles(directory=str(_general_static_dir)),
        name="static_general",
    )

# Статика калькуляторов (app_section_calc_*): /static/app_section_calc_taxes/...
_static_dir = config.app_dir / "app_section_calc"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# =============================================================================
# 5. ТОЧКА ВХОДА
# =============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.is_development,
        log_level="info",
    )