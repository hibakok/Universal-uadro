# @uadro
# @file    tests/test_l2_disasm.py
# @layer   T0
# @branch  l2.uasm.disasm
# @desc    Тесты подшага 1 ветви l2.uasm.disasm: каркас и таблица мнемоник
# @desc    (src/l2/disasm.ubrk): сборка настоящей командой compile, пустой
# @desc    вход, все опкоды без imm64 — по строке на мнемонику, границы
# @desc    диапазонов и дыры таблицы — останов с кодом 0.

"""Тесты подшага 1 ветви l2.uasm.disasm (SPEC/L4-SELFHOST.txt, раздел 7).

Каркас дизассемблера на uBrick (src/l2/disasm.ubrk) собирается настоящей
командой ubrick_cli compile (кирпич l2_image) и исполняется кирпичом
run_with_io (tests/uvm_testkit.py): SYS 0 читает байты образа-входа,
SYS 1 пишет текст uAsm.

Поведение подшага 1: пустой вход — пустой вывод и код 0; байт известного
опкода без imm64 — строка «МНЕМОНИКА»; неизвестный код (дыра диапазона
или за таблицей) — останов декодирования, код 0. Значения imm64 и хвост
DB — следующие подшаги ветви, их входы здесь не проверяются.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uvm_table import TABLE

NOIMM = [rec for rec in TABLE if not rec[3]]   # опкоды без поля imm64
HOLES = (0x08, 0x0F, 0x14, 0x1F, 0x2D, 0x2F,   # дыры между диапазонами
         0x36, 0x3F, 0x46, 0x4F, 0x51, 0xFF)   # и за таблицей


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для пути src/l2 и запуска инструментов
# @does  настоящим процессом в TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method l2_source() -> str
# @in    нет
# @out   path: str — путь к исходнику src/l2/disasm.ubrk
# @does  Строит путь к собственному воплощению дизассемблера (слой L2,
# @does  SPEC/L4-SELFHOST.txt, раздел 3).
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "disasm.ubrk")


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ дизассемблера, собранный командой compile;
# @out   None — ошибка сборки (сообщение печатает cli в stderr)
# @does  Собирает src/l2/disasm.ubrk настоящей командой ubrick_cli
# @does  (режим compile, временный файл образа); кирпич всех тестов ветви.
# @depends ubrick_cli.main
# @uses   sys.stderr — стандартный вывод ошибок хоста (через cli)
def l2_image():
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "disasm.uvm")
        code = ubrick_cli.main(["compile", l2_source(), image])
        if code != 0:
            return None
        with open(image, "rb") as handle:
            return handle.read()


# @method feed(image, data) -> tuple
# @in    image: bytes — образ дизассемблера
# @in    data: bytes — байты входа (дизассемблируемый образ)
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
    # @does  Компиляция src/l2/disasm.ubrk проходит без ошибки (код 0),
    # @does  образ не пуст.
    # @depends l2_image
    def test_image_built(self):
        image = l2_image()
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)


class TestSkeleton(unittest.TestCase):
    """Поведение подшага 1: EOF, известные опкоды, останов на дырах."""

    # @method test_empty_input() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой вход — пустой вывод и код 0 (SPEC/L4-SELFHOST.txt,
    # @does  раздел 5: пустой вход — пустой вывод).
    # @depends l2_image, feed
    def test_empty_input(self):
        code, out = feed(l2_image(), b"")
        self.assertEqual((code, out), (0, b""))

    # @method test_noimm_opcodes() -> None
    # @in    нет
    # @out   нет
    # @does  Все опкоды без imm64 одним потоком: по одной строке
    # @does  «МНЕМОНИКА» на байт — вся таблица мнемоник насквозь.
    # @depends l2_image, feed
    def test_noimm_opcodes(self):
        data = bytes(rec[0] for rec in NOIMM)
        text = "".join(rec[1] + "\n" for rec in NOIMM).encode()
        code, out = feed(l2_image(), data)
        self.assertEqual(code, 0)
        self.assertEqual(out, text)

    # @method test_range_bounds() -> None
    # @in    нет
    # @out   нет
    # @does  Низ и верх каждого диапазона таблицы отдельным байтом:
    # @does  адрес записи = база строки + (код - низ) * 8 на краях строк.
    # @depends l2_image, feed
    def test_range_bounds(self):
        image = l2_image()
        pairs = (
            (0x00, "NOP"), (0x07, "PICK"),
            (0x10, "LOAD8"), (0x13, "STORE64"),
            (0x20, "ADD"), (0x2C, "INV"),
            (0x30, "EQ"), (0x35, "GEU"),
            (0x40, "JMP"), (0x45, "HALT"),
            (0x50, "SYS"),
        )
        for opcode, mnemonic in pairs:
            code, out = feed(image, bytes([opcode]))
            self.assertEqual((code, out), (0, (mnemonic + "\n").encode()))

    # @method test_holes_stop() -> None
    # @in    нет
    # @out   нет
    # @does  Дыры между диапазонами и коды за таблицей: останов
    # @does  декодирования — пустой вывод и код 0 (хвост DB — подшаг 3).
    # @depends l2_image, feed
    def test_holes_stop(self):
        image = l2_image()
        for opcode in HOLES:
            code, out = feed(image, bytes([opcode]))
            self.assertEqual((code, out), (0, b""))

    # @method test_stop_keeps_prefix() -> None
    # @in    нет
    # @out   нет
    # @does  Останов на неизвестном коде сохраняет строки напечатанных
    # @does  до него инструкций и не читает хвост входа.
    # @depends l2_image, feed
    def test_stop_keeps_prefix(self):
        code, out = feed(l2_image(), b"\x00\x00\x08\x00")
        self.assertEqual((code, out), (0, b"NOP\nNOP\n"))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5): uvm_cli."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта настоящими процессами: ubrick_cli compile,
    # @does  затем uvm_cli с входным файлом; вывод — ожидаемые строки,
    # @does  код процесса 0.
    # @depends l2_source
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "disasm.uvm")
            src = os.path.join(tmp, "in.uvm")
            with open(src, "wb") as handle:
                handle.write(b"\x00\x10\x13\x2c\x50")
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
            self.assertEqual(run.stdout, b"NOP\nLOAD8\nSTORE64\nINV\nSYS\n")


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
