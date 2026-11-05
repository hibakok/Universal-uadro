# @uadro
# @file    tests/test_l2_assemble_line.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшага 4 ветви l2.uasm.assemble — разбор строки
# @desc    в запись (src/l2/asmline.ubrk — собственное воплощение эталона
# @desc    tools/uasm_line.py): листинг записей «N:L имя» | «N:C имя=
# @desc    значение» | «N:I код [операнд]» | «N:DB|DW argc» | «N:DS|DZ
# @desc    длина»; ошибки разбора строки — «uAsm: строка N: текст»
# @desc    и код 16 по разделу 7 SPEC/L2-UASM.txt (SPEC/L4-SELFHOST.txt,
# @desc    раздел 5А). Ожидания записей и ошибок строятся эталоном
# @desc    parse_line — паритет с источником истины поведения.

"""Тесты разбора строки в запись подшага 4 ветви l2.uasm.assemble.

Собственный ассемблер (кирпичи l2_image и feed) прогоняется на текстах;
каждая непустая строка даёт запись. Ожидание строит эталон
tools/uasm_line.py (parse_line): вид записи переводится в строку
листинга «N:V …» — метка «L имя», константа «C имя=значение»
(значение по модулю 2^64), инструкция «I код [операнд]», DB/DW —
число аргументов, DS/DZ — длина декодированных байтов (DZ без байта 0 —
его добавит кодирование, подшаг 6). Ошибка разбора — диагностическая
строка «uAsm: строка 1: текст» и код 16; запись ошибки эталона —
источник истины текста. Сплошная сверка (test_sweep) гоняет
представителей всех видов строк через оба воплощения.

Порядок разбора (SPEC/L2-UASM.txt, раздел 7): метка — прежде
мнемоники («PUSH:» — метка), мнемоника — прежде константы («PUSH = 5» —
инструкция), директива — прежде константы («DB = 5» — данные); знак
«=» вне кавычек ищется по всей чистой строке («x=5» без пробелов —
константа).
"""

import os
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_line import parse_line
from tools.uvm_table import TABLE

WORD = 1 << 64
CODES = {rec[1]: rec[0] for rec in TABLE}   # мнемоника -> код


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для пути src/l2.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method l2_source() -> str
# @in    нет
# @out   path: str — путь к исходнику src/l2/assemble.ubrk
# @does  Строит путь к собственному воплощению ассемблера (слой L2,
# @does  SPEC/L4-SELFHOST.txt, раздел 5А); инструмент включает
# @does  asmline.ubrk строкой use.
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "assemble.ubrk")


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ ассемблера (None — ошибка сборки)
# @does  Собирает src/l2/assemble.ubrk командой ubrick_cli (compile);
# @does  кирпич всех тестов файла (asmline.ubrk внутри инструмента).
# @depends ubrick_cli.main
# @uses   sys.stderr — стандартный вывод ошибок хоста (через cli)
def l2_image():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "assemble.uvm")
        code = ubrick_cli.main(["compile", l2_source(), image])
        if code != 0:
            return None
        with open(image, "rb") as handle:
            return handle.read()


# @method feed(text) -> tuple
# @in    text: bytes — текст uAsm (вход ассемблера)
# @out   pair: tuple — (код завершения, байты stdout)
# @does  Прогон образа ассемблера без процесса (run_with_io); кирпич
# @does  всех тестов файла.
# @depends tk.run_with_io
def feed(text):
    return tk.run_with_io(l2_image(), text)


# @method record(line) -> tuple
# @in    line: str — одна строка исходника uAsm
# @out   pair: tuple — (код завершения, строка листинга записи)
# @does  Строит ожидание эталоном (кирпич паритета с tools/uasm_line.py,
# @does  источник истины поведения): parse_line даёт запись — вид
# @does  переводится в строку листинга «1:V …»; None (пустая строка
# @does  либо комментарий) — пустой вывод; ошибка — диагностика
# @does  «uAsm: строка 1: текст» и код 16.
# @depends parse_line, CODES
def record(line):
    rec = parse_line(line)
    if rec is None:
        return 0, b""
    kind = rec[0]
    if kind == "error":
        return 16, ("uAsm: строка 1: " + rec[1] + "\n").encode("utf-8")
    if kind == "label":
        return 0, ("1:L " + rec[1] + "\n").encode("utf-8")
    if kind == "const":
        return 0, ("1:C %s=%d\n" % (rec[1], rec[2] % WORD)).encode("utf-8")
    if kind == "instr":
        out = "1:I %d" % CODES[rec[1]]
        if rec[2] is not None:
            out += " " + rec[2]
        return 0, (out + "\n").encode("utf-8")
    directive, data = rec[1], rec[2]
    if directive in ("DB", "DW"):
        return 0, ("1:%s %d\n" % (directive, len(data))).encode("utf-8")
    n = len(data) - (1 if directive == "DZ" else 0)
    return 0, ("1:%s %d\n" % (directive, n)).encode("utf-8")


