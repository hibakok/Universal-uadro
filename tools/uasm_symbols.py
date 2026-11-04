# @uadro
# @file    tools/uasm_symbols.py
# @layer   T0
# @branch  t0.uasm.symbols
# @desc    Таблица символов uAsm: имя -> значение; единое пространство
# @desc    имён для меток и констант; повторное определение имени —
# @desc    ошибка (SPEC/L2-UASM.txt, разделы 3 и 7).

"""Таблица символов uAsm v0.1 (ветвь t0.uasm.symbols).

Хранилище пар «имя -> значение» для двух проходов ассемблера (SPEC,
раздел 7): проход 1 определяет символы (метки — адресами, константы —
значениями литералов), проход 2 подставляет значения. Пространство имён
одно для меток и констант (SPEC, раздел 3), поэтому ветвь не различает,
откуда пришло имя. Таблица — обычный словарь; имена и значения приносит
вызывающий код (будущая ветвь t0.uasm.assemble).
"""


# @method symbols_new() -> dict
# @in    нет
# @out   table: dict — пустая таблица символов
# @does  Создаёт новую пустую таблицу символов.
def symbols_new():
    return {}


# @method symbol_define(table, name, value) -> str
# @in    table: dict — таблица символов (метод добавляет имя)
# @in    name: str — имя символа
# @in    value: int — значение символа (адрес или число)
# @out   error: str — текст ошибки «повторное определение имени X»
# @out   либо None, если имя определено впервые
# @does  Определяет символ «имя -> значение» (SPEC, раздел 3);
# @does  повторное определение — ошибка, прежнее значение сохраняется.
def symbol_define(table, name, value):
    if name in table:
        return "повторное определение имени " + name
    table[name] = value
    return None


# @method symbol_get(table, name) -> int
# @in    table: dict — таблица символов
# @in    name: str — имя символа
# @out   value: int — значение символа или None, если имя не определено
# @does  Выбирает значение символа по имени для подстановки в проход 2
# @does  (SPEC, разделы 3 и 7).
def symbol_get(table, name):
    return table.get(name)
