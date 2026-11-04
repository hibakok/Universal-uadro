# @uadro
# @file    tools/uasm_lex.py
# @layer   T0
# @branch  t0.uasm.lex
# @desc    Лексические кирпичи uAsm: числовые литералы (десятичные,
# @desc    шестнадцатеричные, двоичные, символьные, с минусом), имена
# @desc    и строковые литералы (SPEC/L2-UASM.txt, разделы 3-4).

"""Лексические кирпичи uAsm v0.1 (ветвь t0.uasm.lex).

Чистые функции без состояния: каждая распознаёт одну форму записи
и возвращает значение либо None, если текст форме не соответствует
(кроме in_literal_range — проверки диапазона). Номера строк и выбор
сообщений об ошибках — задачи ветвей t0.uasm.line и t0.uasm.assemble;
здесь только распознавание по SPEC/L2-UASM.txt, разделы 3-4.
"""

MIN_LITERAL = -(1 << 63)      # нижняя граница литерала (SPEC, раздел 4)
MAX_LITERAL = (1 << 64) - 1   # верхняя граница литерала

HEX_DIGITS = "0123456789abcdefABCDEF"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
NAME_FIRST = LETTERS + "_"
NAME_REST = NAME_FIRST + "0123456789"

CHAR_ESCAPES = {"n": 10, "r": 13, "t": 9, "\\": 92, "'": 39, "0": 0}
STR_ESCAPES = {"n": 10, "r": 13, "t": 9, "\\": 92, '"': 34, "0": 0}


# @method parse_dec(text) -> int
# @in    text: str — слово без пробелов
# @out   value: int — значение или None, если это не десятичный литерал
# @does  Распознаёт десятичный литерал: только ASCII-цифры 0-9, хотя бы
# @does  одна (SPEC, раздел 4).
def parse_dec(text):
    if not text or not (text.isascii() and text.isdigit()):
        return None
    return int(text)


# @method parse_hex(text) -> int
# @in    text: str — слово без пробелов
# @out   value: int — значение или None, если это не шестнадцатеричный
# @out   литерал
# @does  Распознаёт литерал с префиксом 0x (строчными) и цифрами
# @does  0-9A-Fa-f; после префикса — хотя бы одна цифра (SPEC, раздел 4).
def parse_hex(text):
    if not text.startswith("0x"):
        return None
    digits = text[2:]
    if not digits or any(ch not in HEX_DIGITS for ch in digits):
        return None
    return int(digits, 16)


# @method parse_bin(text) -> int
# @in    text: str — слово без пробелов
# @out   value: int — значение или None, если это не двоичный литерал
# @does  Распознаёт литерал с префиксом 0b (строчными) и цифрами 0/1;
# @does  после префикса — хотя бы одна цифра (SPEC, раздел 4).
def parse_bin(text):
    if not text.startswith("0b"):
        return None
    digits = text[2:]
    if not digits or any(ch not in "01" for ch in digits):
        return None
    return int(digits, 2)


# @method parse_char(text) -> int
# @in    text: str — слово без пробелов
# @out   value: int — код символа или None, если это не символьный
# @out   литерал
# @does  Распознаёт символьный литерал 'X' (SPEC, раздел 4): один
# @does  символ в одинарных кавычках — его код; либо escape '\n' '\r'
# @does  '\t' '\\' '\'' '\0' — код из таблицы CHAR_ESCAPES.
def parse_char(text):
    if len(text) == 3 and text[0] == "'" and text[2] == "'":
        return ord(text[1])
    if (len(text) == 4 and text[0] == "'" and text[1] == "\\"
            and text[3] == "'"):
        return CHAR_ESCAPES.get(text[2])
    return None


# @method literal_value(text) -> int
# @in    text: str — слово без пробелов и без знака
# @out   value: int — значение или None, если ни одна форма не подошла
# @does  Пробует формы без знака: десятичную, шестнадцатеричную,
# @does  двоичную, символьную (SPEC, раздел 4); кирпич parse_number.
# @depends parse_dec, parse_hex, parse_bin, parse_char
def literal_value(text):
    for parser in (parse_dec, parse_hex, parse_bin, parse_char):
        value = parser(text)
        if value is not None:
            return value
    return None


# @method parse_number(text) -> int
# @in    text: str — слово без пробелов, возможно с минусом впереди
# @out   value: int — значение или None, если это не числовой литерал
# @does  Полный числовой литерал (SPEC, раздел 4): необязательный минус
# @does  без пробела после него перед десятичной, шестнадцатеричной,
# @does  двоичной или символьной формой; диапазон проверяет отдельный
# @does  кирпич in_literal_range.
# @depends literal_value
def parse_number(text):
    negative = text.startswith("-")
    body = text[1:] if negative else text
    value = literal_value(body)
    if value is None:
        return None
    return -value if negative else value


# @method in_literal_range(value) -> bool
# @in    value: int — значение числового литерала
# @out   flag: bool — True, если значение внутри диапазона литералов
# @does  Проверяет границы литералов -2^63 .. 2^64-1 (SPEC, раздел 4);
# @does  значение вне диапазона — ошибка сборки «литерал вне диапазона».
def in_literal_range(value):
    return MIN_LITERAL <= value <= MAX_LITERAL


# @method is_name(text) -> bool
# @in    text: str — слово без пробелов
# @out   flag: bool — True, если слово — допустимое имя
# @does  Распознаёт имя [A-Za-z_][A-Za-z0-9_]* (SPEC, раздел 3): буква
# @does  или подчёркивание, затем буквы, цифры, подчёркивания; только
# @does  ASCII, регистр значим.
def is_name(text):
    if not text or text[0] not in NAME_FIRST:
        return False
    return all(ch in NAME_REST for ch in text[1:])


# @method parse_string(text) -> bytes
# @in    text: str — текст строкового литерала целиком, с кавычками
# @out   data: bytes — байты UTF-8 без кавычек или None, если литерал
# @out   неверен
# @does  Распознаёт строковый литерал "..." (SPEC, раздел 4): escape
# @does  \n \r \t \\ \" \0; незакрытая кавычка, посторонний символ после
# @does  закрывающей кавычки и неизвестный escape дают None.
def parse_string(text):
    if len(text) < 2 or text[0] != '"':
        return None
    out = bytearray()
    i = 1
    while i < len(text):
        ch = text[i]
        if ch == '"':
            if i != len(text) - 1:
                return None
            return bytes(out)
        if ch == "\\":
            if i + 1 >= len(text) or text[i + 1] not in STR_ESCAPES:
                return None
            out.append(STR_ESCAPES[text[i + 1]])
            i += 2
        else:
            out += ch.encode("utf-8")
            i += 1
    return None
