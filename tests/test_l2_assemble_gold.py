# @uadro
# @file    tests/test_l2_assemble_gold.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Подшаг 7 ветви l2.uasm.assemble — золотой набор и закрытие
# @desc    ветви: полный золотой набор SPEC/L4-SELFHOST.txt (раздел 6)
# @desc    одним файлом — пустой текст, каждая мнемоника отдельно (imm —
# @desc    со значениями 0, 1, 12345, 2^64-1), DB/DW с литералами всех
# @desc    форм и именами, DS/DZ с escape, метки, константы, ссылки
# @desc    вперёд, метка в конце текста, программы этапов 1-2 (образы
# @desc    байт в байт с эталонными), тексты дизассемблера (вывод эталона
# @desc    disasm на образах золотого набора дизассемблера собирается
# @desc    обратно в исходный образ), ошибки входа — по одному тексту
# @desc    на каждый вид раздела 7 SPEC/L2-UASM.txt и ошибки ёмкости
# @desc    раздела 5А, вход сверх лимита без номера строки; страховка
# @desc    полноты категорий — счётные проверки набора; TestProcess —
# @desc    сквозной конвейер процессами: собственный ассемблер собирает
# @desc    src/hello.uasm, собранный образ исполняется и печатает «Hi».
# @desc    Переполнение таблицы символов прогоном не покрыто:
# @desc    квадратичный поиск делает полный набор многократноминутным
# @desc    (решение подшага 5, tests/test_l2_assemble_sym.py; SPEC v0.7,
# @desc    раздел 6).

