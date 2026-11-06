# @uadro
# @file    tests/test_l2_assemble_sym.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшага 5 ветви l2.uasm.assemble — таблица символов
# @desc    и проход 1 (src/l2/asmsym.ubrk — запись и поиск имён; слова
# @desc    p1addr/recsize/p1step главного файла src/l2/assemble.ubrk):
# @desc    выход — образ UVM (подшаг 6): адреса записей наблюдаемы
# @desc    значениями ссылок на метки (imm64 переходов), константы —
# @desc    аргументами DW/DB; ожидания строит эталон assemble
# @desc    (tools/uasm_assemble.py) — паритет с источником истины
# @desc    поведения. Размеры записей всех видов (инструкция 9/1, DB,
# @desc    DW, DS, DZ — recsize), ссылки вперёд, метка в конце текста,
# @desc    повторные определения (метка/константа в любом порядке),
# @desc    лимит имени 63 байта («слишком длинное имя» — контракт
# @desc    инструмента, у эталона лимита нет), дымовые наборы из сотен
# @desc    символов, сквозной прогон процессами. Переполнение таблицы
# @desc    символов прогоном не покрыто: квадратичный поиск делает полный
# @desc    набор (~4,5 тыс. записей) многократноминутным для эмулятора.

"""Тесты таблицы символов и прохода 1 подшага 5 ветви l2.uasm.assemble.

Проход 1 (SPEC/L2-UASM.txt, раздел 7; SPEC/L4-SELFHOST.txt, раздел 5А):
каждой записи назначается адрес, метки определяются адресами следующей
записи, константы — значениями литералов; повторное определение — ошибка.
Выход собственного ассемблера — образ UVM (подшаг 6): адреса записей
видны значениями ссылок на метки (JMP/CALL на метку за N байтов записи),
значения констант — аргументами DW/DB; при ошибке образ не выводится —
только диагностическая строка и код 16.

Паритет (TestParity): ожидания каждой программы строит эталон assemble
(tools/uasm_assemble.py) — расхождение — ошибка собственного воплощения.
Границы контракта инструмента (63 байта имени) сверх эталона — явные
ожидания.
"""

import os
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_assemble import assemble
from tools.uvm_table import TABLE

CODES = {rec[1]: rec[0] for rec in TABLE}   # мнемоника -> код


# @method le(v) -> bytes
# @in    v: int — слово 0..2^64-1
# @out   raw: bytes — восемь байтов little-endian
# @does  Кодирует поле imm64 и аргумент DW в ожиданиях тестов (SPEC/
# @does  L2-UASM.txt, разделы 5-6).
def le(v):
    return v.to_bytes(8, "little")


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
# @does  SPEC/L4-SELFHOST.txt, раздел 5А); инструмент включает asmsym.ubrk
# @does  строкой use.
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "assemble.ubrk")


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ ассемблера (None — ошибка сборки)
# @does  Собирает src/l2/assemble.ubrk командой ubrick_cli (compile);
# @does  кирпич всех тестов файла (asmsym.ubrk внутри инструмента).
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


# @method symwant(text) -> tuple
# @in    text: str — текст uAsm (несколько строк)
# @out   pair: tuple — (код завершения, байты stdout) ожидание
# @does  Строит ожидание эталоном assemble (кирпич паритета с
# @does  tools/uasm_assemble.py, источник истины поведения): успех —
# @does  образ байт в байт, код 0; ошибка — диагностическая строка
# @does  «uAsm: строка N: текст» и код 16.
# @depends assemble
def symwant(text):
    image, error = assemble(text)
    if error is not None:
        return 16, (error + "\n").encode("utf-8")
    return 0, image


class TestParity(unittest.TestCase):
    """Программы целиком — паритет с эталоном assemble (байт в байт)."""

    # @method test_programs() -> None
    # @in    нет
    # @out   нет
    # @does  Представители программ всех форм: метки и константы,
    # @does  инструкции и директивы (сдвигают адреса — наблюдаемо
    # @does  ссылками), несколько меток на одном адресе, ссылки вперёд,
    # @does  метка в конце текста, ошибки разбора и повторных
    # @does  определений — вывод собственного воплощения равен эталону
    # @does  байт в байт.
    # @depends feed, symwant
    def test_programs(self):
        programs = [
            "",
            "\n\n",
            "; только комментарий",
            "x:",
            "NOP\nx:",
            "x:\nNOP\ny:",
            "a:\nb:\nc:",
            "x:\nDB 1 2\ny:\nDW 3\nz:",
            'a:\nDS "s"\nb:\nDZ "z"\nc:',
            "x = 5\na:\nNOP\nb:",
            "x = 18446744073709551615\ny = -1\nz = -9223372036854775808",
            "JMP end\nNOP\nend:",
            "CALL fwd\nfwd:",
            "PUSH 1\nPUSH 2\nADD\nHALT 0",
            "main:\nCALL main\nHALT 0",
            "x:\nx:",
            "x = 1\nx = 2",
            "x:\nx = 1",
            "x = 1\nx:",
            "a:\nNOP\nb:\nb:\nc:",
            "NOP\nPUS",
            "PUSH",
            "DB",
            'DS "a',
            "x = y",
            "5 = 5",
            "a b = 5",
        ]
        for text in programs:
            with self.subTest(text=text):
                self.assertEqual(feed(text.encode("utf-8")),
                                 symwant(text))


