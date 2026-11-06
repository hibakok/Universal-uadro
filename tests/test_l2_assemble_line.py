# @uadro
# @file    tests/test_l2_assemble_line.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшага 4 ветви l2.uasm.assemble — разбор строки
# @desc    в запись (src/l2/asmline.ubrk — собственное воплощение эталона
# @desc    tools/uasm_line.py). Выход — образ UVM либо диагностика
# @desc    (подшаг 6): строка-метка и строка-константа байтов не дают,
# @desc    инструкция и директива данных
# @desc    кодируются байтами (значения имён — проход 2); ошибки разбора
# @desc    строки — «uAsm: строка N: текст» и код 16 по разделу 7 SPEC/
# @desc    L2-UASM.txt (SPEC/L4-SELFHOST.txt, раздел 5А). Ожидания
# @desc    строятся эталоном assemble (tools/uasm_assemble.py) — паритет
# @desc    с источником истины поведения; порядок разбора — явные
# @desc    ожидания (TestOrder).

"""Тесты разбора строки в запись подшага 4 ветви l2.uasm.assemble.

Собственный ассемблер (кирпичи l2_image и feed) прогоняется на текстах;
каждая непустая строка даёт запись. Ожидание строит эталон assemble
(tools/uasm_assemble.py): успех — образ байт в байт (метка и константа
байтов не дают — пустой образ для одиночной строки; инструкция — байт
опкода и, с imm64, значение операнда; директива данных — свои байты),
ошибка — диагностическая строка «uAsm: строка 1: текст» и код 16.
Сплошная сверка (test_sweep) гоняет представителей всех видов строк
через оба воплощения.

Порядок разбора (SPEC/L2-UASM.txt, раздел 7): метка — прежде
мнемоники («PUSH:» — метка), мнемоника — прежде константы («PUSH = 5» —
инструкция с операндом «= 5»), директива — прежде константы («DB = 5» —
данные); знак «=» вне кавычек ищется по всей чистой строке («x=5» без
пробелов — константа).
"""

import os
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_assemble import assemble
# Собственный ассемблер пишется под ISA v0.2 (SPEC/L4-SELFHOST.txt,
# раздел 2): мнемоники — из кирпича isa_v02_table, а не из полной
# таблицы эталона (уже с DEVRD/DEVWR v0.3); собственному ассемблеру
# они приходят подшагом 5.4 (ROADMAP.txt, Этап 5).
V02 = tk.isa_v02_table()                    # ISA v0.2 — 38 опкодов
CODES = {rec[1]: rec[0] for rec in V02}   # мнемоника -> код


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
# @out   pair: tuple — (код завершения, байты stdout) ожидание
# @does  Строит ожидание эталоном (кирпич паритета с
# @does  tools/uasm_assemble.py, источник истины поведения): assemble
# @does  одной строки — успех — образ байт в байт (метка и константа
# @does  байтов не дают), ошибка — диагностика «uAsm: строка 1: текст»
# @does  и код 16 (запись ошибки разбора либо ошибка значения прохода 2:
# @does  операнд-имя без определения, плохой литерал).
# @depends assemble
def record(line):
    image, error = assemble(line + "\n")
    if error is not None:
        return 16, (error + "\n").encode("utf-8")
    return 0, image


# @method line_want(line) -> tuple
# @in    line: str — одна строка исходника uAsm
# @out   pair: tuple — (код завершения, байты stdout) ожидание прогона
# @does  Прогон одной строки с переводом: кирпич коротких проверек
# @does  паритета (сверяет собственное воплощение с эталоном).
# @depends record
def line_want(line):
    code, out = record(line)
    return code, out


# @method err(line, text) -> bytes
# @in    line: int — номер строки текста, начиная с 1
# @in    text: str — текст ошибки
# @out   want: bytes — диагностическая строка с переводом
# @does  Строит ожидаемую диагностику «uAsm: строка N: текст»; кирпич
# @does  тестов порядка разбора (TestOrder).
def err(line, text):
    return ("uAsm: строка %d: %s\n" % (line, text)).encode("utf-8")


