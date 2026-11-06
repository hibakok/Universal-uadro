# @uadro
# @file    tests/test_uvm_ops_sys.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты системных вызовов: SYS 0 — чтение байта, SYS 1 — вывод
# @desc    байта, SYS 2 — завершение с кодом со стека, неизвестный SYS
# @desc    (SPEC/L0-UVM.txt, раздел 6).

"""Тесты группы «SYS» ветви t0.uvm.ops (tools/uvm_ops_sys.py).

Хостовые потоки подменяются кирпичами тест-набора (tk.FakeStream,
tk.patched_stdin): обработчики работают через sys.stdin.buffer /
sys.stdout.buffer как с настоящими потоками. Запуск из корня
репозитория:
    python -m unittest discover -s tests -t . -v
"""

import contextlib
import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_ops_sys as ops


class TestSysWrite(unittest.TestCase):
    """SYS 1 — вывод байта (SPEC, раздел 6)."""

    # @method test_sys1_writes_byte() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 1 снимает байт со стека и выводит его в stdout.
    def test_sys1_writes_byte(self):
        m = tk.small()
        uc.ds_push(m, 65)
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            ops.op_sys(m, 1)
        self.assertEqual(out.buffer.getvalue(), b"A")
        self.assertEqual(tk.stack_of(m), [])

    # @method test_sys1_writes_low_byte() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 1 выводит c по модулю 256: 321 -> 65 -> "A".
    def test_sys1_writes_low_byte(self):
        m = tk.small()
        uc.ds_push(m, 321)
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            ops.op_sys(m, 1)
        self.assertEqual(out.buffer.getvalue(), b"A")

    # @method test_sys1_empty_stack_traps() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 1 с пустым стеком — ловушка 2.
    def test_sys1_empty_stack_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: ops.op_sys(m, 1)),
                         uc.TRAP_DS_EMPTY)


class TestSysRead(unittest.TestCase):
    """SYS 0 — чтение байта из stdin (SPEC, раздел 6)."""

    # @method test_sys0_reads_byte() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 0 читает байт из stdin и кладёт его на стек.
    def test_sys0_reads_byte(self):
        m = tk.small()
        src = tk.FakeStream(b"A")
        tk.patched_stdin(src, lambda: ops.op_sys(m, 0))
        self.assertEqual(tk.stack_of(m), [65])

    # @method test_sys0_reads_sequence_then_eof() -> None
    # @in    нет
    # @out   нет
    # @does  Последовательные SYS 0 читают байты по порядку, за
    # @does  последним — признак конца ввода EOF_WORD.
    def test_sys0_reads_sequence_then_eof(self):
        m = tk.small()
        src = tk.FakeStream(b"AB")
        tk.patched_stdin(src, lambda: (ops.op_sys(m, 0),
                                       ops.op_sys(m, 0),
                                       ops.op_sys(m, 0)))
        self.assertEqual(tk.stack_of(m), [65, 66, ops.EOF_WORD])

    # @method test_sys0_empty_input_is_eof() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой ввод сразу даёт EOF_WORD.
    def test_sys0_empty_input_is_eof(self):
        m = tk.small()
        src = tk.FakeStream()
        tk.patched_stdin(src, lambda: ops.op_sys(m, 0))
        self.assertEqual(tk.stack_of(m), [ops.EOF_WORD])


class TestSysStop(unittest.TestCase):
    """SYS 2 — завершение с кодом со стека (SPEC, раздел 6)."""

    # @method test_sys2_stops_with_code() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 2 снимает код со стека и поднимает UvmHalt с ним —
    # @does  нормальная остановка, как HALT imm.
    def test_sys2_stops_with_code(self):
        m = tk.small()
        uc.ds_push(m, 65)
        self.assertEqual(tk.halt_code(lambda: ops.op_sys(m, 2)), 65)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_sys2_wraps_code_mod_256() -> None
    # @in    нет
    # @out   нет
    # @does  Код c берётся по модулю 256: 321 -> 65, 256 -> 0.
    def test_sys2_wraps_code_mod_256(self):
        m = tk.small()
        uc.ds_push(m, 321)
        self.assertEqual(tk.halt_code(lambda: ops.op_sys(m, 2)), 65)
        uc.ds_push(m, 256)
        self.assertEqual(tk.halt_code(lambda: ops.op_sys(m, 2)), 0)

    # @method test_sys2_empty_stack_traps() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 2 с пустым стеком — ловушка 2: код снимается со стека
    # @does  прежде остановки.
    def test_sys2_empty_stack_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: ops.op_sys(m, 2)),
                         uc.TRAP_DS_EMPTY)


class TestSysUnknown(unittest.TestCase):
    """Неизвестные номера SYS (SPEC, раздел 6)."""

    # @method test_unknown_sys_traps() -> None
    # @in    нет
    # @out   нет
    # @does  SYS с номером вне 0/1/2 — ловушка 8.
    def test_unknown_sys_traps(self):
        for bad in (3, uc.WORD_MASK):
            m = tk.small()
            self.assertEqual(
                tk.trap_code(lambda m=m, bad=bad: ops.op_sys(m, bad)),
                uc.TRAP_BAD_SYS)


if __name__ == "__main__":
    unittest.main()
