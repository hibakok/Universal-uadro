# @uadro
# @file    tools/uasm_assemble.py
# @layer   T0
# @branch  t0.uasm.assemble
# @desc    Сборка текста uAsm в образ UVM двумя проходами: проход 1
# @desc    назначает записям адреса и заполняет таблицу символов, проход 2
# @desc    кодирует записи в байты (SPEC/L2-UASM.txt, раздел 7).

"""Сборка uAsm v0.1 в двоичный образ UVM (ветвь t0.uasm.assemble).

Кирпичи: split_lines (текст в строки), wrap_error (ошибка с номером
строки «uAsm: строка N: текст»), define_symbol (определение метки или
константы в таблицу символов), pass1 (разбор строк, адреса записей,
символы), pass2 (кодирование записей в байты) и assemble (текст ->
образ).

Записи строк даёт ветвь t0.uasm.line, кодирование записей и их размеры
— ветвь t0.uasm.encode, таблица символов — ветвь t0.uasm.symbols.
Ошибки — пара (None, текст) по разделу 7 SPEC; исключения не
используются. Пустой текст (ноль записей) собирается в пустой образ.
"""

from tools.uasm_line import parse_line
from tools.uasm_symbols import symbol_define, symbols_new
from tools.uasm_encode import encode_record, record_size


# @method split_lines(text) -> list
# @in    text: str — исходный текст uAsm
# @out   lines: list — строки текста без концевых байтов CR
# @does  Делит текст на строки по символу LF; концевой CR каждой строки
# @does  снимается — текст с переводами CRLF собирается так же, как
# @does  с LF (SPEC/L2-UASM.txt, раздел 2); текст без LF даёт одну
# @does  строку, пустой текст — одну пустую строку.
def split_lines(text):
    return [line.rstrip("\r") for line in text.split("\n")]


# @method wrap_error(line_no, text) -> str
# @in    line_no: int — номер строки текста, начиная с 1
# @in    text: str — текст ошибки
# @out   msg: str — сообщение «uAsm: строка N: текст»
# @does  Приписывает ошибке номер строки по разделу 7 SPEC/L2-UASM.txt.
def wrap_error(line_no, text):
    return "uAsm: строка " + str(line_no) + ": " + text


# @method define_symbol(symbols, record, addr) -> str
# @in    symbols: dict — таблица символов (метод добавляет имя)
# @in    record: tuple — запись строки: ("label", имя) либо
# @in    ("const", имя, значение); записи других видов не определяют
# @in    ничего
# @in    addr: int — адрес байта следующей записи — значение метки
# @out   error: str — текст ошибки повторного определения либо None,
# @out   если имя определено впервые
# @does  Определяет символ прохода 1 (SPEC, разделы 3 и 7): метка —
# @does  адресом следующей записи, константа — своим значением.
# @depends symbol_define
def define_symbol(symbols, record, addr):
    if record[0] == "label":
        return symbol_define(symbols, record[1], addr)
    if record[0] == "const":
        return symbol_define(symbols, record[1], record[2])
    return None


# @method pass1(lines) -> tuple
# @in    lines: list — строки текста uAsm
# @out   triple: tuple — (записи, таблица символов, None) либо
# @out   (None, None, текст ошибки «uAsm: строка N: ...»); записи —
# @out   список пар (номер строки, запись) всех разобранных строк,
# @out   без пустых строк и комментариев
# @does  Проход 1 сборки (SPEC, раздел 7): разбирает строки в записи
# @does  (parse_line), первая ошибка прекращает проход; определяет
# @does  метки адресами и константы значениями (define_symbol);
# @does  накапливает адрес по размерам записей (record_size) — метка
# @does  получает адрес следующей записи, метка в конце текста —
# @does  адрес конца образа; метки и константы сами байтов не дают.
# @depends parse_line, define_symbol, record_size, wrap_error
def pass1(lines):
    items = []
    symbols = symbols_new()
    addr = 0
    for line_no, line in enumerate(lines, 1):
        record = parse_line(line)
        if record is None:
            continue
        if record[0] == "error":
            return None, None, wrap_error(line_no, record[1])
        error = define_symbol(symbols, record, addr)
        if error is not None:
            return None, None, wrap_error(line_no, error)
        addr += record_size(record)
        items.append((line_no, record))
    return items, symbols, None


# @method pass2(items, symbols) -> tuple
# @in    items: list — пары (номер строки, запись) прохода 1
# @in    symbols: dict — таблица символов прохода 1
# @out   pair: tuple — (образ, None) либо (None, текст ошибки
# @out   «uAsm: строка N: ...»)
# @does  Проход 2 сборки (SPEC, раздел 7): кодирует записи в байты
# @does  (encode_record) с подстановкой значений имён из таблицы
# @does  символов — ссылки вперёд уже разрешены проходом 1; первая
# @does  ошибка прекращает проход; образ — сцепление байтов записей
# @does  в порядке следования.
# @depends encode_record, wrap_error
def pass2(items, symbols):
    image = bytearray()
    for line_no, record in items:
        data, error = encode_record(record, symbols)
        if error is not None:
            return None, wrap_error(line_no, error)
        image += data
    return bytes(image), None


# @method assemble(text) -> tuple
# @in    text: str — исходный текст uAsm
# @out   pair: tuple — (образ, None) либо (None, текст ошибки
# @out   «uAsm: строка N: ...»); пустой текст — пустой образ
# @does  Собирает текст uAsm в двоичный образ UVM двумя проходами
# @does  (SPEC/L2-UASM.txt, раздел 7): split_lines -> pass1 -> pass2.
# @depends split_lines, pass1, pass2
def assemble(text):
    items, symbols, error = pass1(split_lines(text))
    if error is not None:
        return None, error
    return pass2(items, symbols)