class TestParity(unittest.TestCase):
    """Сплошная сверка разбора с эталоном assemble (все виды строк)."""

    # @method test_sweep() -> None
    # @in    нет
    # @out   нет
    # @does  Представители всех видов строк и ошибок — через эталон
    # @does  assemble и собственное воплощение байт в байт: мнемоники
    # @does  с операндами и без (байты опкода и imm64), метки (в том
    # @does  числе PUSH: — роль слова определяет позиция), константы
    # @does  всех форм с минусом и границами диапазона (байтов не дают),
    # @does  директивы данных (байты DB/DW/DS/DZ), ошибки всех текстов
    # @does  раздела 7 SPEC и ошибки значений прохода 2 (операнд-имя
    # @does  без определения), пробелы, табуляции и комментарии.
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
    # @does  раздел 3), а не инструкция — метка байтов не даёт, образ
    # @does  пуст.
    # @depends feed
    def test_label_before_mnemonic(self):
        self.assertEqual(feed(b"PUSH:\n"), (0, b""))

    # @method test_mnemonic_before_const() -> None
    # @in    нет
    # @out   нет
    # @does  Мнемоника разбирается раньше константы: «PUSH = 5» —
    # @does  инструкция с операндом «= 5» (у PUSH есть поле imm64),
    # @does  значение операнда решает проход 2 — «плохой литерал = 5»
    # @does  (константа с именем PUSH собралась бы без ошибки).
    # @depends feed, err
    def test_mnemonic_before_const(self):
        self.assertEqual(feed(b"PUSH = 5\n"),
                         (16, err(1, "плохой литерал = 5")))

    # @method test_directive_before_const() -> None
    # @in    нет
    # @out   нет
    # @does  Директива разбирается раньше константы: «DB = 5» — данные
    # @does  с двумя аргументами «=» и «5» (значения решает проход 2) —
    # @does  первый аргумент не литерал и не имя: «плохой литерал =».
    # @depends feed, err
    def test_directive_before_const(self):
        self.assertEqual(feed(b"DB = 5\n"),
                         (16, err(1, "плохой литерал =")))

    # @method test_eq_in_first_word() -> None
    # @in    нет
    # @out   нет
    # @does  Знак «=» ищется по всей чистой строке, включая первое
    # @does  слово: «x=5» без пробелов — константа с именем x (байтов
    # @does  не даёт, образ пуст).
    # @depends feed
    def test_eq_in_first_word(self):
        self.assertEqual(feed(b"x=5\n"), (0, b""))

    # @method test_eq_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  Знак «=» внутри литералов в кавычках константу не открывает:
    # @does  «foo "a=b"» — ни один вид записи, ошибка «неизвестная
    # @does  мнемоника foo».
    # @depends feed, err
    def test_eq_in_quotes(self):
        self.assertEqual(feed(b'foo "a=b"\n'),
                         (16, err(1, "неизвестная мнемоника foo")))

    # @method test_const_eq_in_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Правая часть константы — символьный литерал с «=»: «x = '='»
    # @does  — константа со значением 61 (find_outside_quotes эталона
    # @does  не считает «=» в кавычках знаком константы); байтов не даёт.
    # @depends feed
    def test_const_eq_in_operand(self):
        self.assertEqual(feed(b"x = '='\n"), (0, b""))


class TestConst(unittest.TestCase):
    """Константы: имена и литералы правой части (SPEC, разделы 3-4)."""

    # @method test_bad_names() -> None
    # @in    нет
    # @out   нет
    # @does  Левая часть не имя (цифра первой, два слова, двоеточие
    # @does  в конце, пустая) — «плохое имя», код 16.
    # @depends feed, err
    def test_bad_names(self):
        for line in ("5 = 5", "a b = 5", "x: = 5", "= 5", "x:=5"):
            with self.subTest(line=line):
                code, out = feed(line.encode() + b"\n")
                self.assertEqual((code, out),
                                 (16, err(1, "плохое имя")))

    # @method test_bad_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Правая часть не литерал — «плохой литерал X» с X — правая
    # @does  часть (bad_literal эталона): имя, мусор, несколько слов;
    # @does  пустая правая часть — «плохой литерал» без X.
    # @depends feed, err
    def test_bad_literals(self):
        self.assertEqual(feed(b"x = y\n"),
                         (16, err(1, "плохой литерал y")))
        self.assertEqual(feed(b"x = 5x\n"),
                         (16, err(1, "плохой литерал 5x")))
        self.assertEqual(feed(b"x = 1 2\n"),
                         (16, err(1, "плохой литерал 1 2")))
        self.assertEqual(feed(b"x =\n"),
                         (16, err(1, "плохой литерал")))

    # @method test_out_of_range() -> None
    # @in    нет
    # @out   нет
    # @does  Верные цифры вне -2^63..2^64-1 — «литерал вне диапазона»:
    # @does  2^64 и -(2^63+1) (границы — в test_sweep).
    # @depends feed, err
    def test_out_of_range(self):
        for right in ("18446744073709551616", "-9223372036854775809"):
            with self.subTest(right=right):
                code, out = feed(("x = " + right + "\n").encode())
                self.assertEqual((code, out),
                                 (16, err(1, "литерал вне диапазона")))


