# @uadro
# @file    tests/test_l2_disasm.py
# @layer   T0
# @branch  l2.uasm.disasm
# @desc    Тесты подшагов 1-3 ветви l2.uasm.disasm: каркас, таблица
# @desc    мнемоник, поле imm64, печать десятичного значения и хвост DB
# @desc    (src/l2/disasm.ubrk): сборка настоящей командой compile, пустой
# @desc    вход, опкоды без imm64 — по строке на мнемонику, инструкции
# @desc    с imm64 — золотая сверка с эталоном disasm байт в байт,
# @desc    хвост DB с опкода останова (обрыв поля, неизвестный опкод,
# @desc    длины хвоста, устаревшее iv/ii) — эталон байт в байт,
# @desc    сквозной прогон настоящими процессами.

"""Тесты подшагов 1-3 ветви l2.uasm.disasm (SPEC/L4-SELFHOST.txt, раздел 7).

Дизассемблер на uBrick (src/l2/disasm.ubrk) собирается настоящей командой
ubrick_cli compile (кирпич l2_image) и исполняется кирпичом run_with_io
(tests/uvm_testkit.py): SYS 0 читает байты образа-входа, SYS 1 пишет текст
uAsm.

Подшаг 1: пустой вход — пустой вывод и код 0; байт известного опкода без
imm64 — строка «МНЕМОНИКА»; границы шести диапазонов таблицы мнемоник.

Подшаг 2: опкод с полем imm64 читает восемь байтов поля (hasimm,
getimm); полное поле — строка «МНЕМОНИКА значение», сверенная с эталоном
disasm байт в байт (золотые значения 0, 1, 12345, 2^64-1).

Подшаг 3: останов декодирования (неизвестный опкод, обрыв поля imm64)
печатает хвост DB с опкода останова до конца входа — по восемь
десятичных аргументов на строку (SPEC/L4-SELFHOST.txt, раздел 5);
сверка с эталоном disasm байт в байт: дыры таблицы, обрывы поля 0-7
байтов, длины хвоста 1-18 (короткая строка, ровно восемь аргументов,
полная строка плюс один), устаревшие iv/ii прежних инструкций не
попадают в хвост, смешанные программы с данными в конце.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_disasm import disasm as ref_disasm
from tools.uvm_table import TABLE

NOIMM = [rec for rec in TABLE if not rec[3]]   # опкоды без поля imm64
IMM = [rec for rec in TABLE if rec[3]]         # опкоды с полем imm64
HOLES = (0x08, 0x0F, 0x14, 0x1F, 0x2D, 0x2F,   # дыры между диапазонами
         0x36, 0x3F, 0x46, 0x4F, 0x51, 0xFF)   # и за таблицей
VALUES = (0, 1, 12345, 2 ** 64 - 1)            # золотые значения imm64


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


# @method gold(image, data) -> None
# @in    image: bytes — образ дизассемблера
# @in    data: bytes — байты входа (дизассемблируемый образ)
# @out   нет (утверждение теста)
# @does  Золотая сверка одного входа с эталоном disasm байт в байт:
# @does  код завершения 0 и вывод равен эталону (SPEC/L4-SELFHOST.txt,
# @does  раздел 6); кирпич золотых тестов ветви.
# @depends feed, ref_disasm
def gold(image, data):
    code, out = feed(image, data)
    assert (code, out) == (0, ref_disasm(data).encode()), (
        code, out, ref_disasm(data).encode())


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
    """Подшаг 1: EOF, опкоды без imm64, границы диапазонов таблицы."""

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
    # @does  Низ и верх каждого диапазона таблицы отдельным байтом
    # @does  без imm64: адрес записи = база строки + (код - низ) * 8
    # @does  на краях строк (границы imm-опкодов — TestImm.test_imm_bounds).
    # @depends l2_image, feed
    def test_range_bounds(self):
        image = l2_image()
        pairs = (
            (0x00, "NOP"), (0x10, "LOAD8"), (0x13, "STORE64"),
            (0x20, "ADD"), (0x2C, "INV"), (0x30, "EQ"),
            (0x35, "GEU"), (0x44, "RET"),
        )
        for opcode, mnemonic in pairs:
            code, out = feed(image, bytes([opcode]))
            self.assertEqual((code, out), (0, (mnemonic + "\n").encode()))


class TestImm(unittest.TestCase):
    """Подшаг 2: инструкции с imm64 — «МНЕМОНИКА значение» (десятичное)."""

    # @method test_imm_bounds() -> None
    # @in    нет
    # @out   нет
    # @does  Границы imm-опкодов (PICK, JMP, CALL, HALT, SYS) с полным
    # @does  полем — золотая сверка строки с эталоном disasm байт в байт.
    # @depends l2_image, gold
    def test_imm_bounds(self):
        image = l2_image()
        pairs = (
            (0x01, 5), (0x07, 1), (0x40, 0),
            (0x43, 64), (0x45, 16), (0x50, 1),
        )
        for opcode, value in pairs:
            gold(image, bytes([opcode]) + tk.imm64(value))

    # @method test_imm_values() -> None
    # @in    нет
    # @out   нет
    # @does  Каждый imm-опкод с каждым золотым значением (0, 1, 12345,
    # @does  2^64-1) — вывод равен эталону disasm байт в байт, код 0
    # @does  (SPEC/L4-SELFHOST.txt, раздел 6: золотой набор).
    # @depends l2_image, gold
    def test_imm_values(self):
        image = l2_image()
        for rec in IMM:
            for value in VALUES:
                gold(image, bytes([rec[0]]) + tk.imm64(value))

    # @method test_mixed_stream() -> None
    # @in    нет
    # @out   нет
    # @does  Смешанный поток инструкций обоих видов — золотая сверка
    # @does  всего вывода с эталоном disasm байт в байт (SPEC, раздел 6).
    # @depends l2_image, gold
    def test_mixed_stream(self):
        gold(l2_image(), b"\x00" + b"\x01" + tk.imm64(12345) + b"\x13"
             + b"\x45" + tk.imm64(1))


class TestDbTail(unittest.TestCase):
    """Подшаг 3: хвост DB с опкода останова — эталон байт в байт."""

    # @method test_holes_tail_golden() -> None
    # @in    нет
    # @out   нет
    # @does  Дыры между диапазонами и коды за таблицей одним байтом:
    # @does  останов декодирования с хвостом DB из одного опкода —
    # @does  строка «DB <опкод>», код 0, сверка с эталоном байт в байт.
    # @depends l2_image, gold
    def test_holes_tail_golden(self):
        image = l2_image()
        for opcode in HOLES:
            gold(image, bytes([opcode]))

    # @method test_imm_cut_tail_golden() -> None
    # @in    нет
    # @out   нет
    # @does  Обрыв поля imm64 (0-7 байтов после опкода) — останов
    # @does  с хвостом DB: опкод и прочитанные байты поля первой строкой
    # @does  данных; сверка с эталоном байт в байт, код 0 (SPEC,
    # @does  раздел 5: хвост DB — опкод и прочитанные байты поля).
    # @depends l2_image, gold
    def test_imm_cut_tail_golden(self):
        image = l2_image()
        for rec in IMM:
            for count in range(8):
                gold(image, bytes([rec[0]]) + b"\x39" * count)

    # @method test_stop_keeps_prefix() -> None
    # @in    нет
    # @out   нет
    # @does  Останов на неизвестном коде сохраняет строки напечатанных
    # @does  до него инструкций и печатает хвост DB с опкода останова
    # @does  (включая данные после него); сверка с эталоном.
    # @depends l2_image, gold
    def test_stop_keeps_prefix(self):
        gold(l2_image(), b"\x00\x00\x08\x00")

    # @method test_imm_cut_keeps_prefix() -> None
    # @in    нет
    # @out   нет
    # @does  Обрыв поля после напечатанных инструкций: префикс сохранён,
    # @does  хвост DB — опкод PUSH и прочитанные байты поля; сверка
    # @does  с эталоном байт в байт.
    # @depends l2_image, gold
    def test_imm_cut_keeps_prefix(self):
        gold(l2_image(), b"\x00\x01\x39\x30\x00\x13")

    # @method test_tail_lengths_golden() -> None
    # @in    нет
    # @out   нет
    # @does  Хвосты данных всех длин 1-18 (короткая строка, ровно
    # @does  восемь аргументов, полная строка плюс один, две полных
    # @does  плюс один) на двух неизвестных опкодах — группировка
    # @does  по восемь аргументов, сверка с эталоном байт в байт
    # @does  (SPEC, раздел 6: длина хвоста кратна восьми, короче
    # @does  восьми и смешанная).
    # @depends l2_image, gold
    def test_tail_lengths_golden(self):
        image = l2_image()
        for opcode in (0x51, 0xFF):
            for count in range(18):
                data = bytes([opcode]) + bytes(
                    (i * 37 + 11) & 0xFF for i in range(count))
                gold(image, data)

    # @method test_tail_exact_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Точная форма строк DB: восемь аргументов — одна строка
    # @does  без пустого хвоста; девять — полная строка и неполная
    # @does  вторая; аргументы — десятичные байты 0..255 через пробел.
    # @depends l2_image, feed
    def test_tail_exact_lines(self):
        image = l2_image()
        code, out = feed(image, b"\x51" + bytes(range(7)))
        self.assertEqual((code, out), (0, b"DB 81 0 1 2 3 4 5 6\n"))
        code, out = feed(image, b"\x51" + bytes(range(8)))
        self.assertEqual((code, out),
                         (0, b"DB 81 0 1 2 3 4 5 6\nDB 7\n"))

    # @method test_tail_stale_ii_golden() -> None
    # @in    нет
    # @out   нет
    # @does  Устаревшие iv/ii прежней инструкции с полем imm64 не
    # @does  попадают в хвост DB следующего неизвестного опкода (dbstop
    # @does  обнуляет ii): после PUSH 5 — хвост только «DB 255»; сверка
    # @does  с эталоном байт в байт.
    # @depends l2_image, gold
    def test_tail_stale_ii_golden(self):
        image = l2_image()
        gold(image, b"\x01" + tk.imm64(5) + b"\xff")
        gold(image, b"\x01" + tk.imm64(0x0102030405060708)
             + b"\x51\x07\x08")

    # @method test_tail_mixed_golden() -> None
    # @in    нет
    # @out   нет
    # @does  Смешанная программа: инструкции обоих видов, затем данные
    # @does  с опкода останова — весь вывод равен эталону disasm байт
    # @does  в байт (SPEC, раздел 6: смешанные программы).
    # @depends l2_image, gold
    def test_tail_mixed_golden(self):
        gold(l2_image(), b"\x00\x01" + tk.imm64(12345) + b"\x13"
             + b"\x45" + tk.imm64(1) + b"\x51\x07\x08")


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5): uvm_cli."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта настоящими процессами: ubrick_cli compile,
    # @does  затем uvm_cli с входным файлом из инструкций обоих видов;
    # @does  вывод — ожидаемые строки, код процесса 0.
    # @depends l2_source
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "disasm.uvm")
            src = os.path.join(tmp, "in.uvm")
            with open(src, "wb") as handle:
                handle.write(b"\x00" + b"\x01" + (12345).to_bytes(8, "little")
                             + b"\x13" + b"\x45" + (0).to_bytes(8, "little"))
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
            self.assertEqual(
                run.stdout, b"NOP\nPUSH 12345\nSTORE64\nHALT 0\n")

    # @method test_process_tail() -> None
    # @in    нет
    # @out   нет
    # @does  Сквозной прогон с хвостом DB во входе: неизвестный опкод
    # @does  и данные после него печатаются директивой DB, код 0
    # @does  (SPEC, раздел 5: останов декодирования — данные директивами
    # @does  DB до конца входа).
    # @depends l2_source
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "disasm.uvm")
            src = os.path.join(tmp, "in.uvm")
            with open(src, "wb") as handle:
                handle.write(b"\x00\x51\x01\x02")
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
            self.assertEqual(run.stdout, b"NOP\nDB 81 1 2\n")


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
