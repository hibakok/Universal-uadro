# @uadro
# @file    tests/test_uvm_run.py
# @layer   T0
# @branch  t0.uvm.run
# @desc    Тесты цикла запуска: коды HALT, ловушки в цикле, переходы
# @desc    и цикл JZ/JMP, вложенные CALL/RET, кирпич run_image
# @desc    (SPEC/L0-UVM.txt, разделы 2-5).

"""Тесты ветви t0.uvm.run (tools/uvm_run.py).

Программы собираются кирпичами тест-набора (tk.load_prog, tk.imm64)
и запускаются целиком циклом run; проверяются код завершения
и состояние машины после остановки. Адреса в тестах подсчитаны
по формату инструкций (SPEC, раздел 4): 1 байт опкода, при наличии
поля imm64 — ещё 8 байтов.
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_run as rn


class TestRunHalt(unittest.TestCase):
    """Нормальное завершение HALT в цикле (SPEC, разделы 3, 5)."""

    # @method test_halt_zero() -> None
    # @in    нет
    # @out   нет
    # @does  HALT 0: run возвращает 0, PC стоит за инструкцией HALT целиком.
    def test_halt_zero(self):
        m = tk.small()
        tk.load_prog(m, [0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), 0)
        self.assertEqual(m.pc, 9)

    # @method test_halt_imm() -> None
    # @in    нет
    # @out   нет
    # @does  HALT 7: run возвращает код imm.
    def test_halt_imm(self):
        m = tk.small()
        tk.load_prog(m, [0x45, tk.imm64(7)])
        self.assertEqual(rn.run(m), 7)

    # @method test_halt_imm_wraps() -> None
    # @in    нет
    # @out   нет
    # @does  HALT 300: код завершения — imm по модулю 256, то есть 44.
    def test_halt_imm_wraps(self):
        m = tk.small()
        tk.load_prog(m, [0x45, tk.imm64(300)])
        self.assertEqual(rn.run(m), 44)

    # @method test_arithmetic_leaves_stack() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH 2, PUSH 3, ADD, HALT 0: код 0, результат 5 остаётся
    # @does  на стеке остановленной машины.
    def test_arithmetic_leaves_stack(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(2), 0x01, tk.imm64(3), 0x20,
                         0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), 0)
        self.assertEqual(tk.stack_of(m), [5])


class TestRunTrap(unittest.TestCase):
    """Ловушки завершают цикл своим кодом (SPEC, раздел 3)."""

    # @method test_trap_div0() -> None
    # @in    нет
    # @out   нет
    # @does  UDIV с нулевым делителем: цикл возвращает код ловушки 1,
    # @does  HALT после него не исполняется.
    def test_trap_div0(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(1), 0x01, tk.imm64(0), 0x23,
                         0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), uc.TRAP_DIV0)

    # @method test_trap_ds_empty() -> None
    # @in    нет
    # @out   нет
    # @does  DROP на пустом стеке: цикл возвращает код ловушки 2.
    def test_trap_ds_empty(self):
        m = tk.small()
        tk.load_prog(m, [0x02, 0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), uc.TRAP_DS_EMPTY)

    # @method test_trap_bad_opcode() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный опкод в программе: цикл возвращает код 6.
    def test_trap_bad_opcode(self):
        m = tk.small()
        tk.load_prog(m, [0x99, 0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), uc.TRAP_BAD_OPCODE)

    # @method test_trap_fetch_outside_ram() -> None
    # @in    нет
    # @out   нет
    # @does  NOP в последнем байте ОЗУ: следующий выбор инструкции
    # @does  вне ОЗУ — цикл возвращает код ловушки 7.
    def test_trap_fetch_outside_ram(self):
        m = tk.small(ram_size=1)
        tk.load_prog(m, [0x00])
        self.assertEqual(rn.run(m), uc.TRAP_OOB)


class TestRunControl(unittest.TestCase):
    """Переходы, циклы и вызовы в цикле запуска (SPEC, разделы 4-5)."""

    # @method test_jmp_skips_bad_byte() -> None
    # @in    нет
    # @out   нет
    # @does  JMP через байт неизвестного опкода прямо на HALT: цикл
    # @does  завершается кодом 0, ловушки 6 не происходит.
    def test_jmp_skips_bad_byte(self):
        m = tk.small()
        tk.load_prog(m, [0x40, tk.imm64(10), 0x99,
                         0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), 0)

    # @method test_jz_loop_counts_down() -> None
    # @in    нет
    # @out   нет
    # @does  Счётный цикл JZ/JMP от 5 до 0: код 0, стек пуст — условие
    # @does  снято, счётчик снят DROP перед HALT.
    def test_jz_loop_counts_down(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(5),        # 0:  PUSH 5
                         0x03,                     # 9:  DUP
                         0x41, tk.imm64(40),       # 10: JZ 40
                         0x01, tk.imm64(1),        # 19: PUSH 1
                         0x21,                     # 28: SUB
                         0x40, tk.imm64(9),        # 29: JMP 9
                         0x00, 0x00,               # 38: выравнивание
                         0x02,                     # 40: DROP
                         0x45, tk.imm64(0)])       # 41: HALT 0
        self.assertEqual(rn.run(m), 0)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_nested_call_ret() -> None
    # @in    нет
    # @out   нет
    # @does  Main вызывает подпрограммы одна из другой (CALL/RET в два
    # @does  уровня): код 0, обе подпрограммы оставили слова на стеке
    # @does  в порядке возвратов.
    def test_nested_call_ret(self):
        m = tk.small()
        parts = [0x43, tk.imm64(30),   # 0:  CALL 30 (подпрограмма 1)
                 0x43, tk.imm64(50),   # 9:  CALL 50 (подпрограмма 2)
                 0x45, tk.imm64(0)]    # 18: HALT 0
        parts += [0x00] * 3            # 27: выравнивание до 30
        parts += [0x01, tk.imm64(111)]  # 30: PUSH 111
        parts += [0x44]                # 39: RET
        parts += [0x00] * 10           # 40: выравнивание до 50
        parts += [0x01, tk.imm64(222)]  # 50: PUSH 222
        parts += [0x44]                # 59: RET
        tk.load_prog(m, parts)
        self.assertEqual(rn.run(m), 0)
        self.assertEqual(tk.stack_of(m), [111, 222])
        self.assertEqual(m.rs, [])


class TestRunImage(unittest.TestCase):
    """Кирпич полного запуска образа (SPEC, раздел 2)."""

    # @method test_image_machine_and_code() -> None
    # @in    нет
    # @out   нет
    # @does  run_image образа HALT 9: код 9, машина с размерами
    # @does  по умолчанию (ОЗУ 1 МиБ), PC за инструкцией HALT.
    def test_image_machine_and_code(self):
        image = bytes([0x45]) + tk.imm64(9)
        m, code = rn.run_image(image)
        self.assertEqual(code, 9)
        self.assertEqual(len(m.ram), uc.RAM_SIZE_DEFAULT)
        self.assertEqual(m.pc, 9)

    # @method test_image_custom_sizes() -> None
    # @in    нет
    # @out   нет
    # @does  run_image с малыми размерами: ОЗУ 64 байта, код 0 —
    # @does  размеры машины управляются параметрами.
    def test_image_custom_sizes(self):
        image = bytes([0x45]) + tk.imm64(0)
        m, code = rn.run_image(image, ram_size=64, ds_size=4, rs_size=2)
        self.assertEqual(code, 0)
        self.assertEqual(len(m.ram), 64)
        self.assertEqual(m.ds_size, 4)
        self.assertEqual(m.rs_size, 2)


if __name__ == "__main__":
    unittest.main()