class TestInstr(unittest.TestCase):
    """Инструкции: операнды (SPEC, раздел 5)."""

    # @method test_operand_is_text() -> None
    # @in    нет
    # @out   нет
    # @does  Операнд остаётся текстом до прохода 2 (SPEC, раздел 7):
    # @does  «CALL main» разбирается без ошибки разбора, но имя не
    # @does  определено — «неизвестное имя main» в проходе 2, код 16;
    # @does  определённая ниже метка разрешается (main: + CALL main —
    # @does  образ с адресом ссылки).
    # @depends feed, err
    def test_operand_is_text(self):
        self.assertEqual(feed(b"CALL main\n"),
                         (16, err(1, "неизвестное имя main")))
        self.assertEqual(feed(b"main:\nCALL main\n"),
                         (0, bytes([CODES["CALL"]])
                          + (0).to_bytes(8, "little")))

    # @method test_missing_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция с imm64 без операнда — «нет операнда у X»:
    # @does  PUSH, HALT, SYS (код 16).
    # @depends feed, err
    def test_missing_operand(self):
        for m in ("PUSH", "HALT", "SYS"):
            with self.subTest(m=m):
                code, out = feed((m + "\n").encode())
                self.assertEqual(
                    (code, out),
                    (16, err(1, "нет операнда у " + m)))

    # @method test_extra_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция без imm64 с операндом — «лишний операнд у X»:
    # @does  NOP, RET, ADD (код 16).
    # @depends feed, err
    def test_extra_operand(self):
        for m in ("NOP", "RET", "ADD"):
            with self.subTest(m=m):
                code, out = feed((m + " 1\n").encode())
                self.assertEqual(
                    (code, out),
                    (16, err(1, "лишний операнд у " + m)))


class TestData(unittest.TestCase):
    """Директивы данных (SPEC, раздел 6)."""

    # @method test_empty_directive() -> None
    # @in    нет
    # @out   нет
    # @does  DB и DW без аргументов — «пустая директива X» (X — слово
    # @does  директивы), код 16.
    # @depends feed, err
    def test_empty_directive(self):
        for m in ("DB", "DW"):
            with self.subTest(m=m):
                code, out = feed((m + "\n").encode())
                self.assertEqual(
                    (code, out),
                    (16, err(1, "пустая директива " + m)))

    # @method test_string_literals_parse() -> None
    # @in    нет
    # @out   нет
    # @does  Строковые литералы DS/DZ кодируются декодированными байтами
    # @does  (escape — по байту, многобайтовый UTF-8 дословно, DZ
    # @does  добавляет байт 0); значения — как у эталона assemble
    # @does  (parse_string + кодирование раздела 6).
    # @depends feed
    def test_string_literals_parse(self):
        cases = [
            ('DS "a\\n\\r\\t\\\\\\"\\0"', b"a\n\r\t\\\"\x00"),
            ('DS "привет"', "привет".encode("utf-8")),
            ('DZ "мир!"', "мир!".encode("utf-8") + b"\x00"),
            ('DS ""', b""),
            ('DZ "ab"', b"ab\x00"),
        ]
        for line, image in cases:
            with self.subTest(line=line):
                self.assertEqual(feed((line + "\n").encode("utf-8")),
                                 (0, image))

    # @method test_bad_string_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Нарушения литерала DS/DZ — «плохой строковый литерал»:
    # @does  без кавычек, не закрыт, мусор после закрывающей, обрыв
    # @does  escape (parse_string эталона None), код 16.
    # @depends feed, err
    def test_bad_string_literal(self):
        for line in (b"DS x", b'DS "a', b'DS "a" x', b'DS "a\\q"',
                     b'DS "a\\'):
            with self.subTest(line=line):
                self.assertEqual(
                    feed(line + b"\n"),
                    (16, err(1, "плохой строковый литерал")))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5А)."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта процессами: ubrick_cli compile, затем
    # @does  uvm_cli с входным файлом; stdout — образ программы
    # @does  всех видов записей (NOP 1 байт, PUSH 1 — 9, DB 1 2 — 2,
    # @does  DW x — 8, DS «s» — 1, DZ «z» — 2; константа и метки байтов
    # @does  не дают) — ожидание строит эталон assemble, код 0.
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        import subprocess
        import sys
        import tempfile
        text = (b"NOP\nPUSH 1\na:\nDB 1 2\nDW x\n"
                b'DS "s"\nDZ "z"\nx = 5\nend:\n')
        image_want, error = assemble(text.decode("utf-8"))
        self.assertIsNone(error)
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "assemble.uvm")
            src = os.path.join(tmp, "in.uasm")
            with open(src, "wb") as handle:
                handle.write(text)
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
            self.assertEqual(run.stdout, image_want)


if __name__ == "__main__":
    unittest.main()
