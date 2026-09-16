"""
app_section_calc_taxes_logic_ndfl.py
-------------------------------
Чистая бизнес-логика расчета НДФЛ (Налог на доходы физических лиц).
Учитывает прогрессивную шкалу налогообложения РФ (2025+).
"""

import decimal
from dataclasses import dataclass
from typing import Optional


@dataclass
class NDFlResult:
    """Результат расчета НДФЛ."""
    gross_income: float  # Доход до вычета налога
    taxable_income: float  # Налогооблагаемая база
    tax_amount: float  # Сумма налога
    net_income: float  # Доход после вычета налога (на руки)
    effective_rate: float  # Эффективная ставка налога (%)
    deductions: float  # Примененные вычеты

    def to_dict(self) -> dict:
        """Преобразование в словарь для передачи в шаблон."""
        return {
            "gross_income": round(self.gross_income, 2),
            "taxable_income": round(self.taxable_income, 2),
            "tax_amount": round(self.tax_amount, 2),
            "net_income": round(self.net_income, 2),
            "effective_rate": round(self.effective_rate, 2),
            "deductions": round(self.deductions, 2),
        }


# Прогрессивная шкала налогообложения (с 2025 года):
# (верхняя граница диапазона, ставка, подпись диапазона для таблицы)
_BRACKETS_META = [
    (2_400_000, 0.13, "до 2 400 000 ₽"),
    (5_000_000, 0.15, "до 5 000 000 ₽"),
    (20_000_000, 0.18, "до 20 000 000 ₽"),
    (50_000_000, 0.20, "до 50 000 000 ₽"),
    (float('inf'), 0.22, "свыше 50 000 000 ₽"),
]

_PROGRESSIVE_BRACKETS = [(limit, rate) for limit, rate, _ in _BRACKETS_META]


def _round_half_up(value: float) -> float:
    """Округление до целого рубля по правилам «0,5 и больше — в большую сторону»."""
    q = decimal.Decimal(str(value)).quantize(decimal.Decimal('1'), rounding=decimal.ROUND_HALF_UP)
    return float(q)


def _apply_progressive_brackets(taxable_income: float) -> float:
    """Считает сумму налога по прогрессивной шкале для заданной базы."""
    tax_amount = 0.0
    remaining_income = taxable_income
    prev_limit = 0

    for limit, rate in _PROGRESSIVE_BRACKETS:
        if remaining_income <= 0:
            break

        bracket_income = min(remaining_income, limit - prev_limit)
        tax_amount += bracket_income * rate

        remaining_income -= bracket_income
        prev_limit = limit

    return tax_amount


def _progressive_breakdown(taxable_income: float) -> list[dict]:
    """
    Разбивка налога по каждой ступени прогрессивной шкалы.
    Возвращает все 5 ступеней (даже с нулевым доходом в них),
    чтобы таблица расчета всегда была полной.
    """
    breakdown = []
    remaining = taxable_income
    prev_limit = 0.0

    for limit, rate, label in _BRACKETS_META:
        span = limit - prev_limit
        bracket_income = min(remaining, span) if remaining > 0 else 0.0
        bracket_tax = bracket_income * rate

        breakdown.append({
            "rate_percent": round(rate * 100),
            "limit_label": label,
            "income": bracket_income,
            "tax": bracket_tax,
        })

        remaining -= bracket_income
        prev_limit = limit

    return breakdown


def _invert_progressive(net_target: float) -> float:
    """
    По известному доходу «на руки» (после вычета налога) находит доход
    «до вычета налога» (grossup), учитывая, что ставка внутри каждой
    ступени прогрессивной шкалы своя.
    """
    prev_gross = 0.0
    prev_net = 0.0

    for limit, rate, _ in _BRACKETS_META:
        if limit == float('inf'):
            return prev_gross + (net_target - prev_net) / (1 - rate)

        gross_span = limit - prev_gross
        net_span = gross_span * (1 - rate)
        net_upper = prev_net + net_span

        if net_target <= net_upper:
            return prev_gross + (net_target - prev_net) / (1 - rate)

        prev_gross = limit
        prev_net = net_upper

    # Практически недостижимо (последняя ступень покрывает всё, что осталось)
    return prev_gross


