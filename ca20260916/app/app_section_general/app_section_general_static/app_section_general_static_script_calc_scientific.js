/**
 * app_section_general_static_script_calc_scientific.js
 * ------------------------------------------------------
 * Клиентская логика научного калькулятора на главной странице.
 * Полностью работает на клиенте (без обращения к серверу):
 *  - построение выражения по нажатиям кнопок
 *  - безопасный разбор и вычисление выражения собственным
 *    рекурсивным парсером (без eval/Function)
 *  - режимы Deg/Rad для тригонометрии
 *  - история вычислений (в памяти вкладки) и Ans
 *  - копирование результата в буфер обмена
 */

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('sciCalc');
  if (!root) return;

  const valueEl = root.querySelector('.sci-calc-value');
  const historyLineEl = root.querySelector('.sci-calc-history-line');
  const historyPanel = root.querySelector('.sci-calc-history-panel');
  const historyList = root.querySelector('.sci-calc-history-list');
  const historyToggleBtn = root.querySelector('[data-action="history"]');
  const copyBtn = root.querySelector('[data-action="copy"]');
  const degRadButtons = root.querySelectorAll('[data-mode]');

  // ---------------------------------------------------------------------
  // Состояние калькулятора
  // ---------------------------------------------------------------------
  const state = {
    expr: '',            // текущее выражение в "человеческом" виде (для отображения)
    angleMode: 'deg',     // 'deg' | 'rad'
    lastAnswer: 0,
    history: [],          // [{expr, result}]
    justEvaluated: false, // true сразу после "=", чтобы новый ввод цифры начинал новое выражение
  };

  const MAX_HISTORY = 20;

  // ---------------------------------------------------------------------
  // Токенизация и разбор выражения (рекурсивный спуск)
  // Поддерживаемая грамматика:
  //   expr   := term (('+'|'-') term)*
  //   term   := power (('×'|'÷') power)*
  //   power  := postfix (('^'|'√') power)?      // '^': x^y, '√': x-й корень из y (правоассоц.)
  //   postfix:= unary ('!' | '%')*
  //   unary  := '-' unary | primary
  //   primary:= NUMBER | CONST | FUNC '(' expr ')' | '(' expr ')'
  // ---------------------------------------------------------------------

  const FUNCTIONS = new Set(['sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'ln', 'log', 'sqrt']);

  function tokenize(input) {
    const tokens = [];
    let i = 0;
    const isDigit = (c) => c >= '0' && c <= '9';
    const isAlpha = (c) => /[a-zA-Z]/.test(c);

    while (i < input.length) {
      const c = input[i];

      if (c === ' ') { i++; continue; }

      if (isDigit(c) || (c === '.' && isDigit(input[i + 1]))) {
        let j = i;
        while (j < input.length && (isDigit(input[j]) || input[j] === '.')) j++;
        tokens.push({ type: 'num', value: parseFloat(input.slice(i, j)) });
        i = j;
        continue;
      }

      if (c === 'π') {
        tokens.push({ type: 'num', value: Math.PI });
        i++;
        continue;
      }

      if (isAlpha(c)) {
        let j = i;
        while (j < input.length && isAlpha(input[j])) j++;
        const word = input.slice(i, j);
        if (FUNCTIONS.has(word)) {
          tokens.push({ type: 'func', value: word });
        } else if (word === 'pi') {
          tokens.push({ type: 'num', value: Math.PI });
        } else if (word === 'e') {
          tokens.push({ type: 'num', value: Math.E });
        } else if (word === 'Ans') {
          tokens.push({ type: 'num', value: state.lastAnswer });
        } else {
          throw new Error(`Неизвестный идентификатор: ${word}`);
        }
        i = j;
        continue;
      }

      if ('+-×÷^√!%()'.includes(c)) {
        tokens.push({ type: 'op', value: c });
        i++;
        continue;
      }

      throw new Error(`Недопустимый символ: ${c}`);
    }

    return tokens;
  }

  function parse(tokens) {
    let pos = 0;
    const peek = () => tokens[pos];
    const next = () => tokens[pos++];

    function parseExpr() {
      let value = parseTerm();
      while (peek() && peek().type === 'op' && (peek().value === '+' || peek().value === '-')) {
        const op = next().value;
        const rhs = parseTerm();
        value = op === '+' ? value + rhs : value - rhs;
      }
      return value;
    }

    function parseTerm() {
      let value = parsePower();
      while (peek() && peek().type === 'op' && (peek().value === '×' || peek().value === '÷')) {
        const op = next().value;
        const rhs = parsePower();
        if (op === '÷') {
          if (rhs === 0) throw new Error('Деление на ноль');
          value = value / rhs;
        } else {
          value = value * rhs;
        }
      }
      return value;
    }

    function parsePower() {
      const base = parsePostfix();
      if (peek() && peek().type === 'op' && (peek().value === '^' || peek().value === '√')) {
        const op = next().value;
        const exponent = parsePower(); // правоассоциативно
        if (op === '^') return Math.pow(base, exponent);
        // base √ exponent  ->  "base"-й корень из "exponent" = exponent ^ (1/base)
        if (base === 0) throw new Error('Деление на ноль');
        return Math.pow(exponent, 1 / base);
      }
      return base;
    }

    function parsePostfix() {
      let value = parseUnary();
      while (peek() && peek().type === 'op' && (peek().value === '!' || peek().value === '%')) {
        const op = next().value;
        if (op === '!') {
          value = factorial(value);
        } else {
          value = value / 100;
        }
      }
      return value;
    }

    function parseUnary() {
      if (peek() && peek().type === 'op' && peek().value === '-') {
        next();
        return -parseUnary();
      }
      return parsePrimary();
    }

    function parsePrimary() {
      const tok = peek();
      if (!tok) throw new Error('Незавершённое выражение');

      if (tok.type === 'num') {
        next();
        return tok.value;
      }

      if (tok.type === 'func') {
        next();
        expectOp('(');
        const arg = parseExpr();
        expectOp(')');
        return applyFunction(tok.value, arg);
      }

      if (tok.type === 'op' && tok.value === '(') {
        next();
        const value = parseExpr();
        expectOp(')');
        return value;
      }

      throw new Error('Ошибка в выражении');
    }

    function expectOp(op) {
      const tok = next();
      if (!tok || tok.type !== 'op' || tok.value !== op) {
        throw new Error(`Ожидался символ "${op}"`);
      }
    }

    const result = parseExpr();
    if (pos !== tokens.length) throw new Error('Ошибка в выражении');
    return result;
  }

  function factorial(n) {
    if (n < 0 || !Number.isInteger(n)) throw new Error('Факториал определён для целых ≥ 0');
    if (n > 170) throw new Error('Слишком большое число');
    let result = 1;
    for (let k = 2; k <= n; k++) result *= k;
    return result;
  }

  function applyFunction(name, arg) {
    const toRad = (v) => (state.angleMode === 'deg' ? (v * Math.PI) / 180 : v);
    const toOut = (v) => (state.angleMode === 'deg' ? (v * 180) / Math.PI : v);

    switch (name) {
      case 'sin': return Math.sin(toRad(arg));
      case 'cos': return Math.cos(toRad(arg));
      case 'tan': return Math.tan(toRad(arg));
      case 'asin': return toOut(Math.asin(arg));
      case 'acos': return toOut(Math.acos(arg));
      case 'atan': return toOut(Math.atan(arg));
      case 'ln': return Math.log(arg);
      case 'log': return Math.log10(arg);
      case 'sqrt': return Math.sqrt(arg);
      default: throw new Error(`Неизвестная функция: ${name}`);
    }
  }

  function evaluateExpression(expr) {
    if (!expr.trim()) return 0;
    const tokens = tokenize(expr);
    const result = parse(tokens);
    if (!Number.isFinite(result)) throw new Error('Некорректный результат');
    return result;
  }

  // ---------------------------------------------------------------------
  // Форматирование
  // ---------------------------------------------------------------------
  function formatNumber(n) {
    if (Object.is(n, -0)) n = 0;
    if (Math.abs(n) !== 0 && (Math.abs(n) < 1e-9 || Math.abs(n) >= 1e15)) {
      return n.toExponential(6).replace(/e\+?/, ' × 10^');
    }
    const rounded = Math.round(n * 1e10) / 1e10;
    return rounded.toString();
  }

  // ---------------------------------------------------------------------
  // Отрисовка
  // ---------------------------------------------------------------------
  function render() {
    valueEl.textContent = state.expr || '0';
    degRadButtons.forEach((btn) => {
      btn.classList.toggle('active-toggle', btn.dataset.mode === state.angleMode);
    });
  }

  function renderHistory() {
    historyList.innerHTML = '';
    if (state.history.length === 0) {
      historyList.innerHTML = '<div class="empty">История пуста</div>';
      return;
    }
    // Последние — сверху
    [...state.history].reverse().forEach((item) => {
      const row = document.createElement('div');
      row.className = 'sci-calc-history-item';
      row.innerHTML = `
        <span class="sci-calc-history-expr">${escapeHtml(item.expr)}</span>
        <span class="sci-calc-history-result">= ${escapeHtml(formatNumber(item.result))}</span>
      `;
      row.addEventListener('click', () => {
        state.expr = formatNumber(item.result);
        state.justEvaluated = true;
        render();
        historyPanel.classList.remove('open');
      });
      historyList.appendChild(row);
    });
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  // ---------------------------------------------------------------------
  // Действия
  // ---------------------------------------------------------------------
  function insert(token) {
    if (state.justEvaluated) {
      // После "=" новый разряд/функция начинает новое выражение,
      // а оператор продолжает работать с результатом (Ans)
      const continuesWithOperator = ['+', '-', '×', '÷', '^', '√', '!', '%'].includes(token);
      state.expr = continuesWithOperator ? state.expr : '';
      state.justEvaluated = false;
    }
    state.expr += token;
    render();
  }

  function backspace() {
    state.expr = state.expr.slice(0, -1);
    state.justEvaluated = false;
    render();
  }

  function clearEntry() {
    state.expr = '';
    state.justEvaluated = false;
    historyLineEl.textContent = '';
    render();
  }

  function allClear() {
    state.expr = '';
    state.justEvaluated = false;
    historyLineEl.textContent = '';
    render();
  }

  function evaluate() {
    if (!state.expr.trim()) return;
    try {
      const result = evaluateExpression(state.expr);
      historyLineEl.textContent = `${state.expr} =`;
      state.history.push({ expr: state.expr, result });
      if (state.history.length > MAX_HISTORY) state.history.shift();
      state.lastAnswer = result;
      state.expr = formatNumber(result);
      state.justEvaluated = true;
      renderHistory();
      render();
    } catch (err) {
      valueEl.textContent = 'Ошибка';
      state.expr = '';
      state.justEvaluated = false;
      setTimeout(render, 900);
    }
  }

  function insertAns() {
    insert('Ans');
  }

  function insertExp() {
    // Научная нотация: вставляем "×10^"
    insert('×10^');
  }

  async function copyResult() {
    const text = state.expr || '0';
    try {
      await navigator.clipboard.writeText(text);
      flashButton(copyBtn);
    } catch (err) {
      // Буфер обмена недоступен (например, нет разрешения) — тихо игнорируем
    }
  }

  function flashButton(btn) {
    if (!btn) return;
    btn.classList.add('active-toggle');
    setTimeout(() => btn.classList.remove('active-toggle'), 350);
  }

  // ---------------------------------------------------------------------
  // Обработчики
  // ---------------------------------------------------------------------
  root.querySelectorAll('[data-key]').forEach((btn) => {
    btn.addEventListener('click', () => insert(btn.dataset.key));
  });

  root.querySelectorAll('[data-func]').forEach((btn) => {
    btn.addEventListener('click', () => insert(`${btn.dataset.func}(`));
  });

  degRadButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      state.angleMode = btn.dataset.mode;
      render();
    });
  });

  root.querySelectorAll('[data-action]').forEach((btn) => {
    const action = btn.dataset.action;
    if (action === 'equals') btn.addEventListener('click', evaluate);
    if (action === 'clear-entry') btn.addEventListener('click', clearEntry);
    if (action === 'all-clear') btn.addEventListener('click', allClear);
    if (action === 'backspace') btn.addEventListener('click', backspace);
    if (action === 'ans') btn.addEventListener('click', insertAns);
    if (action === 'exp') btn.addEventListener('click', insertExp);
    if (action === 'copy') btn.addEventListener('click', copyResult);
    if (action === 'history') {
      btn.addEventListener('click', () => {
        historyPanel.classList.toggle('open');
      });
    }
  });

  // Ввод с клавиатуры
  root.setAttribute('tabindex', '0');
  root.addEventListener('keydown', (e) => {
    const map = { '*': '×', '/': '÷' };
    if (/^[0-9.()+\-]$/.test(e.key)) { insert(e.key); e.preventDefault(); }
    else if (map[e.key]) { insert(map[e.key]); e.preventDefault(); }
    else if (e.key === 'Enter' || e.key === '=') { evaluate(); e.preventDefault(); }
    else if (e.key === 'Backspace') { backspace(); e.preventDefault(); }
    else if (e.key === 'Escape') { allClear(); e.preventDefault(); }
  });

  renderHistory();
  render();
});