"""Золотой набор ассемблера l2.uasm.assemble (SPEC/L4-SELFHOST.txt,
раздел 6; подшаг 7 раздела 5А — закрытие ветви).

Собственное воплощение ассемблера (src/l2/assemble.ubrk с use-включениями,
образ — кирпич l2_image) прогоняется кирпичом run_with_io на каждом тексте
золотого набора (категории — списки RECORDS, LITERALS, STRINGS, SYMBOLS,
ERRORS и DISASM_TEXTS — вывод эталона disasm на образах золотого набора
дизассемблера). Для каждого текста: выход равен эталону assemble байт
в байт, код равен коду эталона; текст дизассемблера образа B собирается
обратно в B (раунд-трип раздела 6).

Категории набора (раздел 6): пустой текст; каждая мнемоника отдельно
(30 без imm64, 8 imm-опкодов со значениями 0, 1, 12345, 2^64-1);
литералы всех форм и имена; DS/DZ с escape; метки, константы, ссылки
вперёд, метка в конце; программы этапов 1-2 — образы байт в байт
с эталонными; 171 текст дизассемблера; ошибки входа — по одному тексту
на каждый вид раздела 7 SPEC/L2-UASM.txt и ошибки ёмкости раздела 5А
(«вход слишком большой» — без номера строки, «образ слишком большой» —
строками DW, «слишком много аргументов», «слишком длинное имя»);
переполнение таблицы символов прогоном не покрыто (квадратичный поиск —
решение подшага 5, SPEC v0.7, раздел 6).

TestProcess — сквозной конвейер настоящими процессами: ubrick_cli
compile собирает собственный ассемблер, uvm_cli исполняет его с входным
файлом src/hello.uasm — stdout равен эталонному образу; собранный образ
исполняется и печатает «Hi», коды процессов 0.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import test_l2_disasm_gold as dg
from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_assemble import assemble
from tools.uasm_disasm import disasm as ref_disasm
from tools.uvm_table import TABLE

PROGRAMS = ("hello.uasm", "arith.uasm", "nested_calls.uasm")
VALUES = (0, 1, 12345, 2 ** 64 - 1)            # золотые значения imm64
IMM = [rec for rec in TABLE if rec[3]]         # опкоды с полем imm64
NOIMM = [rec for rec in TABLE if not rec[3]]   # опкоды без поля
SRC_LIMIT = 0x90000 - 0x10000                  # буфер источника: 512 КиБ
BIG_LINE = "вход слишком большой\n"            # диагностика без номера
IMG_TEXT = "образ слишком большой"             # лимит буфера образа
ARGS_TEXT = "слишком много аргументов"         # лимит 256 пар аргументов
NAME_TEXT = "слишком длинное имя"              # лимит имени 63 байта
IMG_LINES = 32                                 # полные строки DW до отказа

# Каждый вид записи отдельно (SPEC, раздел 6): все мнемоники — 30 без
# imm64 одной строкой и 8 imm-опкодов с каждым золотым значением.
RECORDS = [rec[1] for rec in NOIMM] + [
    "%s %d" % (rec[1], value) for rec in IMM for value in VALUES]

# DB/DW с литералами всех форм и именами (SPEC, разделы 4 и 6): формы,
# минус, границы диапазона, операнд инструкции, имена констант и меток.
LITERALS = [
    "DB 0", "DB 255", "DB 'A'", "DB 0x1F", "DB 0b11", "DB -0",
    "DW 0", "DW 18446744073709551615", "DW -1",
    "DW -9223372036854775808", "DW 'A'", "DW 0xDeAdBeEf", "DW 0b101",
    "PUSH 0x1F", "PUSH 0b101", "PUSH 'A'", "PUSH -'A'", "PUSH -0",
    "k = 5\nDW k", "k = 5\nDB k", "x:\nDW x", "x:\nDB x",
]

# DS/DZ с escape и многобайтовым UTF-8 (SPEC, разделы 4 и 6).
STRINGS = [
    'DS ""', 'DZ ""', 'DS "a"', 'DZ "ab"',
    'DS "a\\n\\r\\t\\\\\\"\\0"', 'DZ "\\n\\r\\t\\\\\\"\\0"',
    'DS "a\\"b"', 'DS "привет"', 'DZ "мир!"',
]

# Метки, константы, ссылки вперёд, метка в конце текста (SPEC, раздел 3).
SYMBOLS = [
    "x:", "NOP\nx:", "a:\nb:\nc:", "x = 5\nPUSH x", "PUSH z\nz = 0",
    "x:\nJMP x", "PUSH 1\nJMP a\na:", "CALL fwd\nfwd:",
    "JMP end\nNOP\nend:", "s1 = 1\ns10 = 10\nPUSH s1\nPUSH s10",
]

# Ошибки входа (SPEC, раздел 6): по одному тексту на каждый вид ошибок
# раздела 7 SPEC/L2-UASM.txt («плохое имя» — обе формы); ожидания — эталон.
ERRORS = [
    "x: NOP\n",                      # плохое имя (слова после метки)
    "5 = 5\n",                       # плохое имя (левая часть)
    "x:\nx:\n",                      # повторное определение имени x
    "PUS\n",                         # неизвестная мнемоника PUS
    "NOP 1\n",                       # лишний операнд у NOP
    "PUSH\n",                        # нет операнда у PUSH
    "PUSH 5x\n",                     # плохой литерал 5x
    "PUSH 99999999999999999999\n",   # литерал вне диапазона
    "DB 256\n",                      # байт вне диапазона
    "PUSH x\n",                      # неизвестное имя x
    "DB\n",                          # пустая директива DB
    'DS "a\n',                       # плохой строковый литерал
]

# Тексты дизассемблера (SPEC, раздел 6): вывод эталона disasm на образах
# золотого набора дизассемблера — сборка каждого равна исходному образу.
DISASM_TEXTS = [(label, ref_disasm(image).encode("utf-8"), image)
                for label, image in dg.golden_images()]


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для путей src/l2, src и запуска
# @does  инструментов настоящим процессом в TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method l2_source() -> str
# @in    нет
# @out   path: str — путь к исходнику src/l2/assemble.ubrk
# @does  Строит путь к собственному воплощению ассемблера (слой L2,
# @does  SPEC/L4-SELFHOST.txt, раздел 5А); use-включения asmmem, asmwords,
# @does  asmmnem, asmlex, asmline, asmsym и asmcode склеивает загрузчик.
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "assemble.ubrk")


# @method src_path(name) -> str
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   path: str — путь к программе этапа 1-2
# @does  Строит путь к исходнику .uasm каталога src/; кирпич src_text
# @does  и TestProcess.
def src_path(name):
    return os.path.join(repo_root(), "src", name)


# @method src_text(name) -> str
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   text: str — текст исходника в кодировке UTF-8
# @does  Читает исходник программы этапа 1-2 целиком; кирпич
# @does  test_stage12_programs.
def src_text(name):
    with open(src_path(name), "r", encoding="utf-8") as handle:
        return handle.read()


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ ассемблера, собранный командой compile;
# @out   None — ошибка сборки (сообщение печатает cli в stderr)
# @does  Собирает src/l2/assemble.ubrk настоящей командой ubrick_cli
# @does  (режим compile, временный файл образа); кирпич всех тестов ветви.
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


# @method feed(image, text) -> tuple
# @in    image: bytes — образ ассемблера
# @in    text: bytes — текст uAsm (вход ассемблера)
# @out   pair: tuple — (код завершения, байты stdout)
# @does  Прогон образа без процесса с подменёнными stdin/stdout; кирпич
# @does  всех проверок ветви.
# @depends tk.run_with_io
def feed(image, text):
    return tk.run_with_io(image, text)


# @method want(text) -> tuple
# @in    text: str — текст uAsm (несколько строк)
# @out   pair: tuple — (код завершения, байты stdout) ожидание
# @does  Строит ожидание эталоном assemble (кирпич паритета с
# @does  tools/uasm_assemble.py, источник истины поведения): успех —
# @does  образ байт в байт, код 0; ошибка — диагностическая строка
# @does  «uAsm: строка N: текст» и код 16.
# @depends assemble
def want(text):
    image, error = assemble(text)
    if error is not None:
        return 16, (error + "\n").encode("utf-8")
    return 0, image


# @method err(line, text) -> bytes
# @in    line: int — номер строки текста, начиная с 1
# @in    text: str — текст ошибки
# @out   want: bytes — диагностическая строка с переводом
# @does  Строит ожидаемую диагностику «uAsm: строка N: текст»; кирпич
# @does  тестов границ контракта инструмента (сверх эталона).
def err(line, text):
    return ("uAsm: строка %d: %s\n" % (line, text)).encode("utf-8")


# @method parity(image, text) -> None
# @in    image: bytes — образ ассемблера
# @in    text: str — золотой текст uAsm
# @out   нет (утверждение теста)
# @does  Сверка с эталоном (SPEC/L4-SELFHOST.txt, раздел 6): выход
# @does  собственного ассемблера на тексте равен ожиданию эталона want
# @does  байт в байт (код и образ либо код и диагностика); кирпич всех
# @does  категорий золотого набора.
# @depends feed, want
def parity(image, text):
    got = feed(image, text.encode("utf-8"))
    assert got == want(text), (text, got, want(text))


# @method golden_disasm(image, label, text, data) -> None
# @in    image: bytes — образ ассемблера
# @in    label: str — имя золотого образа (сообщение при расхождении)
# @in    text: bytes — текст uAsm — вывод эталона disasm на образе
# @in    data: bytes — исходный золотой образ
# @out   нет (утверждение теста)
# @does  Раунд-трип на текстах дизассемблера (SPEC, раздел 6): сборка
# @does  вывода эталона disasm собственным ассемблером равна исходному
# @does  образу байт в байт, код 0.
# @depends feed
def golden_disasm(image, label, text, data):
    got = feed(image, text)
    assert got == (0, data), (label, got, data)


# @method image_overflow_text() -> bytes
# @in    нет
# @out   text: bytes — текст uAsm сверх лимита буфера образа
# @does  Строит текст ошибки ёмкости «образ слишком большой» строками DW
# @does  (SPEC, раздел 5А): 32 строки по 256 аргументов заполняют буфер
# @does  образа 64 КиБ точно (32 * 256 * 8 = 65536), 33-я строка DW 1
# @does  не помещается — диагностика со строкой 33; кирпич
# @does  test_image_over_limit.
def image_overflow_text():
    line = "DW" + " 1" * 256
    return ("\n".join([line] * IMG_LINES) + "\nDW 1\n").encode("utf-8")


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


class TestGoldenSet(unittest.TestCase):
    """Золотой набор подшагом 7: сверка с эталоном и раунд-трип."""

    # @method test_empty_text() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой текст — пустой образ и код 0 (SPEC/L2-UASM.txt,
    # @does  раздел 7; SPEC/L4-SELFHOST.txt, раздел 6): записей нет —
    # @does  байтов нет.
    # @depends l2_image, feed
    def test_empty_text(self):
        self.assertEqual(feed(l2_image(), b""), (0, b""))

    # @method test_each_record_kind() -> None
    # @in    нет
    # @
