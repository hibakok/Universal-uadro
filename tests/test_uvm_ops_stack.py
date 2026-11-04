# @uadro
# @file    tests/test_uvm_ops_stack.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты стековых обработчиков: NOP, PUSH, DROP, DUP, SWAP, OVER,
# @desc    ROT, PICK (SPEC/L0-UVM.txt, раздел 5).

"""Тесты группы «стек» ветви t0.uvm.ops (tools/uvm_ops_stack.py).

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_ops_stack as ops


class TestStackOps(unittest.TestCase):
    """Стековые опкоды (SPEC, раздел 5)."""

    # @method test_nop_changes_nothing() -> None
    # @in    нет
    # @out   нет
    # @does  NOP не меняет ни стек, ни PC.
    def test_nop_changes_nothing(self):
        m = tk.small()
        uc.ds_push(m, 7)
        ops.op_nop(m, 0)
        self.assertEqual(tk.stack_of(m), [7])
        self.assertEqual(m.pc, 0)

    # @method test_push_puts_imm() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH кладёт константу imm вершиной стека.
    def test_push_puts_imm(self):
        m = tk.small()
        ops.op_push(m, 42)
        self.assertEqual(tk.stack_of(m), [42])

    # @method test_push_keeps_word_range() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH кладёт слово по модулю 2^64.
    def test_push_keeps_word_range(self):
        m = tk.small()
        ops.op_push(m, uc.WORD_MASK)
        self.assertEqual(tk.stack_of(m), [uc.WORD_MASK])

    # @method test_drop_removes_top() -> None
    # @in    нет
    # @out   нет
    # @does  DROP снимает только вершину.
    def test_drop_removes_top(self):
        m = tk.small()
        uc.ds_push(m, 1)
        uc.ds_push(m, 2)
        ops.op_drop(m, 0)
        self.assertEqual(tk.stack_of(m), [1])

    # @method test_drop_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  DROP на пустом стеке — ловушка 2.
    def test_drop_empty_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: ops.op_drop(m, 0)),
                         uc.TRAP_DS_EMPTY)

    # @method test_dup_duplicates_top() -> None
    # @in    нет
    # @out   нет
    # @does  DUP: ( a — a a ).
    def test_dup_duplicates_top(self):
        m = tk.small()
        uc.ds_push(m, 5)
        ops.op_dup(m, 0)
        self.assertEqual(tk.stack_of(m), [5, 5])

    # @method test_dup_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  DUP на пустом стеке — ловушка 2 (собран из PICK).
    def test_dup_empty_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: ops.op_dup(m, 0)),
                         uc.TRAP_DS_EMPTY)

    # @method test_swap_reorders_pair() -> None
    # @in    нет
    # @out   нет
    # @does  SWAP: ( a b — b a ); глубже лежащие элементы не трогаются.
    def test_swap_reorders_pair(self):
        m = tk.small()
        for w in (1, 2, 3):
            uc.ds_push(m, w)
        ops.op_swap(m, 0)
        self.assertEqual(tk.stack_of(m), [1, 3, 2])

    # @method test_over_copies_second() -> None
    # @in    нет
    # @out   нет
    # @does  OVER: ( a b — a b a ).
    def test_over_copies_second(self):
        m = tk.small()
        uc.ds_push(m, 1)
        uc.ds_push(m, 2)
        ops.op_over(m, 0)
        self.assertEqual(tk.stack_of(m), [1, 2, 1])

    # @method test_rot_rotates_triple() -> None
    # @in    нет
    # @out   нет
    # @does  ROT: ( a b c — b c a ).
    def test_rot_rotates_triple(self):
        m = tk.small()
        for w in (1, 2, 3):
            uc.ds_push(m, w)
        ops.op_rot(m, 0)
        self.assertEqual(tk.stack_of(m), [2, 3, 1])

    # @method test_pick_copies_by_depth() -> None
    # @in    нет
    # @out   нет
    # @does  PICK: глубина 0 — вершина (DUP), 3 — четвёртый сверху;
    # @does  стек не укорачивается.
    def test_pick_copies_by_depth(self):
        m = tk.small()
        for w in (10, 20, 30):
            uc.ds_push(m, w)
        ops.op_pick(m, 0)
        self.assertEqual(tk.stack_of(m), [10, 20, 30, 30])
        ops.op_pick(m, 3)
        self.assertEqual(tk.stack_of(m), [10, 20, 30, 30, 10])

    # @method test_pick_out_of_range_traps() -> None
    # @in    нет
    # @out   нет
    # @does  PICK с глубиной вне стека — ловушка 2: и слишком глубоко,
    # @does  и отрицательная.
    def test_pick_out_of_range_traps(self):
        m = tk.small()
        uc.ds_push(m, 10)
        self.assertEqual(tk.trap_code(lambda: ops.op_pick(m, 1)),
                         uc.TRAP_DS_EMPTY)
        self.assertEqual(tk.trap_code(lambda: ops.op_pick(m, -1)),
                         uc.TRAP_DS_EMPTY)


if __name__ == "__main__":
    unittest.main()