# @method line_want(line) -> tuple
# @in    line: str — одна строка исходника uAsm
# @out   pair: tuple — (код завершения, байты stdout) ожидание прогона
# @does  Прогон одной строки с переводом: кирпич коротких проверек
# @does  паритета (сверяет собственное воплощение с эталоном).
# @depends record
def line_want(line):
    code, out = record(line)
    return code, out


class TestParity(unittest.TestCase):
    """Сплошная сверка разбора с эталоном parse_line (все виды строк)."""

    # @method test_sweep() -> None
    # @in    нет
    # @out   нет
    # @does  Представители всех видов строк и ошибок — через эталон
    # @does  parse_line и собственное воплощение байт в байт: мнемоники
    # @does  с операндами и без, метки (в том числе PUSH: — роль слова
    # @does  определяет позиция), константы всех форм с минусом
    # @does  и границами диапазона, директивы данных, ошибки всех
    # @does  текстов раздела 7 SPEC, пробелы, табуляции и комментарии.
    # @depends feed, line_want
    def test_sweep(self):
        lines = []
        for m in CODES:
            lines.append(m + " 1")
            lines.append(m)
        lines += [
            "x:", "main:", "_a:", "PUSH:", "DB:", "x: y", ":", "1x:",
            "a-b:", "PUSH::",
            "x = 5", "x=5", "x  =  5", "x = -1", "x = 0x1F",
            "x = 'A'", "x = -0x10", "x = 0b101", "x = -'z'",
            "x = 'a=b'", 'x = "a"', "x = ", "x =", "x = 5x", "x = 1a",
            "x = --5", "x = -",
            "x = 99999999999999999999", "x = 18446744073709551616",
            "x = -9223372036854775808", "x = -9223372036854775809",
            "x = 9223372036854775807", "x = 18446744073709551615",
            "5 = 5", "a b = 5", "= 5", "x = = 5", "x:=5",
            "PUSH 1", "PUSH  1", "PUSH 1 2", "PUSH x", "CALL main",
            "HALT 0", "SYS 1", "PICK 3", "RET", "NOP", "NOP 1",
            "RET x", "PUSH", "PUSH = 5", "DB = 5",
            "DB 1 2 3", "DW 1 x 'A'", "DB 1, 2", "DB", "DW", "DB  ",
            'DS "s"', 'DZ "z"', 'DS ""', 'DZ "ab"', 'DS "a\\nb"',
            "DS x", 'DS "a', 'DS "a" x', 'DS "a\\q"', 'DS "a\\',
            'DS "a;b"', 'DS "a ; b"', 'DS "привет"', 'DZ "мир!"',
            "PUS", "nop", "STORE64X", "x", "'q'", "12x", "0x1F", "-",
            "=", "+", 'foo "a=b"', "a b c", "x\ty", "\tNOP",
            "NOP ; c", "  NOP  ", "; comment", "", "   ",
        ]
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(feed((line + "\n").encode("utf-8")),
                                 line_want(line))


class TestOrder(unittest.TestCase):
    """Порядок разбора строки — раздел 7 SPEC/L2-UASM.txt."""

    # @method test_label_before_mnemonic() -> None
    # @in    нет
    # @out   нет
    # @does  Слово с двоеточием разбирается раньше мнемоники: «PUSH:» —
    # @does  метка с именем PUSH (роль слова определяет позиция, SPEC,
    # @does  раздел 3), а не инструкция.
    # @depends feed
    def test_label_before_mnemonic(self):
        self.assertEqual(feed(b"PUSH:\n"), (0, b"1:L PUSH\n"))

    # @method test_mnemonic_before_const() -> None
    # @in    нет
    # @out   нет
    # @does  Мнемоника разбирается раньше константы: «PUSH = 5» —
    # @does  инструкция с операндом «= 5» (у PUSH есть поле imm64);
    # @does  ошибка литерала возможна только в проходе 2.
    # @depends feed
    def test_mnemonic_before_const(self):
        self.assertEqual(feed(b"PUSH = 5\n"), (0, b"1:I 1 = 5\n"))

    # @method test_directive_before_const() -> None
    # @in    нет
    # @out   нет
    # @does  Директива разбирается раньше константы: «DB = 5» — данные
    # @does  с двумя аргументами «=» и «5» (значения решит проход 2).
    # @depends feed
    def test_directive_before_const(self):
        self.assertEqual(feed(b"DB = 5\n"), (0, b"1:DB 2\n"))

    # @method test_eq_in_first_word() -> None
    # @in    нет
    # @out   нет
    # @does  Знак «=» ищется по всей чистой строке, включая первое
    # @does  слово: «x=5» без пробелов — константа с именем x.
    # @depends feed
    def test_eq_in_first_word(self):
        self.assertEqual(feed(b"x=5\n"), (0, b"1:C x=5\n"))

    # @method test_eq_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  Знак «=» внутри литералов в кавычках константу не открывает:
    # @does  «foo \"a=b\"» — ни один вид записи, ошибка «неизвестная
    # @does  мнемоника foo».
    # @depends feed
    def test_eq_in_quotes(self):
        self.assertEqual(feed(b'foo "a=b"\n'),
                         (16, "uAsm: строка 1: неизвестная мнемоника "
                              "foo\n".encode("utf-8")))

    # @method test_const_eq_in_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Правая часть константы — символьный литерал с «=»: «x = '='»
    # @does  — константа со значением 61 (find_outside_quotes эталона
    # @does  не считает «=» в кавычках знаком константы).
    # @depends feed
    def test_const_eq_in_operand(self):
        self.assertEqual(feed(b"x = '='\n"), (0, b"1:C x=61\n"))


