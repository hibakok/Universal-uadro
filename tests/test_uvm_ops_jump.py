# @uadro
# @file    tests/test_uvm_ops_jump.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты обработчиков переходов и остановки: JMP, JZ, JNZ, CALL,
# @desc    RET, HALT (SPEC/L0-UVM.txt, разделы 4-5).

"""Тесты группы «переходы» ветви t0.uvm.ops (tools/uvm_ops_jump.py).

Контракт PC: к моменту вызова обработчика PC уже указывает на байт,
следующий за инструкцией. Тесты моделируют это, выставляя m.pc
напрямую. Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_ops_jump as ops


class TestJumps(unittest.TestCase):
    """Безусловный и условные переходы (SPEC, раздел 5)."""

    # @method test_jmp_sets_pc() -> None
    # @in    нет
    # @out   нет
    # @does  JMP: PC = addr, стек не трогается.
    def test_jmp_sets_pc(self):
        m = tk.small()
        m.pc = 100
        uc.ds_push(m, 9)
        ops.op_jmp(m, 55)
        self.assertEqual(m.pc, 55)
        self.assertEqual(tk.stack_of(m), [9])

    # @method test_jz_jumps_on_zero() -> None
    # @in    нет
    # @out   нет
    # @does  JZ: c = 0 — переход, условие снято со стека.
    def test_jz_jumps_on_zero(self):
        m = tk.small()
        m.pc = 100
        uc.ds_push(m, 0)
        ops.op_jz(m, 55)
        self.assertEqual(m.pc, 55)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_jz_keeps_pc_on_nonzero() -> None
    # @in    нет
    # @out   нет
    # @does  JZ: c не 0 — PC не меняется, условие всё равно снято.
    def test_jz_keeps_pc_on_nonzero(self):
        m = tk.small()
        m.pc = 100
        uc.ds_push(m, 7)
        ops.op_jz(m, 55)
        self.assertEqual(m.pc, 100)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_jnz_jumps_on_nonzero() -> None
    # @in    нет
    # @out   нет
    # @does  JNZ: c не 0 — переход.
    def test_jnz_jumps_on_nonzero(self):
        m = tk.small()
        m.pc = 100
        uc.ds_push(m, 7)
        ops.op_jnz(m, 55)
        self.assertEqual(m.pc, 55)

    # @method test_jnz_keeps_pc_on_zero() -> None
    # @in    нет
    # @out   нет
    # @does  JNZ: c = 0 — PC не меняется.
    def test_jnz_keeps_pc_on_zero(self):
        m = tk.small()
        m.pc = 100
        uc.ds_push(m, 0)
        ops.op_jnz(m, 55)
        self.assertEqual(m.pc, 100)

    # @method test_conditional_jump_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  JZ без условия на стеке — ловушка 2.
    def test_conditional_jump_empty_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: ops.op_jz(m, 55)),
                         uc.TRAP_DS_EMPTY)


class TestCallRet(unittest.TestCase):
    """Вызовы CALL/RET (SPEC, разделы 4-5)."""

    # @method test_call_saves_return_and_jumps() -> None
    # @in    нет
    # @out   нет
    # @does  CALL: адрес возврата (текущий PC) — на RS, PC = addr.
    def test_call_saves_return_and_jumps(self):
        m = tk.small()
        m.pc = 100
        ops.op_call(m, 7)
        self.assertEqual(m.rs, [100])
        self.assertEqual(m.pc, 7)

    # @method test_call_rs_overflow_traps() -> None
    # @in    нет
    # @out   нет
    # @does  CALL при переполненном RS — ловушка 5.
    def test_call_rs_overflow_traps(self):
        m = tk.small(rs_size=2)
        uc.rs_push(m, 1)
        uc.rs_push(m, 2)
        self.assertEqual(tk.trap_code(lambda: ops.op_call(m, 7)),
                         uc.TRAP_RS_FULL)

    # @method test_ret_pops_rs_into_pc() -> None
    # @in    нет
    # @out   нет
    # @does  RET: PC <- вершина RS.
    def test_ret_pops_rs_into_pc(self):
        m = tk.small()
        uc.rs_push(m, 42)
        ops.op_ret(m, 0)
        self.assertEqual(m.pc, 42)

    # @method test_ret_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  RET при пустом RS — ловушка 4.
    def test_ret_empty_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: ops.op_ret(m, 0)),
                         uc.TRAP_RS_EMPTY)

    # @method test_call_ret_roundtrip() -> None
    # @in    нет
    # @out   нет
    # @does  Пара CALL/RET возвращает PC на адрес возврата.
    def test_call_ret_roundtrip(self):
        m = tk.small()
        m.pc = 100
        ops.op_call(m, 7)
        ops.op_ret(m, 0)
        self.assertEqual(m.pc, 100)
        self.assertEqual(m.rs, [])


class TestHalt(unittest.TestCase):
    """Нормальная остановка HALT (SPEC, раздел 5)."""

    # @method test_halt_raises_with_code() -> None
    # @in    нет
    # @out   нет
    # @does  HALT поднимает UvmHalt с кодом imm.
    def test_halt_raises_with_code(self):
        m = tk.small()
        self.assertEqual(tk.halt_code(lambda: ops.op_halt(m, 0)), 0)

    # @method test_halt_code_mod_256() -> None
    # @in    нет
    # @out   нет
    # @does  Код HALT — imm по модулю 256.
    def test_halt_code_mod_256(self):
        m = tk.small()
        self.assertEqual(tk.halt_code(lambda: ops.op_halt(m, 300)), 44)
        self.assertEqual(tk.halt_code(lambda: ops.op_halt(m, 256)), 0)

    # @method test_halt_is_not_trap() -> None
    # @in    нет
    # @out   нет
    # @does  UvmHalt — не UvmTrap: цикл запуска отличит нормальную
    # @does  остановку от ловушки.
    def test_halt_is_not_trap(self):
        m = tk.small()
        try:
            ops.op_halt(m, 0)
        except uc.UvmTrap:
            self.fail("HALT поднял ловушку вместо остановки")
        except uc.UvmHalt:
            pass
        else:
            self.fail("HALT не поднял остановку")


if __name__ == "__main__":
    unittest.main()
