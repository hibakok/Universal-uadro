# @uadro
# @file    tests/test_uasm_symbols.py
# @layer   T0
# @branch  t0.uasm.symbols
# @desc    Тесты таблицы символов uAsm: создание, выборка, определение,
# @desc    повторное определение имени, единое пространство имён
# @desc    (SPEC/L2-UASM.txt, раздел 3).

"""Тесты ветви t0.uasm.symbols (tools/uasm_symbols.py).

Пространство имён одно для меток и констант: любое второе определение
имени — ошибка «повторное определение имени X», прежнее значение
сохраняется.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.uasm_symbols import symbol_define, symbol_get, symbols_new


class TestSymbolsNew(unittest.TestCase):
    """Создание таблицы (SPEC, раздел 7: проход 1)."""

    # @method test_new_is_empty() -> None
    # @in    нет
    # @out   нет
    # @does  Новая таблица пуста: выборка любого имени даёт None.
    def test_new_is_empty(self):
        table = symbols_new()
        self.assertEqual(table, {})
        self.assertIsNone(symbol_get(table, "x"))


class TestSymbolDefine(unittest.TestCase):
    """Определение символов (SPEC, раздел 3)."""

    # @method test_define_and_get() -> None
    # @in    нет
    # @out   нет
    # @does  Первое определение имени — не ошибка, значение читается
    # @does  обратно; разные имена не мешают друг другу.
    def test_define_and_get(self):
        table = symbols_new()
        self.assertIsNone(symbol_define(table, "start", 0))
        self.assertIsNone(symbol_define(table, "size", 4096))
        self.assertEqual(symbol_get(table, "start"), 0)
        self.assertEqual(symbol_get(table, "size"), 4096)

    # @method test_define_twice_is_error() -> None
    # @in    нет
    # @out   нет
    # @does  Повторное определение имени — ошибка с именем в тексте;
    # @does  прежнее значение сохраняется.
    def test_define_twice_is_error(self):
        table = symbols_new()
        symbol_define(table, "x", 1)
        self.assertEqual(symbol_define(table, "x", 2),
                         "повторное определение имени x")
        self.assertEqual(symbol_get(table, "x"), 1)

    # @method test_label_and_const_share_namespace() -> None
    # @in    нет
    # @out   нет
    # @does  Метка и константа с одним именем конфликтуют: пространство
    # @does  имён одно (SPEC, раздел 3).
    def test_label_and_const_share_namespace(self):
        table = symbols_new()
        self.assertIsNone(symbol_define(table, "entry", 8))    # метка
        self.assertEqual(symbol_define(table, "entry", 5),     # константа
                         "повторное определение имени entry")

    # @method test_boundary_values() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль, отрицательные и 64-битные значения хранятся как есть.
    def test_boundary_values(self):
        table = symbols_new()
        cases = (("z", 0), ("min", -9223372036854775808),
                 ("max", 18446744073709551615))
        for name, value in cases:
            self.assertIsNone(symbol_define(table, name, value), name)
            self.assertEqual(symbol_get(table, name), value, name)


if __name__ == "__main__":
    unittest.main()
