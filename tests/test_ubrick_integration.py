# @uadro
# @file    tests/test_ubrick_integration.py
# @layer   T0
# @branch  t0.ubrick.integration
# @desc    Интеграционные программы Этапа 3: исходники src/*.ubrk
# @desc    собираются командой ubrick_cli compile и исполняются uvm_cli;
# @desc    поведение — как у эталонов Этапов 1-2 (SPEC/L3-UBRICK.txt,
# @desc    ROADMAP.txt Этап 3).

"""Интеграционные программы Этапа 3 (ветвь t0.ubrick.integration).

Три исходника .ubrk в src/ закрывают DoD Этапа 3 (ROADMAP.txt):
«вывод символа» (src/hello.ubrk — text и слово prints), «арифметика»
(src/arith.ubrk — литералы и примитивы), «вложенные вычисления»
(src/nested_calls.ubrk — var, производные слова, BEGIN/UNTIL).
Каждый собирается настоящей командой ubrick_cli (режим compile,
кирпич cli_image) и исполняется циклом run_image либо командой uvm_cli
(тест-набор run_via_cli).

Образы uBrick содержат все производные слова словаря (SPEC, раздел 7),
поэтому с эталонами Этапов 1-2 сравнивается поведение, а не байты:
вывод, стек данных, пустой RS и код завершения. TestProcess гоняет
обе команды документации настоящими процессами (compile, затем run).

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
from tools import ubrick_cli
from tools import uvm_run as rn


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для путей src/ и запуска инструментов
# @does  настоящим процессом в TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method src_path(name) -> str
# @in    name: str — имя исходника в src/, например "hello.ubrk"
# @out   path: str — путь к исходнику слоя L3
# @does  Строит путь к программе .ubrk из каталога src/.
def src_path(name):
    return os.path.join(repo_root(), "src", name)


# @method cli_image(name) -> bytes
# @in    name: str — имя исходника в src/, например "hello.ubrk"
# @out   image: bytes — образ, собранный командой compile; None — ошибка
# @does  Собирает src/NAME настоящей командой ubrick_cli (режим compile,
# @does  временный файл образа) и возвращает байты файла; при ошибке
# @does  сборки команда сама печатает сообщение в stderr.
# @depends ubrick_cli.main
# @uses   sys.stderr — стандартный вывод ошибок хоста (через cli)
def cli_image(name):
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "prog.uvm")
        code = ubrick_cli.main(["compile", src_path(name), image])
        if code != 0:
            return None
        with open(image, "rb") as handle:
            return handle.read()


class TestHello(unittest.TestCase):
    """«Вывод символа»: src/hello.ubrk — text/prints и "Hi" в stdout."""

    # @method test_compile_success() -> None
    # @in    нет
    # @out   нет
    # @does  Команда compile собирает исходник с text-данными в образ
    # @does  (не None): разбор, сборка и ассемблирование прошли.
    def test_compile_success(self):
        self.assertIsNotNone(cli_image("hello.ubrk"))

    # @method test_uvm_cli_outputs_hi() -> None
    # @in    нет
    # @out   нет
    # @does  uvm_cli: код 0, в stdout — "Hi" (поведение эталона
    # @does  src/hello.uasm Этапа 2).
    def test_uvm_cli_outputs_hi(self):
        code, out = tk.run_via_cli(cli_image("hello.ubrk"))
        self.assertEqual(code, 0)
        self.assertEqual(out, b"Hi")


class TestArith(unittest.TestCase):
    """«Арифметика»: src/arith.ubrk — (2+3)*4 литералами и ADD/MUL."""

    # @method test_run_image_stack_is_20() -> None
    # @in    нет
    # @out   нет
    # @does  run_image: код 0, на стеке данных — 20 (поведение эталона
    # @does  src/arith.uasm Этапа 2: результат остаётся в машине).
    def test_run_image_stack_is_20(self):
        m, code = rn.run_image(cli_image("arith.ubrk"))
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [20])

    # @method test_uvm_cli_silent_zero() -> None
    # @in    нет
    # @out   нет
    # @does  uvm_cli: код 0, вывода нет — результат остаётся в машине.
    def test_uvm_cli_silent_zero(self):
        code, out = tk.run_via_cli(cli_image("arith.ubrk"))
        self.assertEqual(code, 0)
        self.assertEqual(out, b"")


class TestNestedCalls(unittest.TestCase):
    """«Вложенные вычисления»: var, производные слова, BEGIN/UNTIL."""

    # @method test_run_image_semantics() -> None
    # @in    нет
    # @out   нет
    # @does  run_image: код 0, вывод "!", стек [111, 222], RS пуст —
    # @does  var-ячейки прочитаны, цикл BEGIN/UNTIL завершён, оба
    # @does  вложенных вызова вернулись (поведение эталона
    # @does  src/nested_calls.uasm Этапа 2).
    def test_run_image_semantics(self):
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            m, code = rn.run_image(cli_image("nested_calls.ubrk"))
        self.assertEqual(code, 0)
        self.assertEqual(out.buffer.getvalue(), b"!")
        self.assertEqual(tk.stack_of(m), [111, 222])
        self.assertEqual(m.rs, [])

    # @method test_uvm_cli_outputs_marker() -> None
    # @in    нет
    # @out   нет
    # @does  uvm_cli: код 0, в stdout — "!" (маркер после возвратов
    # @does  и цикла).
    def test_uvm_cli_outputs_marker(self):
        code, out = tk.run_via_cli(cli_image("nested_calls.ubrk"))
        self.assertEqual(code, 0)
        self.assertEqual(out, b"!")


class TestProcess(unittest.TestCase):
    """Сквозной запуск настоящими процессами: команды документации."""

    # @method test_process_compile_and_run() -> None
    # @in    нет
    # @out   нет
    # @does  python tools/ubrick_cli.py compile src/hello.ubrk
    # @does  ОБРАЗ.uvm, затем python tools/uvm_cli.py ОБРАЗ.uvm: оба
    # @does  процесса завершаются кодом 0, stdout второго — "Hi"
    # @does  (команды раздела 9 SPEC/L3-UBRICK.txt).
    def test_process_compile_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "hello.uvm")
            comp_proc = subprocess.run(
                [sys.executable, os.path.join("tools", "ubrick_cli.py"),
                 "compile", os.path.join("src", "hello.ubrk"), image],
                capture_output=True, cwd=repo_root(), timeout=60)
            run_proc = subprocess.run(
                [sys.executable, os.path.join("tools", "uvm_cli.py"),
                 image],
                capture_output=True, cwd=repo_root(), timeout=60)
        self.assertEqual(comp_proc.returncode, 0)
        self.assertEqual(run_proc.returncode, 0)
        self.assertEqual(run_proc.stdout, b"Hi")


if __name__ == "__main__":
    unittest.main()
