/**
 * app_section_calc_investment_static_script_deposit.js
 * -------------------------------------------------------
 * Клиентская логика страницы калькулятора вкладов:
 *  - переключение подписи и доступности поля "Периодичность" в зависимости
 *    от капитализации;
 *  - показ/скрытие блоков пополнения, снятия и инфляции по чекбоксам;
 *  - быстрый выбор срока размещения кнопками;
 *  - копирование значений результата в буфер обмена;
 *  - ограничение полей ввода только цифрами.
 *
 * Сам расчёт всегда выполняется на сервере (POST-форма) — это единственный
 * источник истины для графика начисления процентов и налога.
 */

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('depositForm');
  if (!form) return;

  const capitalizationInput = document.getElementById('capitalization');
  const payoutFrequencyLabel = document.getElementById('payoutFrequencyLabel');

  function syncPayoutLabel() {
    if (!payoutFrequencyLabel) return;
    payoutFrequencyLabel.textContent = capitalizationInput.checked
      ? 'Периодичность капитализации'
      : 'Периодичность выплаты процентов';
  }
  if (capitalizationInput) {
    capitalizationInput.addEventListener('change', syncPayoutLabel);
    syncPayoutLabel();
  }

  /* ---------- toggle conditional blocks ---------- */
  function bindToggle(checkboxId, blockId) {
    const checkbox = document.getElementById(checkboxId);
    const block = document.getElementById(blockId);
    if (!checkbox || !block) return;
    checkbox.addEventListener('change', () => {
      block.style.display = checkbox.checked ? 'grid' : 'none';
    });
  }
  bindToggle('replenishment_enabled', 'replenishmentFields');
  bindToggle('withdrawal_enabled', 'withdrawalFields');
  bindToggle('consider_inflation', 'inflationFields');

  /* ---------- copy to clipboard ---------- */
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-copy');
      const target = document.getElementById(targetId);
      if (!target) return;
      const text = target.textContent;

      const markCopied = () => {
        btn.classList.add('copied');
        setTimeout(() => btn.classList.remove('copied'), 1200);
      };

      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(markCopied).catch(() => {});
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); markCopied(); } catch (err) { /* noop */ }
        document.body.removeChild(ta);
      }
    });
  });

  /* ---------- restrict free-text inputs to numeric characters ---------- */
  document.querySelectorAll('.integer-only').forEach((input) => {
    input.addEventListener('input', function () {
      this.value = this.value.replace(/[^0-9]/g, '');
    });
    input.addEventListener('paste', function (e) {
      e.preventDefault();
      const paste = (e.clipboardData || window.clipboardData).getData('text');
      const digitsOnly = paste.replace(/[^0-9]/g, '');
      if (digitsOnly) document.execCommand('insertText', false, digitsOnly);
    });
  });

  document.querySelectorAll('.decimal-only').forEach((input) => {
    input.addEventListener('input', function () {
      let value = this.value.replace(/[^0-9.,]/g, '').replace(',', '.');
      const parts = value.split('.');
      if (parts.length > 2) value = parts[0] + '.' + parts.slice(1).join('');
      this.value = value;
    });
    input.addEventListener('paste', function (e) {
      e.preventDefault();
      const paste = (e.clipboardData || window.clipboardData).getData('text');
      const cleanPaste = paste.replace(/[^0-9.,]/g, '').replace(',', '.');
      if (cleanPaste) document.execCommand('insertText', false, cleanPaste);
    });
  });
});
