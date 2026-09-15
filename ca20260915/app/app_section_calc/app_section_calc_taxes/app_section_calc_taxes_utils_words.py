"""
app_section_calc_taxes_utils_words.py
---------------------------------
Вспомогательные функции для форматирования денежных сумм:
- format_rub: форматирование в стиле "1 234,56 ₽"
- amount_to_words: перевод суммы прописью ("одна тысяча рублей 00 копеек")

Используются как Jinja2-фильтры в шаблонах раздела "Налоги".
"""

_ONES = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
_ONES_FEM = ['', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
_TEENS = [
    'десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать',
    'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать',
]
_TENS = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
_HUNDREDS = [
    '', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот',
    'шестьсот', 'семьсот', 'восемьсот', 'девятьсот',
]

_SCALE = [
    (1_000_000_000, ('миллиард', 'миллиарда', 'миллиардов'), False),
    (1_000_000, ('миллион', 'миллиона', 'миллионов'), False),
    (1_000, ('тысяча', 'тысячи', 'тысяч'), True),
]


def _three_digit_words(n: int, fem: bool = False) -> list[str]:
    words: list[str] = []
    hundreds, rem = divmod(n, 100)
    if hundreds:
        words.append(_HUNDREDS[hundreds])
    if 10 <= rem < 20:
        words.append(_TEENS[rem - 10])
    else:
        tens, ones = divmod(rem, 10)
        if tens:
            words.append(_TENS[tens])
        if ones:
            words.append((_ONES_FEM if fem else _ONES)[ones])
    return words


def _plural_form(n: int, forms: tuple[str, str, str]) -> str:
    abs_n = abs(int(n)) % 100
    last = abs_n % 10
    if 10 < abs_n < 20:
        return forms[2]
    if last == 1:
        return forms[0]
    if 1 < last < 5:
        return forms[1]
    return forms[2]


def _integer_to_words(n: int) -> str:
    if n == 0:
        return 'ноль'
    remainder = n
    parts: list[str] = []
    for divisor, forms, fem in _SCALE:
        count, remainder = divmod(remainder, divisor)
        if count > 0:
            parts.extend(_three_digit_words(count, fem))
            parts.append(_plural_form(count, forms))
    parts.extend(_three_digit_words(remainder, False))
    return ' '.join(p for p in parts if p)


def amount_to_words(value: float) -> str:
    """Переводит денежную сумму в текст, например: 'одна тысяча рублей 00 копеек'."""
    rounded = round(abs(float(value)), 2)
    rubles = int(rounded)
    kopecks = int(round((rounded - rubles) * 100))
    ruble_word = _plural_form(rubles, ('рубль', 'рубля', 'рублей'))
    kopeck_word = _plural_form(kopecks, ('копейка', 'копейки', 'копеек'))
    return f"{_integer_to_words(rubles)} {ruble_word} {kopecks:02d} {kopeck_word}"


def format_rub(value: float) -> str:
    """Форматирует сумму в стиле '1 234,56 ₽'."""
    rounded = round(float(value), 2)
    formatted = f"{rounded:,.2f}"
    formatted = formatted.replace(',', ' ').replace('.', ',')
    return f"{formatted} ₽"
