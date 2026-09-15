/**
 * app_section_calc_taxes_static_script_nds.js
 * --------------------------------------------
 * Клиентская логика страницы калькулятора НДС:
 *  - переключение режима расчёта (подпись поля, required для одиночного ввода)
 *  - режим пакетного ввода (до 50 чисел, расчёт полностью на клиенте,
 *    т.к. на бэкенде нет отдельного маршрута для пакетного расчёта)
 *  - копирование значений в буфер обмена
 *
 * Одиночный расчёт (обычная отправка формы) всегда идёт через сервер —
 * это единственный источник истины для чисел и суммы прописью,
 * которые уже отрендерены в HTML при перезагрузке страницы.
 */

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('ndsForm');
  const modeGroup = document.getElementById('modeGroup');
  const modeOptions = modeGroup.querySelectorAll('.mode-option');
  const amountLabel = document.getElementById('amountLabel');
  const amountInput = document.getElementById('amount');
  const amountBatch = document.getElementById('amountBatch');
  const batchToggle = document.getElementById('batchToggle');
  const batchHint = document.getElementById('batchHint');
  const rateInput = document.getElementById('rate');
  const rateWarning = document.getElementById('rateWarning');
  const batchResultBox = document.getElementById('batchResult');
  const batchTableBody = document.getElementById('batchTableBody');
  const batchColBase = document.getElementById('batchColBase');
  const batchColTax = document.getElementById('batchColTax');
  const batchColTotal = document.getElementById('batchColTotal');

  if (!form) return;

  const labels = {
    add: 'Сумма без НДС (₽)',
    extract: 'Сумма',
    by_vat: 'Сумма НДС (₽)'
  };

  const taxColLabels = {
    add: rate => `НДС начислен (${rate}%)`,
    extract: rate => `НДС выделен (${rate}%)`,
    by_vat: rate => `НДС добавлен (${rate}%)`
  };

  let isBatchMode = false;

  function currentMode() {
    const checked = modeGroup.querySelector('input[name="action"]:checked');
    return checked ? checked.value : 'add';
  }

  modeOptions.forEach(opt => {
    opt.addEventListener('click', () => {
      modeOptions.forEach(o => o.classList.remove('active'));
      opt.classList.add('active');
      const mode = opt.querySelector('input').value;
      amountLabel.textContent = labels[mode] || labels.add;
      batchResultBox.style.display = 'none';
    });
  });

  batchToggle.addEventListener('click', () => {
    isBatchMode = !isBatchMode;
    batchToggle.classList.toggle('active', isBatchMode);
    amountInput.style.display = isBatchMode ? 'none' : 'block';
    amountInput.required = !isBatchMode;
    amountBatch.style.display = isBatchMode ? 'block' : 'none';
    batchHint.style.display = isBatchMode ? 'block' : 'none';
    batchResultBox.style.display = 'none';
  });

  function fmt(n) {
    return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₽';
  }

  /* ---------- core VAT math (mirrors app_section_calc_taxes_logic_nds.py) ---------- */
  function computeVat(mode, amount, rate) {
    let base, tax, total;
    if (mode === 'add') {
      base = amount;
      tax = amount * rate / 100;
      total = base + tax;
    } else if (mode === 'extract') {
      total = amount;
      tax = amount * rate / (100 + rate);
      base = total - tax;
    } else {
      tax = amount;
      base = rate > 0 ? tax * 100 / rate : 0;
      total = base + tax;
    }
    return { base, tax, total };
  }

  function runBatchCalculation() {
    const mode = currentMode();
    const rate = parseFloat((rateInput.value || '').replace(',', '.')) || 0;

    if (rate < 0 || rate > 100) {
      rateWarning.classList.add('show');
      batchResultBox.style.display = 'none';
      return;
    }
    rateWarning.classList.remove('show');

    const numbers = amountBatch.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line !== '')
      .map(line => parseFloat(line.replace(',', '.')))
      .filter(n => !isNaN(n))
      .slice(0, 50);

    batchColBase.textContent = 'Сумма до НДС';
    batchColTax.textContent = taxColLabels[mode] ? taxColLabels[mode](rate) : `НДС (${rate}%)`;
    batchColTotal.textContent = 'Сумма с НДС';

    batchTableBody.innerHTML = numbers.map(n => {
      const { base, tax, total } = computeVat(mode, n, rate);
      return `<tr><td>${fmt(base)}</td><td>${fmt(tax)}</td><td>${fmt(total)}</td></tr>`;
    }).join('');

    batchResultBox.style.display = numbers.length ? 'block' : 'none';
  }

  /* ---------- form submit: batch mode is client-only, single mode hits the server ---------- */
  form.addEventListener('submit', (e) => {
    if (isBatchMode) {
      e.preventDefault();
      runBatchCalculation();
    }
    // одиночный режим: обычная отправка формы на /taxes/nds (POST), результат рендерит сервер
  });

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
  function setupNumericInputs() {
    document.querySelectorAll('.integer-only').forEach(input => {
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

    document.querySelectorAll('.decimal-only').forEach(input => {
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
  }
  setupNumericInputs();

  /* ---------- initial label sync (in case server re-rendered a non-default action) ---------- */
  amountLabel.textContent = labels[currentMode()] || labels.add;
});
