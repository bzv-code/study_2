"""
app_section_general_logic_catalog.py
-------------------------------------
Бизнес-логика главной страницы агрегатора.
Формирует каталог доступных разделов и калькуляторов для витрины на "/".

Чистые функции/dataclass без зависимостей от FastAPI — маршруты
(app_section_general_routes.py) только вызывают get_sections_catalog()
и передают результат в шаблон.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CalculatorEntry:
    """Один калькулятор внутри раздела."""

    name: str
    description: str
    url: str
    is_available: bool = True


@dataclass(frozen=True)
class SectionEntry:
    """Раздел агрегатора (напр. «Налоги»), объединяющий набор калькуляторов."""

    name: str
    description: str
    url: str
    icon: str
    calculators: list[CalculatorEntry] = field(default_factory=list)

    @property
    def calculators_count(self) -> int:
        return len(self.calculators)


def get_sections_catalog() -> list[SectionEntry]:
    """
    Возвращает каталог всех разделов агрегатора для отображения на главной.

    При добавлении нового раздела калькуляторов — дополнить этот список
    новой записью SectionEntry, не затрагивая маршруты и шаблон.
    """

    return [
        SectionEntry(
            name="Налоги",
            description=(
                "Расчёт налога на добавленную стоимость и налога на доходы "
                "физических лиц с учётом актуальных ставок."
            ),
            url="/taxes",
            icon="\U0001f4c8",  # 📈
            calculators=[
                CalculatorEntry(
                    name="Калькулятор НДС",
                    description="Начисление, выделение НДС из суммы",
                    url="/taxes/nds",
                ),
                CalculatorEntry(
                    name="Калькулятор НДФЛ",
                    description="Расчёт НДФЛ с учётом прогрессивной шкалы",
                    url="/taxes/ndfl",
                ),
            ],
        ),
        SectionEntry(
            name="Инвестиции",
            description=(
                "Расчёт доходности вклада с учётом капитализации, "
                "пополнений, снятий и налога на процентный доход."
            ),
            url="/investment",
            icon="\U0001f4b0",  # 💰
            calculators=[
                CalculatorEntry(
                    name="Калькулятор вкладов",
                    description="Доходность вклада с капитализацией, пополнениями и налогом",
                    url="/investment/deposit",
                ),
                CalculatorEntry(
                    name="Калькулятор сложного процента",
                    description="Доходность инвестиций с реинвестированием и пополнением, подбор ставки, срока или капитала",
                    url="/investment/compound-interest",
                ),
            ],
        ),
    ]


def get_total_calculators_count() -> int:
    """Суммарное количество доступных калькуляторов во всех разделах."""

    return sum(section.calculators_count for section in get_sections_catalog())