def calculate_ndfl(
        income: float,
        rate: float = 13.0,
        mode: str = "flat",
        income_type: str = "before",
        deductions: float = 0.0
) -> dict:
    """
    Расчет НДФЛ.

    Поддерживает два режима:
    - "flat" — расчет по единой фиксированной ставке (rate, %). Доход может
      быть указан как "до вычета налога" (income_type="before") — тогда налог
      начисляется сверх дохода, — так и "после вычета налога"
      (income_type="after") — тогда налог "накручивается" обратно по формуле
      Ставка / (1 − Ставка).
    - "progressive" — расчет по прогрессивной шкале (13% – 22%). Доход может
      быть указан как "до вычета налога" (income_type="before") — тогда сразу
      известна налоговая база, — так и "после вычета налога"
      (income_type="after") — тогда доход "до налога" находится методом
      grossup по обратной прогрессивной шкале.

    Args:
        income: Сумма дохода, введенная пользователем
        rate: Ставка НДФЛ в процентах (используется только в режиме "flat")
        mode: Режим расчета — "flat" или "progressive"
        income_type: Тип введенного дохода — "before" или "after"
        deductions: Сумма налоговых вычетов (применяется в режиме "progressive"
            при income_type="before")

    Returns:
        dict: Данные для отображения в шаблоне (структура зависит от режима)

    Raises:
        ValueError: Если входные данные некорректны
    """
    if income < 0:
        raise ValueError("Доход не может быть отрицательным")

    if deductions < 0:
        raise ValueError("Вычеты не могут быть отрицательными")

    if mode == "flat":
        if rate < 0 or rate >= 100:
            raise ValueError("Ставка НДФЛ должна быть от 0 до 100%")

        rate_fraction = rate / 100

        if income_type == "after":
            # Известна сумма "на руки" — восстанавливаем сумму налога и доход до вычета
            tax_amount = income * (rate_fraction / (1 - rate_fraction))
            gross_income = income + tax_amount
            net_income = income
        else:
            gross_income = income
            tax_amount = income * rate_fraction
            net_income = income - tax_amount

        return {
            "mode": "flat",
            "income_type": income_type,
            "income": round(gross_income, 2),
            "tax": round(tax_amount, 2),
            "net_income": round(net_income, 2),
        }

    elif mode == "progressive":
        if income_type == "after":
            gross_raw = _invert_progressive(income)
            net_raw = income
        else:
            taxable_income = max(0.0, income - deductions)
            tax_raw_before = _apply_progressive_brackets(taxable_income)
            gross_raw = income
            net_raw = income - tax_raw_before

        taxable_base_raw = max(0.0, gross_raw - deductions) if income_type != "after" else gross_raw
        breakdown = _progressive_breakdown(taxable_base_raw)
        tax_raw = sum(row["tax"] for row in breakdown)
        income_raw_total = sum(row["income"] for row in breakdown)

        if income_type == "after":
            net_raw = income
            gross_raw = net_raw + tax_raw
        else:
            net_raw = gross_raw - tax_raw

        avg_rate = (tax_raw / gross_raw * 100) if gross_raw > 0 else 0.0
        avg_rate_display = f"{avg_rate:.3f}".rstrip('0').rstrip('.')
        if avg_rate_display == "" or avg_rate_display == "-":
            avg_rate_display = "0"

        return {
            "mode": "progressive",
            "income_type": income_type,
            "gross_raw": round(income_raw_total, 2),
            "tax_raw": round(tax_raw, 2),
            "net_raw": round(net_raw, 2),
            "gross_rounded": _round_half_up(gross_raw),
            "tax_rounded": _round_half_up(tax_raw),
            "net_rounded": _round_half_up(net_raw),
            "taxable_base_raw": round(taxable_base_raw, 2),
            "breakdown": breakdown,
            "avg_rate_display": avg_rate_display,
        }

    else:
        raise ValueError("Неизвестный режим расчета НДФЛ")


def calculate_monthly_ndfl(
        monthly_income: float,
        monthly_deductions: float = 0.0
) -> dict:
    """
    Расчет НДФЛ для ежемесячного дохода по прогрессивной шкале
    (автоматически умножает на 12).

    Args:
        monthly_income: Ежемесячный доход
        monthly_deductions: Ежемесячные вычеты

    Returns:
        dict: Результаты за год (см. calculate_ndfl)
    """
    annual_income = monthly_income * 12
    annual_deductions = monthly_deductions * 12

    return calculate_ndfl(annual_income, mode="progressive", deductions=annual_deductions)