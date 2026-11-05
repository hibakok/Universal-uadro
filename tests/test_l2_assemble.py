# @uadro
# @file    tests/test_l2_assemble.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшагов 1-2 ветви l2.uasm.assemble: каркас, память
# @desc    и строки со словами (src/l2/assemble.ubrk + use-включения
# @desc    asmmem.ubrk, asmwords.ubrk, asmmnem.ubrk, asmlex.ubrk,
# @desc    asmline.ubrk): сборка compile, пустой вход и пустые строки
# @desc    молчат, чистка строки (концевые CR, комментарий «;» вне
# @desc    кавычек, крайние пробелы и табуляции), нумерация строк,
# @desc    все 38 мнемоник, буфер аргументов (256 пар DB/DW — норма,
# @desc    257 — ошибка 16), границы лимита 512 КиБ, сквозной прогон
# @desc    процессами; записи строк (листинг «N:V …» подшага 4
# @desc    и паритет с эталоном разбора) — tests/test_l2_assemble_line.py.

"""Тесты подшагов 1-2 ветви l2.uasm.assemble (SPEC/L4-SELFHOST.txt, раздел 5А).

Ассемблер uAsm на uBrick (src/l2/assemble.ubrk с use-включениями)
собирается командой ubrick_cli compile (кирпич l2_image) и исполняется
кирпичом run_with_io: SYS 0 читает текст-вход, SYS 1 пишет выход подшага
4 — листинг записей «N:V …». Подшаг 1: вход целиком в буфер 512 КиБ,
сверх — «вход слишком большой» и код 16 (границы — самые медленные
тесты, около минуты на пару). Подшаг 2: пустые строки и комментарии
молчат, концевые CR и комментарий «;» вне кавычек отрезаются, крайние
пробелы игнорируются; 257-й аргумент DB/DW — ошибка 16.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uvm_table import TABLE

SRC_LIMIT = 0x90000 - 0x10000     # ёмкость буфера источника: 512 КиБ
BIG_TEXT = "вход слишком большой\n".encode("utf-8")   # диагностика без
                                                     # номера строки
ARGS_TEXT = "слишком много аргументов"                 # ошибка ёмкости
MNEMONICS = [rec[1] for rec in TABLE]                  # 38 мнемоник
CODES = {rec[1]: rec[0] for rec in TABLE}             # мнемоника -> код
IMMS = {rec[1]: rec[3] for rec in TABLE}               # мнемоника -> imm64


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
# @does  asmwords, asmmnem, asmlex и asmline склеивает загрузчик ветви
# @does  t0.ubrick.source; кирпич всех тестов ветви.
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
# @does  проверек листинга записей); сборка образа — l2_image.
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
    # @does  asmwords, asmmnem, asmlex и asmline проходит без ошибки
    # @does  (код 0), образ не пуст.
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
    # @does  Пустой вход — пустой вывод и код 0 (SPEC/L4-SELFHOST.txt,
    # @does  раздел 5А).
    # @depends listing
    def test_empty_input(self):
        self.assertEqual(listing(b""), (0, b""))

    # @method test_blank_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Пустые строки и строки-комментарии не попадают в листинг;
    # @does  нумерация последующих строк не сбивается (код 0).
    # @depends listing
    def test_blank_lines(self):
        text = b"\n   \n; comment\n\t\n"
        self.assertEqual(listing(text), (0, b""))


class TestRecords(unittest.TestCase):
    """Подшаг 4: строки листинга записей «N:V …»."""

    # @method test_small_program() -> None
    # @in    нет
    # @out   нет
    # @does  Каждая непустая строка даёт запись: номер, вид, данные —
    # @does  инструкции «N:I код [операнд]» (коды — десятичные: NOP=0,
    # @does  PUSH=1, HALT=69).
    # @depends listing
    def test_small_program(self):
        self.assertEqual(
            listing(b"NOP\nPUSH 1\nHALT 0\n"),
            (0, b"1:I 0\n2:I 1 1\n3:I 69 0\n"))

    # @method test_no_trailing_lf() -> None
    # @in    нет
    # @out   нет
    # @does  Последняя строка без перевода строки обрабатывается как
    # @does  строка (конец буфера — конец строки).
    # @depends listing
    def test_no_trailing_lf(self):
        self.assertEqual(
            listing(b"NOP\nPUSH 1"),
            (0, b"1:I 0\n2:I 1 1\n"))

    # @method test_line_numbers() -> None
    # @in    нет
    # @out   нет
    # @does  Номера строк считаются по переводам с единицы: одиннадцать
    # @does  пустых строк молчат, NOP — строка 12 (многозначный номер).
    # @depends listing
    def test_line_numbers(self):
        self.assertEqual(listing(b"\n" * 11 + b"NOP\n"),
                         (0, b"12:I 0\n"))

    # @method test_all_mnemonics() -> None
    # @in    нет
    # @out   нет
    # @does  Все 38 мнемоник таблицы опкодов разбираются в записи
    # @does  инструкций с верными кодами (ожидание — из эталонной
    # @does  таблицы tools/uvm_table, источник истины кодов): без imm64 —
    # @does  «N:I код», с imm64 — с операндом «N:I код 1».
    # @depends listing, TABLE, CODES, IMMS
    def test_all_mnemonics(self):
        lines = [(m + " 1") if IMMS[m] else m for m in MNEMONICS]
        text = ("\n".join(lines) + "\n").encode()
        want = "".join(
            "%d:I %d%s\n" % (i + 1, CODES[m], " 1" if IMMS[m] else "")
            for i, m in enumerate(MNEMONICS)).encode()
        self.assertEqual(listing(text), (0, want))

    # @method test_not_mnemonics() -> None
    # @in    нет
    # @out   нет
    # @does  Строки не-мнемоники дают записи своих видов: метка «N:L имя»,
    # @does  директивы «N:DB argc», «N:DW argc», «N:DS длина», «N:DZ
    # @does  длина» (аргументы и литералы — тексты/длины, значения
    # @does  подставит проход 2).
    # @depends listing
    def test_not_mnemonics(self):
        text = b"a:\nDB 1 2\nDW x\nDS \"s\"\nDZ \"z\"\n"
        self.assertEqual(
            listing(text),
            (0, b"1:L a\n2:DB 2\n3:DW 1\n4:DS 1\n5:DZ 1\n"))

    # @method test_const_line() -> None
    # @in    нет
    # @out   нет
    # @does  Строка константы «x = 5» — запись «N:C имя=значение»:
    # @does  имя и значение по модулю 2^64 (знак «=» разбирает
    # @does  parseline, подшаг 4).
    # @depends listing
    def test_const_line(self):
        self.assertEqual(listing(b"x = 5\n"), (0, b"1:C x=5\n"))

    # @method test_tabs() -> None
    # @in    нет
    # @out   нет
    # @does  Табуляция — разделитель слов наравне с пробелом: между
    # @does  мнемоникой и операндом и между аргументами DB (чистка краёв
    # @does  и деление на слова, SPEC/L2-UASM.txt, раздел 2).
    # @depends listing
    def test_tabs(self):
        self.assertEqual(listing(b"PUSH\t1\n"), (0, b"1:I 1 1\n"))
        self.assertEqual(listing(b"DB\t1\t2\n"), (0, b"1:DB 2\n"))

    # @method test_spaces_between_args() -> None
    # @in    нет
    # @out   нет
    # @does  Несколько пробелов между аргументами схлопываются: слова
    # @does  делятся по последовательностям пробелов и табуляций —
    # @does  оба аргумента в одной записи DB.
    # @depends listing
    def test_spaces_between_args(self):
        self.assertEqual(listing(b"DB  1   2\n"),
                         (0, b"1:DB 2\n"))

    # @method test_label_at_end() -> None
    # @in    нет
    # @out   нет
    # @does  Метка в конце текста (адрес конца образа — значение даст
    # @does  проход 1) разбирается последней записью без ошибки.
    # @depends listing
    def test_label_at_end(self):
        self.assertEqual(listing(b"NOP\nx:"), (0, b"1:I 0\n2:L x\n"))

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
    """Подшаги 2-4: чистка строки — CR, комментарий, кавычки."""

    # @method test_crlf() -> None
    # @in    нет
    # @out   нет
    # @does  Концевой CR каждой строки снимается (как split_lines
    # @does  эталона): текст с переводами CRLF собирается как с LF.
    # @depends listing
    def test_crlf(self):
        self.assertEqual(listing(b"NOP\r\nPUSH 1\r\n"),
                         (0, b"1:I 0\n2:I 1 1\n"))

    # @method test_trailing_crs() -> None
    # @in    нет
    # @out   нет
    # @does  Все концевые CR снимаются подряд («x:\r\r\n» — метка x);
    # @does  CR без LF внутри строки — значимый байт слова: «B\rC» —
    # @does  слово целиком в сообщении ошибки.
    # @depends listing, err
    def test_trailing_crs(self):
        want = b"1:L x\n" + err(2, "неизвестная мнемоника B\rC")
        self.assertEqual(listing(b"x:\r\r\nB\rC\n"), (16, want))

    # @method test_comment_cut() -> None
    # @in    нет
    # @out   нет
    # @does  Комментарий «;» вне кавычек отрезается до конца строки —
    # @does  остаток не разбирается (SPEC/L2-UASM.txt, раздел 2).
    # @depends listing
    def test_comment_cut(self):
        self.assertEqual(listing(b"NOP ; comment ; ;\n"),
                         (0, b"1:I 0\n"))

    # @method test_semicolon_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  «;» внутри литералов в кавычках комментарий не начинает:
    # @does  литерал DS с «;» разбирается целиком — длина 3 байта.
    # @depends listing
    def test_semicolon_in_quotes(self):
        self.assertEqual(listing(b'DS "a;b" ; x\n'),
                         (0, b'1:DS 3\n'))

    # @method test_spaces_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  Пробелы внутри литерала значимы: длина декодированных байтов
    # @does  «a ; b» — 5 (литерал — остаток строки целиком, а не слова).
    # @depends listing
    def test_spaces_in_quotes(self):
        self.assertEqual(listing(b'DS "a ; b"\n'),
                         (0, b'1:DS 5\n'))

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
    # @does  декодированная длина — три байта (a, кавычка, b).
    # @depends listing
    def test_escaped_quote(self):
        self.assertEqual(listing(b'DS "a\\"b" ; x\n'),
                         (0, b'1:DS 3\n'))

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
    """Подшаг 4: произвольные байты входа не ломают инструмент."""

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
    """Подшаг 2: буфер аргументов и его лимит 256 пар."""

    # @method test_many_args_fit() -> None
    # @in    нет
    # @out   нет
    # @does  256 аргументов одной строки DB — норма: пары занимают буфер
    # @does  аргументов целиком (argbase..arglimit), запись — «1:DB 256»,
    # @does  код 0.
    # @depends listing
    def test_many_args_fit(self):
        line = "DB" + " 7" * 256
        self.assertEqual(listing(line.encode() + b"\n"),
                         (0, b"1:DB 256\n"))

    # @method test_trailing_spaces_after_args() -> None
    # @in    нет
    # @out   нет
    # @does  Пробелы в конце строки после последнего аргумента не дают
    # @does  пустого 257-го слова (пробелы пропускаются до проверки
    # @does  лимита) — норма, код 0.
    # @depends listing
    def test_trailing_spaces_after_args(self):
        line = "DB" + " 7" * 256
        self.assertEqual(listing(line.encode() + b"   \n"),
                         (0, b"1:DB 256\n"))

    # @method test_too_many_args() -> None
    # @in    нет
    # @out   нет
    # @does  257-й аргумент строки DB — ошибка ёмкости: «uAsm: строка 2:
    # @does  слишком много аргументов» и код 16 (SPEC/L4-SELFHOST.txt,
    # @does  раздел 5А); записи строк до ошибки уже выведены.
    # @depends listing, err
    def test_too_many_args(self):
        text = "NOP\nDB" + " 7" * 257
        want = b"1:I 0\n" + err(2, ARGS_TEXT)
        self.assertEqual(listing(text.encode()), (16, want))


class TestLimit(unittest.TestCase):
    """Подшаг 1: лимит буфера источника 512 КиБ (SPEC, раздел 5А)."""

    # @method test_exact_fit() -> None
    # @in    нет
    # @out   нет
    # @does  Вход ровно в 512 КиБ занимает буфер целиком (последний байт
    # @does  пишется в 0x8FFFF) — успех: одна строка-комментарий молчит,
    # @does  вывод пуст, код 0; чистка комментария на огромной строке
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
    # @does  затем uvm_cli с входным файлом-текстом; stdout — листинг
    # @does  записей трёх строк, код процесса 0.
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
            self.assertEqual(
                run.stdout, b"1:I 0\n2:I 1 1\n3:I 69 0\n")


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
