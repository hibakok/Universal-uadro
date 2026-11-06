# @uadro
# @file    tests/test_uvm_integration.py
# @layer   T0
# @branch  t0.uvm.integration
# @desc    Интеграционные программы Этапа 1: «вывод символа», арифметика,
# @desc    вложенные CALL/RET — образы исполняются целиком через
# @desc    run_image и cli (SPEC/L0-UVM.txt, ROADMAP.txt Этап 1);
# @desc    «вывод символа через порт» — DEVWR в CON_TX шины устройств
# @desc    (Этап 5, подшаг 5.2, SPEC/L0-UVM.txt, 6А.2-6А.4).

"""Интеграционные программы Этапа 1 (ветвь t0.uvm.integration).

Три программы закрывают DoD Этапа 1 (ROADMAP.txt): «вывод символа»,
«арифметика», «вложенные CALL/RET». Каждая программа — кирпич-сборщик
образа: байты опкодов и полей imm64, адреса подсчитаны по формату
инструкций (SPEC, раздел 4: 1 байт опкода, при наличии поля imm64 —
ещё 8 байтов). Каждая исполняется дважды: циклом run_image (доступ
к остановленной машине: стек DS, стек RS) и целиком через cli.main
с временным файлом (файл -> образ -> код завершения). Вывод SYS
ловится заглушкой FakeStream тест-набора. Этап 2 собрал те же
программы исходниками .uasm в src/ (ветвь t0.uasm.integration):
«вывод символа» и «арифметика» — байт в байт с этими эталонами,
«вложенные CALL/RET» — метками, без NOP-выравнивания, с тем же
поведением. «Вывод символа через порт» (подшаг 5.2) пишет байт
инструкцией DEVWR в порт CON_TX (0x01): стандартный набор устройств —
консоль и таймер — привязывает run_image (SPEC, 6А.4); исходник —
src/hello_dev.uasm (ветвь t0.uasm.integration).
"""

import contextlib
import unittest

from tests import uvm_testkit as tk
from tools import uvm_run as rn


# @method prog_char_output() -> bytes
# @in    нет
# @out   image: bytes — образ программы «вывод символа»
# @does  Выводит "Hi" двумя SYS 1 и завершается HALT 0: PUSH 72,
# @does  SYS 1, PUSH 105, SYS 1, HALT 0.
def prog_char_output():
    return tk.image_of([0x01, tk.imm64(72),    # 0:  PUSH 'H'
                        0x50, tk.imm64(1),     # 9:  SYS 1
                        0x01, tk.imm64(105),   # 18: PUSH 'i'
                        0x50, tk.imm64(1),     # 27: SYS 1
                        0x45, tk.imm64(0)])    # 36: HALT 0


# @method prog_arithmetic() -> bytes
# @in    нет
# @out   image: bytes — образ программы «арифметика»
# @does  Считает (2+3)*4 = 20 и оставляет результат на стеке:
# @does  PUSH 2, PUSH 3, ADD, PUSH 4, MUL, HALT 0.
def prog_arithmetic():
    return tk.image_of([0x01, tk.imm64(2),     # 0:  PUSH 2
                        0x01, tk.imm64(3),     # 9:  PUSH 3
                        0x20,                  # 18: ADD
                        0x01, tk.imm64(4),     # 19: PUSH 4
                        0x22,                  # 28: MUL
                        0x45, tk.imm64(0)])    # 29: HALT 0


# @method prog_nested_calls() -> bytes
# @in    нет
# @out   image: bytes — образ программы «вложенные CALL/RET»
# @does  Main вызывает подпрограмму 1 (адрес 60), та изнутри —
# @does  подпрограмму 2 (адрес 90): глубина вложенности два; подпрограммы
# @does  оставляют на стеке 111 и 222, оба RET возвращают управление
# @does  по цепочке, main выводит "!" и завершается HALT 0; между
# @does  блоками — NOP.
def prog_nested_calls():
    parts = [0x43, tk.imm64(60),    # 0:  CALL 60 (подпрограмма 1)
             0x01, tk.imm64(33),    # 9:  PUSH '!'
             0x50, tk.imm64(1),     # 18: SYS 1
             0x45, tk.imm64(0)]     # 27: HALT 0
    parts += [0x00] * 24            # 36: NOP до подпрограммы 1
    parts += [0x01, tk.imm64(111),  # 60: PUSH 111
              0x43, tk.imm64(90),   # 69: CALL 90 (подпрограмма 2)
              0x44]                 # 78: RET
    parts += [0x00] * 11            # 79: NOP до подпрограммы 2
    parts += [0x01, tk.imm64(222),  # 90: PUSH 222
              0x44]                 # 99: RET
    return tk.image_of(parts)


