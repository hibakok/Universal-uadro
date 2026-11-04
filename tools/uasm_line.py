# @uadro
# @file    tools/uasm_line.py
# @layer   T0
# @branch  t0.uasm.line
# @desc    Разбор одной строки uAsm в запись: метка, константа, директива
# @desc    данных, инструкция, пустая строка или комментарий; порядок
# @desc    разбора — SPEC/L2-UASM.txt, раздел 7.

"""Разбор одной строки uAsm v0.1 (ветвь t0.uasm.line).

Кирпичи подготовки строки: find_outside_quotes (поиск символа вне
литералов в кавычках), strip_comment (комментарий «;» вне кавычек),
clean_line (комментарий плюс пробелы и табуляции по краям), find_eq
(знак «=» вне кавычек), split_first (первое слово и остаток строки),
split_words (разбиение на слова по пробелам и табуляциям).

parse_line разбирает строку в запись по порядку раздела 7 SPEC.
Виды записей (первый элемент — вид):

- None                    — пустая строка или строка-комментарий
- ("error", текст)        — ошибка разбора; номер строки добавит сборка
- ("label", имя)          — метка «имя:» (без двоеточия)
- ("const", имя, число)   — константа; значение — разобранный литерал
- ("instr", мнемоника, операнд) — операнд: текст либо None
- ("data", "DB", аргументы)     — аргументы: кортеж текстов
- ("data", "DW", аргументы)     — аргументы: кортеж текстов
- ("data", "DS", байты)         — байты UTF-8 строки
- ("data", "DZ", байты)         — байты UTF-8 строки плюс байт 0x00

Операнд инструкции и аргументы DB/DW остаются текстом: имя может быть
определено ниже по тексту, значения подставляет проход 2 ассемблера
(SPEC, раздел 7). Значение константы — всегда числовой литерал, поэтому
разбирается сразу. Исключения не используются: ошибка — запись
("error", текст) с текстом из раздела 7 SPEC.
"""

from tools.uasm_lex import in_literal_range, is_name, parse_number, parse_string
from tools.uvm_table import entry_by_mnemonic

DIRECTIVES = ("DB", "DW", "DS", "DZ")  # директивы данных (SPEC, раздел 6)
SPACES = " \t"                          # разделители слов (SPEC, раздел 2)
QUOTES = "'\""                          # кавычки литералов


# @method find_outside_quotes(text, ch) -> int
# @in    text: str — текст строки
# @in    ch: str — искомый символ (один)
# @out   index: int — позиция первого ch вне кавычек либо -1
# @does  Ищет первое вхождение символа вне литералов в кавычках: символы
# @does  внутри "..." и '...' не считаются, escape-кавычка не закрывает
# @does  литерал; незакрытая кавычка тянется до конца строки (SPEC,
# @does  раздел 2).
def find_outside_quotes(text, ch):
    i = 0
    quote = ""
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in QUOTES:
            quote = c
        elif c == ch:
            return i
        i += 1
    return -1


# @method strip_comment(line) -> str
# @in    line: str — исходная строка текста
# @out   text: str — строка до комментария (крайние пробелы остаются)
# @does  Удаляет комментарий: от «;» вне кавычек до конца строки (SPEC,
# @does  раздел 2); «;» внутри "..." и '...' не начинается.
# @depends find_outside_quotes
def strip_comment(line):
    i = find_outside_quotes(line, ";")
    return line if i < 0 else line[:i]


# @method clean_line(line) -> str
# @in    line: str — исходная строка текста
# @out   text: str — строка без комментария и крайних пробелов/табуляций
# @does  Готовит строку к разбору (SPEC, раздел 2): комментарий «;» вне
# @does  кавычек и пробелы с табуляциями по краям удаляются; пустой
# @does  результат — пустая строка или строка-комментарий.
# @depends strip_comment
def clean_line(line):
    return strip_comment(line).strip(SPACES)


# @method find_eq(text) -> int
# @in    text: str — подготовленная строка
# @out   index: int — позиция первого «=» вне кавычек либо -1
# @does  Ищет знак «=» константы вне литералов в кавычках (SPEC,
# @does  раздел 7, шаг 3 порядка разбора).
# @depends find_outside_quotes
def find_eq(text):
    return find_outside_quotes(text, "=")


# @method split_first(text) -> tuple
# @in    text: str — непустая строка без пробелов в начале
# @out   pair: tuple — (первое слово, остаток без пробелов в начале)
# @does  Отделяет первое слово (до пробела или табуляции) от остатка
# @does  строки; пробелы внутри остатка значимы (SPEC, раздел 2).
def split_first(text):
    i = 0
    while i < len(text) and text[i] not in SPACES:
        i += 1
    return text[:i], text[i:].lstrip(SPACES)


# @method split_words(text) -> list
# @in    text: str — остаток строки после первого слова
# @out   words: list — слова, разделённые пробелами и табуляциями
# @does  Разбивает текст на слова по последовательностям пробелов
# @does  и табуляций (SPEC, раздел 2); пустой текст даёт пустой список.
def split_words(text):
    words = []
    word = ""
    for c in text:
        if c in SPACES:
            if word:
                words.append(word)
                word = ""
        else:
            word += c
    if word:
        words.append(word)
    return words


