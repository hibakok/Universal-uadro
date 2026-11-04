# @uadro
# @file    tests/test_uvm_ops_arith.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты арифметических и побитовых обработчиков: ADD, SUB, MUL,
# @desc    UDIV, UMOD, NEG, SHL, SHR, SAR, AND, OR, XOR, INV
# @desc    (SPEC/L0-UVM.txt, раздел 5).

"""Тесты группы «арифметика и биты» ветви t0.uvm.ops.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_ops_arith as ops


# @method word_result(op, a, b) -> list
# @in    op: callable — обработчик вида handler(m, imm)
# @in    a: int — первый операнд (кладётся глубже)
# @in    b: int — второй операнд (кладётся вершиной)
# @out   items: list — содержимое DS после обработки
# @does  Прогоняет бинарный обработчик над операндами и возвращает
# @does  снимок стека.
# @depends tk.small, uc.ds_push, tk.stack_of
def word_result(op, a, b):
    m = tk.small()
    uc.ds_push(m, a)
    uc.ds_push(m, b)
    op(m, 0)
    return tk.stack_of(m)


# @method unary_result(op, a) -> list
# @in    op: callable — обработчик вида handler(m, imm)
# @in    a: int — единственный операнд
# @out   items: list — содержимое DS после обработки
# @does  Прогоняет унарный обработчик ( a — р ) и возвращает снимок
# @does  стека (кирпич тестов NEG и INV).
# @depends tk.small, uc.ds_push, tk.stack_of
def unary_result(op, a):
    m = tk.small()
    uc.ds_push(m, a)
    op(m, 0)
    return tk.stack_of(m)


class TestAddSub(unittest.TestCase):
    """Сложение и вычитание по модулю 2^64 (SPEC, раздел 5)."""

    # @method test_add_sums() -> None
    # @in    нет
    # @out   нет
    # @does  ADD: 2 + 3 = 5.
    def test_add_sums(self):
        self.assertEqual(word_result(ops.op_add, 2, 3), [5])

    # @method test_add_wraps() -> None
    # @in    нет
    # @out   нет
    # @does  Сложение оборачивается по модулю 2^64.
    def test_add_wraps(self):
        self.assertEqual(word_result(ops.op_add, uc.WORD_MASK, 1), [0])

    # @method test_sub_differs() -> None
    # @in    нет
    # @out   нет
    # @does  SUB: a - b, где a глубже: 10 - 3 = 7.
    def test_sub_differs(self):
        self.assertEqual(word_result(ops.op_sub, 10, 3), [7])

    # @method test_sub_order_and_wrap() -> None
    # @in    нет
    # @out   нет
    # @does  SUB: 2 - 10 = -8 по модулю 2^64 — порядок операндов
    # @does  соблюдён, вычитание оборачивается.
    def test_sub_order_and_wrap(self):
        self.assertEqual(word_result(ops.op_sub, 2, 10),
                         [uc.to_word(-8)])

    # @method test_binary_op_needs_two_words() -> None
    # @in    нет
    # @out   нет
    # @does  Бинарная операция с одним словом на стеке — ловушка 2.
    def test_binary_op_needs_two_words(self):
        m = tk.small()
        uc.ds_push(m, 5)
        self.assertEqual(tk.trap_code(lambda: ops.op_add(m, 0)),
                         uc.TRAP_DS_EMPTY)


class TestMulDiv(unittest.TestCase):
    """Умножение и беззнаковое деление (SPEC, раздел 5)."""

    # @method test_mul_products() -> None
    # @in    нет
    # @out   нет
    # @does  MUL: 6 * 7 = 42.
    def test_mul_products(self):
        self.assertEqual(word_result(ops.op_mul, 6, 7), [42])

    # @method test_mul_keeps_low_64_bits() -> None
    # @in    нет
    # @out   нет
    # @does  MUL оставляет младшие 64 бита: (2^32+1)^2 = 2^33+1
    # @does  по модулю 2^64.
    def test_mul_keeps_low_64_bits(self):
        a = (1 << 32) + 1
        self.assertEqual(word_result(ops.op_mul, a, a),
                         [uc.to_word(a * a)])
        self.assertEqual(word_result(ops.op_mul, a, a), [(1 << 33) + 1])

    # @method test_udiv_quotients() -> None
    # @in    нет
    # @out   нет
    # @does  UDIV: 7 / 2 = 3; порядок: a глубже, b вершина.
    def test_udiv_quotients(self):
        self.assertEqual(word_result(ops.op_udiv, 7, 2), [3])
        self.assertEqual(word_result(ops.op_udiv, 2, 7), [0])

    # @method test_umod_remainders() -> None
    # @in    нет
    # @out   нет
    # @does  UMOD: 7 % 2 = 1.
    def test_umod_remainders(self):
        self.assertEqual(word_result(ops.op_umod, 7, 2), [1])

    # @method test_division_by_zero_traps() -> None
    # @in    нет
    # @out   нет
    # @does  UDIV и UMOD с нулевым делителем — ловушка 1.
    def test_division_by_zero_traps(self):
        m = tk.small()
        uc.ds_push(m, 7)
        uc.ds_push(m, 0)
        self.assertEqual(tk.trap_code(lambda: ops.op_udiv(m, 0)),
                         uc.TRAP_DIV0)
        m = tk.small()
        uc.ds_push(m, 7)
        uc.ds_push(m, 0)
        self.assertEqual(tk.trap_code(lambda: ops.op_umod(m, 0)),
                         uc.TRAP_DIV0)


class TestNegInv(unittest.TestCase):
    """Отрицание и инверсия (SPEC, раздел 5)."""

    # @method test_neg_negates() -> None
    # @in    нет
    # @out   нет
    # @does  NEG: 5 -> 0-5 = -5 по модулю 2^64; 0 -> 0; 2^63 -> 2^63
    # @does  (самое отрицательное переходит в себя).
    def test_neg_negates(self):
        self.assertEqual(unary_result(ops.op_neg, 5), [uc.to_word(-5)])
        self.assertEqual(unary_result(ops.op_neg, 0), [0])
        self.assertEqual(unary_result(ops.op_neg, 1 << 63), [1 << 63])

    # @method test_inv_inverts_bits() -> None
    # @in    нет
    # @out   нет
    # @does  INV: ~0 = WORD_MASK, ~WORD_MASK = 0, ~0xF0 — инверсия
    # @does  младших бит.
    def test_inv_inverts_bits(self):
        self.assertEqual(unary_result(ops.op_inv, 0), [uc.WORD_MASK])
        self.assertEqual(unary_result(ops.op_inv, uc.WORD_MASK), [0])
        self.assertEqual(unary_result(ops.op_inv, 0xF0),
                         [uc.WORD_MASK ^ 0xF0])


class TestShifts(unittest.TestCase):
    """Сдвиги SHL, SHR, SAR (SPEC, раздел 5)."""

    # @method test_shl_shifts_left() -> None
    # @in    нет
    # @out   нет
    # @does  SHL: 1 << 3 = 8; бит, ушедший за 2^64, теряется (2 << 63
    # @does  = 0).
    def test_shl_shifts_left(self):
        self.assertEqual(word_result(ops.op_shl, 1, 3), [8])
        self.assertEqual(word_result(ops.op_shl, 2, 63), [0])

    # @method test_shl_truncates_count() -> None
    # @in    нет
    # @out   нет
    # @does  SHL усекает счётчик до 0..63: n = 65 работает как n = 1.
    def test_shl_truncates_count(self):
        self.assertEqual(word_result(ops.op_shl, 1, 65), [2])

    # @method test_shr_shifts_logical() -> None
    # @in    нет
    # @out   нет
    # @does  SHR — логический сдвиг: WORD_MASK >> 60 = 15; слово со
    # @does  старшим битом сдвигается без знакового расширения.
    def test_shr_shifts_logical(self):
        self.assertEqual(word_result(ops.op_shr, uc.WORD_MASK, 60), [15])
        self.assertEqual(word_result(ops.op_shr, uc.to_word(-8), 1),
                         [(1 << 63) - 4])

    # @method test_sar_shifts_arithmetic() -> None
    # @in    нет
    # @out   нет
    # @does  SAR — арифметический сдвиг: -8 >> 1 = -4 по знаку;
    # @does  положительные сдвигаются как логически.
    def test_sar_shifts_arithmetic(self):
        self.assertEqual(word_result(ops.op_sar, uc.to_word(-8), 1),
                         [uc.to_word(-4)])
        self.assertEqual(word_result(ops.op_sar, 8, 2), [2])

    # @method test_sar_truncates_count() -> None
    # @in    нет
    # @out   нет
    # @does  SAR усекает счётчик до 0..63: n = 65 работает как n = 1.
    def test_sar_truncates_count(self):
        self.assertEqual(word_result(ops.op_sar, uc.to_word(-8), 65),
                         [uc.to_word(-4)])


class TestBitwise(unittest.TestCase):
    """Побитовые AND, OR, XOR (SPEC, раздел 5)."""

    # @method test_and_or_xor_tables() -> None
    # @in    нет
    # @out   нет
    # @does  AND, OR, XOR работают по таблице истинности на паре
    # @does  0b1100 и 0b1010.
    def test_and_or_xor_tables(self):
        a, b = 0b1100, 0b1010
        self.assertEqual(word_result(ops.op_and, a, b), [0b1000])
        self.assertEqual(word_result(ops.op_or, a, b), [0b1110])
        self.assertEqual(word_result(ops.op_xor, a, b), [0b0110])


if __name__ == "__main__":
    unittest.main()
