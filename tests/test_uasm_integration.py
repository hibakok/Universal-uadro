# @uadro
# @file    tests/test_uasm_integration.py
# @layer   T0
# @branch  t0.uasm.integration
# @desc    Интеграционные программы Этапа 2: исходники src/*.uasm
# @desc    собираются командой uasm_cli asm и исполняются uvm_cli;
# @desc    «вывод символа» и «арифметика» — байт в байт с эталонами
# @desc    Этапа 1, «вложенные CALL/RET» — метками, с тем же поведением
# @desc    (SPEC/L2-UASM.txt, ROADMAP.txt Этап 2); «вывод символа через
# @desc    порт» — DEVWR в CON_TX, подшаг 5.2 Этапа 5 (SPEC/L0-UVM.txt,
# @desc    6А.2; мнемоники DEVRD/DEVWR — SPEC/L2-UASM.txt v0.2).

"""Интеграционные программы Этапа 2 (ветвь t0.uasm.integration).

Три исходника .uasm в src/ закрывают DoD Этапа 2 (ROADMAP.txt):
«вывод символа» (src/hello.uasm), «арифметика» (src/arith.uasm),
«вложенные CALL/RET» (src/nested_calls.uasm). Каждый собирается
настоящей командой uasm_cli (режим asm, кирпич cli_image) и исполняется
циклом run_image либо командой uvm_cli (тест-набор run_via_cli).

Образы «вывода символа» и «арифметики» сравниваются байт в байт
с эталонами Этапа 1 (tests/test_uvm_integration.py): ассемблер
воспроизводит ручную сборку точно. «Вложенные CALL/RET» пишутся
метками без NOP-выравнивания — образ короче эталона, поведение то же:
вывод "!", стек [111, 222], пустой RS, код 0; раунд-трип
assemble(disasm(B)) == B проверен на его образе. «Вывод символа через
порт» (src/hello_dev.uasm, подшаг 5.2) собирается в образ эталона
prog_char_output_dev и пишет байт в порт CON_TX шины устройств —
стандартный набор привязывает run_image (SPEC/L0-UVM.txt, 6А.2-6А.4).
TestProcess гоняет обе команды документации настоящими процессами
(asm, затем run).

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import contextlib
import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tests.test_uvm_integration import (prog_arithmetic, prog_char_output,
                                         prog_char_output_dev)
from tools import uasm_assemble as am
from tools import uasm_cli
from tools import uasm_disasm as dis
from tools import uvm_run as rn


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для путей src/ и запуска инструментов
# @does  настоящим процессом в TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method src_path(name) -> str
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   path: str — путь к исходнику слоя L2
# @does  Строит путь к программе .uasm из каталога src/.
def src_path(name):
    return os.path.join(repo_root(), "src", name)


# @method cli_image(name) -> bytes
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   image: bytes — образ, собранный командой asm; None — ошибка
# @does  Собирает src/NAME настоящей командой uasm_cli (режим asm,
# @does  временный файл образа) и возвращает байты файла; при ошибке
# @does  сборки команда сама печатает сообщение в stderr.
# @depends uasm_cli.main
# @uses   sys.stderr — стандартный вывод ошибок хоста (через cli)
def cli_image(name):
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "prog.uvm")
        code = uasm_cli.main(["asm", src_path(name), image])
        if code != 0:
            return None
        with open(image, "rb") as handle:
            return handle.read()


class TestHello(unittest.TestCase):
    """«Вывод символа»: src/hello.uasm — "Hi" и байт в байт с эталоном."""

    # @method test_cli_asm_matches_reference() -> None
    # @in    нет
    # @out   нет
    # @does  Команда asm собирает исходник в образ, равный эталону
    # @does  Этапа 1 prog_char_output: PUSH 'H', SYS 1, PUSH 'i',
    # @does  SYS 1, HALT 0.
    def test_cli_asm_matches_reference(self):
        self.assertEqual(cli_image("hello.uasm"), prog_char_output())

    # @method test_uvm_cli_outputs_hi() -> None
    # @in    нет
    # @out   нет
    # @does  uvm_cli: код 0, в stdout — "Hi".
    def test_uvm_cli_outputs_hi(self):
        code, out = tk.run_via_cli(cli_image("hello.uasm"))
        self.assertEqual(code, 0)
        self.assertEqual(out, b"Hi")


class TestArith(unittest.TestCase):
    """«Арифметика»: src/arith.uasm — (2+3)*4 константами и стеком."""

    # @method test_cli_asm_matches_reference() -> None
    # @in    нет
    # @out   нет
    # @does  Команда asm собирает исходник с константами a, b, k
    # @does  в образ, равный эталону Этапа 1 prog_arithmetic.
    def test_cli_asm_matches_reference(self):
        self.assertEqual(cli_image("arith.uasm"), prog_arithmetic())

    # @method test_run_image_stack_is_20() -> None
    # @in    нет
    # @out   нет
    # @does  run_image: код 0, на стеке данных — 20.
    def test_run_image_stack_is_20(self):
        m, code = rn.run_image(cli_image("arith.uasm"))
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [20])

    # @method test_uvm_cli_silent_zero() -> None
    # @in    нет
    # @out   нет
    # @does  uvm_cli: код 0, вывода нет (результат остаётся в машине).
    def test_uvm_cli_silent_zero(self):
        code, out = tk.run_via_cli(cli_image("arith.uasm"))
        self.assertEqual(code, 0)
        self.assertEqual(out, b"")


class TestNestedCalls(unittest.TestCase):
    """«Вложенные CALL/RET»: src/nested_calls.uasm — метки вместо адресов."""

    # @method test_run_image_semantics() -> None
    # @in    нет
    # @out   нет
    # @does  run_image: код 0, вывод "!", стек [111, 222], стек
    # @does  возвратов пуст — оба RET отработали.
    def test_run_image_semantics(self):
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            m, code = rn.run_image(cli_image("nested_calls.uasm"))
        self.assertEqual(code, 0)
        self.assertEqual(out.buffer.getvalue(), b"!")
        self.assertEqual(tk.stack_of(m), [111, 222])
        self.assertEqual(m.rs, [])

    # @method test_uvm_cli_outputs_marker() -> None
    # @in    нет
    # @out   нет
    # @does  uvm_cli: код 0, в stdout — "!" (маркер после возвратов).
    def test_uvm_cli_outputs_marker(self):
        code, out = tk.run_via_cli(cli_image("nested_calls.uasm"))
        self.assertEqual(code, 0)
        self.assertEqual(out, b"!")

    # @method test_roundtrip_stable() -> None
    # @in    нет
    # @out   нет
    # @does  Раунд-трип на реальной программе (SPEC/L2-UASM.txt,
    # @does  раздел 8): assemble(disasm(B)) == B для образа,
    # @does  собранного из src/nested_calls.uasm с метками.
    def test_roundtrip_stable(self):
        image = cli_image("nested_calls.uasm")
        again, error = am.assemble(dis.disasm(image))
        self.assertIsNone(error)
        self.assertEqual(again, image)


class TestHelloDev(unittest.TestCase):
    """«Вывод символа через порт»: DEVWR в CON_TX (подшаг 5.2)."""

    # @method test_cli_asm_matches_reference() -> None
    # @in    нет
    # @out   нет
    # @does  Команда asm собирает исходник с мнемоникой DEVWR (SPEC/
    # @does  L2-UASM.txt v0.2: операнда нет) в образ, равный эталону
    # @does  prog_char_output_dev: PUSH 'H', PUSH 0x01, DEVWR, HALT 0.
    def test_cli_asm_matches_reference(self):
        self.assertEqual(cli_image("hello_dev.uasm"),
                         prog_char_output_dev())

    # @method test_run_image_outputs_h() -> None
    # @in    нет
    # @out   нет
    # @does  run_image (привязка стандартного набора — консоль):
    # @does  код 0, в stdout — "H", стек пуст.
    def test_run_image_outputs_h(self):
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            m, code = rn.run_image(cli_image("hello_dev.uasm"))
        self.assertEqual(code, 0)
        self.assertEqual(out.buffer.getvalue(), b"H")
        self.assertEqual(tk.stack_of(m), [])

    # @method test_uvm_cli_outputs_h() -> None
    # @in    нет
    # @out   нет
    # @does  uvm_cli: код 0, в stdout — "H".
    def test_uvm_cli_outputs_h(self):
        code, out = tk.run_via_cli(cli_image("hello_dev.uasm"))
        self.assertEqual(code, 0)
        self.assertEqual(out, b"H")


class TestProcess(unittest.TestCase):
    """Сквозной запуск настоящими процессами: команды документации."""

    # @method test_process_asm_and_run() -> None
    # @in    нет
    # @out   нет
    # @does  python tools/uasm_cli.py asm src/hello.uasm ОБРАЗ.uvm,
    # @does  затем python tools/uvm_cli.py ОБРАЗ.uvm: оба процесса
    # @does  завершаются кодом 0, stdout второго — "Hi".
    def test_process_asm_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "hello.uvm")
            asm_proc = subprocess.run(
                [sys.executable, os.path.join("tools", "uasm_cli.py"),
                 "asm", os.path.join("src", "hello.uasm"), image],
                capture_output=True, cwd=repo_root(), timeout=60)
            run_proc = subprocess.run(
                [sys.executable, os.path.join("tools", "uvm_cli.py"),
                 image],
                capture_output=True, cwd=repo_root(), timeout=60)
        self.assertEqual(asm_proc.returncode, 0)
        self.assertEqual(run_proc.returncode, 0)
        self.assertEqual(run_proc.stdout, b"Hi")


if __name__ == "__main__":
    unittest.main()
