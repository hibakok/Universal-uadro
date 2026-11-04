# @uadro
# @file    tests/test_uvm_ops_cmp.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты обработчиков сравнений: EQ, NEQ, LTU, GTU, LEU, GEU
# @desc    (SPEC/L0-UVM.txt, раздел 5).

"""Тесты группы «сравнения» ветви t0.uvm.ops.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_ops_cmp as ops


# @method flag_of(op_name, a, b) -> int
# @in    op_name: str — имя обработчика в модуле ops
# @in    a: int — первый операнд (кладётся глубже)
# @in    b: int — второй операнд (кладётся вершиной)
# @out   f: int — снятый со стека флаг 0/1
# @does  Прогоняет сравнение ( a b — ф ) и возвращает флаг.
# @depends tk.small, uc.ds_push, uc.ds_pop
def flag_of(op_name, a, b):
    m = tk.small()
    uc.ds_push(m, a)
    uc.ds_push(m, b)
    handler = getattr(ops, op_name)
    handler(m, 0)
    return uc.ds_pop(m)


class TestEquality(unittest.TestCase):
    """EQ и NEQ (SPEC, раздел 5)."""

    # @method test_eq_flags() -> None
    # @in    нет
    # @out   нет
    # @does  EQ: 1 при равенстве (включая 0 = 0), 0 при различии.
    def test_eq_flags(self):
        self.assertEqual(flag_of("op_eq", 7, 7), 1)
        self.assertEqual(flag_of("op_eq", 0, 0), 1)
        self.assertEqual(flag_of("op_eq", 7, 8), 0)

    # @method test_neq_flags() -> None
    # @in    нет
    # @out   нет
    # @does  NEQ: 1 при различии, 0 при равенстве.
    def test_neq_flags(self):
        self.assertEqual(flag_of("op_neq", 7, 8), 1)
        self.assertEqual(flag_of("op_neq", 7, 7), 0)


class TestUnsignedOrder(unittest.TestCase):
    """LTU, GTU, LEU, GEU — порядок без знака (SPEC, раздел 5)."""

    # @method test_ltu_flags() -> None
    # @in    нет
    # @out   нет
    # @does  LTU: a < b без знака; WORD_MASK больше 1.
    def test_ltu_flags(self):
        self.assertEqual(flag_of("op_ltu", 1, 2), 1)
        self.assertEqual(flag_of("op_ltu", 2, 1), 0)
        self.assertEqual(flag_of("op_ltu", uc.WORD_MASK, 1), 0)

    # @method test_gtu_flags() -> None
    # @in    нет
    # @out   нет
    # @does  GTU: a > b без знака; 1 меньше WORD_MASK.
    def test_gtu_flags(self):
        self.assertEqual(flag_of("op_gtu", 2, 1), 1)
        self.assertEqual(flag_of("op_gtu", 1, 2), 0)
        self.assertEqual(flag_of("op_gtu", 1, uc.WORD_MASK), 0)

    # @method test_leu_flags() -> None
    # @in    нет
    # @out   нет
    # @does  LEU: a <= b, включая равенство.
    def test_leu_flags(self):
        self.assertEqual(flag_of("op_leu", 2, 2), 1)
        self.assertEqual(flag_of("op_leu", 2, 3), 1)
        self.assertEqual(flag_of("op_leu", 3, 2), 0)

    # @method test_geu_flags() -> None
    # @in    нет
    # @out   нет
    # @does  GEU: a >= b, включая равенство.
    def test_geu_flags(self):
        self.assertEqual(flag_of("op_geu", 2, 2), 1)
        self.assertEqual(flag_of("op_geu", 3, 2), 1)
        self.assertEqual(flag_of("op_geu", 2, 3), 0)

    # @method test_comparison_is_word_flag() -> None
    # @in    нет
    # @out   нет
    # @does  Флаг — слово 0 или 1, операнды снимаются со стека.
    def test_comparison_is_word_flag(self):
        m = tk.small()
        uc.ds_push(m, 1)
        uc.ds_push(m, 2)
        ops.op_ltu(m, 0)
        self.assertEqual(tk.stack_of(m), [1])
        self.assertEqual(uc.ds_pop(m), 1)

    # @method test_comparison_needs_two_words() -> None
    # @in    нет
    # @out   нет
    # @does  Сравнение с одним операндом — ловушка 2.
    def test_comparison_needs_two_words(self):
        m = tk.small()
        uc.ds_push(m, 1)
        self.assertEqual(tk.trap_code(lambda: ops.op_eq(m, 0)),
                         uc.TRAP_DS_EMPTY)


if __name__ == "__main__":
    unittest.main()