class TestConst(unittest.TestCase):
    """Константы: значения, имена, диапазон (SPEC, разделы 3-4)."""

    # @method test_values() -> None
    # @in    нет
    # @out   нет
    # @does  Значения всех форм по модулю 2^64: -1 обёрнут
    # @does  в 18446744073709551615, -2^63 — в 2^63, hex и символьная
    # @does  формы считаются дословно.
    # @depends feed
    def test_values(self):
        self.assertEqual(feed(b"x = -1\n"),
                         (0, b"1:C x=18446744073709551615\n"))
        self.assertEqual(feed(b"x = -9223372036854775808\n"),
                         (0, b"1:C x=9223372036854775808\n"))
        self.assertEqual(feed(b"k = 0xDeAdBeEf\n"),
                         (0, b"1:C k=3735928559\n"))
        self.assertEqual(feed(b"k = 'A'\n"), (0, b"1:C k=65\n"))

    # @method test_bad_names() -> None
    # @in    нет
    # @out   нет
    # @does  Левая часть не имя (цифра первой, два слова, двоеточие
    # @does  в конце, пустая) — «плохое имя», код 16.
    # @depends feed
    def test_bad_names(self):
        for line in ("5 = 5", "a b = 5", "x: = 5", "= 5", "x:=5"):
            with self.subTest(line=line):
                code, out = feed(line.encode() + b"\n")
                self.assertEqual((code, out),
                                 (16, "uAsm: строка 1: плохое имя\n"
                                      .encode("utf-8")))

    # @method test_bad_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Правая часть не литерал — «плохой литерал X» с X — правая
    # @does  часть (bad_literal эталона): имя, мусор, несколько слов;
    # @does  пустая правая часть — «плохой литерал» без X.
    # @depends feed
    def test_bad_literals(self):
        self.assertEqual(feed(b"x = y\n"),
                         (16, "uAsm: строка 1: плохой литерал y\n"
                              .encode("utf-8")))
        self.assertEqual(feed(b"x = 5x\n"),
                         (16, "uAsm: строка 1: плохой литерал 5x\n"
                              .encode("utf-8")))
        self.assertEqual(feed(b"x = 1 2\n"),
                         (16, "uAsm: строка 1: плохой литерал 1 2\n"
                              .encode("utf-8")))
        self.assertEqual(feed(b"x =\n"),
                         (16, "uAsm: строка 1: плохой литерал\n"
                              .encode("utf-8")))

    # @method test_out_of_range() -> None
    # @in    нет
    # @out   нет
    # @does  Верные цифры вне -2^63..2^64-1 — «литерал вне диапазона»:
    # @does  2^64 и -(2^63+1) (границы — в test_sweep).
    # @depends feed
    def test_out_of_range(self):
        for right in ("18446744073709551616", "-9223372036854775809"):
            with self.subTest(right=right):
                code, out = feed(("x = " + right + "\n").encode())
                self.assertEqual((code, out),
                                 (16, "uAsm: строка 1: литерал вне "
                                      "диапазона\n".encode("utf-8")))


