"""
app_section_calc_investment_logic_compound_interest.py
---------------------------------------------------------
Чистая бизнес-логика инвестиционного калькулятора сложного процента
с пополнением. Без зависимостей от FastAPI — только dataclass'ы и функции.

Поддерживает 5 режимов вычисления (как на calcus.ru):
  - "income"      — доход (по заданным капиталу, ставке, сроку, пополнениям)
  - "rate"        — требуемая ставка для достижения целевой суммы
  - "principal"   — требуемый стартовый капитал для достижения целевой суммы
  - "term"        — требуемый срок для достижения целевой суммы
  - "contribution"— требуемый размер пополнений для достижения целевой суммы

Прочие возможности:
  - Реинвестирование дохода (сложный процент) с выбираемой периодичностью
    капитализации, либо расчёт по простым процентам без реинвестирования.
  - Регулярные пополнения/изъятия с ежегодной индексацией суммы взноса.
  - Налог на инвестиционный доход (13% / 15%, упрощённо, единым итогом за весь срок).
  - Учёт инфляции (реальная итоговая сумма и реальный доход).
  - Погодовой график для таблицы результатов и данные для линейного графика прироста.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# =============================================================================
# КОНСТАНТЫ
# =============================================================================

FREQUENCY_MONTHS_STEP: dict[str, int] = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}

NDFL_FLAT_THRESHOLD = 2_400_000.0
NDFL_RATE_LOW = 0.13
NDFL_RATE_HIGH = 0.15

CalcMode = Literal["income", "rate", "principal", "term", "contribution"]
ContributionType = Literal["add", "withdraw"]


# =============================================================================
# DATACLASS'Ы
# =============================================================================

@dataclass
class YearRow:
    """Одна строка итоговой таблицы (за календарный год инвестирования)."""
    period_label: str
    start_balance: float
    interest_income: float
    tax_amount: float
    contributions: float
    end_balance: float


@dataclass
class ChartSeries:
    """Данные для графика прироста (накопительным итогом по точкам)."""
    labels: list[str] = field(default_factory=list)
    principal_line: list[float] = field(default_factory=list)
    contributions_line: list[float] = field(default_factory=list)
    income_line: list[float] = field(default_factory=list)


@dataclass
class InvestmentResult:
    mode: CalcMode
    principal: float                  # стартовый капитал (введённый либо найденный)
    term_months: int                  # срок инвестирования (введённый либо найденный)
    rate: float                       # ставка % годовых (введённая либо найденная)
    contribution: float               # размер регулярного взноса (введённый либо найденный)
    total_contributions: float        # сумма всех пополнений/изъятий (со знаком) за срок
    income: float                     # доход (проценты) за весь срок, до налога
    tax_amount: float                 # налог с дохода
    income_after_tax: float           # доход за вычетом налога
    final_amount: float               # итоговая сумма
    growth_percent: float             # прирост, % (к начальному капиталу)
    real_final_amount: Optional[float]     # итоговая сумма с поправкой на инфляцию
    real_income: Optional[float]           # доход с поправкой на инфляцию
    chart_principal_share: float = 0.0
    chart_contributions_share: float = 0.0
    chart_income_share: float = 0.0
    yearly_table: list[YearRow] = field(default_factory=list)
    chart: ChartSeries = field(default_factory=ChartSeries)
    solved_ok: bool = True             # False, если целевая сумма недостижима заданными параметрами

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "principal": round(self.principal, 2),
            "term_months": self.term_months,
            "rate": round(self.rate, 3),
            "contribution": round(self.contribution, 2),
            "total_contributions": round(self.total_contributions, 2),
            "income": round(self.income, 2),
            "tax_amount": round(self.tax_amount, 2),
            "income_after_tax": round(self.income_after_tax, 2),
            "final_amount": round(self.final_amount, 2),
            "growth_percent": round(self.growth_percent, 2),
            "real_final_amount": round(self.real_final_amount, 2) if self.real_final_amount is not None else None,
            "real_income": round(self.real_income, 2) if self.real_income is not None else None,
            "chart_principal_share": round(self.chart_principal_share, 1),
            "chart_contributions_share": round(self.chart_contributions_share, 1),
            "chart_income_share": round(self.chart_income_share, 1),
            "solved_ok": self.solved_ok,
            "yearly_table": [
                {
                    "period_label": row.period_label,
                    "start_balance": round(row.start_balance, 2),
                    "interest_income": round(row.interest_income, 2),
                    "tax_amount": round(row.tax_amount, 2),
                    "contributions": round(row.contributions, 2),
                    "end_balance": round(row.end_balance, 2),
                }
                for row in self.yearly_table
            ],
            "chart": {
                "labels": self.chart.labels,
                "principal_line": [round(v, 2) for v in self.chart.principal_line],
                "contributions_line": [round(v, 2) for v in self.chart.contributions_line],
                "income_line": [round(v, 2) for v in self.chart.income_line],
            },
        }


# =============================================================================
# НАЛОГ НА ИНВЕСТИЦИОННЫЙ ДОХОД (упрощённо, единым итогом за весь срок)
# =============================================================================

def calculate_investment_tax(income: float) -> float:
    """НДФЛ с инвестиционного дохода: 13% до 2,4 млн ₽, 15% — сверх этой суммы."""
    if income <= 0:
        return 0.0
    if income <= NDFL_FLAT_THRESHOLD:
        return income * NDFL_RATE_LOW
    return NDFL_FLAT_THRESHOLD * NDFL_RATE_LOW + (income - NDFL_FLAT_THRESHOLD) * NDFL_RATE_HIGH


# =============================================================================
# ЯДРО РАСЧЁТА: помесячная симуляция баланса
# =============================================================================

def _simulate(
    principal: float,
    term_months: int,
    rate: float,
    reinvest: bool,
    reinvest_frequency: str,
    contribution: float,
    contribution_frequency: str,
    contribution_growth_percent: float,
    contribution_type: ContributionType,
) -> tuple[float, float, float, list[dict]]:
    """
    Возвращает (total_contributions, income, final_amount, monthly_points), где
    monthly_points — список {month, balance, cum_contrib, cum_income} для графика.

    Простые проценты (reinvest=False): проценты не капитализируются, начисляются
    только на стартовый капитал и на каждое пополнение пропорционально времени,
    остающемуся до конца срока (что в точности соответствует эталонному примеру
    calcus.ru: 1 000 000 ₽, 10% годовых, взнос 10 000 ₽/мес., 1 год → доход 105 500 ₽).

    Сложные проценты (reinvest=True): начисленные проценты периодически
    (согласно reinvest_frequency) капитализируются и дальше тоже приносят доход.
    """
    contrib_step = FREQUENCY_MONTHS_STEP.get(contribution_frequency, 1)
    reinvest_step = FREQUENCY_MONTHS_STEP.get(reinvest_frequency, 1)
    sign = 1.0 if contribution_type == "add" else -1.0
    monthly_points: list[dict] = []

    if not reinvest:
        # ---------------- Простые проценты ----------------
        principal_income = principal * (rate / 100) * (term_months / 12)

        total_contrib = 0.0
        contrib_income = 0.0
        cum_contrib = 0.0
        cum_income = 0.0

        # график баланса помесячно
        balance_track = principal
        month_events: dict[int, tuple[float, float]] = {}  # month -> (contrib_amount, contrib_income_i)

        if contribution > 0:
            m = contrib_step
            while m <= term_months:
                elapsed_years_full = (m - 1) // 12
                amount = contribution * ((1 + contribution_growth_percent / 100) ** elapsed_years_full) * sign
                remaining_years = (term_months - m) / 12
                income_i = amount * (rate / 100) * remaining_years
                month_events[m] = (amount, income_i)
                total_contrib += amount
                contrib_income += income_i
                m += contrib_step

        for month in range(1, term_months + 1):
            amount, income_i = month_events.get(month, (0.0, 0.0))
            cum_contrib += amount
            # проценты по вкладу и по уже сделанным взносам "накапливаются" линейно во времени
            month_principal_income = principal_income * (month / term_months) if term_months else 0.0
            # для взносов доход учитываем по мере того, как он "заработан" линейно от момента взноса до конца срока
            cum_income = month_principal_income
            for mm, (_, inc_i) in month_events.items():
                if mm <= month:
                    total_months_i = term_months - mm
                    elapsed_i = month - mm
                    if total_months_i > 0:
                        cum_income += inc_i * min(1.0, elapsed_i / total_months_i)
            monthly_points.append({
                "month": month,
                "balance": principal + cum_contrib + cum_income,
                "cum_contrib": cum_contrib,
                "cum_income": cum_income,
            })

        income = principal_income + contrib_income
        final_amount = principal + total_contrib + income
        return total_contrib, income, final_amount, monthly_points

    # ---------------- Сложные проценты (реинвестирование) ----------------
    balance = principal
    pending_interest = 0.0
    total_contrib = 0.0
    cum_income = 0.0

    for month in range(1, term_months + 1):
        interest_month = balance * (rate / 100) / 12
        pending_interest += interest_month
        cum_income += interest_month

        is_cap_point = (month % reinvest_step == 0) or (month == term_months)
        if is_cap_point:
            balance += pending_interest
            pending_interest = 0.0

        if contribution > 0 and month % contrib_step == 0:
            elapsed_years_full = (month - 1) // 12
            amount = contribution * ((1 + contribution_growth_percent / 100) ** elapsed_years_full) * sign
            balance += amount
            total_contrib += amount

        monthly_points.append({
            "month": month,
            "balance": balance,
            "cum_contrib": total_contrib,
            "cum_income": cum_income,
        })

    final_amount = balance
    income = final_amount - principal - total_contrib
    return total_contrib, income, final_amount, monthly_points


# =============================================================================
# СБОРКА ПОГОДОВОЙ ТАБЛИЦЫ И ГРАФИКА
# =============================================================================

def _build_yearly_table(
    principal: float,
    monthly_points: list[dict],
    apply_tax: bool,
    reinvest: bool,
) -> list[YearRow]:
    """
    Строит погодовую таблицу.

    При реинвестировании (reinvest=True) начальная сумма каждого следующего
    года — это итоговая сумма предыдущего года (проценты капитализируются).

    Без реинвестирования (reinvest=False) проценты не присоединяются к телу
    инвестиции — начальная сумма каждого года остаётся равной стартовому
    капиталу плюс пополнения, сделанные к этому моменту, но БЕЗ учёта уже
    полученных процентов. Итоговая сумма (конечная) при этом всё равно растёт
    год от года, так как отражает накопленный доход на руках у инвестора.
    """
    if not monthly_points:
        return []

    rows: list[YearRow] = []
    total_income_all = monthly_points[-1]["cum_income"]
    total_tax_all = calculate_investment_tax(total_income_all) if apply_tax else 0.0

    running_total = principal    # накопленная итоговая сумма (растёт каждый год)
    prev_cum_contrib = 0.0
    prev_cum_income = 0.0

    year_index = 1
    month_cursor = 0
    n_months = len(monthly_points)

    while month_cursor < n_months:
        year_end_month = min(month_cursor + 12, n_months)
        point = monthly_points[year_end_month - 1]

        year_income = point["cum_income"] - prev_cum_income
        year_contrib = point["cum_contrib"] - prev_cum_contrib
        year_tax = (
            total_tax_all * (year_income / total_income_all)
            if apply_tax and total_income_all > 0 else 0.0
        )

        start_balance = running_total if reinvest else (principal + prev_cum_contrib)
        end_balance = running_total + year_income + year_contrib - year_tax

        rows.append(YearRow(
            period_label=f"Год {year_index}",
            start_balance=start_balance,
            interest_income=year_income,
            tax_amount=year_tax,
            contributions=year_contrib,
            end_balance=end_balance,
        ))

        running_total = end_balance
        prev_cum_contrib = point["cum_contrib"]
        prev_cum_income = point["cum_income"]
        month_cursor = year_end_month
        year_index += 1

    return rows


def _build_chart(principal: float, monthly_points: list[dict]) -> ChartSeries:
    if not monthly_points:
        return ChartSeries()

    n = len(monthly_points)
    # адаптивный шаг выборки точек, чтобы график не был перегружен
    if n <= 36:
        step = 1
    elif n <= 120:
        step = 3
    else:
        step = 12

    indices = list(range(step - 1, n, step))
    if not indices or indices[-1] != n - 1:
        indices.append(n - 1)

    labels: list[str] = []
    principal_line: list[float] = []
    contributions_line: list[float] = []
    income_line: list[float] = []

    for idx in indices:
        point = monthly_points[idx]
        month_no = point["month"]
        if step >= 12 or n > 36:
            labels.append(f"{month_no // 12}г" if month_no % 12 == 0 else f"{month_no}м")
        else:
            labels.append(str(month_no))
        principal_line.append(principal)
        contributions_line.append(point["cum_contrib"])
        income_line.append(point["cum_income"])

    return ChartSeries(
        labels=labels,
        principal_line=principal_line,
        contributions_line=contributions_line,
        income_line=income_line,
    )


# =============================================================================
# ОСНОВНАЯ ФУНКЦИЯ "ДОХОД" — используется напрямую и как ядро для solve-режимов
# =============================================================================

def _compute_income_mode(
    principal: float,
    term_months: int,
    rate: float,
    reinvest: bool,
    reinvest_frequency: str,
    contribution: float,
    contribution_frequency: str,
    contribution_growth_percent: float,
    contribution_type: ContributionType,
    apply_tax: bool,
    consider_inflation: bool,
    inflation_rate: float,
) -> InvestmentResult:
    total_contrib, income, final_amount, monthly_points = _simulate(
        principal, term_months, rate, reinvest, reinvest_frequency,
        contribution, contribution_frequency, contribution_growth_percent, contribution_type,
    )

    tax_amount = calculate_investment_tax(income) if apply_tax else 0.0
    income_after_tax = income - tax_amount
    final_after_tax = principal + total_contrib + income_after_tax

    growth_percent = ((final_after_tax - principal) / principal * 100) if principal > 0 else 0.0

    real_final_amount = None
    real_income = None
    if consider_inflation:
        years = term_months / 12
        inflation_factor = (1 + inflation_rate / 100) ** years
        real_final_amount = final_after_tax / inflation_factor
        real_income = real_final_amount - principal - total_contrib

    pie_base = principal + total_contrib + income_after_tax
    if pie_base > 0:
        chart_principal_share = principal / pie_base * 100
        chart_contributions_share = total_contrib / pie_base * 100
        chart_income_share = income_after_tax / pie_base * 100
    else:
        chart_principal_share = chart_contributions_share = chart_income_share = 0.0

    yearly_table = _build_yearly_table(principal, monthly_points, apply_tax, reinvest)
    chart = _build_chart(principal, monthly_points)

    return InvestmentResult(
        mode="income",
        principal=principal,
        term_months=term_months,
        rate=rate,
        contribution=contribution,
        total_contributions=total_contrib,
        income=income,
        tax_amount=tax_amount,
        income_after_tax=income_after_tax,
        final_amount=final_after_tax,
        growth_percent=growth_percent,
        real_final_amount=real_final_amount,
        real_income=real_income,
        chart_principal_share=chart_principal_share,
        chart_contributions_share=chart_contributions_share,
        chart_income_share=chart_income_share,
        yearly_table=yearly_table,
        chart=chart,
    )


# =============================================================================
# ПУБЛИЧНАЯ ФУНКЦИЯ: рассчитать по одному из 5 режимов
# =============================================================================

def calculate_investment(
    mode: CalcMode,
    principal: float = 0.0,
    term_months: int = 12,
    rate: float = 0.0,
    reinvest: bool = False,
    reinvest_frequency: str = "monthly",
    contribution: float = 0.0,
    contribution_frequency: str = "monthly",
    contribution_growth_percent: float = 0.0,
    contribution_type: ContributionType = "add",
    apply_tax: bool = False,
    consider_inflation: bool = False,
    inflation_rate: float = 0.0,
    target_amount: float = 0.0,
) -> InvestmentResult:
    """
    Универсальный расчёт инвестиционного калькулятора сложного процента.

    mode:
      - "income"       — считает доход/итоговую сумму по всем заданным параметрам
      - "rate"         — подбирает ставку так, чтобы итоговая сумма достигла target_amount
      - "principal"    — подбирает стартовый капитал так, чтобы итоговая сумма достигла target_amount
      - "term"         — подбирает срок (в месяцах) так, чтобы итоговая сумма достигла target_amount
      - "contribution" — подбирает размер взноса так, чтобы итоговая сумма достигла target_amount

    Для режимов, отличных от "income", соответствующий входной параметр
    (rate / principal / term_months / contribution) игнорируется — вместо
    него используется найденное значение.
    """
    _validate_common(term_months, rate, contribution_growth_percent, inflation_rate)

    if mode == "income":
        if principal <= 0:
            raise ValueError("Стартовый капитал должен быть больше нуля")
        return _compute_income_mode(
            principal, term_months, rate, reinvest, reinvest_frequency,
            contribution, contribution_frequency, contribution_growth_percent, contribution_type,
            apply_tax, consider_inflation, inflation_rate,
        )

    if target_amount <= 0:
        raise ValueError("Укажите целевую сумму, которой нужно достичь")

    if mode == "principal":
        return _solve_principal(
            term_months, rate, reinvest, reinvest_frequency,
            contribution, contribution_frequency, contribution_growth_percent, contribution_type,
            apply_tax, consider_inflation, inflation_rate, target_amount,
        )

    if mode == "contribution":
        if principal < 0:
            raise ValueError("Стартовый капитал не может быть отрицательным")
        return _solve_contribution(
            principal, term_months, rate, reinvest, reinvest_frequency,
            contribution_frequency, contribution_growth_percent, contribution_type,
            apply_tax, consider_inflation, inflation_rate, target_amount,
        )

    if mode == "rate":
        if principal <= 0:
            raise ValueError("Стартовый капитал должен быть больше нуля")
        return _solve_rate(
            principal, term_months, reinvest, reinvest_frequency,
            contribution, contribution_frequency, contribution_growth_percent, contribution_type,
            apply_tax, consider_inflation, inflation_rate, target_amount,
        )

    if mode == "term":
        if principal <= 0:
            raise ValueError("Стартовый капитал должен быть больше нуля")
        return _solve_term(
            principal, rate, reinvest, reinvest_frequency,
            contribution, contribution_frequency, contribution_growth_percent, contribution_type,
            apply_tax, consider_inflation, inflation_rate, target_amount,
        )

    raise ValueError(f"Неизвестный режим расчёта: {mode}")


def _validate_common(term_months, rate, contribution_growth_percent, inflation_rate):
    if term_months <= 0 or term_months > 600:
        raise ValueError("Срок инвестирования должен быть от 1 месяца до 50 лет")
    if rate < -99 or rate > 100_000:
        raise ValueError("Процентная ставка должна быть в диапазоне от -99 до 100 000%")
    if contribution_growth_percent < 0 or contribution_growth_percent > 100:
        raise ValueError("Ежегодное увеличение взноса должно быть от 0 до 100%")
    if inflation_rate < 0 or inflation_rate > 100:
        raise ValueError("Ставка инфляции должна быть от 0 до 100%")


# =============================================================================
# SOLVE-РЕЖИМЫ
# =============================================================================

def _solve_principal(term_months, rate, reinvest, reinvest_frequency,
                      contribution, contribution_frequency, contribution_growth_percent, contribution_type,
                      apply_tax, consider_inflation, inflation_rate, target_amount) -> InvestmentResult:
    # Итоговая сумма линейна по стартовому капиталу: final(P) = P * k + b
    _, _, final_at_0, _ = _simulate(0.0, term_months, rate, reinvest, reinvest_frequency,
                                     contribution, contribution_frequency, contribution_growth_percent, contribution_type)
    _, _, final_at_1, _ = _simulate(1.0, term_months, rate, reinvest, reinvest_frequency,
                                     contribution, contribution_frequency, contribution_growth_percent, contribution_type)
    k = final_at_1 - final_at_0
    b = final_at_0

    solved_ok = True
    if abs(k) < 1e-9:
        principal = 0.0
        solved_ok = False
    else:
        principal = (target_amount - b) / k
        if principal < 0:
            principal = 0.0
            solved_ok = False

    result = _compute_income_mode(
        max(principal, 0.01), term_months, rate, reinvest, reinvest_frequency,
        contribution, contribution_frequency, contribution_growth_percent, contribution_type,
        apply_tax, consider_inflation, inflation_rate,
    )
    result.mode = "principal"
    result.solved_ok = solved_ok
    return result


def _solve_contribution(principal, term_months, rate, reinvest, reinvest_frequency,
                         contribution_frequency, contribution_growth_percent, contribution_type,
                         apply_tax, consider_inflation, inflation_rate, target_amount) -> InvestmentResult:
    # Итоговая сумма линейна по размеру взноса: final(C) = C * k + b
    _, _, final_at_0, _ = _simulate(principal, term_months, rate, reinvest, reinvest_frequency,
                                     0.0, contribution_frequency, contribution_growth_percent, contribution_type)
    _, _, final_at_1, _ = _simulate(principal, term_months, rate, reinvest, reinvest_frequency,
                                     1.0, contribution_frequency, contribution_growth_percent, contribution_type)
    k = final_at_1 - final_at_0
    b = final_at_0

    solved_ok = True
    if abs(k) < 1e-9:
        contribution = 0.0
        solved_ok = False
    else:
        contribution = (target_amount - b) / k
        if contribution < 0:
            contribution = 0.0
            solved_ok = False

    result = _compute_income_mode(
        principal, term_months, rate, reinvest, reinvest_frequency,
        contribution, contribution_frequency, contribution_growth_percent, contribution_type,
        apply_tax, consider_inflation, inflation_rate,
    )
    result.mode = "contribution"
    result.solved_ok = solved_ok
    return result


def _solve_rate(principal, term_months, reinvest, reinvest_frequency,
                contribution, contribution_frequency, contribution_growth_percent, contribution_type,
                apply_tax, consider_inflation, inflation_rate, target_amount) -> InvestmentResult:
    def final_for_rate(r: float) -> float:
        _, _, final_amount, _ = _simulate(principal, term_months, r, reinvest, reinvest_frequency,
                                           contribution, contribution_frequency, contribution_growth_percent, contribution_type)
        return final_amount

    lo, hi = -99.0, 200.0
    max_hi = 100_000.0
    solved_ok = True

    # итоговая сумма растёт вместе со ставкой — если верхняя граница не
    # накрывает целевую сумму, расширяем её (нужно для высоких требуемых ставок,
    # например при небольшом капитале / коротком сроке / большой целевой сумме)
    while final_for_rate(hi) < target_amount and hi < max_hi:
        hi *= 2

    if final_for_rate(lo) > target_amount:
        rate = lo
        solved_ok = False
    elif final_for_rate(hi) < target_amount:
        rate = hi
        solved_ok = False
    else:
        for _ in range(80):
            mid = (lo + hi) / 2
            if final_for_rate(mid) < target_amount:
                lo = mid
            else:
                hi = mid
        rate = (lo + hi) / 2

    result = _compute_income_mode(
        principal, term_months, rate, reinvest, reinvest_frequency,
        contribution, contribution_frequency, contribution_growth_percent, contribution_type,
        apply_tax, consider_inflation, inflation_rate,
    )
    result.mode = "rate"
    result.solved_ok = solved_ok
    return result


def _solve_term(principal, rate, reinvest, reinvest_frequency,
                 contribution, contribution_frequency, contribution_growth_percent, contribution_type,
                 apply_tax, consider_inflation, inflation_rate, target_amount) -> InvestmentResult:
    def final_for_term(t: int) -> float:
        _, _, final_amount, _ = _simulate(principal, t, rate, reinvest, reinvest_frequency,
                                           contribution, contribution_frequency, contribution_growth_percent, contribution_type)
        return final_amount

    lo, hi = 1, 600
    max_hi = 12_000  # 1000 лет — разумный верхний предел для поиска

    # итоговая сумма растёт вместе со сроком — если верхняя граница не
    # накрывает целевую сумму, расширяем её (нужно для небольших ставок/капитала
    # и/или крупной целевой суммы, когда требуется очень долгий срок)
    while final_for_term(hi) < target_amount and hi < max_hi:
        hi = min(hi * 2, max_hi)

    solved_ok = True
    if final_for_term(hi) < target_amount:
        term_months = hi
        solved_ok = False
    elif final_for_term(lo) >= target_amount:
        term_months = lo
    else:
        while lo < hi:
            mid = (lo + hi) // 2
            if final_for_term(mid) < target_amount:
                lo = mid + 1
            else:
                hi = mid
        term_months = lo

    result = _compute_income_mode(
        principal, term_months, rate, reinvest, reinvest_frequency,
        contribution, contribution_frequency, contribution_growth_percent, contribution_type,
        apply_tax, consider_inflation, inflation_rate,
    )
    result.mode = "term"
    result.solved_ok = solved_ok
    return result


# =============================================================================
# СПРАВОЧНЫЕ ДАННЫЕ ДЛЯ ФОРМЫ
# =============================================================================

def get_frequency_options() -> list[dict]:
    return [
        {"value": "monthly", "label": "ежемесячно"},
        {"value": "quarterly", "label": "ежеквартально"},
        {"value": "semiannual", "label": "раз в полгода"},
        {"value": "annual", "label": "ежегодно"},
    ]


def get_contribution_frequency_options() -> list[dict]:
    return [
        {"value": "monthly", "label": "раз в месяц"},
        {"value": "quarterly", "label": "раз в квартал"},
        {"value": "semiannual", "label": "раз в полгода"},
        {"value": "annual", "label": "раз в год"},
    ]


def get_mode_options() -> list[dict]:
    return [
        {"value": "income", "label": "Доход"},
        {"value": "rate", "label": "Ставку"},
        {"value": "principal", "label": "Стартовый капитал"},
        {"value": "term", "label": "Срок достижения цели"},
        {"value": "contribution", "label": "Размер пополнений"},
    ]
