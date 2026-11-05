# @uadro
# @file    tests/test_l2_assemble_lex.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшага 3 ветви l2.uasm.assemble — литералы и имена
# @desc    (src/l2/asmlex.ubrk — собственное воплощение эталона
# @desc    tools/uasm_lex.py): пометы слов-аргументов листинга — «#значение»
# @desc    (литерал, по модулю 2^64), «!» (вне -2^63..2^64-1), «*» (имя),
# @desc    «?» (прочее); скан DS/DZ — «#длина» байтов либо «!»
# @desc    (SPEC/L2-UASM.txt, разделы 3-4 и 6; SPEC/L4-SELFHOST.txt,
# @desc    раздел 5А). Ожидания помет строятся эталоном — паритет
# @desc    с источником истины поведения, байт в байт.

"""Тесты литералов и имён подшага 3 ветви l2.uasm.assemble.

Собственный ассемблер (кирпичи l2_image и run_with_io) прогоняется
на строках «DB слово…»: слова-аргументы получают пометы lexmark:
«#значение» (литерал в диапазоне, по модулю 2^64, -1 ->
18446744073709551615), «!» (цифры верны, вне диапазона), «*» (имя
[A-Za-z_][A-Za-z0-9_]*), «?» (прочее). Ожидание строит эталон (кирпич
mark: parse_number + in_literal_range + is_name; latin-1 — байт
в байт для всех 256 байтов); границы проверены и явно (2^63-1,
2^64-1, 2^64, -2^63).

DS/DZ (dsline): остаток целиком (буфер аргументов не заполняется),
«#длина» после escape-разворачивания (UTF-8 дословно) либо «!» при
ошибке (нет кавычек, не закрыта, мусор после закрывающей, неизвестный
escape, обрыв escape).
"""

import os
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_lex import in_literal_range, is_name, parse_number

WORD = 1 << 64
MARK_LIT = "#"      # помета числового литерала (значение по модулю 2^64)
MARK_RANGE = "!"    # цифры верны, значение вне диапазона
MARK_NAME = "*"     # помета имени
MARK_BAD = "?"      # ни литерал, ни имя


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
# @does  SPEC/L4-SELFHOST.txt, раздел 5А); инструмент включает asmlex.ubrk
# @does  строкой use.
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "assemble.ubrk")


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ ассемблера (None — ошибка сборки)
# @does  Собирает src/l2/assemble.ubrk командой ubrick_cli (compile);
# @does  кирпич всех тестов файла (asmlex.ubrk внутри инструмента).
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


# @method mark(word) -> str
# @in    word: bytes — слово-аргумент без пробелов
# @out   marker: str — ожидаемая помета листинга подшага 3
# @does  Строит помету эталоном (кирпич паритета с tools/uasm_lex.py):
# @does  parse_number даёт значение — in_literal_range решает диапазон
# @does  («#» и значение по модулю 2^64 либо «!»), None и is_name — «*»
# @does  либо «?»; декодирование latin-1 сохраняет байты один к одному
# @does  (символьные литералы, не-ASCII имена).
# @depends parse_number, in_literal_range, is_name
def mark(word):
    value = parse_number(word.decode("latin-1"))
    if value is not None:
        if in_literal_range(value):
            return MARK_LIT + str(value % WORD)
        return MARK_RANGE
    if is_name(word.decode("latin-1")):
        return MARK_NAME
    return MARK_BAD


# @method db_line(words) -> tuple
# @in    words: list — слова-аргументы (bytes) одной строки DB
# @out   pair: tuple — (код завершения, листинг) собственной сборки
# @does  Строка «DB w1 w2 …» одним прогоном; кирпич тестов помет.
# @depends feed
def db_line(words):
    return feed(b"DB " + b" ".join(words) + b"\n")


