"""
app_section_calc_investment_logic_deposit.py
----------------------------------------------
Чистая бизнес-логика калькулятора вкладов (депозитов).
Без зависимостей от FastAPI — только dataclass'ы и функции.

Поддерживает:
- Фиксированную процентную ставку.
- Капитализацию процентов с выбираемой периодичностью
  (ежемесячно / ежеквартально / раз в полгода / раз в год) либо
  выплату процентов без капитализации (проценты не увеличивают тело вклада).
- Регулярные пополнения и частичные снятия (с той же периодичностью, что и капитализация).
- Точный расчёт по фактическим дням (факт/365, фактическое количество дней в периоде).
- Налог на доход по вкладам (НДФЛ) с учётом необлагаемой суммы
  (1 000 000 ₽ × ключевая ставка ЦБ) и прогрессии 13% / 15%,
  с разбивкой по календарным годам (проценты, полученные в разные годы,
  облагаются налогом отдельно, каждый год имеет свой вычет).
"""

from __future__ import annotations

import calendar
import decimal
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional


# =============================================================================
# КОНСТАНТЫ
# =============================================================================

# Периодичность капитализации/выплаты процентов и периодичность пополнений/снятий:
# количество периодов в году.
FREQUENCY_PERIODS_PER_YEAR: dict[str, int] = {
    "monthly": 12,
    "quarterly": 4,
    "semiannual": 2,
    "annual": 1,
    "end": 0,  # проценты начисляются один раз, в конце срока
}

FREQUENCY_MONTHS_STEP: dict[str, int] = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}

# Необлагаемая налогом сумма процентов по вкладам = 1 000 000 ₽ × ключевая ставка ЦБ
NON_TAXABLE_BASE = 1_000_000.0

# Пороги прогрессивной шкалы НДФЛ для процентного дохода по вкладам (13% / 15%)
NDFL_FLAT_THRESHOLD = 2_400_000.0
NDFL_RATE_LOW = 0.13
NDFL_RATE_HIGH = 0.15


# =============================================================================
# DATACLASS'Ы
# =============================================================================

@dataclass
class CashFlowEvent:
    """Разовое или регулярное пополнение/снятие."""
    amount: float  # положительное — пополнение, будет вычтено для снятия отдельным полем


@dataclass
class ScheduleRow:
    """Одна строка графика начисления процентов."""
    period_date: date
    accrued_interest: float     # проценты, начисленные за период
    balance_change: float       # изменение баланса из-за пополнения/снятия/капитализации (со знаком)
    balance: float              # баланс на конец периода
    change_label: str = ""      # человекочитаемая подпись изменения


@dataclass
class YearTaxRow:
    """Разбивка налога на доход по вкладам за один календарный год."""
    year: int
    income: float                # проценты, полученные (выплаченные/начисленные) в этом году
    deduction: float              # необлагаемая сумма (1 млн х ключевая ставка ЦБ)
    taxable_income: float         # доход, облагаемый налогом
    tax_amount: float             # сумма налога к уплате
    pay_by: date                  # срок уплаты — 1 декабря следующего года


