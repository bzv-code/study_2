"""
app_section_general_routes.py
------------------------------
HTTP-маршруты главной страницы агрегатора.
Только HTTP-обработка и рендер шаблона — вся логика вынесена
в app_section_general_logic_catalog.py.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.app_core.app_core_logger import logger
from app.app_section_general.app_section_general_logic_catalog import (
    get_sections_catalog,
    get_total_calculators_count,
)


# =============================================================================
# НАСТРОЙКА РОУТЕРА И ШАБЛОНОВ
# =============================================================================
router = APIRouter(
    tags=["Главная"],
    responses={404: {"description": "Не найдено"}},
)

# Директория шаблонов главной страницы
_tpl_dir = Path(__file__).parent / "app_section_general_tpl"
templates = Jinja2Templates(directory=str(_tpl_dir))


# =============================================================================
# ГЛАВНАЯ СТРАНИЦА АГРЕГАТОРА
# =============================================================================
@router.get("/", response_class=HTMLResponse, name="general_index")
async def index_page(request: Request):
    """Главная страница агрегатора: каталог разделов и научный калькулятор."""

    logger.info("Запрошена главная страница")

    sections = get_sections_catalog()

    return templates.TemplateResponse(
        request=request,
        name="app_section_general_tpl_index.html",
        context={
            "sections": sections,
            "total_calculators": get_total_calculators_count(),
        },
    )
