# @uadro
# @file    tests/test_uvm_exec.py
# @layer   T0
# @branch  t0.uvm.exec
# @desc    Тесты шага исполнения: декодирование по PC и вызов обработчика
# @desc    всех групп опкодов, HALT, ловушки 6, 7, 8 (SPEC/L0-UVM.txt).

"""Тесты ветви t0.uvm.exec (tools/uvm_exec.py).

Каждый тест собирает маленькую программу кирпичами тест-набора
(tk.load_prog, tk.imm64) и делает один или несколько шагов step.
Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_exec as ex


class TestStepStack(unittest.TestCase):
    """Шаги стековых и арифметических инструкций (SPEC, раздел 5)."""

    # @method test_step_nop() -> None
    # @in    нет
    # @out   нет
    # @does  NOP: один шаг — PC + 1, стек пуст.
    def test_step_nop(self):
        m = tk.small()
        tk.load_prog(m, [0x00])
        ex.step(m)
        self.assertEqual(m.pc, 1)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_step_push() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH imm: слово imm на стеке, PC за полем imm64.
    def test_step_push(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(77)])
        ex.step(m)
        self.assertEqual(tk.stack_of(m), [77])
        self.assertEqual(m.pc, 9)

    # @method test_step_add() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH 2, PUSH 3, ADD: три шага дают 5 на стеке.
    def test_step_add(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(2), 0x01, tk.imm64(3), 0x20])
        for _ in range(3):
            ex.step(m)
        self.assertEqual(tk.stack_of(m), [5])
        self.assertEqual(m.pc, 19)


class TestStepMem(unittest.TestCase):
    """Шаги инструкций памяти (SPEC, раздел 5)."""

    # @method test_step_store8_writes_ram() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH 0x41, PUSH 10, STORE8: байт 0x41 в ОЗУ по адресу 10.
    def test_step_store8_writes_ram(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(0x41), 0x01, tk.imm64(10), 0x12])
        for _ in range(3):
            ex.step(m)
        self.assertEqual(m.ram[10], 0x41)


class TestStepJump(unittest.TestCase):
    """Шаги переходов и вызовов (SPEC, разделы 4-5)."""

    # @method test_step_jmp_sets_pc() -> None
    # @in    нет
    # @out   нет
    # @does  JMP addr: один шаг — PC = addr.
    def test_step_jmp_sets_pc(self):
        m = tk.small()
        tk.load_prog(m, [0x40, tk.imm64(50)])
        ex.step(m)
        self.assertEqual(m.pc, 50)

    # @method test_step_jz_taken() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH 0, JZ addr: переход по нулю, условие снято со стека.
    def test_step_jz_taken(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(0), 0x41, tk.imm64(60)])
        ex.step(m)
        ex.step(m)
        self.assertEqual(m.pc, 60)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_step_call_saves_return() -> None
    # @in    нет
    # @out   нет
    # @does  CALL addr: на RS — адрес байта за полем imm64, PC = addr.
    def test_step_call_saves_return(self):
        m = tk.small()
        tk.load_prog(m, [0x43, tk.imm64(20)])
        ex.step(m)
        self.assertEqual(m.rs, [9])
        self.assertEqual(m.pc, 20)


class TestStepStop(unittest.TestCase):
    """Остановка и ловушки на шаге (SPEC, разделы 3-5)."""

    # @method test_step_halt_raises() -> None
    # @in    нет
    # @out   нет
    # @does  HALT imm: шаг поднимает нормальную остановку с кодом imm.
    def test_step_halt_raises(self):
        m = tk.small()
        tk.load_prog(m, [0x45, tk.imm64(3)])
        self.assertEqual(tk.halt_code(lambda: ex.step(m)), 3)

    # @method test_step_unknown_opcode_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный опкод в программе — ловушка 6.
    def test_step_unknown_opcode_traps(self):
        m = tk.small()
        tk.load_prog(m, [0x99])
        self.assertEqual(tk.trap_code(lambda: ex.step(m)),
                         uc.TRAP_BAD_OPCODE)

    # @method test_step_fetch_outside_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Выбор инструкции за границей ОЗУ — ловушка 7.
    def test_step_fetch_outside_ram_traps(self):
        m = tk.small(ram_size=1)
        tk.load_prog(m, [0x00])
        ex.step(m)
        self.assertEqual(tk.trap_code(lambda: ex.step(m)), uc.TRAP_OOB)

    # @method test_step_unknown_sys_traps() -> None
    # @in    нет
    # @out   нет
    # @does  SYS с неизвестным номером — ловушка 8 через полный путь
    # @does  декодирования imm64 и вызова обработчика.
    def test_step_unknown_sys_traps(self):
        m = tk.small()
        tk.load_prog(m, [0x50, tk.imm64(5)])
        self.assertEqual(tk.trap_code(lambda: ex.step(m)),
                         uc.TRAP_BAD_SYS)


if __name__ == "__main__":
    unittest.main()
