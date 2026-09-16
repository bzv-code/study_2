"""
app_section_calc_taxes_logic_nds.py
------------------------------
Чистая бизнес-логика расчета НДС.
Поддерживает 3 режима: начисление, выделение и расчет по сумме НДС.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class NDSResult:
    """Результат расчета НДС."""
    action: str             # Тип расчета: 'add', 'extract', 'by_vat'
    input_amount: float     # Введенная пользователем сумма
    rate: float             # Ставка НДС (%)
    net_amount: float       # Сумма без НДС
    vat_amount: float       # Сумма НДС
    total_amount: float     # Сумма с НДС

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "input_amount": round(self.input_amount, 2),
            "rate": self.rate,
            "net_amount": round(self.net_amount, 2),
            "vat_amount": round(self.vat_amount, 2),
            "total_amount": round(self.total_amount, 2),
        }


def calculate_nds(
    amount: float,
    rate: float,
    action: Literal["add", "extract", "by_vat"] = "add"
) -> NDSResult:
    """
    Расчет НДС по одному из трех сценариев.

    Args:
        amount: Введенная сумма (зависит от action)
        rate: Ставка НДС (%)
        action:
            - "add": Начислить НДС (amount = сумма без НДС)
            - "extract": Выделить НДС (amount = сумма с НДС)
            - "by_vat": Рассчитать сумму по НДС (amount = сумма самого НДС)
    """
    if amount < 0:
        raise ValueError("Сумма не может быть отрицательной")

    if rate < 0 or rate > 100:
        raise ValueError("Ставка НДС должна быть от 0 до 100%")

    if action == "add":
        # Начислить НДС: НДС = Сумма × Ставка / 100
        vat_amount = (amount * rate) / 100
        net_amount = amount
        total_amount = amount + vat_amount

    elif action == "extract":
        # Выделить НДС: НДС = Сумма с НДС × Ставка / (100 + Ставка)
        vat_amount = (amount * rate) / (100 + rate)
        net_amount = amount - vat_amount
        total_amount = amount

    elif action == "by_vat":
        # Рассчитать по НДС: Сумма без НДС = НДС × 100 / Ставка
        if rate == 0:
            raise ValueError("При ставке 0% расчет суммы по НДС невозможен")
        vat_amount = amount
        net_amount = (vat_amount * 100) / rate
        total_amount = net_amount + vat_amount

    else:
        raise ValueError("Неизвестный тип расчета")

    return NDSResult(
        action=action,
        input_amount=amount,
        rate=rate,
        net_amount=net_amount,
        vat_amount=vat_amount,
        total_amount=total_amount
    )


def get_nds_rates() -> list[dict]:
    """Возвращает список доступных ставок НДС."""
    return [
        {"value": 22, "label": "22% (новая основная ставка с 2025 г.)"},
        {"value": 20, "label": "20% (основная ставка)"},
        {"value": 10, "label": "10% (льготная ставка)"},
        {"value": 5, "label": "5% (пониженная ставка для некоторых услуг)"},
        {"value": 0, "label": "0% (экспорт, международные перевозки)"},
    ]