class TestAddresses(unittest.TestCase):
    """Адреса записей: recsize всех видов наблюдаем ссылками на метки."""

    # @method test_sizes() -> None
    # @in    нет
    # @out   нет
    # @does  Записи всех видов кодируются с верными размерами (SPEC/
    # @does  L2-UASM.txt, раздел 7): DB 1 2 — 2 байта, DW 3 4 — 16,
    # @does  DS «s» — 1, DZ «z» — 2 (плюс байт 0), NOP — 1, PUSH 1 — 9;
    # @does  JMP на метку за всеми записями получает накопленный адрес
    # @does  40 (9 + 2 + 16 + 1 + 2 + 1 + 9 — проверка recsize всех видов
    # @does  разом; метка в конце — адрес конца образа).
    # @depends feed
    def test_sizes(self):
        text = ("JMP g\nDB 1 2\nDW 3 4\nDS \"s\"\nDZ \"z\"\n"
                "NOP\nPUSH 1\ng:\n")
        self.assertEqual(
            feed(text.encode()),
            (0, bytes([CODES["JMP"]]) + le(40) + b"\x01\x02"
             + le(3) + le(4) + b"s" + b"z\x00"
             + bytes([CODES["NOP"]]) + bytes([CODES["PUSH"]]) + le(1)))

    # @method test_label_at_end() -> None
    # @in    нет
    # @out   нет
    # @does  Метка в конце текста получает адрес конца образа (SPEC/
    # @does  L2-UASM.txt, раздел 3), наблюдаемый ссылкой на неё: JMP на
    # @does  метку после NOP — адрес 10 (9 + 1); JMP на метку сразу за
    # @does  ним — 9; метка без перевода строки в конце входа тоже
    # @does  разбирается (JMP после PUSH 1 и HALT 0 — адрес 27).
    # @depends feed
    def test_label_at_end(self):
        self.assertEqual(
            feed(b"JMP x\nNOP\nx:"),
            (0, bytes([CODES["JMP"]]) + le(10) + bytes([CODES["NOP"]])))
        self.assertEqual(feed(b"JMP x\nx:"),
                         (0, bytes([CODES["JMP"]]) + le(9)))
        self.assertEqual(
            feed(b"JMP end\nPUSH 1\nHALT 0\nend:"),
            (0, bytes([CODES["JMP"]]) + le(27) + bytes([CODES["PUSH"]])
             + le(1) + bytes([CODES["HALT"]]) + le(0)))

    # @method test_forward_reference() -> None
    # @in    нет
    # @out   нет
    # @does  Ссылка вперёд: метка после использования получает адрес,
    # @does  который подставляет проход 2 (SPEC/L2-UASM.txt, раздел 3):
    # @does  JMP end — 9 байтов, NOP — 1, end = 10; CALL fwd — 9,
    # @does  fwd = 9.
    # @depends feed
    def test_forward_reference(self):
        self.assertEqual(
            feed(b"JMP end\nNOP\nend:"),
            (0, bytes([CODES["JMP"]]) + le(10) + bytes([CODES["NOP"]])))
        self.assertEqual(
            feed(b"CALL fwd\nfwd:"),
            (0, bytes([CODES["CALL"]]) + le(9)))

    # @method test_const_no_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  Метки и константы байтов не дают (record_size эталона — 0):
    # @does  константа между инструкциями не сдвигает адреса — образ
    # @does  одной инструкции NOP.
    # @depends feed
    def test_const_no_bytes(self):
        self.assertEqual(feed(b"x = 5\nNOP\n"), (0, bytes([CODES["NOP"]])))

    # @method test_string_sizes() -> None
    # @in    нет
    # @out   нет
    # @does  Длины литералов DS/DZ — декодированные байты: «a» плюс шесть
    # @does  escape — 7 байтов (escape по байту), многобайтовый UTF-8
    # @does  дословно («привет» — 12); DZ добавляет байт 0 («мир!» —
    # @does  7 + 1 = 8) — JMP на метку за директивой получает адрес
    # @does  9 + длина (16, 21 и 17).
    # @depends feed
    def test_string_sizes(self):
        jump = bytes([CODES["JMP"]])
        self.assertEqual(
            feed(b'JMP b\nDS "a\\n\\r\\t\\\\\\"\\0"\nb:\n'),
            (0, jump + le(16) + b"a\n\r\t\\\"\x00"))
        self.assertEqual(
            feed('JMP b\nDS "привет"\nb:\n'.encode("utf-8")),
            (0, jump + le(21) + "привет".encode("utf-8")))
        self.assertEqual(
            feed('JMP b\nDZ "мир!"\nb:\n'.encode("utf-8")),
            (0, jump + le(17) + "мир!".encode("utf-8") + b"\x00"))


