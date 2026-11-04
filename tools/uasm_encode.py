# @uadro
# @file    tools/uasm_encode.py
# @layer   T0
# @branch  t0.uasm.encode
# @desc    Кодирование записей uAsm в байты: слово little-endian с
# @desc    оборачиванием отрицательных, байт DB, разрешение операнда
# @desc    (литерал или имя), инструкции и директивы данных, размер
# @desc    записи для адресов прохода 1 (SPEC/L2-UASM.txt, разделы 4-7).

"""Кодирование записей uAsm v0.1 в байты (ветвь t0.uasm.encode).

Кирпичи: to_word (значение слова — отрицательные оборачиваются
по модулю 2^64), word_le (восемь байтов little-endian), byte_of (байт
директивы DB), resolve_value (операнд — числовой литерал или имя из
таблицы символов), encode_instr, encode_db, encode_dw (записи в байты),
record_size (размер записи для адресов прохода 1) и encode_record
(запись целиком — вход прохода 2).

Записи строит ветвь t0.uasm.line; значения имён даёт таблица символов
ветви t0.uasm.symbols; коды опкодов — таблица ветви t0.uvm.table.
Байты DS/DZ запись уже несёт готовыми — они проходят насквозь. Кирпичи
полны: проверяют и входы, которые разбор строки отверг бы сам, — ветвь
пригодна и для прямого построения записей без текстового фронтенда.
Ошибки — пара (None, текст) по разделу 7 SPEC; исключения
не используются.
"""

from tools.uasm_lex import in_literal_range, is_name, parse_number
from tools.uasm_symbols import symbol_get
from tools.uasm_line import bad_literal
from tools.uvm_table import entry_by_mnemonic

WORD_MOD = 1 << 64     # модуль оборачивания слова UVM (SPEC/L0-UVM.txt)
WORD_SIZE = 8           # размер слова в байтах: поле imm64 и аргумент DW


# @method to_word(value) -> int
# @in    value: int — значение литерала или имени (любое целое)
# @out   word: int — слово 0..2^64-1
# @does  Приводит значение к слову UVM: отрицательные значения
# @does  оборачиваются по модулю 2^64 (SPEC/L0-UVM.txt, раздел 1;
# @does  SPEC/L2-UASM.txt, раздел 4).
def to_word(value):
    return value % WORD_MOD


# @method word_le(value) -> bytes
# @in    value: int — значение (литерал, имя или слово)
# @out   data: bytes — восемь байтов little-endian
# @does  Кодирует слово: поле imm64 инструкции и аргумент DW — восемь
# @does  байтов little-endian (SPEC/L2-UASM.txt, разделы 5-6); отрицательное
# @does  значение сначала оборачивается по модулю 2^64.
# @depends to_word
def word_le(value):
    return to_word(value).to_bytes(WORD_SIZE, "little")


# @method byte_of(value) -> int
# @in    value: int — значение аргумента директивы DB
# @out   byte: int — байт 0..255 либо None, если значение вне диапазона
# @does  Проверяет аргумент DB на диапазон 0..255 (SPEC/L2-UASM.txt,
# @does  раздел 6); None — сигнал ошибки «байт вне диапазона».
def byte_of(value):
    if 0 <= value <= 255:
        return value
    return None


# @method resolve_value(text, symbols) -> tuple
# @in    text: str — операнд инструкции или аргумент DB/DW
# @in    symbols: dict — таблица символов (ветвь t0.uasm.symbols)
# @out   pair: tuple — (значение, None) либо (None, текст ошибки):
# @out   «литерал вне диапазона», «неизвестное имя X», «плохой литерал X»
# @does  Разрешает операнд в значение (SPEC/L2-UASM.txt, разделы 5-6):
# @does  числовой литерал раздела 4 в диапазоне -2^63..2^64-1 либо имя
# @does  из таблицы символов. Значение имени берётся как есть, без
# @does  оборачивания: оборачивание отрицательных — при кодировании,
# @does  кирпичами to_word и word_le.
# @depends parse_number, in_literal_range, is_name, symbol_get, bad_literal
def resolve_value(text, symbols):
    value = parse_number(text)
    if value is not None:
        if not in_literal_range(value):
            return None, "литерал вне диапазона"
        return value, None
    if is_name(text):
        value = symbol_get(symbols, text)
        if value is None:
            return None, "неизвестное имя " + text
        return value, None
    return None, bad_literal(text)