class TestInstr(unittest.TestCase):
    """Инструкции: операнды (SPEC, раздел 5)."""

    # @method test_operand_is_text() -> None
    # @in    нет
    # @out   нет
    # @does  Операнд остаётся текстом (имя разрешит проход 2): «CALL
    # @does  main» — код 67 и операнд main; «PUSH 1 2» — операнд из
    # @does  двух слов (ошибка литерала — только в проходе 2).
    # @depends feed
    def test_operand_is_text(self):
        self.assertEqual(feed(b"CALL main\n"), (0, b"1:I 67 main\n"))
        self.assertEqual(feed(b"PUSH 1 2\n"), (0, b"1:I 1 1 2\n"))

    # @method test_missing_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция с imm64 без операнда — «нет операнда у X»:
    # @does  PUSH, HALT, SYS (код 16).
    # @depends feed
    def test_missing_operand(self):
        for m in ("PUSH", "HALT", "SYS"):
            with self.subTest(m=m):
                code, out = feed((m + "\n").encode())
                self.assertEqual(
                    (code, out),
                    (16, ("uAsm: строка 1: нет операнда у " + m + "\n")
                         .encode("utf-8")))

    # @method test_extra_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция без imm64 с операндом — «лишний операнд у X»:
    # @does  NOP, RET, ADD (код 16).
    # @depends feed
    def test_extra_operand(self):
        for m in ("NOP", "RET", "ADD"):
            with self.subTest(m=m):
                code, out = feed((m + " 1\n").encode())
                self.assertEqual(
                    (code, out),
                    (16, ("uAsm: строка 1: лишний операнд у " + m + "\n")
                         .encode("utf-8")))


class TestData(unittest.TestCase):
    """Директивы данных (SPEC, раздел 6)."""

    # @method test_empty_directive() -> None
    # @in    нет
    # @out   нет
    # @does  DB и DW без аргументов — «пустая директива X» (X — слово
    # @does  директивы), код 16.
    # @depends feed
    def test_empty_directive(self):
        for m in ("DB", "DW"):
            with self.subTest(m=m):
                code, out = feed((m + "\n").encode())
                self.assertEqual(
                    (code, out),
                    (16, ("uAsm: строка 1: пустая директива " + m + "\n")
                         .encode("utf-8")))

    # @method test_string_literal_lengths() -> None
    # @in    нет
    # @out   нет
    # @does  Длина литералов DS/DZ — декодированные байты: 'a' плюс шесть
    # @does  escape — 7 байтов (escape по байту), многобайтовый UTF-8
    # @does  дословно («привет» — 12); байт 0 добавит только кодирование
    # @does  DZ (подшаг 6).
    # @depends feed
    def test_string_literal_lengths(self):
        self.assertEqual(feed(b'DS "a\\n\\r\\t\\\\\\"\\0"\n'),
                         (0, b"1:DS 7\n"))
        self.assertEqual(feed('DS "привет"\n'.encode("utf-8")),
                         (0, '1:DS 12\n'.encode("utf-8")))
        self.assertEqual(feed('DZ "мир!"\n'.encode("utf-8")),
                         (0, '1:DZ 7\n'.encode("utf-8")))

    # @method test_bad_string_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Нарушения литерала DS/DZ — «плохой строковый литерал»:
    # @does  без кавычек, не закрыт, мусор после закрывающей, обрыв
    # @does  escape (parse_string эталона None), код 16.
    # @depends feed
    def test_bad_string_literal(self):
        for line in (b"DS x", b'DS "a', b'DS "a" x', b'DS "a\\q"',
                     b'DS "a\\'):
            with self.subTest(line=line):
                self.assertEqual(
                    feed(line + b"\n"),
                    (16, "uAsm: строка 1: плохой строковый литерал\n"
                         .encode("utf-8")))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5А)."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта процессами: ubrick_cli compile, затем
    # @does  uvm_cli с входным файлом; stdout — листинг записей всех
    # @does  видов, код 0.
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "assemble.uvm")
            src = os.path.join(tmp, "in.uasm")
            with open(src, "wb") as handle:
                handle.write(b"NOP\nPUSH 1\na:\nDB 1 2\nDW x\n"
                             b'DS "s"\nDZ "z"\nx = 5\n')
            compile_code = subprocess.call(
                [sys.executable,
                 os.path.join(repo_root(), "tools", "ubrick_cli.py"),
                 "compile", l2_source(), image],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(compile_code, 0)
            with open(src, "rb") as handle:
                run = subprocess.run(
                    [sys.executable,
                     os.path.join(repo_root(), "tools", "uvm_cli.py"),
                     image],
                    stdin=handle, capture_output=True)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(
                run.stdout,
                b"1:I 0\n2:I 1 1\n3:L a\n4:DB 2\n5:DW 1\n6:DS 1\n"
                b"7:DZ 1\n8:C x=5\n")


if __name__ == "__main__":
    unittest.main()