class TestDuplicates(unittest.TestCase):
    """Повторные определения — единое пространство имён (SPEC, раздел 3)."""

    # @method test_duplicates() -> None
    # @in    нет
    # @out   нет
    # @does  Повторное определение имени — ошибка с номером строки
    # @does  второго определения (SPEC/L2-UASM.txt, раздел 7): метка
    # @does  после метки, константа после константы, константа после
    # @does  метки и метка после константы; образ при ошибке
    # @does  не выводится — только диагностика, код 16.
    # @depends feed
    def test_duplicates(self):
        cases = [
            ("x:\nx:\n", 2, "x"),
            ("x = 1\nx = 2\n", 2, "x"),
            ("x:\nx = 1\n", 2, "x"),
            ("x = 1\nx:\n", 2, "x"),
            ("a:\nNOP\nb:\nb:\nc:\n", 4, "b"),
        ]
        for text, line, name in cases:
            with self.subTest(text=text):
                want = ("uAsm: строка %d: повторное определение "
                        "имени %s\n" % (line, name)).encode("utf-8")
                self.assertEqual(feed(text.encode()), (16, want))


class TestNames(unittest.TestCase):
    """Лимит имени 63 байта — контракт инструмента (SPEC, раздел 5А)."""

    # @method test_name_limits() -> None
    # @in    нет
    # @out   нет
    # @does  Имя 63 байта — норма (метка и константа наблюдаются
    # @does  аргументом DW: адрес метки 0 и значение константы 7), 64 —
    # @does  «слишком длинное имя» и код 16 (SPEC/L4-SELFHOST.txt,
    # @does  раздел 5А: запись «значение 8 LE + имя + 0»; у эталона
    # @does  лимита нет — ожидания явные, не паритет).
    # @depends feed
    def test_name_limits(self):
        ok = "a" * 63
        self.assertEqual(feed((ok + ":\nDW " + ok + "\n").encode()),
                         (0, le(0)))
        self.assertEqual(
            feed((ok + " = 7\nDW " + ok + "\n").encode()),
            (0, le(7)))
        for line in ("b" * 64 + ":", "b" * 64 + " = 1"):
            with self.subTest(line=line[-2:]):
                code, out = feed((line + "\n").encode())
                self.assertEqual(
                    (code, out),
                    (16, "uAsm: строка 1: слишком длинное имя\n"
                         .encode("utf-8")))


class TestSmoke(unittest.TestCase):
    """Дымовые наборы: десятки и сотни символов за один прогон."""

    # @method test_many_consts() -> None
    # @in    нет
    # @out   нет
    # @does  100 пар «константа + DW имя»: каждая дописывает запись
    # @does  в таблицу, поиск различает имена без ложных совпадений
    # @does  (s0/s1/s10 — префиксы), значения кодируются little-endian;
    # @does  ожидание строит эталон assemble.
    # @depends feed, symwant
    def test_many_consts(self):
        count = 100
        text = "".join("s%d = %d\nDW s%d\n" % (i, i, i)
                       for i in range(count))
        self.assertEqual(feed(text.encode()), symwant(text))

    # @method test_label_chain() -> None
    # @in    нет
    # @out   нет
    # @does  60 пар «DB 7 + метка»: каждая метка — накопленный адрес
    # @does  (DB — один байт), JMP на конечную метку получает 9 + 60 =
    # @does  69; курсор таблицы продвигается symnext корректно на каждой
    # @does  записи.
    # @depends feed
    def test_label_chain(self):
        count = 60
        text = "JMP end\n" + "".join("DB 7\nl%d:\n" % i
                                     for i in range(count)) + "end:\n"
        self.assertEqual(
            feed(text.encode()),
            (0, bytes([CODES["JMP"]]) + le(count + 9)
             + b"\x07" * count))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5А)."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта процессами: ubrick_cli compile, затем
    # @does  uvm_cli с входным файлом; stdout — образ программы
    # @does  со ссылкой вперёд (JMP end: опкод 0x40, imm64 10 — адрес
    # @does  метки за NOP), код 0.
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "assemble.uvm")
            src = os.path.join(tmp, "in.uasm")
            with open(src, "wb") as handle:
                handle.write(b"JMP end\nNOP\nend:\n")
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
            self.assertEqual(run.stdout,
                             bytes([CODES["JMP"]]) + le(10)
                             + bytes([CODES["NOP"]]))


if __name__ == "__main__":
    unittest.main()
