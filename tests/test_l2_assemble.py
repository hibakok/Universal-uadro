# @uadro
# @file    tests/test_l2_assemble.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшагов 1-2 ветви l2.uasm.assemble: каркас, память
# @desc    и строки со словами (src/l2/assemble.ubrk + use-включения
# @desc    asmmem.ubrk, asmwords.ubrk, asmmnem.ubrk, asmlex.ubrk):
# @desc    сборка compile, листинг «N:слово[=код] …» с пометами
# @desc    подшага 3 (литерал «#значение» по модулю 2^64, вне диапазона
# @desc    «!», имя «*», прочее «?»; DS/DZ — остаток целиком и «#длина»
# @desc    либо «!»); чистка строки, нумерация, все 38 мнемоник,
# @desc    буфер аргументов (256 пар — норма, 257 — ошибка 16), границы
# @desc    лимита 512 КиБ, сквозной прогон процессами (SPEC/
# @desc    L4-SELFHOST.txt, раздел 5А); пометы литералов —
# @desc    tests/test_l2_assemble_lex.py.

"""Тесты подшагов 1-2 ветви l2.uasm.assemble (SPEC/L4-SELFHOST.txt, раздел 5А).

Ассемблер uAsm на uBrick (src/l2/assemble.ubrk, use-включения asmmem,
asmwords, asmmnem и asmlex склеивает загрузчик t0.ubrick.source) собирается
настоящей командой ubrick_cli compile (кирпич l2_image) и исполняется
кирпичом run_with_io: SYS 0 читает байты текста-входа, SYS 1 пишет листинг.

Подшаг 1: вход читается целиком в буфер 512 КиБ; сверх лимита — строка
«вход слишком большой» и код 16 (единственная диагностика без номера);
вход ровно в лимит — успех. Границы гоняют полный буфер — самые
медленные тести набора (около минуты на пару).

Подшаг 2: пустые строки и комментарии молчат; концевые CR снимаются,
комментарий «;» отрезается вне кавычек, крайние пробелы и табуляции
игнорируются; 38 мнемоник сверяются с эталонной таблицей опкодов;
257-й аргумент — «uAsm: строка N: слишком много аргументов», код 16.

Подшаг 3 добавил пометы аргументам листинга: «#значение» (литерал
в диапазоне, по модулю 2^64), «!» (цифры вне диапазона), «*» (имя),
«?» (прочее); DS/DZ — остаток целиком, «#длина» либо «!». Границы
помет — tests/test_l2_assemble_lex.py.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uvm_table import TABLE

SRC_BASE = 0x10000      # база буфера источника (SPEC, раздел 5А)
SRC_LIMIT = 0x90000 - SRC_BASE   # ёмкость буфера источника: 512 КиБ
BIG_TEXT = "вход слишком большой\n".encode("utf-8")   # диагностика без
                                                     # номера строки
ARGS_TEXT = "слишком много аргументов"                 # ошибка ёмкости
MNEMONICS = [rec[1] for rec in TABLE]                  # 38 мнемоник
CODES = {rec[1]: rec[0] for rec in TABLE}              # мнемоника -> код


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
# @does  asmwords, asmmnem и asmlex склеивает загрузчик ветви
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
# @out   pair: tuple — (код завершения, байты листинга)
# @does  Прогон ассемблера на тексте одним вызовом (кирпич коротких
# @does  проверок листинга); сборка образа — l2_image.
# @depends l2_image, feed
def listing(text):
    return feed(l2_image(), text)


class TestCompile(unittest.TestCase):
    """Каркас собирается настоящей командой compile."""

    # @method test_image_built() -> None
    # @in    нет
    # @out   нет
    # @does  Компиляция src/l2/assemble.ubrk с use-включениями asmmem,
    # @does  asmwords, asmmnem и asmlex проходит без ошибки (код 0),
    # @does  образ не пуст.
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


class TestListing(unittest.TestCase):
    """Подшаги 2-3: строки листинга «N:слово[=код] аргументы#…»."""

    # @method test_small_program() -> None
    # @in    нет
    # @out   нет
    # @does  Каждая непустая строка даёт строку листинга: номер, двоеточие,
    # @does  первое слово, код мнемоники после «=», аргументы с пометами
    # @does  подшага 3 — числовой литерал «#значение» (коды — десятичные:
    # @does  NOP=0, PUSH=1, HALT=69).
    # @depends listing
    def test_small_program(self):
        self.assertEqual(
            listing(b"NOP\nPUSH 1\nHALT 0\n"),
            (0, b"1:NOP=0\n2:PUSH=1 1#1\n3:HALT=69 0#0\n"))

    # @method test_no_trailing_lf() -> None
    # @in    нет
    # @out   нет
    # @does  Последняя строка без перевода строки обрабатывается как
    # @does  строка (конец буфера — конец строки).
    # @depends listing
    def test_no_trailing_lf(self):
        self.assertEqual(
            listing(b"NOP\nPUSH 1"),
            (0, b"1:NOP=0\n2:PUSH=1 1#1\n"))

    # @method test_line_numbers() -> None
    # @in    нет
    # @out   нет
    # @does  Номера строк считаются по переводам с единицы: одиннадцать
    # @does  пустых строк молчат, NOP — строка 12 (многозначный номер).
    # @depends listing
    def test_line_numbers(self):
        self.assertEqual(listing(b"\n" * 11 + b"NOP\n"),
                         (0, b"12:NOP=0\n"))

    # @method test_all_mnemonics() -> None
    # @in    нет
    # @out   нет
    # @does  Все 38 мнемоник таблицы опкодов находятся таблицей asmmnem
    # @does  с верными кодами: ожидание строится из эталонной таблицы
    # @does  tools/uvm_table (источник истины кодов); у мнемоник без
    # @does  аргументов помет нет.
    # @depends listing, TABLE, CODES
    def test_all_mnemonics(self):
        text = ("\n".join(MNEMONICS) + "\n").encode()
        want = "".join("%d:%s=%d\n" % (i + 1, name, CODES[name])
                       for i, name in enumerate(MNEMONICS)).encode()
        self.assertEqual(listing(text), (0, want))

    # @method test_not_mnemonics() -> None
    # @in    нет
    # @out   нет
    # @does  Слова не-мнемоники кода не печатают: метка «a:», директивы
    # @does  DB/DW/DS/DZ; аргументы-литералы и имена получают пометы
    # @does  подшага 3: «1#1 2#2», «x*»; DS/DZ — остаток с «#длина»
    # @does  декодированных байтов.
    # @depends listing
    def test_not_mnemonics(self):
        text = b"a:\nDB 1 2\nDW x\nDS \"s\"\nDZ \"z\"\n"
        self.assertEqual(
            listing(text),
            (0, b"1:a:\n2:DB 1#1 2#2\n3:DW x*\n"
                b"4:DS \"s\"#1\n5:DZ \"z\"#1\n"))

    # @method test_word_shapes() -> None
    # @in    нет
    # @out   нет
    # @does  Усечённая мнемоника (PUS) и строчная (nop) совпадением
    # @does  не считаются — сравнение с записью точное, дополнение
    # @does  нулями обязательно; слово с хвостом (STORE64X) тоже.
    # @depends listing
    def test_word_shapes(self):
        self.assertEqual(
            listing(b"PUS\nnop\nSTORE64X\n"),
            (0, b"1:PUS\n2:nop\n3:STORE64X\n"))

    # @method test_const_line() -> None
    # @in    нет
    # @out   нет
    # @does  Строка константы «x = 5»: первое слово x, аргументы «=» и 5
    # @does  с пометами подшага 3 — «=» ни литерал, ни имя («?»),
    # @does  литерал «#5» (знак «=» разбирает запись строки — подшаг 4).
    # @depends listing
    def test_const_line(self):
        self.assertEqual(listing(b"x = 5\n"), (0, b"1:x =? 5#5\n"))

    # @method test_tabs() -> None
    # @in    нет
    # @out   нет
    # @does  Табуляция — разделитель слов наравне с пробелом: чистка краёв
    # @does  и деление на слова (SPEC/L2-UASM.txt, раздел 2); мнемоника
    # @does  PUSH в роли аргумента — имя («*»): роль слова определяет
    # @does  позиция, а не форма (SPEC, раздел 3).
    # @depends listing
    def test_tabs(self):
        self.assertEqual(listing(b"\tNOP\tPUSH\t1\t\n"),
                         (0, b"1:NOP=0 PUSH* 1#1\n"))

    # @method test_spaces_between_args() -> None
    # @in    нет
    # @out   нет
    # @does  Несколько пробелов между аргументами схлопываются: слова
    # @does  делятся по последовательностям пробелов и табуляций.
    # @depends listing
    def test_spaces_between_args(self):
        self.assertEqual(listing(b"DB  1   2\n"),
                         (0, b"1:DB 1#1 2#2\n"))