# @method encode_instr(mnemonic, operand, symbols) -> tuple
# @in    mnemonic: str — мнемоника опкода
# @in    operand: str — операнд-текст либо None (операнда нет)
# @in    symbols: dict — таблица символов
# @out   pair: tuple — (байты, None) либо (None, текст ошибки):
# @out   «неизвестная мнемоника X», «нет операнда у X», «лишний операнд
# @out   у X» и ошибки кирпича resolve_value
# @does  Кодирует инструкцию (SPEC/L2-UASM.txt, раздел 5): байт опкода;
# @does  у опкода с полем imm64 (PUSH, PICK, JMP, JZ, JNZ, CALL, HALT,
# @does  SYS) — ещё восемь байтов little-endian со значением операнда.
# @does  Кирпич полон: проверяет и вход, который разбор строки отверг бы.
# @depends entry_by_mnemonic, resolve_value, word_le
def encode_instr(mnemonic, operand, symbols):
    entry = entry_by_mnemonic(mnemonic)
    if entry is None:
        return None, "неизвестная мнемоника " + mnemonic
    if not entry[3]:
        if operand is not None:
            return None, "лишний операнд у " + mnemonic
        return bytes([entry[0]]), None
    if operand is None:
        return None, "нет операнда у " + mnemonic
    value, error = resolve_value(operand, symbols)
    if error is not None:
        return None, error
    return bytes([entry[0]]) + word_le(value), None


# @method encode_db(args, symbols) -> tuple
# @in    args: tuple — аргументы-тексты директивы DB
# @in    symbols: dict — таблица символов
# @out   pair: tuple — (байты, None) либо (None, текст ошибки):
# @out   «пустая директива DB», «байт вне диапазона» и ошибки кирпича
# @out   resolve_value
# @does  Кодирует DB (SPEC/L2-UASM.txt, раздел 6): один байт на аргумент;
# @does  значение аргумента разрешает resolve_value, байт даёт byte_of.
# @depends resolve_value, byte_of
def encode_db(args, symbols):
    if not args:
        return None, "пустая директива DB"
    out = bytearray()
    for arg in args:
        value, error = resolve_value(arg, symbols)
        if error is not None:
            return None, error
        byte = byte_of(value)
        if byte is None:
            return None, "байт вне диапазона"
        out.append(byte)
    return bytes(out), None


# @method encode_dw(args, symbols) -> tuple
# @in    args: tuple — аргументы-тексты директивы DW
# @in    symbols: dict — таблица символов
# @out   pair: tuple — (байты, None) либо (None, текст ошибки):
# @out   «пустая директива DW» и ошибки кирпича resolve_value
# @does  Кодирует DW (SPEC/L2-UASM.txt, раздел 6): восемь байтов
# @does  little-endian на аргумент; значение аргумента разрешает
# @does  resolve_value, слово кодирует word_le.
# @depends resolve_value, word_le
def encode_dw(args, symbols):
    if not args:
        return None, "пустая директива DW"
    out = bytearray()
    for arg in args:
        value, error = resolve_value(arg, symbols)
        if error is not None:
            return None, error
        out += word_le(value)
    return bytes(out), None


# @method record_size(record) -> int
# @in    record: tuple — запись ветви t0.uasm.line: метка, константа,
# @in    инструкция или директива данных
# @out   size: int — размер записи в байтах
# @does  Даёт размер записи для адресов прохода 1 (SPEC/L2-UASM.txt,
# @does  раздел 7): инструкция с полем imm64 — 9 байтов, без — 1; DB —
# @does  по байту на аргумент; DW — по 8 байтов; DS и DZ — длина готовых
# @does  байтов записи (нуль-байт DZ уже включён); метка, константа
# @does  и неизвестная запись байтов не дают — 0.
# @depends entry_by_mnemonic
def record_size(record):
    kind = record[0]
    if kind == "instr":
        entry = entry_by_mnemonic(record[1])
        if entry is None:
            return 0
        return 9 if entry[3] else 1
    if kind == "data":
        directive, payload = record[1], record[2]
        if directive == "DB":
            return len(payload)
        if directive == "DW":
            return WORD_SIZE * len(payload)
        return len(payload)      # DS и DZ: готовые байты записи
    return 0                     # метка, константа, иное


# @method encode_record(record, symbols) -> tuple
# @in    record: tuple — запись ветви t0.uasm.line
# @in    symbols: dict — таблица символов
# @out   pair: tuple — (байты, None) либо (None, текст ошибки): ошибки
# @out   кирпичей кодирования, текст записи-ошибки либо «плохая запись»
# @does  Кодирует запись целиком — вход прохода 2 сборки: инструкция —
# @does  encode_instr; DB и DW — encode_db/encode_dw; DS и DZ — готовые
# @does  байты записи; метка и константа байтов не дают; запись-ошибка
# @does  возвращает свой текст; записи вне контракта — «плохая запись».
# @depends encode_instr, encode_db, encode_dw
def encode_record(record, symbols):
    kind = record[0]
    if kind == "instr":
        return encode_instr(record[1], record[2], symbols)
    if kind == "data":
        directive = record[1]
        if directive == "DB":
            return encode_db(record[2], symbols)
        if directive == "DW":
            return encode_dw(record[2], symbols)
        if directive in ("DS", "DZ"):
            if isinstance(record[2], (bytes, bytearray)):
                return bytes(record[2]), None
    if kind in ("label", "const"):
        return b"", None
    if kind == "error":
        return None, record[1]
    return None, "плохая запись"
