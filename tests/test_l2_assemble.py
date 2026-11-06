# @uadro
# @file    tests/test_l2_assemble.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшагов 1-2 ветви l2.uasm.assemble: каркас, память
# @desc    и строки со словами (src/l2/assemble.ubrk + use-включения
# @desc    asmmem.ubrk, asmwords.ubrk, asmmnem.ubrk, asmlex.ubrk,
# @desc    asmline.ubrk, asmsym.ubrk, asmcode.ubrk): сборка compile,
# @desc    пустой вход и пустые строки молчат, чистка строки (концевые
# @desc    CR, комментарий «;» вне кавычек, крайние пробелы и табуляции),
# @desc    нумерация строк, буфер аргументов (256 пар DB/DW — норма,
# @desc    257 — ошибка 16), границы лимита 512 КиБ, сквозной прогон
# @desc    процессами; выход — образ UVM байт в байт (подшаг 6: метка
# @desc    наблюдаема адресом ссылки, инструкция — байтами опкода
# @desc    и imm64); разбор строки (паритет с эталоном) —
# @desc    tests/test_l2_assemble_line.py, символы и адреса —
# @desc    tests/test_l2_assemble_sym.py, кодирование значений —
# @desc    tests/test_l2_assemble_code.py.

"""Тесты подшагов 1-2 ветви l2.uasm.assemble (SPEC/L4-SELFHOST.txt, раздел 5А).

Ассемблер uAsm на uBrick (src/l2/assemble.ubrk с use-включениями)
собирается командой ubrick_cli compile (кирпич l2_image) и исполняется
кирпичом run_with_io. Подшаг 1: вход целиком в буфер 512 КиБ, сверх —
«вход слишком большой» и код 16 (границы — самые медленные тесты, около
минуты на пару). Подшаг 2: пустые строки и комментарии молчат, концевые
CR и комментарий «;» вне кавычек отрезаются, крайние пробелы
игнорируются; 257-й аргумент DB/DW — ошибка 16. Выход — образ UVM
(подшаг 6): чистка и нумерация строк наблюдаемы байтами образа и
номерами строк ошибок; при ошибке образ не выводится — только
диагностика.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_assemble import assemble
from tools.uvm_table import TABLE

SRC_LIMIT = 0x90000 - 0x10000     # ёмкость буфера источника: 512 КиБ
BIG_TEXT = "вход слишком большой\n".encode("utf-8")   # диагностика без
                                                     # номера строки
ARGS_TEXT = "слишком много аргументов"                 # ошибка ёмкости
CODES = {rec[1]: rec[0] for rec in TABLE}              # мнемоника -> код


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
# @does  (режим compile, временный файл образа): use-включения asmmem,
# @does  asmwords, asmmnem, asmlex, asmline, asmsym и asmcode склеивает
# @does  загрузчик ветви t0.ubrick.source; кирпич всех тестов ветви.
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


# @method listing(text) -> tuple
# @in    text: bytes — текст uAsm (вход ассемблера)
# @out   pair: tuple — (код завершения, байты выхода)
# @does  Прогон ассемблера на тексте одним вызовом (кирпич коротких
# @does  проверек выхода — образ либо диагностика); сборка образа —
# @does  l2_image.
# @depends l2_image, feed
def listing(text):
    return feed(l2_image(), text)


# @method err(line, text) -> bytes
# @in    line: int — номер строки текста, начиная с 1
# @in    text: str — текст ошибки по разделу 7 SPEC/L2-UASM.txt
# @out   want: bytes — диагностическая строка с переводом
# @does  Строит ожидаемую диагностику «uAsm: строка N: текст» (SPEC/
# @does  L4-SELFHOST.txt, раздел 5А); кирпич тестов ошибок.
def err(line, text):
    return ("uAsm: строка %d: %s\n" % (line, text)).encode("utf-8")


class TestCompile(unittest.TestCase):
    """Каркас собирается настоящей командой compile."""

    # @method test_image_built() -> None
    # @in    нет
    # @out   нет
    # @does  Компиляция src/l2/assemble.ubrk с use-включениями asmmem,
    # @does  asmwords, asmmnem, asmlex, asmline, asmsym и asmcode
    # @does  проходит без ошибки (код 0), образ не пуст.
    # @depends l2_image
    def test_image_built(self):
        image = l2_image()
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)


class TestSilence(unittest.TestCase):
    """Пустой вход, пустые строки и комментарии молчат."""

    # @method test_empty_input() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой вход — пустой образ и код 0 (SPEC/L2-UASM.txt,
    # @does  раздел 7; SPEC/L4-SELFHOST.txt, раздел 5А): записей нет —
    # @does  байтов нет.
    # @depends listing
    def test_empty_input(self):
        self.assertEqual(listing(b""), (0, b""))

    # @method test_blank_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Пустые строки и строки-комментарии не попадают в проходы:
    # @does  байтов нет, вывод пуст, код 0; нумерация последующих строк
    # @does  не сбивается (ошибки — test_line_numbers).
    # @depends listing
    def test_blank_lines(self):
        text = b"\n   \n; comment\n\t\n"
        self.assertEqual(listing(text), (0, b""))


class TestLines(unittest.TestCase):
    """Механика строк: последняя без LF, нумерация, разделители слов."""

    # @method test_no_trailing_lf() -> None
    # @in    нет
    # @out   нет
    # @does  Последняя строка без перевода строки обрабатывается как
    # @does  строка (конец буфера — конец строки): ошибка второй строки
    # @does  получает номер 2.
    # @depends listing, err
    def test_no_trailing_lf(self):
        self.assertEqual(listing(b"NOP\nPUS"),
                         (16, err(2, "неизвестная мнемоника PUS")))

    # @method test_line_numbers() -> None
    # @in    нет
    # @out   нет
    # @does  Номера строк считаются по переводам с единицы: одиннадцать
    # @does  пустых строк молчат, ошибка — строка 12 (многозначный
    # @does  номер в префиксе диагностики).
    # @depends listing, err
    def test_line_numbers(self):
        self.assertEqual(listing(b"\n" * 11 + b"PUS\n"),
                         (16, err(12, "неизвестная мнемоника PUS")))

    # @method test_tabs() -> None
    # @in    нет
    # @out   нет
    # @does  Табуляция — разделитель слов наравне с пробелом: «PUSH\t1» —
    # @does  инструкция с операндом (байт опкода 0x01 и imm64 1),
    # @does  «DB\t1\t2» — директива с двумя аргументами (байты 1 и 2;
    # @does  иначе строка была бы одним словом — ошибка «неизвестная
    # @does  мнемоника»).
    # @depends listing
    def test_tabs(self):
        self.assertEqual(listing(b"PUSH\t1\n"),
                         (0, bytes([CODES["PUSH"]]) + le(1)))
        self.assertEqual(listing(b"DB\t1\t2\n"), (0, b"\x01\x02"))

    # @method test_spaces_between_args() -> None
    # @in    нет
    # @out   нет
    # @does  Несколько пробелов между словами схлопываются: оба аргумента
    # @does  DB — в одной записи (два байта образа).
    # @depends listing
    def test_spaces_between_args(self):
        self.assertEqual(listing(b"DB  1   2\n"), (0, b"\x01\x02"))

    # @method test_word_shapes() -> None
    # @in    нет
    # @out   нет
    # @does  Усечённая мнемоника (PUS), строчная (nop) и слово с хвостом
    # @does  (STORE64X) мнемониками не считаются — первое ошибочное
    # @does  слово прекращает сборку: «неизвестная мнемоника PUS»,
    # @does  код 16 (SPEC/L2-UASM.txt, раздел 7).
    # @depends listing, err
    def test_word_shapes(self):
        self.assertEqual(listing(b"PUS\nnop\nSTORE64X\n"),
                         (16, err(1, "неизвестная мнемоника PUS")))


class TestClean(unittest.TestCase):
    """Чистка строки — CR, комментарий, кавычки (подшаги 2-4)."""

    # @method test_crlf() -> None
    # @in    нет
    # @out   нет
    # @does  Концевой CR каждой строки снимается (как split_lines
    # @does  эталона): «x:\r» был бы словом с хвостом и дал бы ошибку
    # @does  «неизвестная мнемоника», но метка определяется, NOP перед
    # @does  меткой y кодируется байтом опкода 0x00.
    # @depends listing
    def test_crlf(self):
        self.assertEqual(listing(b"x:\r\nNOP\r\ny:"), (0, b"\x00"))

    # @method test_trailing_crs() -> None
    # @in    нет
    # @out   нет
    # @does  Все концевые CR снимаются подряд («x:\r\r\n» — метка x);
    # @does  CR без LF внутри строки — значимый байт слова: «B\rC» —
    # @does  слово целиком в сообщении ошибки; при ошибке образ
    # @does  не выводится — только диагностика.
    # @depends listing, err
    def test_trailing_crs(self):
        self.assertEqual(listing(b"x:\r\r\nB\rC\n"),
                         (16, err(2, "неизвестная мнемоника B\rC")))

    # @method test_comment_cut() -> None
    # @in    нет
    # @out   нет
    # @does  Комментарий «;» вне кавычек отрезается до конца строки:
    # @does  «x: ; comment ; ;» — метка x без лишних слов (не отрезали —
    # @does  была бы «плохое имя»); метка байтов не даёт — образ пуст.
    # @depends listing
    def test_comment_cut(self):
        self.assertEqual(listing(b"x: ; comment ; ;\n"), (0, b""))

    # @method test_semicolon_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  «;» внутри литералов в кавычках комментарий не начинает:
    # @does  литерал DS с «;» кодируется целиком — три байта a, ;, b.
    # @depends listing
    def test_semicolon_in_quotes(self):
        self.assertEqual(listing(b'a:\nDS "a;b"\nb:\n'),
                         (0, b"a;b"))

    # @method test_spaces_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  Пробелы внутри литерала значимы: декодированные байты
    # @does  «a ; b» — все пять (литерал — остаток строки целиком,
    # @does  а не слова).
    # @depends listing
    def test_spaces_in_quotes(self):
        self.assertEqual(listing(b'a:\nDS "a ; b"\nb:\n'),
                         (0, b"a ; b"))

    # @method test_unclosed_quote() -> None
    # @in    нет
    # @out   нет
    # @does  Незакрытая кавычка тянется до конца строки («;» внутри неё
    # @does  комментарий не начинает), скан литерала видит ошибку —
    # @does  «плохой строковый литерал», код 16 (SPEC/L2-UASM.txt,
    # @does  разделы 6-7).
    # @depends listing, err
    def test_unclosed_quote(self):
        self.assertEqual(listing(b'DS "a ; b\n'),
                         (16, err(1, "плохой строковый литерал")))

    # @method test_escaped_quote() -> None
    # @in    нет
    # @out   нет
    # @does  Escape-кавычка внутри литерала не закрывает его: «;» после
    # @does  закрытия — комментарий, escape-последовательность цела;
    # @does  декодированные байты — a, кавычка, b.
    # @depends listing
    def test_escaped_quote(self):
        self.assertEqual(listing(b'a:\nDS "a\\"b" ; x\nb:\n'),
                         (0, b'a"b'))

    # @method test_apostrophe_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Апостроф открывает символьный литерал: «;» после закрытого
    # @does  литерала — комментарий; сам литерал — не метка, не мнемоника
    # @does  и не директива, знака «=» нет — «неизвестная мнемоника 'q'».
    # @depends listing, err
    def test_apostrophe_literal(self):
        self.assertEqual(listing(b"'q' ; x\n"),
                         (16, err(1, "неизвестная мнемоника 'q'")))


class TestBinary(unittest.TestCase):
    """Произвольные байты входа не ломают инструмент (подшаг 4)."""

    # @method test_binary_input() -> None
    # @in    нет
    # @out   нет
    # @does  Вход — все байты 0..255 подряд: первая строка — байты 0..9,
    # @does  концевая табуляция (9) срезается чисткой; слово из байтов
    # @does  0..8 — не метка, не мнемоника, не директива, знака «=» нет —
    # @does  «неизвестная мнемоника» со словом X из байтов 0..8 (printw
    # @does  печатает байты дословно, NUL включительно), код 16.
    # @depends listing
    def test_binary_input(self):
        want = ("uAsm: строка 1: неизвестная мнемоника ").encode(
            "utf-8") + bytes(range(9)) + b"\n"
        self.assertEqual(listing(bytes(range(256))), (16, want))


class TestArgs(unittest.TestCase):
    """Буфер аргументов и его лимит 256 пар (подшаг 2)."""

    # @method test_many_args_fit() -> None
    # @in    нет
    # @out   нет
    # @does  256 аргументов одной строки DB — норма: пары занимают буфер
    # @does  аргументов целиком (argbase..arglimit), проход 2 кодирует
    # @does  по байту на аргумент — 256 байтов 7, код 0.
    # @depends listing
    def test_many_args_fit(self):
        line = "x:\nDB" + " 7" * 256 + "\ny:"
        self.assertEqual(listing(line.encode()), (0, b"\x07" * 256))

    # @method test_trailing_spaces_after_args() -> None
    # @in    нет
    # @out   нет
    # @does  Пробелы в конце строки после последнего аргумента не дают
    # @does  пустого 257-го слова (пробелы пропускаются до проверки
    # @does  лимита) — норма, образ — 256 байтов 7, код 0.
    # @depends listing
    def test_trailing_spaces_after_args(self):
        line = "x:\nDB" + " 7" * 256
        self.assertEqual(listing(line.encode() + b"   \ny:"),
                         (0, b"\x07" * 256))

    # @method test_too_many_args() -> None
    # @in    нет
    # @out   нет
    # @does  257-й аргумент строки DB — ошибка ёмкости: «uAsm: строка 2:
    # @does  слишком много аргументов» и код 16 (SPEC/L4-SELFHOST.txt,
    # @does  раздел 5А); при ошибке образ не выводится — только
    # @does  диагностика.
    # @depends listing, err
    def test_too_many_args(self):
        text = "NOP\nDB" + " 7" * 257
        self.assertEqual(listing(text.encode()),
                         (16, err(2, ARGS_TEXT)))


class TestLimit(unittest.TestCase):
    """Лимит буфера источника 512 КиБ (SPEC, раздел 5А)."""

    # @method test_exact_fit() -> None
    # @in    нет
    # @out   нет
    # @does  Вход ровно в 512 КиБ занимает буфер целиком (последний байт
    # @does  пишется в 0x8FFFF) — успех: одна строка-комментарий молчит,
    # @does  образ пуст, код 0; чистка комментария на огромной строке
    # @does  не читает её целиком.
    # @depends listing
    def test_exact_fit(self):
        code, out = listing(b";" * SRC_LIMIT)
        self.assertEqual((code, out), (0, b""))

    # @method test_over_limit() -> None
    # @in    нет
    # @out   нет
    # @does  Вход на байт больше лимита: 524288 байтов читаются без
    # @does  ошибки, 524289-й не помещается — строка «вход слишком
    # @does  большой» с переводом строки и код 16 (SPEC, раздел 5А:
    # @does  единственная диагностика без номера строки).
    # @depends listing
    def test_over_limit(self):
        code, out = listing(b"A" * (SRC_LIMIT + 1))
        self.assertEqual((code, out), (16, BIG_TEXT))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5А)."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта настоящими процессами: ubrick_cli compile,
    # @does  затем uvm_cli с входным файлом-текстом; stdout — образ
    # @does  программы NOP (байт 0x00), PUSH 1 (0x01 + imm64 1), HALT 0
    # @does  (0x45 + imm64 0) — 19 байтов, код процесса 0.
    # @depends l2_source
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "assemble.uvm")
            src = os.path.join(tmp, "in.uasm")
            with open(src, "wb") as handle:
                handle.write(b"NOP\nPUSH 1\nHALT 0\nend:\n")
            compile_code = subprocess.call(
                [sys_python(), tools_path("ubrick_cli.py"), "compile",
                 l2_source(), image],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(compile_code, 0)
            with open(src, "rb") as handle:
                run = subprocess.run(
                    [sys_python(), tools_path("uvm_cli.py"), image],
                    stdin=handle, capture_output=True)
            image_want, error = assemble("NOP\nPUSH 1\nHALT 0\nend:\n")
            self.assertIsNone(error)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stdout, image_want)


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
