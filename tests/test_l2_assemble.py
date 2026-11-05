# @uadro
# @file    tests/test_l2_assemble.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшага 1 ветви l2.uasm.assemble: каркас и память
# @desc    (src/l2/assemble.ubrk + use-включение src/l2/asmmem.ubrk):
# @desc    сборка настоящей командой compile, пустой/малый/бинарный вход —
# @desc    код 0 и пустой вывод, границы лимита буфера источника (ровно
# @desc    512 КиБ — успех, сверх — «вход слишком большой» и код 16),
# @desc    сквозной прогон настоящими процессами (SPEC/L4-SELFHOST.txt,
# @desc    раздел 5А, подшаг 1).

"""Тесты подшага 1 ветви l2.uasm.assemble (SPEC/L4-SELFHOST.txt, раздел 5А).

Ассемблер uAsm на uBrick собирается настоящей командой ubrick_cli
compile (кирпич l2_image — use-включение asmmem.ubrk склеивает загрузчик
ветви t0.ubrick.source) и исполняется кирпичом run_with_io
(tests/uvm_testkit.py): SYS 0 читает байты текста-входа; подшаг 1 ничего
не выводит и всегда завершается кодом 0, пока вход в лимите.

Подшаг 1 (каркас и память): пустой вход — пустой вывод и код 0; вход
в пределах лимита читается в буфер целиком — вывод пуст, код 0; вход
ровно в 512 КиБ занимает последний байт буфера — ещё успех; вход сверх
лимита — строка «вход слишком большой» с переводом и код 16, единственная
диагностика без номера строки (SPEC, раздел 5А). Границы лимита гоняют
полный буфер через UVM — самые медленные тесты набора (около минуты
на пару).
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli

SRC_BASE = 0x10000      # база буфера источника (SPEC, раздел 5А)
SRC_LIMIT = 0x90000 - SRC_BASE   # ёмкость буфера источника: 512 КиБ
BIG_TEXT = "вход слишком большой\n".encode("utf-8")   # диагностика без
                                                     # номера строки


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для пути src/l2 и запуска инструментов
# @does  настоящим процессом в TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method l2_source() -> str
# @in    нет
# @out   path: str — путь к исходнику src/l2/assemble.ubrk
# @does  Строит путь к собственному воплощению ассемблера (слой L2,
# @does  SPEC/L4-SELFHOST.txt, раздел 5А).
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "assemble.ubrk")


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ ассемблера, собранный командой compile;
# @out   None — ошибка сборки (сообщение печатает cli в stderr)
# @does  Собирает src/l2/assemble.ubrk настоящей командой ubrick_cli
# @does  (режим compile, временный файл образа): use-включение
# @does  asmmem.ubrk склеивает загрузчик ветви t0.ubrick.source;
# @does  кирпич всех тестов ветви.
# @depends ubrick_cli.main
# @uses   sys.stderr — стандартный вывод ошибок хоста (через cli)
def l2_image():
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "assemble.uvm")
        code = ubrick_cli.main(["compile", l2_source(), image])
        if code != 0:
            return None
        with open(image, "rb") as handle:
            return handle.read()


# @method feed(image, data) -> tuple
# @in    image: bytes — образ ассемблера
# @in    data: bytes — байты входа (текст uAsm)
# @out   pair: tuple — (код завершения, байты stdout)
# @does  Прогон образа без процесса с подменёнными stdin/stdout; кирпич
# @does  всех тестов ветви.
# @depends tk.run_with_io
def feed(image, data):
    return tk.run_with_io(image, data)


class TestCompile(unittest.TestCase):
    """Каркас собирается настоящей командой compile."""

    # @method test_image_built() -> None
    # @in    нет
    # @out   нет
    # @does  Компиляция src/l2/assemble.ubrk с use-включением
    # @does  asmmem.ubrk проходит без ошибки (код 0), образ не пуст.
    # @depends l2_image
    def test_image_built(self):
        image = l2_image()
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)


class TestSkeleton(unittest.TestCase):
    """Подшаг 1: чтение stdin в буфер источника, вывод пуст, код 0."""

    # @method test_empty_input() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой вход — пустой вывод и код 0 (SPEC/L4-SELFHOST.txt,
    # @does  раздел 5А, подшаг 1).
    # @depends l2_image, feed
    def test_empty_input(self):
        code, out = feed(l2_image(), b"")
        self.assertEqual((code, out), (0, b""))

    # @method test_small_input() -> None
    # @in    нет
    # @out   нет
    # @does  Небольшой текст uAsm читается в буфер целиком — вывод пуст,
    # @does  код 0 (разбор строк — подшаг 2, вывод образа — подшаг 6).
    # @depends l2_image, feed
    def test_small_input(self):
        text = b"NOP\nPUSH 1\nHALT 0\n"
        code, out = feed(l2_image(), text)
        self.assertEqual((code, out), (0, b""))

    # @method test_binary_input() -> None
    # @in    нет
    # @out   нет
    # @does  Вход — все байты 0..255 подряд (чтение не разбирает вход):
    # @does  вывод пуст, код 0.
    # @depends l2_image, feed
    def test_binary_input(self):
        code, out = feed(l2_image(), bytes(range(256)))
        self.assertEqual((code, out), (0, b""))


class TestLimit(unittest.TestCase):
    """Подшаг 1: лимит буфера источника 512 КиБ (SPEC, раздел 5А)."""

    # @method test_exact_fit() -> None
    # @in    нет
    # @out   нет
    # @does  Вход ровно в 512 КиБ занимает буфер целиком, последний байт
    # @does  пишется в 0x8FFFF — успех: вывод пуст, код 0 (SPEC,
    # @does  раздел 5А: лимит входа).
    # @depends l2_image, feed
    def test_exact_fit(self):
        code, out = feed(l2_image(), b"A" * SRC_LIMIT)
        self.assertEqual((code, out), (0, b""))

    # @method test_over_limit() -> None
    # @in    нет
    # @out   нет
    # @does  Вход на байт больше лимита: 524288 байтов читаются без
    # @does  ошибки, 524289-й не помещается — строка «вход слишком
    # @does  большой» с переводом строки и код 16 (SPEC, раздел 5А:
    # @does  единственная диагностика без номера строки).
    # @depends l2_image, feed
    def test_over_limit(self):
        code, out = feed(l2_image(), b"A" * (SRC_LIMIT + 1))
        self.assertEqual((code, out), (16, BIG_TEXT))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5А)."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта настоящими процессами: ubrick_cli compile,
    # @does  затем uvm_cli с входным файлом-текстом; stdout пуст, код
    # @does  процесса 0.
    # @depends l2_source
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "assemble.uvm")
            src = os.path.join(tmp, "in.uasm")
            with open(src, "wb") as handle:
                handle.write(b"NOP\nPUSH 1\nHALT 0\n")
            compile_code = subprocess.call(
                [sys_python(), tools_path("ubrick_cli.py"), "compile",
                 l2_source(), image],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(compile_code, 0)
            with open(src, "rb") as handle:
                run = subprocess.run(
                    [sys_python(), tools_path("uvm_cli.py"), image],
                    stdin=handle, capture_output=True)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stdout, b"")


# @method sys_python() -> str
# @in    нет
# @out   python: str — интерпретатор для запуска инструментов процессом
# @does  Даёт исполняемый файл Python, запустивший тесты.
# @uses   sys.executable — интерпретатор текущего процесса
def sys_python():
    return sys.executable


# @method tools_path(name) -> str
# @in    name: str — имя сценария в каталоге tools
# @out   path: str — путь к инструменту репозитория
# @does  Строит путь к сценарию инструментов для запуска процессом.
# @depends repo_root
def tools_path(name):
    return os.path.join(repo_root(), "tools", name)


if __name__ == "__main__":
    unittest.main()
