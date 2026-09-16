"""
app_section_calc_investment_routes.py
---------------------------------------
HTTP-маршруты для раздела "Инвестиции".
Обрабатывает запросы к калькулятору вкладов (депозитов).
Только HTTP-обработка, валидация и рендер шаблонов — вся бизнес-логика
вынесена в app_section_calc_investment_logic_deposit.py.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.app_core.app_core_logger import logger
from app.app_section_calc.app_section_calc_investment import (
    app_section_calc_investment_logic_deposit as logic_deposit,
)
from app.app_section_calc.app_section_calc_investment import (
    app_section_calc_investment_logic_compound_interest as logic_compound,
)
from app.app_section_calc.app_section_calc_taxes.app_section_calc_taxes_utils_words import (
    amount_to_words,
    format_rub,
)


# =============================================================================
# НАСТРОЙКА РОУТЕРА И ШАБЛОНОВ
# =============================================================================
router = APIRouter(
    prefix="/investment",
    tags=["Инвестиции"],
    responses={404: {"description": "Не найдено"}},
)

# Директория шаблонов для этого раздела
_tpl_dir = Path(__file__).parent / "app_section_calc_investment_tpl"
templates = Jinja2Templates(directory=str(_tpl_dir))

# Фильтры для форматирования денежных сумм в шаблонах
templates.env.filters["rub"] = format_rub
templates.env.filters["words"] = amount_to_words


# =============================================================================
# ГЛАВНАЯ СТРАНИЦА РАЗДЕЛА "ИНВЕСТИЦИИ"
# =============================================================================
@router.get("/", response_class=HTMLResponse, name="investment_hub")
async def investment_hub_page(request: Request):
    logger.info("Запрошена страница раздела Инвестиции")

    calculators = [
        {
            "name": "Калькулятор вкладов",
            "description": "Расчёт доходности вклада с учётом капитализации, пополнений, снятий и налога",
            "url": "/investment/deposit",
        },
        {
            "name": "Калькулятор сложного процента",
            "description": "Доходность инвестиций с реинвестированием и регулярными пополнениями. Умеет также подбирать ставку, стартовый капитал, срок или размер взносов под целевую сумму",
            "url": "/investment/compound-interest",
        },
    ]

    return templates.TemplateResponse(
        request=request,
        name="app_section_calc_investment_tpl_hub.html",
        context={"calculators": calculators},
    )


# =============================================================================
# КАЛЬКУЛЯТОР ВКЛАДОВ (GET и POST)
# =============================================================================
def _default_context() -> dict:
    """Значения формы по умолчанию для первого открытия страницы."""
    today = date.today()
    return {
        "result": None,
        "error": None,
        "input_amount": 100_000,
        "input_period": 12,
        "input_period_unit": "months",
        "input_start_date": today.strftime("%Y-%m-%d"),
        "input_rate": 18,
        "input_capitalization": False,
        "input_payout_frequency": "monthly",
        "input_replenishment_enabled": False,
        "input_replenishment_amount": "",
        "input_replenishment_frequency": "monthly",
        "input_withdrawal_enabled": False,
        "input_withdrawal_amount": "",
        "input_withdrawal_frequency": "monthly",
        "input_consider_inflation": False,
        "input_inflation_rate": 7,
        "input_key_rate": 14,
        "payout_frequency_options": logic_deposit.get_payout_frequency_options(),
    }


@router.get("/deposit", response_class=HTMLResponse, name="investment_deposit")
async def deposit_calculator_page(request: Request):
    logger.info("Запрошена страница калькулятора вкладов")

    return templates.TemplateResponse(
        request=request,
        name="app_section_calc_investment_tpl_deposit.html",
        context=_default_context(),
    )


@router.post("/deposit", response_class=HTMLResponse, name="investment_deposit_process")
async def deposit_calculator_process(
    request: Request,
    amount: float = Form(...),
    period: int = Form(...),
    period_unit: str = Form("months"),
    start_date: str = Form(...),
    rate: float = Form(...),
    capitalization: str = Form(None),
    payout_frequency: str = Form("monthly"),
    replenishment_enabled: str = Form(None),
    replenishment_amount: float = Form(0),
    replenishment_frequency: str = Form("monthly"),
    withdrawal_enabled: str = Form(None),
    withdrawal_amount: float = Form(0),
    withdrawal_frequency: str = Form("monthly"),
    consider_inflation: str = Form(None),
    inflation_rate: float = Form(7),
    key_rate: float = Form(14),
):
    logger.info(
        f"Расчет вклада (POST): amount={amount}, period={period} {period_unit}, rate={rate}, "
        f"capitalization={bool(capitalization)}, payout_frequency={payout_frequency}"
    )

    is_capitalization = bool(capitalization)
    is_replenishment = bool(replenishment_enabled)
    is_withdrawal = bool(withdrawal_enabled)
    is_inflation = bool(consider_inflation)
    period_months = _term_to_months(period, period_unit)

    form_context = {
        "input_amount": amount,
        "input_period": period,
        "input_period_unit": period_unit,
        "input_start_date": start_date,
        "input_rate": rate,
        "input_capitalization": is_capitalization,
        "input_payout_frequency": payout_frequency,
        "input_replenishment_enabled": is_replenishment,
        "input_replenishment_amount": replenishment_amount,
        "input_replenishment_frequency": replenishment_frequency,
        "input_withdrawal_enabled": is_withdrawal,
        "input_withdrawal_amount": withdrawal_amount,
        "input_withdrawal_frequency": withdrawal_frequency,
        "input_consider_inflation": is_inflation,
        "input_inflation_rate": inflation_rate,
        "input_key_rate": key_rate,
        "payout_frequency_options": logic_deposit.get_payout_frequency_options(),
    }

    try:
        parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        result = logic_deposit.calculate_deposit(
            amount=amount,
            period_months=period_months,
            start_date=parsed_start_date,
            rate=rate,
            capitalization=is_capitalization,
            payout_frequency=payout_frequency,
            replenishment_amount=replenishment_amount if is_replenishment else 0.0,
            replenishment_frequency=replenishment_frequency,
            withdrawal_amount=withdrawal_amount if is_withdrawal else 0.0,
            withdrawal_frequency=withdrawal_frequency,
            consider_inflation=is_inflation,
            inflation_rate=inflation_rate,
            key_rate=key_rate,
        )
        logger.info(f"Результат расчета вклада: итог={result.final_balance}")

        return templates.TemplateResponse(
            request=request,
            name="app_section_calc_investment_tpl_deposit.html",
            context={**form_context, "result": result.to_dict(), "error": None},
        )
    except ValueError as e:
        logger.error(f"Ошибка валидации калькулятора вкладов: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_calc_investment_tpl_deposit.html",
            context={**form_context, "result": None, "error": str(e)},
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при расчете вклада: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_calc_investment_tpl_deposit.html",
            context={
                **form_context,
                "result": None,
                "error": "Произошла ошибка при расчете. Проверьте введённые данные.",
            },
        )


# =============================================================================
# КАЛЬКУЛЯТОР СЛОЖНОГО ПРОЦЕНТА (GET и POST)
# =============================================================================
def _compound_default_context() -> dict:
    """Значения формы по умолчанию для первого открытия страницы."""
    return {
        "result": None,
        "error": None,
        "input_mode": "income",
        "input_principal": 1_000_000,
        "input_term_value": 1,
        "input_term_unit": "years",
        "input_rate": 10,
        "input_reinvest": False,
        "input_reinvest_frequency": "monthly",
        "input_contribution_enabled": True,
        "input_contribution": 10_000,
        "input_contribution_frequency": "monthly",
        "input_contribution_growth": 0,
        "input_contribution_type": "add",
        "input_apply_tax": False,
        "input_consider_inflation": False,
        "input_inflation_rate": 7,
        "input_target_amount": "",
        "mode_options": logic_compound.get_mode_options(),
        "frequency_options": logic_compound.get_frequency_options(),
        "contribution_frequency_options": logic_compound.get_contribution_frequency_options(),
    }


def _term_to_months(value: float, unit: str) -> int:
    if unit == "years":
        return round(value * 12)
    return round(value)


@router.get("/compound-interest", response_class=HTMLResponse, name="investment_compound_interest")
async def compound_interest_calculator_page(request: Request):
    logger.info("Запрошена страница калькулятора сложного процента")

    return templates.TemplateResponse(
        request=request,
        name="app_section_calc_investment_tpl_compound_interest.html",
        context=_compound_default_context(),
    )


@router.post("/compound-interest", response_class=HTMLResponse, name="investment_compound_interest_process")
async def compound_interest_calculator_process(
    request: Request,
    mode: str = Form("income"),
    principal: float = Form(0),
    term_value: int = Form(1),
    term_unit: str = Form("years"),
    rate: float = Form(0),
    reinvest: str = Form(None),
    reinvest_frequency: str = Form("monthly"),
    contribution_enabled: str = Form(None),
    contribution: float = Form(0),
    contribution_frequency: str = Form("monthly"),
    contribution_growth: float = Form(0),
    contribution_type: str = Form("add"),
    apply_tax: str = Form(None),
    consider_inflation: str = Form(None),
    inflation_rate: float = Form(7),
    target_amount: float = Form(0),
):
    logger.info(
        f"Расчет сложного процента (POST): mode={mode}, principal={principal}, "
        f"term={term_value} {term_unit}, rate={rate}, reinvest={bool(reinvest)}"
    )

    is_reinvest = bool(reinvest)
    is_contribution = bool(contribution_enabled)
    is_tax = bool(apply_tax)
    is_inflation = bool(consider_inflation)
    term_months = _term_to_months(term_value, term_unit)

    form_context = {
        "input_mode": mode,
        "input_principal": principal,
        "input_term_value": term_value,
        "input_term_unit": term_unit,
        "input_rate": rate,
        "input_reinvest": is_reinvest,
        "input_reinvest_frequency": reinvest_frequency,
        "input_contribution_enabled": is_contribution,
        "input_contribution": contribution,
        "input_contribution_frequency": contribution_frequency,
        "input_contribution_growth": contribution_growth,
        "input_contribution_type": contribution_type,
        "input_apply_tax": is_tax,
        "input_consider_inflation": is_inflation,
        "input_inflation_rate": inflation_rate,
        "input_target_amount": target_amount,
        "mode_options": logic_compound.get_mode_options(),
        "frequency_options": logic_compound.get_frequency_options(),
        "contribution_frequency_options": logic_compound.get_contribution_frequency_options(),
    }

    try:
        result = logic_compound.calculate_investment(
            mode=mode,
            principal=principal,
            term_months=term_months,
            rate=rate,
            reinvest=is_reinvest,
            reinvest_frequency=reinvest_frequency,
            contribution=contribution if is_contribution else 0.0,
            contribution_frequency=contribution_frequency,
            contribution_growth_percent=contribution_growth if is_contribution else 0.0,
            contribution_type=contribution_type,
            apply_tax=is_tax,
            consider_inflation=is_inflation,
            inflation_rate=inflation_rate,
            target_amount=target_amount,
        )
        logger.info(f"Результат расчета сложного процента: итог={result.final_amount}")

        return templates.TemplateResponse(
            request=request,
            name="app_section_calc_investment_tpl_compound_interest.html",
            context={**form_context, "result": result.to_dict(), "error": None},
        )
    except ValueError as e:
        logger.error(f"Ошибка валидации калькулятора сложного процента: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_calc_investment_tpl_compound_interest.html",
            context={**form_context, "result": None, "error": str(e)},
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при расчете сложного процента: {e}")
        return templates.TemplateResponse(
            request=request,
            name="app_section_calc_investment_tpl_compound_interest.html",
            context={
                **form_context,
                "result": None,
                "error": "Произошла ошибка при расчете. Проверьте введённые данные.",
            },
        )
