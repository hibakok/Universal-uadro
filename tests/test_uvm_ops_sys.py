# @uadro
# @file    tests/test_uvm_ops_sys.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты системных вызовов: SYS 0 — чтение байта, SYS 1 — вывод
# @desc    байта, неизвестный SYS (SPEC/L0-UVM.txt, раздел 6).

"""Тесты группы «SYS» ветви t0.uvm.ops (tools/uvm_ops_sys.py).

Хостовые потоки подменяются заглушками с полем buffer — обработчики
работают через sys.stdin.buffer / sys.stdout.buffer как с настоящими
потоками. Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import contextlib
import io
import sys
import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_ops_sys as ops


# @method FakeStream(data)
# @in    data: bytes — начальные байты (для заглушки ввода)
# @out   fake: FakeStream — поток с полем buffer
# @does  Заглушка stdin/stdout: обработчики SYS читают и пишут через
# @does  поле buffer, как у реальных потоков Python; для stdout —
# @does  с contextlib.redirect_stdout, для stdin — с patched_stdin.
class FakeStream:
    """Заглушка стандартного потока: buffer — BytesIO."""

    def __init__(self, data=b""):
        self.buffer = io.BytesIO(data)


# @method patched_stdin(stream, action) -> None
# @in    stream: FakeStream — заглушка стандартного ввода
# @in    action: callable — проверяемое действие
# @out   нет
# @does  Подменяет sys.stdin на время действия и гарантированно
# @does  восстанавливает после (в contextlib нет redirect_stdin).
# @uses  sys.stdin — стандартный ввод хоста (подмена на время действия)
def patched_stdin(stream, action):
    saved = sys.stdin
    sys.stdin = stream
    try:
        action()
    finally:
        sys.stdin = saved


class TestSysWrite(unittest.TestCase):
    """SYS 1 — вывод байта (SPEC, раздел 6)."""

    # @method test_sys1_writes_byte() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 1 снимает байт со стека и выводит его в stdout.
    def test_sys1_writes_byte(self):
        m = tk.small()
        uc.ds_push(m, 65)
        out = FakeStream()
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
        out = FakeStream()
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
        src = FakeStream(b"A")
        patched_stdin(src, lambda: ops.op_sys(m, 0))
        self.assertEqual(tk.stack_of(m), [65])

    # @method test_sys0_reads_sequence_then_eof() -> None
    # @in    нет
    # @out   нет
    # @does  Последовательные SYS 0 читают байты по порядку, за
    # @does  последним — признак конца ввода EOF_WORD.
    def test_sys0_reads_sequence_then_eof(self):
        m = tk.small()
        src = FakeStream(b"AB")
        patched_stdin(src, lambda: (ops.op_sys(m, 0),
                                    ops.op_sys(m, 0),
                                    ops.op_sys(m, 0)))
        self.assertEqual(tk.stack_of(m), [65, 66, ops.EOF_WORD])

    # @method test_sys0_empty_input_is_eof() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой ввод сразу даёт EOF_WORD.
    def test_sys0_empty_input_is_eof(self):
        m = tk.small()
        src = FakeStream()
        patched_stdin(src, lambda: ops.op_sys(m, 0))
        self.assertEqual(tk.stack_of(m), [ops.EOF_WORD])


class TestSysUnknown(unittest.TestCase):
    """Неизвестные номера SYS (SPEC, раздел 6)."""

    # @method test_unknown_sys_traps() -> None
    # @in    нет
    # @out   нет
    # @does  SYS с номером вне 0/1 — ловушка 8.
    def test_unknown_sys_traps(self):
        for bad in (2, uc.WORD_MASK):
            m = tk.small()
            self.assertEqual(
                tk.trap_code(lambda m=m, bad=bad: ops.op_sys(m, bad)),
                uc.TRAP_BAD_SYS)


if __name__ == "__main__":
    unittest.main()