class TestClean(unittest.TestCase):
    """Подшаги 2-3: чистка строки — CR, комментарий, кавычки."""

    # @method test_crlf() -> None
    # @in    нет
    # @out   нет
    # @does  Концевой CR каждой строки снимается (как split_lines
    # @does  эталона): текст с CRLF собирается как с LF; CR без LF
    # @does  внутри строки — значимый байт слова.
    # @depends listing
    def test_crlf(self):
        self.assertEqual(listing(b"NOP\r\nPUSH 1\r\n"),
                         (0, b"1:NOP=0\n2:PUSH=1 1#1\n"))

    # @method test_trailing_crs() -> None
    # @in    нет
    # @out   нет
    # @does  Все концевые CR снимаются подряд («A\r\r\n» — слово A).
    # @depends listing
    def test_trailing_crs(self):
        self.assertEqual(listing(b"A\r\r\nB\rC\n"),
                         (0, b"1:A\n2:B\rC\n"))

    # @method test_comment_cut() -> None
    # @in    нет
    # @out   нет
    # @does  Комментарий «;» вне кавычек отрезается до конца строки —
    # @does  остаток не разбирается (SPEC/L2-UASM.txt, раздел 2).
    # @depends listing
    def test_comment_cut(self):
        self.assertEqual(listing(b"NOP ; comment ; ;\n"),
                         (0, b"1:NOP=0\n"))

    # @method test_semicolon_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  «;» внутри литералов в кавычках комментарий не начинает:
    # @does  строковый литерал с «;» остаётся аргументом; помета DS —
    # @does  длина декодированных байтов (parsestr, подшаг 3).
    # @depends listing
    def test_semicolon_in_quotes(self):
        self.assertEqual(listing(b'DS "a;b" ; x\n'),
                         (0, b'1:DS "a;b"#3\n'))

    # @method test_spaces_in_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  Пробелы внутри литерала значимы: DS/DZ печатает остаток
    # @does  строки целиком (dsline), двойной пробел сохраняется — в отличие
    # @does  от слов-аргументов буфера; длина — декодированные байты.
    # @depends listing
    def test_spaces_in_quotes(self):
        self.assertEqual(listing(b'DS "a ; b"\n'),
                         (0, b'1:DS "a ; b"#5\n'))

    # @method test_unclosed_quote() -> None
    # @in    нет
    # @out   нет
    # @does  Незакрытая кавычка тянется до конца строки: «;» внутри неё
    # @does  комментарий не начинает (как find_outside_quotes эталона);
    # @does  скан литерала dsline видит ошибку — помета «!» (parsestr
    # @does  возвращает 0, подшаг 3).
    # @depends listing
    def test_unclosed_quote(self):
        self.assertEqual(listing(b'DS "a ; b\n'),
                         (0, b'1:DS "a ; b!\n'))

    # @method test_escaped_quote() -> None
    # @in    нет
    # @out   нет
    # @does  Escape-кавычка внутри литерала не закрывает его: «;» после
    # @does  закрытия — комментарий, escape-последовательность цела;
    # @does  декодированная длина — три байта (a, кавычка, b).
    # @depends listing
    def test_escaped_quote(self):
        self.assertEqual(listing(b'DS "a\\"b" ; x\n'),
                         (0, b'1:DS "a\\"b"#3\n'))

    # @method test_apostrophe_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Апостроф открывает символьный литерал: «;» после закрытого
    # @does  литерала — комментарий, сам литерал — первое слово без
    # @does  пометы (пометы — у аргументов).
    # @depends listing
    def test_apostrophe_literal(self):
        self.assertEqual(listing(b"'q' ; x\n"), (0, b"1:'q'\n"))