@dataclass
class DepositResult:
    """Итоговый результат расчёта вклада."""
    principal: float                  # исходная сумма вклада
    total_replenishments: float       # сумма всех пополнений за срок
    total_withdrawals: float          # сумма всех частичных снятий за срок
    accrued_interest: float           # суммарные начисленные проценты за весь срок
    final_balance: float              # сумма вклада с процентами на конец срока
    nominal_rate: float               # введённая номинальная ставка, %
    effective_rate: float             # эффективная (с учётом капитализации) годовая ставка, %
    tax_total: float                  # суммарный налог на процентный доход
    income_after_tax: float           # доход за вычетом налога (проценты минус налог)
    real_yield_percent: float         # реальная годовая доходность после налога (и инфляции), %
    inflation_adjusted_income: Optional[float]  # доход с поправкой на инфляцию (если учитывается)
    schedule: list[ScheduleRow] = field(default_factory=list)
    tax_by_year: list[YearTaxRow] = field(default_factory=list)
    chart_principal_share: float = 0.0
    chart_replenishments_share: float = 0.0
    chart_interest_share: float = 0.0

    def to_dict(self) -> dict:
        return {
            "principal": round(self.principal, 2),
            "total_replenishments": round(self.total_replenishments, 2),
            "total_withdrawals": round(self.total_withdrawals, 2),
            "accrued_interest": round(self.accrued_interest, 2),
            "final_balance": round(self.final_balance, 2),
            "nominal_rate": round(self.nominal_rate, 2),
            "effective_rate": round(self.effective_rate, 2),
            "tax_total": round(self.tax_total, 2),
            "income_after_tax": round(self.income_after_tax, 2),
            "real_yield_percent": round(self.real_yield_percent, 2),
            "inflation_adjusted_income": (
                round(self.inflation_adjusted_income, 2)
                if self.inflation_adjusted_income is not None else None
            ),
            "schedule": [
                {
                    "date": row.period_date.strftime("%d.%m.%Y"),
                    "accrued_interest": round(row.accrued_interest, 2),
                    "balance_change": round(row.balance_change, 2),
                    "balance": round(row.balance, 2),
                    "change_label": row.change_label,
                }
                for row in self.schedule
            ],
            "tax_by_year": [
                {
                    "year": row.year,
                    "income": round(row.income, 2),
                    "deduction": round(row.deduction, 2),
                    "taxable_income": round(row.taxable_income, 2),
                    "tax_amount": round(row.tax_amount, 2),
                    "pay_by": row.pay_by.strftime("%d.%m.%Y"),
                }
                for row in self.tax_by_year
            ],
            "chart_principal_share": round(self.chart_principal_share, 1),
            "chart_replenishments_share": round(self.chart_replenishments_share, 1),
            "chart_interest_share": round(self.chart_interest_share, 1),
        }


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _add_months(source: date, months: int) -> date:
    """Прибавляет к дате указанное количество месяцев, сохраняя корректность дня."""
    month_index = source.month - 1 + months
    year = source.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _days_in_year(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


def _period_interest(balance: float, annual_rate_percent: float, start: date, end: date) -> float:
    """
    Считает проценты, начисленные на balance по ставке annual_rate_percent
    за период [start, end), с учётом фактического числа дней и фактической
    длины года (365/366) — если период затрагивает два календарных года,
    считает раздельно для каждого года.
    """
    if end <= start:
        return 0.0

    rate_fraction = annual_rate_percent / 100
    total_interest = 0.0
    cursor = start

    while cursor < end:
        year_end = date(cursor.year + 1, 1, 1)
        segment_end = min(end, year_end)
        days = (segment_end - cursor).days
        total_interest += balance * rate_fraction * days / _days_in_year(cursor.year)
        cursor = segment_end

    return total_interest


def _round_half_up(value: float, digits: int = 2) -> float:
    quantum = decimal.Decimal("1").scaleb(-digits)
    q = decimal.Decimal(str(value)).quantize(quantum, rounding=decimal.ROUND_HALF_UP)
    return float(q)


# =============================================================================
# НАЛОГ НА ДОХОД ПО ВКЛАДАМ
# =============================================================================

def calculate_deposit_tax(taxable_income: float) -> float:
    """
    Считает НДФЛ с суммы, облагаемой налогом (уже за вычетом необлагаемой суммы),
    по правилу 13% до 2,4 млн руб., 15% — сверх этой суммы.
    """
    if taxable_income <= 0:
        return 0.0
    if taxable_income <= NDFL_FLAT_THRESHOLD:
        return taxable_income * NDFL_RATE_LOW
    return (
        NDFL_FLAT_THRESHOLD * NDFL_RATE_LOW
        + (taxable_income - NDFL_FLAT_THRESHOLD) * NDFL_RATE_HIGH
    )


def _tax_by_year(income_by_year: dict[int, float], key_rate_percent: float) -> list[YearTaxRow]:
    """
    Формирует разбивку налога по годам. Необлагаемая сумма считается по единой
    ключевой ставке ЦБ (введённой пользователем) для всех лет — это упрощение,
    так как точная ставка «на 1-е число каждого месяца года» неизвестна заранее
    для будущих периодов.
    """
    deduction = NON_TAXABLE_BASE * key_rate_percent / 100
    rows: list[YearTaxRow] = []

    for year in sorted(income_by_year.keys()):
        income = income_by_year[year]
        taxable = max(0.0, income - deduction)
        tax = calculate_deposit_tax(taxable)
        rows.append(
            YearTaxRow(
                year=year,
                income=income,
                deduction=deduction if income > 0 else 0.0,
                taxable_income=taxable,
                tax_amount=tax,
                pay_by=date(year + 1, 12, 1),
            )
        )

    return rows


# =============================================================================
# ОСНОВНОЙ РАСЧЁТ ВКЛАДА
# =============================================================================

def calculate_deposit(
    amount: float,
    period_months: int,
    start_date: date,
    rate: float,
    capitalization: bool = False,
    payout_frequency: Literal["monthly", "quarterly", "semiannual", "annual", "end"] = "monthly",
    replenishment_amount: float = 0.0,
    replenishment_frequency: Literal["monthly", "quarterly", "semiannual", "annual"] = "monthly",
    withdrawal_amount: float = 0.0,
    withdrawal_frequency: Literal["monthly", "quarterly", "semiannual", "annual"] = "monthly",
    consider_inflation: bool = False,
    inflation_rate: float = 0.0,
    key_rate: float = 14.0,
) -> DepositResult:
    """
    Полный расчёт вклада: график начисления процентов, итоговая сумма,
    налог на процентный доход и реальная доходность.

    Args:
        amount: сумма вклада (₽)
        period_months: срок размещения (месяцев), от 1 до 60
        start_date: дата открытия вклада
        rate: годовая процентная ставка (%)
        capitalization: капитализировать ли проценты (присоединять к телу вклада)
        payout_frequency: периодичность капитализации/выплаты процентов
        replenishment_amount: сумма регулярного пополнения (0 — без пополнений)
        replenishment_frequency: периодичность пополнений
        withdrawal_amount: сумма регулярного частичного снятия (0 — без снятий)
        withdrawal_frequency: периодичность снятий
        consider_inflation: учитывать ли инфляцию при расчёте реальной доходности
        inflation_rate: ожидаемая годовая инфляция (%), используется если consider_inflation=True
        key_rate: ключевая ставка ЦБ (%), используется для расчёта необлагаемой суммы налога

    Returns:
        DepositResult
    """
    if amount <= 0:
        raise ValueError("Сумма вклада должна быть больше нуля")
    if period_months <= 0 or period_months > 60:
        raise ValueError("Срок размещения должен быть от 1 до 60 месяцев")
    if rate < 0 or rate > 100:
        raise ValueError("Процентная ставка должна быть от 0 до 100%")
    if replenishment_amount < 0 or withdrawal_amount < 0:
        raise ValueError("Суммы пополнений и снятий не могут быть отрицательными")
    if key_rate < 0 or key_rate > 100:
        raise ValueError("Ключевая ставка ЦБ должна быть от 0 до 100%")

    end_date = _add_months(start_date, period_months)

    # Шаг капитализации/выплаты процентов: при "end" — один раз в конце срока
    payout_step = FREQUENCY_MONTHS_STEP.get(payout_frequency, period_months)
    if payout_frequency == "end":
        payout_step = period_months

    replenishment_step = FREQUENCY_MONTHS_STEP.get(replenishment_frequency, 1)
    withdrawal_step = FREQUENCY_MONTHS_STEP.get(withdrawal_frequency, 1)

    balance = amount               # тело вклада (используется для начисления %, растёт при капитализации)
    paid_out_total = 0.0           # проценты, выплаченные "на руки" (без капитализации)
    total_replenishments = 0.0
    total_withdrawals = 0.0
    total_accrued_interest = 0.0

    schedule: list[ScheduleRow] = []
    income_by_year: dict[int, float] = {}

    cursor = start_date
    months_elapsed = 0

    # Отмечаем начальную строку графика (открытие вклада)
    schedule.append(
        ScheduleRow(
            period_date=start_date,
            accrued_interest=0.0,
            balance_change=amount,
            balance=balance,
            change_label="Открытие вклада",
        )
    )

    while months_elapsed < period_months:
        # Определяем ближайшую следующую "контрольную точку": капитализация,
        # пополнение, снятие или конец срока — идём минимальными шагами по месяцам.
        next_payout_month = ((months_elapsed // payout_step) + 1) * payout_step if payout_step else period_months
        next_replenishment_month = (
            ((months_elapsed // replenishment_step) + 1) * replenishment_step
            if replenishment_amount > 0 else period_months + 1
        )
        next_withdrawal_month = (
            ((months_elapsed // withdrawal_step) + 1) * withdrawal_step
            if withdrawal_amount > 0 else period_months + 1
        )

        next_month_mark = min(next_payout_month, next_replenishment_month, next_withdrawal_month, period_months)
        next_date = _add_months(start_date, next_month_mark)

        # Начисляем проценты на текущий баланс за прошедший интервал
        interest = _period_interest(balance, rate, cursor, next_date)
        total_accrued_interest += interest

        # Распределяем проценты по календарным годам (для налога) по дате начисления
        income_by_year[next_date.year] = income_by_year.get(next_date.year, 0.0) + interest

        balance_change = 0.0
        change_labels = []

        is_payout_point = (next_month_mark == next_payout_month) or (next_month_mark == period_months)
        if is_payout_point and interest > 0:
            if capitalization:
                balance += interest
                balance_change += interest
                change_labels.append("Капитализация процентов")
            else:
                paid_out_total += interest
                change_labels.append("Выплата процентов")

        if next_month_mark == next_replenishment_month and replenishment_amount > 0:
            balance += replenishment_amount
            balance_change += replenishment_amount
            total_replenishments += replenishment_amount
            change_labels.append("Пополнение")

        if next_month_mark == next_withdrawal_month and withdrawal_amount > 0:
            withdrawal_applied = min(withdrawal_amount, balance)
            balance -= withdrawal_applied
            balance_change -= withdrawal_applied
            total_withdrawals += withdrawal_applied
            change_labels.append("Частичное снятие")

        schedule.append(
            ScheduleRow(
                period_date=next_date,
                accrued_interest=interest,
                balance_change=balance_change,
                balance=balance,
                change_label=" + ".join(change_labels) if change_labels else "Начисление процентов",
            )
        )

        cursor = next_date
        months_elapsed = next_month_mark

    # Итоговая сумма вклада с процентами = баланс (уже включает капитализацию
    # и пополнения/снятия) + проценты, выплаченные отдельно (не капитализированные)
    final_balance = balance + paid_out_total

    # ---------------- Налог ----------------
    tax_rows = _tax_by_year(income_by_year, key_rate)
    tax_total = sum(row.tax_amount for row in tax_rows)
    income_after_tax = total_accrued_interest - tax_total

    # ---------------- Эффективная ставка ----------------
    periods_per_year = FREQUENCY_PERIODS_PER_YEAR.get(payout_frequency, 1)
    if capitalization and periods_per_year > 0:
        effective_rate = ((1 + (rate / 100) / periods_per_year) ** periods_per_year - 1) * 100
    else:
        effective_rate = rate

    # ---------------- Реальная доходность ----------------
    years_fraction = period_months / 12
    avg_invested = amount + total_replenishments / 2  # грубая оценка средней вложенной суммы
    if years_fraction > 0 and avg_invested > 0:
        real_yield_percent = (income_after_tax / avg_invested) / years_fraction * 100
    else:
        real_yield_percent = 0.0

    inflation_adjusted_income = None
    if consider_inflation:
        inflation_factor = (1 + inflation_rate / 100) ** years_fraction
        inflation_adjusted_income = income_after_tax - amount * (inflation_factor - 1)
        if years_fraction > 0 and avg_invested > 0:
            real_yield_percent = (inflation_adjusted_income / avg_invested) / years_fraction * 100

    # ---------------- Доли для круговой диаграммы ----------------
    total_pie_base = amount + total_replenishments + total_accrued_interest
    if total_pie_base > 0:
        chart_principal_share = amount / total_pie_base * 100
        chart_replenishments_share = total_replenishments / total_pie_base * 100
        chart_interest_share = total_accrued_interest / total_pie_base * 100
    else:
        chart_principal_share = chart_replenishments_share = chart_interest_share = 0.0

    return DepositResult(
        principal=amount,
        total_replenishments=total_replenishments,
        total_withdrawals=total_withdrawals,
        accrued_interest=total_accrued_interest,
        final_balance=final_balance,
        nominal_rate=rate,
        effective_rate=effective_rate,
        tax_total=tax_total,
        income_after_tax=income_after_tax,
        real_yield_percent=real_yield_percent,
        inflation_adjusted_income=inflation_adjusted_income,
        schedule=schedule,
        tax_by_year=tax_rows,
        chart_principal_share=chart_principal_share,
        chart_replenishments_share=chart_replenishments_share,
        chart_interest_share=chart_interest_share,
    )


def get_payout_frequency_options() -> list[dict]:
    """Варианты периодичности капитализации/выплаты процентов для формы."""
    return [
        {"value": "monthly", "label": "раз в месяц"},
        {"value": "quarterly", "label": "раз в квартал"},
        {"value": "semiannual", "label": "раз в полгода"},
        {"value": "annual", "label": "раз в год"},
        {"value": "end", "label": "в конце срока"},
    ]
