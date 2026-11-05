# @uadro
# @file    tests/test_l2_assemble_sym.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшага 5 ветви l2.uasm.assemble — таблица символов
# @desc    и проход 1 (src/l2/asmsym.ubrk — запись и поиск имён; слова
# @desc    p1addr/recsize/p1step/symlist главного файла src/l2/assemble.ubrk):
# @desc    выход — листинг символов «имя=значение» в порядке определения;
# @desc    ожидания строит эталон pass1 (tools/uasm_assemble.py) — паритет
# @desc    с источником истины поведения. Адреса записей всех видов
# @desc    (инструкция 9/1, DB, DW, DS, DZ — recsize), все 38 мнемоник
# @desc    с накоплением адресов, ссылки вперёд, метка в конце текста,
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
Выход собственного ассемблера — листинг «имя=значение» по записи на
строку, в порядке определения; при ошибке листинг не печатается — только
диагностическая строка и код 16.

Паритет (test_parity): ожидания каждой программы строит эталон pass1
(tools/uasm_assemble.py) — таблица символов в порядке определения
(словарь Python сохраняет порядок вставки) либо обёрнутая диагностика;
расхождение — ошибка собственного воплощения. Границы контракта
инструмента (63 байта имени) сверх эталона — явные ожидания.
"""

import os
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_assemble import pass1, split_lines
from tools.uvm_table import TABLE

WORD = 1 << 64
MNEMONICS = [rec[1] for rec in TABLE]   # 38 мнемоник
IMMS = {rec[1]: rec[3] for rec in TABLE}   # мнемоника -> imm64


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
# @does  Строит ожидание эталоном pass1 (кирпич паритета с
# @does  tools/uasm_assemble.py, источник истины поведения): таблица
# @does  символов в порядке определения печатается строками
# @does  «имя=значение» (значение по модулю 2^64), ошибка — своя
# @does  диагностическая строка «uAsm: строка N: текст» и код 16.
# @depends pass1, split_lines, WORD
def symwant(text):
    _, symbols, error = pass1(split_lines(text))
    if error is not None:
        return 16, (error + "\n").encode("utf-8")
    out = "".join("%s=%d\n" % (name, value % WORD)
                  for name, value in symbols.items())
    return 0, out.encode("utf-8")


class TestParity(unittest.TestCase):
    """Программы целиком — паритет с эталоном pass1 (байт в байт)."""

    # @method test_programs() -> None
    # @in    нет
    # @out   нет
    # @does  Представители программ всех форм: метки и константы,
    # @does  инструкции и директивы (сдвигают адреса), несколько меток
    # @does  на одном адресе, ссылки вперёд, метка в конце текста,
    # @does  ошибки разбора и повторных определений — вывод собственного
    # @does  воплощения равен эталону pass1 байт в байт.
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
    """Адреса записей: recsize всех видов и все мнемоники."""

    # @method test_sizes() -> None
    # @in    нет
    # @out   нет
    # @does  Метки между записями всех видов получают верные адреса
    # @does  (SPEC/L2-UASM.txt, раздел 7): DB 1 2 — 2 байта, DW 3 4 —
    # @does  16, DS «s» — 1, DZ «z» — 2 (плюс байт 0), NOP — 1,
    # @does  PUSH 1 — 9; значения — накопление recsize.
    # @depends feed
    def test_sizes(self):
        text = (b"a:\nDB 1 2\nb:\nDW 3 4\nc:\nDS \"s\"\nd:\nDZ \"z\"\n"
                b"e:\nNOP\nf:\nPUSH 1\ng:\n")
        self.assertEqual(
            feed(text),
            (0, b"a=0\nb=2\nc=18\nd=19\ne=21\nf=22\ng=31\n"))

    # @method test_all_mnemonics() -> None
    # @in    нет
    # @out   нет
    # @does  Все 38 мнемоник таблицы опкодов разбираются и копят адрес
    # @does  верно (ожидание — из эталонной таблицы tools/uvm_table,
    # @does  источник истины кодов и признака imm64): после каждой
    # @does  инструкции метка с накопленным адресом — 9 байтов у мнемоники
    # @does  с imm64, 1 без.
    # @depends feed, MNEMONICS, IMMS
    def test_all_mnemonics(self):
        lines = []
        want = []
        addr = 0
        for i, m in enumerate(MNEMONICS):
            lines.append(m + (" 1" if IMMS[m] else ""))
            lines.append("l%d:" % i)
            addr += 9 if IMMS[m] else 1
            want.append("l%d=%d\n" % (i, addr))
        code, out = feed(("\n".join(lines) + "\n").encode())
        self.assertEqual((code, out), (0, "".join(want).encode()))

    # @method test_label_at_end() -> None
    # @in    нет
    # @out   нет
    # @does  Метка в конце текста получает адрес конца образа (SPEC/
    # @does  L2-UASM.txt, раздел 3): NOP до метки — адрес 1; метка без
    # @does  перевода строки в конце входа — тоже разбирается.
    # @depends feed
    def test_label_at_end(self):
        self.assertEqual(feed(b"NOP\nx:"), (0, b"x=1\n"))
        self.assertEqual(feed(b"x:"), (0, b"x=0\n"))
        self.assertEqual(feed(b"NOP\nPUSH 1\nHALT 0\nend:"),
                         (0, b"end=19\n"))

    # @method test_forward_reference() -> None
    # @in    нет
    # @out   нет
    # @does  Ссылка вперёд: метка после использования получает адрес,
    # @does  который подставит проход 2 (SPEC/L2-UASM.txt, раздел 3):
    # @does  JMP end — 9 байтов, NOP — 1, end = 10.
    # @depends feed
    def test_forward_reference(self):
        self.assertEqual(feed(b"JMP end\nNOP\nend:"),
                         (0, b"end=10\n"))
        self.assertEqual(feed(b"CALL fwd\nfwd:"), (0, b"fwd=9\n"))

    # @method test_const_no_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  Метки и константы байтов не дают (record_size эталона — 0):
    # @does  константа между метками не сдвигает адреса; порядок
    # @does  листинга — порядок определения.
    # @depends feed
    def test_const_no_bytes(self):
        self.assertEqual(feed(b"x = 5\na:\nNOP\nb:"),
                         (0, b"x=5\na=0\nb=1\n"))

    # @method test_string_sizes() -> None
    # @in    нет
    # @out   нет
    # @does  Длины литералов DS/DZ — декодированные байты: «a» плюс шесть
    # @does  escape — 7 байтов (escape по байту), многобайтовый UTF-8
    # @does  дословно («привет» — 12); DZ добавляет байт 0 при
    # @does  кодировании («мир!» — 7 + 1 = 8 — метка за директивой).
    # @depends feed
    def test_string_sizes(self):
        self.assertEqual(feed(b'a:\nDS "a\\n\\r\\t\\\\\\"\\0"\nb:\n'),
                         (0, b"a=0\nb=7\n"))
        self.assertEqual(feed('a:\nDS "привет"\nb:\n'.encode("utf-8")),
                         (0, 'a=0\nb=12\n'.encode("utf-8")))
        self.assertEqual(feed('a:\nDZ "мир!"\nb:\n'.encode("utf-8")),
                         (0, 'a=0\nb=8\n'.encode("utf-8")))


class TestDuplicates(unittest.TestCase):
    """Повторные определения — единое пространство имён (SPEC, раздел 3)."""

    # @method test_duplicates() -> None
    # @in    нет
    # @out   нет
    # @does  Повторное определение имени — ошибка с номером строки
    # @does  второго определения (SPEC/L2-UASM.txt, раздел 7): метка
    # @does  после метки, константа после константы, константа после
    # @does  метки и метка после константы; листинг при ошибке не
    # @does  печатается — только диагностика, код 16.
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

    # @method test_distinct_names() -> None
    # @in    нет
    # @out   нет
    # @does  Разные имена — норма: метки и константы рядом, поиск
    # @does  различает имена без ложных совпадений (префиксы s0/s1/s10
    # @does  и метки, одноимённые с мнемониками PUSH и DB, — роль слова
    # @does  определяет позиция в строке).
    # @depends feed
    def test_distinct_names(self):
        self.assertEqual(feed(b"s0 = 0\ns1 = 1\ns10 = 10\ns100 = 100\n"),
                         (0, b"s0=0\ns1=1\ns10=10\ns100=100\n"))
        self.assertEqual(feed(b"PUSH:\nDB:\n"),
                         (0, b"PUSH=0\nDB=0\n"))


class TestNames(unittest.TestCase):
    """Лимит имени 63 байта — контракт инструмента (SPEC, раздел 5А)."""

    # @method test_name_limits() -> None
    # @in    нет
    # @out   нет
    # @does  Имя 63 байта — норма (метка и константа), 64 — «слишком
    # @does  длинное имя» и код 16 (SPEC/L4-SELFHOST.txt, раздел 5А:
    # @does  запись «значение 8 LE + имя + 0»; у эталона лимита нет —
    # @does  ожидания явные, не паритет).
    # @depends feed
    def test_name_limits(self):
        ok = "a" * 63
        self.assertEqual(feed((ok + ":\n").encode()),
                         (0, (ok + "=0\n").encode()))
        self.assertEqual(feed((ok + " = 7\n").encode()),
                         (0, (ok + "=7\n").encode()))
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
    # @does  100 констант подряд: каждая дописывает запись в таблицу,
    # @does  поиск прохода по всем записям не находит ложных повторов,
    # @does  листинг — все 100 символов в порядке определения.
    # @depends feed
    def test_many_consts(self):
        count = 100
        text = "".join("s%d = %d\n" % (i, i) for i in range(count))
        want = "".join("s%d=%d\n" % (i, i) for i in range(count))
        code, out = feed(text.encode())
        self.assertEqual((code, out), (0, want.encode()))

    # @method test_label_chain() -> None
    # @in    нет
    # @out   нет
    # @does  60 пар «метка + DB 7»: каждая метка — накопленный адрес
    # @does  (DB — один байт), конечная метка — 60; курсор таблицы
    # @does  продвигается symnext корректно на каждой записи.
    # @depends feed
    def test_label_chain(self):
        count = 60
        text = "".join("l%d:\nDB 7\n" % i for i in range(count)) + "end:\n"
        want = "".join("l%d=%d\n" % (i, i) for i in range(count))
        want += "end=%d\n" % count
        code, out = feed(text.encode())
        self.assertEqual((code, out), (0, want.encode()))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5А)."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта процессами: ubrick_cli compile, затем
    # @does  uvm_cli с входным файлом; stdout — листинг символов
    # @does  программы со ссылкой вперёд (end = 10), код 0.
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
            self.assertEqual(run.stdout, b"end=10\n")


if __name__ == "__main__":
    unittest.main()