class TestBinary(unittest.TestCase):
    """Подшаги 2-3: произвольные байты входа не ломают инструмент."""

    # @method test_binary_input() -> None
    # @in    нет
    # @out   нет
    # @does  Вход — все байты 0..255 подряд: LF один (байт 10) — две
    # @does  строки; кавычка (34) в первой открывает литерал до конца
    # @does  строки (вторая строка — целиком «в кавычке», комментария
    # @does  нет), табуляция (9) в конце первой строки срезается чисткой
    # @does  края; словá с NUL-байтами мнемониками не признаются; вторая
    # @does  строка — первое слово без пробелов и один аргумент-хвост
    # @does  (байты 33-255, без пробелов и табуляций) с пометой «?»:
    # @does  не литерал (не-цифра первой) и не имя (не буква и не
    # @does  подчёркивание первой).
    # @depends listing
    def test_binary_input(self):
        want = (b"1:" + bytes(range(0, 9)) + b"\n"
                + b"2:" + bytes(range(11, 32)) + b" "
                + bytes(range(33, 256)) + b"?\n")
        self.assertEqual(listing(bytes(range(256))), (0, want))


class TestArgs(unittest.TestCase):
    """Подшаг 2: буфер аргументов и его лимит 256 пар."""

    # @method test_many_args_fit() -> None
    # @in    нет
    # @out   нет
    # @does  256 аргументов одной строки — норма: пары занимают буфер
    # @does  аргументов целиком (argbase..arglimit), каждый аргумент —
    # @does  литерал «7» с пометой «#7», вывод — все слова с пометами
    # @does  через пробел, код 0.
    # @depends listing
    def test_many_args_fit(self):
        line = "DB" + " 7" * 256
        want = "1:" + line.replace(" 7", " 7#7") + "\n"
        self.assertEqual(listing(line.encode() + b"\n"), (0, want.encode()))

    # @method test_trailing_spaces_after_args() -> None
    # @in    нет
    # @out   нет
    # @does  Пробелы в конце строки после последнего аргумента не дают
    # @does  пустого 257-го слова (пробелы пропускаются до проверки
    # @does  лимита) — норма, код 0.
    # @depends listing
    def test_trailing_spaces_after_args(self):
        line = "DB" + " 7" * 256
        want = "1:" + line.replace(" 7", " 7#7") + "\n"
        self.assertEqual(listing(line.encode() + b"   \n"),
                         (0, want.encode()))

    # @method test_too_many_args() -> None
    # @in    нет
    # @out   нет
    # @does  257-й аргумент строки — ошибка ёмкости: «uAsm: строка 2:
    # @does  слишком много аргументов» и код 16 (SPEC/L4-SELFHOST.txt,
    # @does  раздел 5А); строки до ошибки уже выведены.
    # @depends listing
    def test_too_many_args(self):
        text = "NOP\nDB" + " 7" * 257
        want = ("1:NOP=0\nuAsm: строка 2: " + ARGS_TEXT + "\n").encode()
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
    # @does  трёх строк с пометами подшага 3, код процесса 0.
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
                run.stdout, b"1:NOP=0\n2:PUSH=1 1#1\n3:HALT=69 0#0\n")


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
