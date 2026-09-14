"""
app_section_taxes_logic_ndfl.py
-------------------------------
Чистая бизнес-логика расчета НДФЛ (Налог на доходы физических лиц).
Учитывает прогрессивную шкалу налогообложения РФ (2025+).
"""

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


def calculate_ndfl(
        annual_income: float,
        deductions: float = 0.0
) -> NDFlResult:
    """
    Расчет НДФЛ с учетом прогрессивной шкалы налогообложения РФ.

    Прогрессивная шкала (с 2025 года):
    - До 2.4 млн руб/год: 13%
    - От 2.4 до 5 млн руб/год: 15%
    - От 5 до 20 млн руб/год: 18%
    - От 20 до 50 млн руб/год: 20%
    - Свыше 50 млн руб/год: 22%

    Args:
        annual_income: Годовой доход (до вычета налога)
        deductions: Сумма налоговых вычетов (стандартные, имущественные и т.д.)

    Returns:
        NDFlResult: Объект с результатами расчета

    Raises:
        ValueError: Если доход или вычеты отрицательные
    """
    if annual_income < 0:
        raise ValueError("Доход не может быть отрицательным")

    if deductions < 0:
        raise ValueError("Вычеты не могут быть отрицательными")

    # Налогооблагаемая база = Доход - Вычеты
    taxable_income = max(0, annual_income - deductions)

    # Прогрессивная шкала налогообложения
    tax_brackets = [
        (2_400_000, 0.13),  # До 2.4 млн: 13%
        (5_000_000, 0.15),  # От 2.4 до 5 млн: 15%
        (20_000_000, 0.18),  # От 5 до 20 млн: 18%
        (50_000_000, 0.20),  # От 20 до 50 млн: 20%
        (float('inf'), 0.22),  # Свыше 50 млн: 22%
    ]

    tax_amount = 0.0
    remaining_income = taxable_income
    prev_limit = 0

    for limit, rate in tax_brackets:
        if remaining_income <= 0:
            break

        # Сумма в текущем диапазоне
        bracket_income = min(remaining_income, limit - prev_limit)
        tax_amount += bracket_income * rate

        remaining_income -= bracket_income
        prev_limit = limit

    # Чистый доход (на руки)
    net_income = annual_income - tax_amount

    # Эффективная ставка налога
    effective_rate = (tax_amount / annual_income * 100) if annual_income > 0 else 0

    return NDFlResult(
        gross_income=annual_income,
        taxable_income=taxable_income,
        tax_amount=tax_amount,
        net_income=net_income,
        effective_rate=effective_rate,
        deductions=deductions
    )


def calculate_monthly_ndfl(
        monthly_income: float,
        monthly_deductions: float = 0.0
) -> NDFlResult:
    """
    Расчет НДФЛ для ежемесячного дохода (автоматически умножает на 12).

    Args:
        monthly_income: Ежемесячный доход
        monthly_deductions: Ежемесячные вычеты

    Returns:
        NDFlResult: Результаты за год
    """
    annual_income = monthly_income * 12
    annual_deductions = monthly_deductions * 12

    return calculate_ndfl(annual_income, annual_deductions)