# @method db_want(words) -> bytes
# @in    words: list — слова-аргументы (bytes) одной строки DB
# @out   want: bytes — ожидаемый листинг строки
# @does  Строит ожидание «1:DB слово-пометка …» пометами эталона
# @does  (кирпич mark).
# @depends mark
def db_want(words):
    line = "1:DB " + " ".join(
        w.decode("latin-1") + mark(w) for w in words)
    return (line + "\n").encode("latin-1")


class TestDec(unittest.TestCase):
    """Десятичная форма [0-9]+ (SPEC/L2-UASM.txt, раздел 4)."""

    # @method test_values() -> None
    # @in    нет
    # @out   нет
    # @does  Значения 0, 1, 42, 12345 и старшие 2^63-1, 2^64-1 — литералы
    # @does  в диапазоне, пометы «#значение».
    # @depends db_line, db_want
    def test_values(self):
        words = [b"0", b"1", b"42", b"12345",
                 str(2 ** 63 - 1).encode(), str(WORD - 1).encode()]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_leading_zeros() -> None
    # @in    нет
    # @out   нет
    # @does  Ведущие нули не меняют значения: 007 — 7, 00000000000000005 — 5
    # @does  (как int эталона; длина слова значимости не имеет).
    # @depends db_line, db_want
    def test_leading_zeros(self):
        words = [b"007", b"00000000000000005"]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_digits_only() -> None
    # @in    нет
    # @out   нет
    # @does  Не-цифра до конца слова ломает форму: 12x, 1a, 5+, — эталон
    # @does  parse_dec даёт None; имена они тоже не образуют (не буква
    # @does  первой) — помета «?».
    # @depends db_line, db_want
    def test_digits_only(self):
        words = [b"12x", b"1a", b"5+"]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestHex(unittest.TestCase):
    """Шестнадцатеричная форма 0x[0-9A-Fa-f]+ (SPEC, раздел 4)."""

    # @method test_values() -> None
    # @in    нет
    # @out   нет
    # @does  Значения 0x0, 0xff, 0xFF, 0xDeAdBeEf и старшие 0x7F…F (2^63-1),
    # @does  0xFF…F (2^64-1) — регистр цифр не значим.
    # @depends db_line, db_want
    def test_values(self):
        words = [b"0x0", b"0xff", b"0xFF", b"0xDeAdBeEf",
                 b"0x" + b"7" + b"F" * 15, b"0x" + b"F" * 16]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_prefix_shapes() -> None
    # @in    нет
    # @out   нет
    # @does  Префикс строчными обязателен: 0X1F не форма; без цифр после
    # @does  префикса (0x) и короткие (0b2 — не двоичные цифры) — не формы;
    # @does  пометы по эталону.
    # @depends db_line, db_want
    def test_prefix_shapes(self):
        words = [b"0X1F", b"0x", b"0b2", b"0xG"]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestBin(unittest.TestCase):
    """Двоичная форма 0b[01]+ (SPEC, раздел 4)."""

    # @method test_values() -> None
    # @in    нет
    # @out   нет
    # @does  Значения 0b0, 0b101, 0b1 и 63 нуля (2^63), 64 единицы
    # @does  (2^64-1) — литералы в диапазоне.
    # @depends db_line, db_want
    def test_values(self):
        words = [b"0b0", b"0b101", b"0b1" + b"0" * 63, b"0b" + b"1" * 64]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_not_binary() -> None
    # @in    нет
    # @out   нет
    # @does  Цифры 2-9 не двоичные: 0b2 — не форма; префикс строчными:
    # @does  0B1 — не форма (как parse_bin эталона).
    # @depends db_line, db_want
    def test_not_binary(self):
        words = [b"0b2", b"0B1", b"0b"]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestChar(unittest.TestCase):
    """Символьная форма 'X' и '\e' (SPEC, раздел 4, CHAR_ESCAPES)."""

    # @method test_plain_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  Любой байт в кавычках — его код: 'A' 65, 'z' 122, '0' 48,
    # @does  кавычка '"' 34, апостроф ''' 39 (39 39 39), слэш без
    # @does  удвоения '\' 92 (39 92 39); пробел внутри ' ' — разделитель
    # @does  слов: как аргумент литерал разваливается на два «?»
    # @does  (split_words эталона делает то же; операнд инструкции
    # @does  останется целым — он берётся из остатка, подшаг 4).
    # @depends db_line, db_want, feed
    def test_plain_bytes(self):
        words = [b"'A'", b"'z'", b"'0'",
                 b"'" + bytes([34]) + b"'", bytes([39]) * 3,
                 b"'" + bytes([92]) + b"'"]
        self.assertEqual(db_line(words), (0, db_want(words)))
        self.assertEqual(feed(b"DB ' '\n"), (0, b"1:DB '? '?\n"))

    # @method test_escapes() -> None
    # @in    нет
    # @out   нет
    # @does  Все шесть escape CHAR_ESCAPES: '\n' 10, '\r' 13, '\t' 9,
    # @does  '\\' 92 (удвоение), '\'' 39, '\0' 0.
    # @depends db_line, db_want
    def test_escapes(self):
        words = [b"'\\n'", b"'\\r'", b"'\\t'", b"'\\\\'",
                 b"'\\''", b"'\\0'"]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_bad_shapes() -> None
    # @in    нет
    # @out   нет
    # @does  Длина не 3 и не 4 (''), неизвестный escape ('\q'), кавычка
    # @does  не на месте ('a, 'ab') — не формы; имена они не образуют — «?».
    # @depends db_line, db_want
    def test_bad_shapes(self):
        words = [b"''", b"'\\q'", b"'a", b"'ab'", b"'ab''"]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestMinus(unittest.TestCase):
    """Унарный минус и диапазон -2^63..2^64-1 (SPEC, раздел 4)."""

    # @method test_forms() -> None
    # @in    нет
    # @out   нет
    # @does  Минус перед любой формой: -0 -> 0, -1 -> 2^64-1, -0x10,
    # @does  -0b101, -'A' — значения оборачиваются по модулю 2^64
    # @does  (parse_number эталона даёт отрицательные, кодирование
    # @does  оборачивает — SPEC/L0-UVM.txt, раздел 1).
    # @depends db_line, db_want
    def test_forms(self):
        words = [b"-0", b"-1", b"-0x10", b"-0b101", b"-'A'"]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_minus_only() -> None
    # @in    нет
    # @out   нет
    # @does  Голый минус и минус с не-формой (--5, -x) — не литералы
    # @does  (literal_value тела возвращает None, как эталон); «?».
    # @depends db_line, db_want
    def test_minus_only(self):
        words = [b"-", b"--5", b"-x", b"-'ab'"]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestRange(unittest.TestCase):
    """Диапазон -2^63..2^64-1: верные цифры вне диапазона — «!»."""

    # @method test_over_positive() -> None
    # @in    нет
    # @out   нет
    # @does  Положительные сверх 2^64-1: 2^64 десятично, hex 0x1000…0
    # @does  (17 цифр), двоично 65 единиц — «!» (in_literal_range
    # @does  эталона: False, но цифры верны — kind 2).
    # @depends db_line, db_want
    def test_over_positive(self):
        words = [str(WORD).encode(),
                 b"0x" + b"1" + b"0" * 16,
                 b"0b" + b"1" * 65,
                 b"999999999999999999999999"]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_over_negative() -> None
    # @in    нет
    # @out   нет
    # @does  Отрицательные ниже -2^63: -(2^63+1) и огромные — «!»;
    # @does  граница -2^63 — литерал, обёрнутый в 2^63 (0x8000…0).
    # @depends db_line, db_want
    def test_over_negative(self):
        words = [b"-" + str(2 ** 63 + 1).encode(),
                 b"-" + str(WORD).encode(),
                 b"-" + str(2 ** 64 + 5).encode()]
        self.assertEqual(db_line(words), (0, db_want(words)))
        self.assertEqual(db_line([b"-" + str(2 ** 63).encode()]),
                         (0, ("1:DB -" + str(2 ** 63) + MARK_LIT
                              + str(2 ** 63) + "\n").encode()))

    # @method test_bad_shape_over_range() -> None
    # @in    нет
    # @out   нет
    # @does  Верные цифры с мусором — не литерал, несмотря на величину:
    # @does  999…9x — parse_dec эталона None («плохой литерал», подшаг 4),
    # @does  помета «?» — форма важнее переполнения (kind 0 приоритетнее
    # @does  kind 2).
    # @depends db_line, db_want
    def test_bad_shape_over_range(self):
        words = [b"18446744073709551616x", b"0b" + b"1" * 65 + b"z"]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestNames(unittest.TestCase):
    """Имена [A-Za-z_][A-Za-z0-9_]* (SPEC/L2-UASM.txt, раздел 3)."""

    # @method test_valid() -> None
    # @in    нет
    # @out   нет
    # @does  Буква или подчёркивание первой, дальше буквы, цифры,
    # @does  подчёркивания: x, abc, X, Z9, a1_b2, _1x, A9_; регистр
    # @does  значим; мнемоника в роли аргумента — имя («PUSH»): роль
    # @does  слова определяет позиция (SPEC, раздел 3).
    # @depends db_line, db_want
    def test_valid(self):
        words = [b"x", b"abc", b"X", b"Z9", b"a1_b2", b"_1x", b"A9_",
                 b"PUSH", b"DS"]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_invalid() -> None
    # @in    нет
    # @out   нет
    # @does  Цифра первой (1a), минус (-x), дефис (a-b), точка (a.b),
    # @does  не-ASCII байты внутри (a + 0xC3 0xA9) — не имена; часть —
    # @does  литералы (123), часть — мусор («?»).
    # @depends db_line, db_want
    def test_invalid(self):
        words = [b"1a", b"-x", b"a-b", b"a.b",
                 b"a" + bytes([195, 169]), b"123"]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestMixed(unittest.TestCase):
    """Смешанные строки: пометы по эталону на всём спектре форм."""

    # @method test_all_kinds_one_line() -> None
    # @in    нет
    # @out   нет
    # @does  Одна строка DB: литералы всех форм, имя, вне диапазона,
    # @does  мусор — пометы эталона байт в байт.
    # @depends db_line, db_want
    def test_all_kinds_one_line(self):
        words = [b"5", b"0x1F", b"0b101", b"'A'", b"-1", b"x",
                 str(WORD).encode(), b"0x", b"="]
        self.assertEqual(db_line(words), (0, db_want(words)))

    # @method test_sweep() -> None
    # @in    нет
    # @out   нет
    # @does  Сплошная проверка: слова-представители всех форм, границ
    # @does  и мусора — пометы эталона без ручных ожиданий.
    # @depends db_line, db_want
    def test_sweep(self):
        words = [b"0", b"1", b"9", b"10", b"255", b"256",
                 b"0x0", b"0xA", b"0xaF", b"0b0", b"0b1111",
                 b"'A'", b"'\\n'", b"'\\0'",
                 b"-1", b"-2", b"-0x1", b"-'z'",
                 str(2 ** 63).encode(), str(2 ** 63 - 1).encode(),
                 str(WORD - 1).encode(), str(WORD).encode(),
                 b"_" + b"x" * 60, b"1", b"a", b"z", b"_", b"Z_9",
                 b"x" * 9, b"-", b"=", b"+", b"0z", b"'", b"\""]
        self.assertEqual(db_line(words), (0, db_want(words)))


