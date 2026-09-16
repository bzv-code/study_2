/**
 * app_section_calc_investment_static_script_compound_interest.js
 * ------------------------------------------------------------------
 * Клиентская логика страницы калькулятора сложного процента:
 *  - переключение полей формы в зависимости от выбранного режима
 *    вычисления ("Доход"/"Ставку"/"Стартовый капитал"/"Срок"/"Пополнения");
 *  - показ/скрытие блоков реинвестирования, пополнений и инфляции;
 *  - копирование значений результата в буфер обмена;
 *  - построение линейного/столбчатого графика прироста (чистый SVG,
 *    без сторонних библиотек) по данным, зашитым в data-атрибуты;
 *  - ограничение полей ввода только цифрами.
 *
 * Сам расчёт всегда выполняется на сервере (POST-форма).
 */

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('compoundForm');
  if (!form) return;

  /* ---------- mode-dependent field visibility ---------- */
  const modeSelect = document.getElementById('mode');
  const targetAmountField = document.getElementById('targetAmountField');
  const principalField = document.getElementById('principalField');
  const rateField = document.getElementById('rateField');
  const termField = document.getElementById('termField');
  const contributionAmountRow = document.getElementById('contributionAmountRow');

  function syncModeFields() {
    const mode = modeSelect ? modeSelect.value : 'income';
    targetAmountField.style.display = mode === 'income' ? 'none' : 'block';
    principalField.style.display = mode === 'principal' ? 'none' : 'block';
    rateField.style.display = mode === 'rate' ? 'none' : 'block';
    termField.style.display = mode === 'term' ? 'none' : 'grid';
    if (contributionAmountRow) {
      contributionAmountRow.style.display = mode === 'contribution' ? 'none' : 'grid';
    }
  }
  if (modeSelect) modeSelect.addEventListener('change', syncModeFields);
  syncModeFields();

  /* ---------- toggle conditional blocks ---------- */
  function bindToggle(checkboxId, blockId, displayValue) {
    const checkbox = document.getElementById(checkboxId);
    const block = document.getElementById(blockId);
    if (!checkbox || !block) return;
    checkbox.addEventListener('change', () => {
      block.style.display = checkbox.checked ? displayValue : 'none';
    });
  }
  bindToggle('reinvest', 'reinvestFrequencyField', 'block');
  bindToggle('contribution_enabled', 'contributionFields', 'block');
  bindToggle('consider_inflation', 'inflationFields', 'block');

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

  /* ---------- numeric input restriction ---------- */
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
      let value = this.value.replace(/[^0-9.,-]/g, '').replace(',', '.');
      const parts = value.split('.');
      if (parts.length > 2) value = parts[0] + '.' + parts.slice(1).join('');
      this.value = value;
    });
  });

  /* ---------- growth chart (vanilla SVG) ---------- */
  const chartContainer = document.getElementById('growthChart');
  if (chartContainer) {
    const labels = (chartContainer.dataset.labels || '').split(',').filter(Boolean);
    const principal = (chartContainer.dataset.principal || '').split(',').filter(Boolean).map(Number);
    const contrib = (chartContainer.dataset.contrib || '').split(',').filter(Boolean).map(Number);
    const income = (chartContainer.dataset.income || '').split(',').filter(Boolean).map(Number);

    let chartType = 'line';

    function formatShort(value) {
      if (Math.abs(value) >= 1_000_000) return (value / 1_000_000).toFixed(1).replace('.0', '') + 'М';
      if (Math.abs(value) >= 1_000) return Math.round(value / 1_000) + 'к';
      return Math.round(value).toString();
    }

    function renderChart() {
      if (!labels.length) {
        chartContainer.innerHTML = '<p style="color:var(--ink-faint); font-size:.85rem; padding:20px;">Недостаточно данных для построения графика.</p>';
        return;
      }

      const width = 720;
      const height = 300;
      const padLeft = 56;
      const padBottom = 30;
      const padTop = 14;
      const padRight = 14;
      const plotW = width - padLeft - padRight;
      const plotH = height - padTop - padBottom;

      // стек: начальный капитал (низ) + пополнения + доход (верх), совпадает с чертой "Итоговая сумма"
      const totals = labels.map((_, i) => principal[i] + contrib[i] + income[i]);
      const maxVal = Math.max(...totals, 1);

      const xStep = labels.length > 1 ? plotW / (labels.length - 1) : plotW;
      const scaleY = (v) => padTop + plotH - (v / maxVal) * plotH;
      const scaleX = (i) => padLeft + i * xStep;

      let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`;

      // grid + y labels
      const gridSteps = 5;
      for (let g = 0; g <= gridSteps; g++) {
        const val = (maxVal / gridSteps) * g;
        const y = scaleY(val);
        svg += `<line class="grid-line" x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}"></line>`;
        svg += `<text class="axis-label" x="${padLeft - 8}" y="${y + 3}" text-anchor="end">${formatShort(val)}</text>`;
      }

      // x labels (skip some if too many)
      const labelEvery = Math.ceil(labels.length / 10);
      labels.forEach((lab, i) => {
        if (i % labelEvery === 0 || i === labels.length - 1) {
          svg += `<text class="axis-label" x="${scaleX(i)}" y="${height - padBottom + 16}" text-anchor="middle">${lab}</text>`;
        }
      });

      if (chartType === 'line') {
        const buildPath = (arr) => arr.map((v, i) => `${i === 0 ? 'M' : 'L'} ${scaleX(i)} ${scaleY(v)}`).join(' ');
        svg += `<path class="line-principal" d="${buildPath(principal)}"></path>`;
        svg += `<path class="line-contrib" d="${buildPath(contrib)}"></path>`;
        svg += `<path class="line-income" d="${buildPath(income)}"></path>`;
      } else {
        const barGroupWidth = xStep * 0.6;
        const barWidth = barGroupWidth / 2;
        labels.forEach((_, i) => {
          const x = scaleX(i) - barGroupWidth / 2;
          const yContrib = scaleY(contrib[i]);
          const yIncome = scaleY(income[i]);
          const baseline = scaleY(0);
          svg += `<rect class="bar-contrib" x="${x}" y="${yContrib}" width="${barWidth}" height="${Math.max(0, baseline - yContrib)}"></rect>`;
          svg += `<rect class="bar-income" x="${x + barWidth}" y="${yIncome}" width="${barWidth}" height="${Math.max(0, baseline - yIncome)}"></rect>`;
        });
      }

      svg += `</svg>`;
      chartContainer.innerHTML = svg;
    }

    renderChart();

    document.querySelectorAll('.chart-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.chart-toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        chartType = btn.getAttribute('data-chart-type');
        renderChart();
      });
    });
  }
});