# @method prog_char_output_dev() -> bytes
# @in    нет
# @out   image: bytes — образ программы «вывод символа через порт»
# @does  Выводит "H" записью в порт CON_TX шины устройств и завершается
# @does  HALT 0: PUSH 72, PUSH 0x01, DEVWR, HALT 0 (SPEC, 6А.2-6А.3);
# @does  эталон исходника src/hello_dev.uasm — байт в байт.
def prog_char_output_dev():
    return tk.image_of([0x01, tk.imm64(72),   # 0:  PUSH 'H'
                        0x01, tk.imm64(1),    # 9:  PUSH 0x01 (CON_TX)
                        0x53,                 # 18: DEVWR
                        0x45, tk.imm64(0)])   # 19: HALT 0


class TestCharOutput(unittest.TestCase):
    """Программа «вывод символа»: SYS 1 выводит байты, HALT 0."""

    # @method test_run_image_outputs() -> None
    # @in    нет
    # @out   нет
    # @does  run_image: код 0, в stdout — "Hi", стек данных пуст.
    def test_run_image_outputs(self):
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            m, code = rn.run_image(prog_char_output())
        self.assertEqual(code, 0)
        self.assertEqual(out.buffer.getvalue(), b"Hi")
        self.assertEqual(tk.stack_of(m), [])

    # @method test_cli_outputs() -> None
    # @in    нет
    # @out   нет
    # @does  cli: код 0, в stdout — "Hi".
    def test_cli_outputs(self):
        code, out = tk.run_via_cli(prog_char_output())
        self.assertEqual(code, 0)
        self.assertEqual(out, b"Hi")


class TestArithmetic(unittest.TestCase):
    """Программа «арифметика»: (2+3)*4 остаётся на стеке."""

    # @method test_run_image_result() -> None
    # @in    нет
    # @out   нет
    # @does  run_image: код 0, на стеке — 20.
    def test_run_image_result(self):
        m, code = rn.run_image(prog_arithmetic())
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [20])

    # @method test_cli_exit_code() -> None
    # @in    нет
    # @out   нет
    # @does  cli: код 0, вывода нет (результат остаётся в машине).
    def test_cli_exit_code(self):
        code, out = tk.run_via_cli(prog_arithmetic())
        self.assertEqual(code, 0)
        self.assertEqual(out, b"")


class TestNestedCalls(unittest.TestCase):
    """Программа «вложенные CALL/RET»: два уровня вызовов."""

    # @method test_run_image_stack_and_rs() -> None
    # @in    нет
    # @out   нет
    # @does  run_image: код 0, стек [111, 222], стек возвратов пуст —
    # @does  все RET отработали.
    def test_run_image_stack_and_rs(self):
        m, code = rn.run_image(prog_nested_calls())
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [111, 222])
        self.assertEqual(m.rs, [])

    # @method test_cli_outputs_marker() -> None
    # @in    нет
    # @out   нет
    # @does  cli: код 0, в stdout — "!" (маркер после возвратов).
    def test_cli_outputs_marker(self):
        code, out = tk.run_via_cli(prog_nested_calls())
        self.assertEqual(code, 0)
        self.assertEqual(out, b"!")


class TestCharOutputViaPort(unittest.TestCase):
    """«Вывод символа через порт»: DEVWR в CON_TX (v0.3, 6А.2-6А.4)."""

    # @method test_run_image_outputs() -> None
    # @in    нет
    # @out   нет
    # @does  run_image привязывает стандартный набор (консоль): DEVWR
    # @does  в CON_TX выводит "H", код 0, стек пуст.
    def test_run_image_outputs(self):
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            m, code = rn.run_image(prog_char_output_dev())
        self.assertEqual(code, 0)
        self.assertEqual(out.buffer.getvalue(), b"H")
        self.assertEqual(tk.stack_of(m), [])

    # @method test_cli_outputs() -> None
    # @in    нет
    # @out   нет
    # @does  cli: код 0, в stdout — "H" (привязка набора — в run_image,
    # @does  от cli ничего не зависит).
    def test_cli_outputs(self):
        code, out = tk.run_via_cli(prog_char_output_dev())
        self.assertEqual(code, 0)
        self.assertEqual(out, b"H")


if __name__ == "__main__":
    unittest.main()
