"""
app_section_taxes_routes.py
---------------------------
HTTP-маршруты для раздела "Налоги".
Обрабатывает запросы к калькуляторам НДС и НДФЛ.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.app_core.app_core_logger import logger
from app.app_section.app_section_taxes import (
    app_section_taxes_logic_nds as logic_nds,
    app_section_taxes_logic_ndfl as logic_ndfl
)
from app.app_section.app_section_taxes.app_section_taxes_utils_words import (
    amount_to_words,
    format_rub,
)


# =============================================================================
# НАСТРОЙКА РОУТЕРА И ШАБЛОНОВ
# =============================================================================
router = APIRouter(
    prefix="/taxes",
    tags=["Налоги"],
    responses={404: {"description": "Не найдено"}},
)

# Директория шаблонов для этого раздела
_tpl_dir = Path(__file__).parent / "app_section_taxes_tpl"
templates = Jinja2Templates(directory=str(_tpl_dir))

# Фильтры для форматирования денежных сумм в шаблонах (используются калькулятором НДС)
templates.env.filters["rub"] = format_rub
templates.env.filters["words"] = amount_to_words


# =============================================================================
# ГЛАВНАЯ СТРАНИЦА РАЗДЕЛА "НАЛОГИ"
# =============================================================================
@router.get("/", response_class=HTMLResponse, name="taxes_hub")
async def taxes_hub_page(request: Request):
    logger.info("Запрошена страница раздела Налоги")

    calculators = [
        {
            "name": "Калькулятор НДС",
            "description": "Расчет налога на добавленную стоимость: выделение или начисление",
            "url": "/taxes/nds"
        },
        {
            "name": "Калькулятор НДФЛ",
            "description": "Расчет налога на доходы физических лиц с учетом прогрессивной шкалы",
            "url": "/taxes/ndfl"
        }
    ]

    return templates.TemplateResponse(
        request=request,
        name="app_section_taxes_tpl_hub.html",
        context={"calculators": calculators}
    )


# =============================================================================
# КАЛЬКУЛЯТОР НДС (GET и POST)
# =============================================================================
@router.get("/nds", response_class=HTMLResponse, name="taxes_nds")
async def nds_calculator_page(request: Request):
    logger.info("Запрошена страница калькулятора НДС")

    return templates.TemplateResponse(
        request=request,
        name="app_section_taxes_tpl_calc_nds.html",
        context={
            "result": None,
            "input_action": "add",
            "input_amount": "",
            "input_rate": 20
        }
    )


# ⚠️ ИМЕННО ЭТОТ БЛОК ОТВЕЧАЕТ ЗА ОБРАБОТКУ ФОРМЫ (POST)
@router.post("/nds", response_class=HTMLResponse, name="taxes_nds_process")
async def nds_calculator_process(
    request: Request,
    action: str = Form("add"),
    amount: float = Form(...),
    rate: int = Form(20),
):
    logger.info(f"Расчет НДС (POST): action={action}, сумма={amount}, ставка={rate}")

    try:
        result = logic_nds.calculate_nds(amount, rate, action)
        logger.info(f"Результат расчета НДС: {result}")

        return templates.TemplateResponse(
            request=request,
            name="app_section_taxes_tpl_calc_nds.html",
            context={
                "result": result.to_dict(),
                "input_action": action,
                "input_amount": amount,
                "input_rate": rate
            }
        )
    except ValueError as e:
        logger.error(f"Ошибка валидации НДС: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_taxes_tpl_calc_nds.html",
            context={
                "error": str(e),
                "input_action": action,
                "input_amount": amount,
                "input_rate": rate
            }
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при расчете НДС: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_taxes_tpl_calc_nds.html",
            context={
                "error": "Произошла ошибка при расчете. Проверьте введенные данные.",
                "input_action": action,
                "input_amount": amount,
                "input_rate": rate
            }
        )


# =============================================================================
# КАЛЬКУЛЯТОР НДФЛ (GET и POST)
# =============================================================================
@router.get("/ndfl", response_class=HTMLResponse, name="taxes_ndfl")
async def ndfl_calculator_page(request: Request):
    logger.info("Запрошена страница калькулятора НДФЛ")

    return templates.TemplateResponse(
        request=request,
        name="app_section_taxes_tpl_calc_ndfl.html",
        context={
            "result": None,
            "input_income": "",
            "input_deductions": 0,
            "input_monthly": False
        }
    )


@router.post("/ndfl", response_class=HTMLResponse, name="taxes_ndfl_process")
async def ndfl_calculator_process(
        request: Request,
        mode: str = Form("flat"),
        income: float = Form(...),
        income_type: str = Form("before"),
        rate: int = Form(13),
):
    logger.info(f"Расчет НДФЛ: mode={mode}, доход={income}, тип={income_type}, ставка={rate}")

    try:
        result = logic_ndfl.calculate_ndfl(income, rate, mode, income_type)

        return templates.TemplateResponse(
            request=request,
            name="app_section_taxes_tpl_calc_ndfl.html",
            context={
                "result": result,
                "input_mode": mode,
                "input_income": income,
                "input_income_type": income_type,
                "input_rate": rate
            }
        )
    except ValueError as e:
        logger.error(f"Ошибка валидации НДФЛ: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_taxes_tpl_calc_ndfl.html",
            context={
                "error": str(e),
                "input_mode": mode,
                "input_income": income,
                "input_income_type": income_type,
                "input_rate": rate
            }
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при расчете НДФЛ: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_taxes_tpl_calc_ndfl.html",
            context={
                "error": "Произошла ошибка при расчете. Проверьте введенные данные.",
                "input_mode": mode,
                "input_income": income,
                "input_income_type": income_type,
                "input_rate": rate
            }
        )