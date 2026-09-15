"""
main.py
-------
Точка входа в приложение "Агрегатор Калькуляторов".
Инициализирует FastAPI, подключает ядро, разделы и запускает локальный сервер.
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Импорт ядра
from app.app_core.app_core_config import config
from app.app_core.app_core_logger import logger

# =========================================================================
# 🚨 ВАЖНО: Импорт роутера раздела "Налоги"
# =========================================================================
from app.app_section_calc.app_section_calc_taxes.app_section_calc_taxes_routes import router as calc_taxes_router


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
# 🚨 ВАЖНО: Добавляем маршруты раздела "Налоги" в приложение
app.include_router(calc_taxes_router)


# =============================================================================
# 4. ПОДКЛЮЧЕНИЕ СТАТИКИ
# =============================================================================
_static_dir = config.app_dir / "app_section_calc"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# =============================================================================
# 5. ГЛАВНАЯ СТРАНИЦА
# =============================================================================
@app.get("/", response_class=HTMLResponse, tags=["Главная"])
async def index_page():
    """Главная страница агрегатора с навигацией."""
    logger.info("Запрошена главная страница")

    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Агрегатор Калькуляторов</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
            h1 {{ color: #2563eb; }}
            .status {{ background: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; }}
            .links {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 15px; margin: 20px 0; }}
            .links a {{ display: block; margin: 10px 0; color: #2563eb; text-decoration: none; font-weight: 600; }}
            .links a:hover {{ text-decoration: underline; }}
            code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>🧮 Агрегатор Калькуляторов</h1>
        <div class="status">
            <strong>✅ Ядро запущено успешно!</strong><br>
            Режим: <code>{config.env}</code> | Хост: <code>{config.host}:{config.port}</code> | Debug: <code>{config.debug}</code>
        </div>
        <div class="links">
            <strong>📌 Доступные разделы:</strong>
            <a href="/taxes">📊 Раздел: Налоги (НДС, НДФЛ)</a>
        </div>
        <p>Документация API (Swagger): <a href="/docs">/docs</a></p>
    </body>
    </html>
    """


# =============================================================================
# 6. ТОЧКА ВХОДА
# =============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.is_development,
        log_level="info",
    )