# @method parse_label(word, rest) -> tuple
# @in    word: str — первое слово строки, оканчивающееся на «:»
# @in    rest: str — остаток строки после первого слова
# @out   record: tuple — ("label", имя) либо ("error", "плохое имя")
# @does  Разбирает метку «имя:» (SPEC, разделы 3 и 7): вся строка
# @does  целиком, имя — по разделу 3; плохое имя или лишние слова после
# @does  метки — «плохое имя».
# @depends is_name
def parse_label(word, rest):
    name = word[:-1]
    if not is_name(name) or rest:
        return ("error", "плохое имя")
    return ("label", name)


# @method bad_literal(text) -> str
# @in    text: str — текст, оказавшийся не числовым литералом
# @out   msg: str — текст ошибки «плохой литерал X»; без X, если текст
# @out   пуст («плохой литерал»)
# @does  Строит сообщение об ошибке по разделу 7 SPEC: X — слово или
# @does  остаток строки из исходного текста.
def bad_literal(text):
    if text:
        return "плохой литерал " + text
    return "плохой литерал"


# @method parse_const(text, eq) -> tuple
# @in    text: str — подготовленная строка со знаком «=» вне кавычек
# @in    eq: int — позиция знака «=»
# @out   record: tuple — ("const", имя, значение) либо ("error", текст):
# @out   «плохое имя», «плохой литерал X», «литерал вне диапазона»
# @does  Разбирает константу «имя = числовой литерал» (SPEC, раздел 3):
# @does  имя — по разделу 3, значение — литерал раздела 4 в диапазоне
# @does  -2^63..2^64-1; константа не может ссылаться на имя.
# @depends is_name, parse_number, in_literal_range, bad_literal
def parse_const(text, eq):
    left = text[:eq].strip(SPACES)
    right = text[eq + 1:].strip(SPACES)
    if not is_name(left):
        return ("error", "плохое имя")
    value = parse_number(right)
    if value is None:
        return ("error", bad_literal(right))
    if not in_literal_range(value):
        return ("error", "литерал вне диапазона")
    return ("const", left, value)


# @method parse_instr(mnemonic, imm64, rest) -> tuple
# @in    mnemonic: str — мнемоника из таблицы опкодов
# @in    imm64: bool — признак поля imm64 у опкода
# @in    rest: str — остаток строки после мнемоники
# @out   record: tuple — ("instr", мнемоника, операнд) либо ("error",
# @out   «нет операнда у X» или «лишний операнд у X»)
# @does  Разбирает инструкцию (SPEC, раздел 5): у опкода с полем imm64
# @does  операнд обязателен (остаётся текстом — значение подставит
# @does  проход 2), у остальных операнд запрещён.
def parse_instr(mnemonic, imm64, rest):
    if imm64:
        if not rest:
            return ("error", "нет операнда у " + mnemonic)
        return ("instr", mnemonic, rest)
    if rest:
        return ("error", "лишний операнд у " + mnemonic)
    return ("instr", mnemonic, None)


# @method parse_data(directive, rest) -> tuple
# @in    directive: str — DB, DW, DS или DZ
# @in    rest: str — остаток строки после директивы
# @out   record: tuple — ("data", директива, данные) либо ("error",
# @out   «пустая директива X» или «плохой строковый литерал»)
# @does  Разбирает директиву данных (SPEC, раздел 6): DB/DW — слова-
# @does  аргументы (тексты, значения подставит проход 2); DS/DZ — ровно
# @does  один строковый литерал в байтах UTF-8, DZ добавляет байт 0x00.
# @depends split_words, parse_string
def parse_data(directive, rest):
    if directive in ("DB", "DW"):
        args = split_words(rest)
        if not args:
            return ("error", "пустая директива " + directive)
        return ("data", directive, tuple(args))
    data = parse_string(rest)
    if data is None:
        return ("error", "плохой строковый литерал")
    if directive == "DZ":
        data = data + b"\x00"
    return ("data", directive, data)


# @method parse_line(line) -> tuple
# @in    line: str — исходная строка текста uAsm
# @out   record: tuple — запись строки либо None (пустая строка или
# @out   комментарий); виды записей перечислены в описании модуля
# @does  Разбирает одну строку по порядку раздела 7 SPEC/L2-UASM.txt:
# @does  метка «имя:» -> инструкция или директива данных -> константа
# @does  «=» -> иначе «неизвестная мнемоника X»; роль слова определяет
# @does  позиция, поэтому имя метки может совпасть с мнемоникой, а
# @does  константа с именем мнемоники невозможна.
# @depends clean_line, split_first, parse_label, parse_instr, parse_data, parse_const, find_eq, entry_by_mnemonic
def parse_line(line):
    text = clean_line(line)
    if not text:
        return None
    word, rest = split_first(text)
    if word.endswith(":"):
        return parse_label(word, rest)
    entry = entry_by_mnemonic(word)
    if entry is not None:
        return parse_instr(word, entry[3], rest)
    if word in DIRECTIVES:
        return parse_data(word, rest)
    eq = find_eq(text)
    if eq >= 0:
        return parse_const(text, eq)
    return ("error", "неизвестная мнемоника " + word)