class TestString(unittest.TestCase):
    """Строковые литералы DS/DZ (SPEC, разделы 4 и 6, parse_string)."""

    # @method ds(line) -> tuple
    # @in    line: bytes — строка исходника без перевода
    # @out   pair: tuple — (код завершения, листинг) строки 1
    # @does  Прогон строки-директивы с переводом; кирпич тестов DS/DZ.
    # @depends feed
    def ds(self, line):
        return feed(line + b"\n")

    # @method test_lengths() -> None
    # @in    нет
    # @out   нет
    # @does  Пустая строка «""» — 0 байтов; escape дают по байту
    # @does  (\n \r \t \\ \" \0), прочие байты — дословно; помета —
    # @does  длина декодированных байтов (DZ добавит 0 при кодировании).
    # @depends ds
    def test_lengths(self):
        self.assertEqual(self.ds(b'DS ""'), (0, b'1:DS ""#0\n'))
        self.assertEqual(self.ds(b'DS "a"'),
                         (0, b'1:DS "a"#1\n'))
        self.assertEqual(self.ds(b'DS "\\n\\r\\t\\\\\\"\\0"'),
                         (0, b'1:DS "\\n\\r\\t\\\\\\"\\0"#6\n'))
        self.assertEqual(self.ds(b'DZ "ab"'), (0, b'1:DZ "ab"#2\n'))

    # @method test_utf8_verbatim() -> None
    # @in    нет
    # @out   нет
    # @does  Многобайтовые UTF-8 символы идут дословно: «привет» — 12
    # @does  байтов, «мир!» — 7; двойные пробелы внутри сохраняются
    # @does  (остаток печатается целиком, а не словами-аргументами).
    # @depends ds
    def test_utf8_verbatim(self):
        self.assertEqual(self.ds('DS "привет"'.encode("utf-8")),
                         (0, '1:DS "привет"#12\n'.encode("utf-8")))
        self.assertEqual(self.ds('DZ "мир!"'.encode("utf-8")),
                         (0, '1:DZ "мир!"#7\n'.encode("utf-8")))
        self.assertEqual(self.ds(b'DS "a  b"'),
                         (0, b'1:DS "a  b"#4\n'))

    # @method test_bad_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Ошибки скана — «!»: без кавычек, короткая кавычка,
    # @does  не закрыта, мусор после закрывающей, неизвестный escape,
    # @does  обрыв escape в конце (parse_string эталона None).
    # @depends ds
    def test_bad_literals(self):
        self.assertEqual(self.ds(b"DS x"), (0, b"1:DS x!\n"))
        self.assertEqual(self.ds(b'DS "'), (0, b'1:DS "!\n'))
        self.assertEqual(self.ds(b'DS "a'), (0, b'1:DS "a!\n'))
        self.assertEqual(self.ds(b'DS "a" x'), (0, b'1:DS "a" x!\n'))
        self.assertEqual(self.ds(b'DS "a\\q"'), (0, b'1:DS "a\\q"!\n'))
        self.assertEqual(self.ds(b'DS "a\\'), (0, b'1:DS "a\\!\n'))

    # @method test_many_words_no_args_error() -> None
    # @in    нет
    # @out   нет
    # @does  Буфер аргументов для DS/DZ не заполняется: 600 слов внутри
    # @does  кавычек не дают «слишком много аргументов» (лимит — только
    # @does  аргументы DB/DW); длина — все байты литерала.
    # @depends ds
    def test_many_words_no_args_error(self):
        line = b'DS "' + b"w " * 300 + b'"'
        want = b'1:' + line + b"#600\n"
        self.assertEqual(self.ds(line), (0, want))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, раздел 5А)."""

    # @method test_process_run() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта процессами: ubrick_cli compile, затем
    # @does  uvm_cli с входным файлом; stdout — листинг с пометами
    # @does  литералов и имён, код 0.
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_run(self):
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "assemble.uvm")
            src = os.path.join(tmp, "in.uasm")
            with open(src, "wb") as handle:
                handle.write(b"DB 0x1F x -1\nDZ \"a\\n\"\n")
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
                b"1:DB 0x1F#31 x* -1#18446744073709551615\n"
                b'2:DZ "a\\n"#2\n')


if __name__ == "__main__":
    unittest.main()
