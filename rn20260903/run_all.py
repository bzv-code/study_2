"""
Главный скрипт запуска всех RSS-парсеров по очереди.

Запускает все скрипты последовательно с паузой 15 секунд между запусками.
Каждый скрипт выполняется в отдельном процессе через subprocess для изоляции.

Использование:
    python run_all.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from app.utils.logger_utils import get_logger

logger = get_logger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Список скриптов для запуска в порядке выполнения
SCRIPTS_TO_RUN = [
    "run_finam.py",
    "run_investing_commodities.py",
    "run_investing_company_news.py",
    "run_investing_currency_market.py",
    "run_investing_econom.py",
    "run_investing_economic_indicators.py",
    "run_investing_forex.py",
    "run_investing_forms_sec.py",
    "run_investing_futures_and_commodity_markets.py",
    "run_investing_income_reports.py",
    "run_investing_insider_trading.py",
    "run_investing_investment_ideas.py",
    "run_investing_market_analysts.py",
    "run_investing_profit_and_loss_statements.py",
    "run_investing_russia_and_neighbors.py",
    "run_investing_stock.py",
    "run_investing_stock_market.py",
    "run_investing_world_news.py",
    "run_profinance_econom.py",
    "run_profinance_fond.py",
    "run_profinance_forex.py",
]

# Пауза между запусками скриптов (в секундах)
DELAY_BETWEEN_SCRIPTS = 15

# Таймаут для каждого скрипта (в секундах)
SCRIPT_TIMEOUT = 600  # 10 минут на один скрипт

# Директория проекта
PROJECT_DIR = Path(__file__).resolve().parent

# Интерпретатор Python
PYTHON_EXECUTABLE = sys.executable


# =============================================================================
# SCRIPT EXECUTION
# =============================================================================

def run_script(script_name: str, timeout: int = SCRIPT_TIMEOUT) -> tuple[bool, int, str]:
    """
    Запустить один скрипт через subprocess.

    Returns:
        tuple: (success: bool, return_code: int, message: str)
    """
    script_path = PROJECT_DIR / script_name

    # Проверяем существование файла
    if not script_path.exists():
        return False, -1, f"Файл не найден: {script_path}"

    logger.info("RUN ALL: запуск скрипта: %s", script_name)
    start_time = time.time()

    try:
        # Запускаем скрипт в отдельном процессе
        result = subprocess.run(
            [PYTHON_EXECUTABLE, str(script_path)],
            cwd=str(PROJECT_DIR),
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        elapsed_time = time.time() - start_time

        if result.returncode == 0:
            message = f"Успешно завершён за {elapsed_time:.1f} сек"
            logger.info("RUN ALL: %s: %s", script_name, message)
            return True, result.returncode, message
        else:
            # Скрипт завершился с ошибкой
            error_output = result.stderr or result.stdout
            short_error = error_output[-500:] if len(error_output) > 500 else error_output
            message = f"Ошибка (код {result.returncode}) за {elapsed_time:.1f} сек"
            logger.error("RUN ALL: %s: %s", script_name, message)
            if short_error.strip():
                logger.error("RUN ALL: %s: последние строки вывода:\n%s", script_name, short_error)
            return False, result.returncode, message

    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        message = f"Таймаут после {elapsed_time:.1f} сек (лимит {timeout} сек)"
        logger.error("RUN ALL: %s: %s", script_name, message)
        return False, -2, message

    except KeyboardInterrupt:
        # Пользователь прервал выполнение
        raise

    except Exception as e:
        elapsed_time = time.time() - start_time
        message = f"Неожиданная ошибка за {elapsed_time:.1f} сек: {type(e).__name__}: {e}"
        logger.exception("RUN ALL: %s: %s", script_name, message)
        return False, -3, message


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_all_scripts() -> None:
    """Запустить все скрипты по очереди с паузами между ними."""

    total_scripts = len(SCRIPTS_TO_RUN)
    start_all = time.time()

    # Статистика
    success_count = 0
    failed_count = 0
    failed_scripts = []

    logger.info("=" * 70)
    logger.info("RUN ALL: НАЧАЛО ВЫПОЛНЕНИЯ ВСЕХ СКРИПТОВ")
    logger.info("=" * 70)
    logger.info("RUN ALL: всего скриптов: %s", total_scripts)
    logger.info("RUN ALL: пауза между скриптами: %s сек", DELAY_BETWEEN_SCRIPTS)
    logger.info("RUN ALL: таймаут одного скрипта: %s сек", SCRIPT_TIMEOUT)
    logger.info("RUN ALL: время начала: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 70)

    try:
        for index, script_name in enumerate(SCRIPTS_TO_RUN, start=1):
            logger.info("")
            logger.info("─" * 70)
            logger.info("RUN ALL: [%s/%s] %s", index, total_scripts, script_name)
            logger.info("─" * 70)

            success, return_code, message = run_script(script_name)

            if success:
                success_count += 1
            else:
                failed_count += 1
                failed_scripts.append((script_name, return_code, message))

            # Пауза между скриптами (кроме последнего)
            if index < total_scripts:
                logger.info("RUN ALL: пауза %s секунд до следующего скрипта...", DELAY_BETWEEN_SCRIPTS)
                time.sleep(DELAY_BETWEEN_SCRIPTS)

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("=" * 70)
        logger.warning("RUN ALL: ВЫПОЛНЕНИЕ ПРЕРВАНО ПОЛЬЗОВАТЕЛЕМ (Ctrl+C)")
        logger.warning("=" * 70)
        # Всё равно показываем статистику

    # =========================================================================
    # ФИНАЛЬНАЯ СТАТИСТИКА
    # =========================================================================
    elapsed_all = time.time() - start_all

    logger.info("")
    logger.info("=" * 70)
    logger.info("RUN ALL: ИТОГОВАЯ СТАТИСТИКА")
    logger.info("=" * 70)
    logger.info("RUN ALL: время начала: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("RUN ALL: общее время выполнения: %.1f сек (%.1f мин)",
                elapsed_all, elapsed_all / 60)
    logger.info("RUN ALL: всего скриптов: %s", total_scripts)
    logger.info("RUN ALL: успешно выполнено: %s", success_count)
    logger.info("RUN ALL: выполнено с ошибками: %s", failed_count)

    if failed_scripts:
        logger.info("")
        logger.info("RUN ALL: СКРИПТЫ С ОШИБКАМИ:")
        logger.info("-" * 70)
        for script_name, return_code, message in failed_scripts:
            logger.info("  ✗ %s", script_name)
            logger.info("    %s", message)
    else:
        logger.info("")
        logger.info("RUN ALL: ✓ ВСЕ СКРИПТЫ ВЫПОЛНЕНЫ УСПЕШНО!")

    logger.info("=" * 70)
    logger.info("RUN ALL: ЗАВЕРШЕНИЕ")
    logger.info("=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    try:
        run_all_scripts()
    except KeyboardInterrupt:
        logger.warning("RUN ALL: прервано пользователем")
        sys.exit(130)
    except Exception:
        logger.exception("RUN ALL: критическая ошибка")
        sys.exit(1)


if __name__ == "__main__":
    main()