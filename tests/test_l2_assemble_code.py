# @uadro
# @file    tests/test_l2_assemble_code.py
# @layer   T0
# @branch  l2.uasm.assemble
# @desc    Тесты подшага 6 ветви l2.uasm.assemble — проход 2 и вывод
# @desc    образа (src/l2/asmcode.ubrk — кодирование записей: p2step,
# @desc    putbyte/putword, resval, emitdb/emitdw, emitds/emitdz,
# @desc    emitinstr; слова ps/imgout главного файла src/l2/assemble.ubrk):
# @desc    выход — образ UVM байт в байт с эталоном assemble
# @desc    (tools/uasm_assemble.py) либо диагностическая строка и код 16.
# @desc    Все 38 мнемоник (ожидание — из таблицы опкодов tools/
# @desc    uvm_table), формы значений imm64 и аргументов DB/DW (десятичная,
# @desc    шестнадцатеричная, двоичная, символьная, минус, границы
# @desc    диапазона), байты DS/DZ с escape и многобайтовым UTF-8, имена
# @desc    и ссылки вперёд, ошибки значений («неизвестное имя X», «плохой
# @desc    литерал X», «литерал вне диапазона», «байт вне диапазона»),
# @desc    лимит буфера образа 64 КиБ — «образ слишком большой»
# @desc    (контракт инструмента, у эталона лимита нет — ожидания явные;
# @desc    самые медленные тесты ветви, около минуты на пару, как лимит
# @desc    входа в tests/test_l2_assemble.py).

"""Тесты прохода 2 и вывода образа подшага 6 ветви l2.uasm.assemble.

Проход 2 (SPEC/L2-UASM.txt, раздел 7; SPEC/L4-SELFHOST.txt, раздел 5А):
записи кодируются в байты с подстановкой значений имён из таблицы
символов прохода 1; выход инструмента — образ целиком при успехе
(код 0), при ошибке — только диагностическая строка «uAsm: строка N:
текст» и код 16. Пустой текст — пустой образ.

Паритет (TestParity): ожидания каждой программы строит эталон assemble
(tools/uasm_assemble.py) — источник истины поведения; расхождение —
ошибка собственного воплощения. Границы контракта инструмента (лимит
образа 64 КиБ) сверх эталона — явные ожидания. Коды опкодов и признак
imm64 — таблица tools/uvm_table (TestMnemonics).
"""

import os
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_assemble import assemble
from tools.uvm_table import TABLE

IMG_TEXT = "образ слишком большой"      # ошибка ёмкости буфера образа
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
# @does  SPEC/L4-SELFHOST.txt, раздел 5А); инструмент включает asmcode.ubrk
# @does  строкой use.
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "assemble.ubrk")


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ ассемблера (None — ошибка сборки)
# @does  Собирает src/l2/assemble.ubrk командой ubrick_cli (compile);
# @does  кирпич всех тестов файла (asmcode.ubrk внутри инструмента).
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


class TestParity(unittest.TestCase):
    """Кодирование значений и ошибки — паритет с эталоном assemble."""

    # @method test_programs() -> None
    # @in    нет
    # @out   нет
    # @does  Представители программ прохода 2: значения imm64 всех форм
    # @does  (0, 1, 12345, 2^64-1, -1, -2^63, -0, hex, двоичная,
    # @does  символьная, минус символьной) у всех imm-опкодов; DB и DW
    # @does  с литералами всех форм и именами; DS/DZ с escape
    # @does  и многобайтовым UTF-8; имена и ссылки вперёд; ошибки
    # @does  значений («неизвестное имя X» в операнде и аргументах,
    # @does  «плохой литерал X», «литерал вне диапазона», «байт вне
    # @does  диапазона»: 256, -1, имя-константа 300) — вывод собственного
    # @does  воплощения равен эталону байт в байт.
    # @depends feed, want
    def test_programs(self):
        programs = [
            "PUSH 0", "PUSH 1", "PUSH 12345",
            "PUSH 18446744073709551615", "PUSH -1",
            "PUSH -9223372036854775808", "PUSH -0",
            "PUSH 0x1F", "PUSH 0b101", "PUSH 'A'", "PUSH -'A'",
            "JMP 0x10", "JZ 5", "JNZ 0", "CALL 0", "HALT 0", "SYS 1",
            "PICK 3", "NOP", "RET", "ADD",
            "DB 0", "DB 255", "DB -0", "DB 'A'", "DB 0x1F", "DB 0b11",
            "DW 0", "DW 18446744073709551615", "DW -1",
            "DW -9223372036854775808", "DW 'A'", "DW 0b101",
            'DS ""', 'DS "a"', 'DZ ""', 'DZ "ab"',
            'DS "a\\n\\r\\t\\\\\\"\\0"', 'DZ "\\n"', 'DS "привет"',
            'DZ "мир!"',
            "x = 5\nDW x", "x = 5\nDB x", "x:\nDW x",
            "JMP end\nNOP\nend:", "CALL fwd\nfwd:",
            "PUSH a\nADD\na:", "x = 65\ny = x\nDW x y",
            "m1:\nJMP m1", "NOP\nPUSH 1\nHALT 0",
            "main:\nCALL main\nHALT 0",
            "DB 255 0 1", "DW 1 2 3", "DB 7\nDB 7\nDB 7",
            "PUSH x", "DB x", "DW x",
            "PUSH 5x", "PUSH 1 2", "PUSH -",
            "PUSH 99999999999999999999", "PUSH -9223372036854775809",
            "DB 256", "DB -1", "DB 65536",
            "x = 300\nDB x", "x = -1\nDB x",
            "DW x\nx = 1",
        ]
        for text in programs:
            with self.subTest(text=text):
                self.assertEqual(feed(text.encode("utf-8")),
                                 want(text))

    # @method test_imm_names_and_labels() -> None
    # @in    нет
    # @out   нет
    # @does  Операнд-имя разрешается значением из таблицы символов
    # @does  прохода 1: метки дают адреса (JMP на метку за PUSH — 9),
    # @does  константы — значения литералов; ссылка вперёд на метку
    # @does  в конце текста; имён-омонимов нет: s1 и s10 различаются
    # @does  (префикс не совпадает) — вывод равен эталону.
    # @depends feed, want
    def test_imm_names_and_labels(self):
        programs = [
            "a:\nJMP a",
            "PUSH 1\nJMP a\na:",
            "k = 7\nPUSH k",
            "s1 = 1\ns10 = 10\nPUSH s1\nPUSH s10",
            "PUSH z\nz = 0",
            "JZ fin\nNOP\nNOP\nfin:\nHALT 0",
        ]
        for text in programs:
            with self.subTest(text=text):
                self.assertEqual(feed(text.encode("utf-8")),
                                 want(text))


class TestMnemonics(unittest.TestCase):
    """Все 38 мнемоник: код опкода и поле imm64 (таблица опкодов)."""

    # @method test_all_mnemonics() -> None
    # @in    нет
    # @out   нет
    # @does  Все 38 мнемоник таблицы опкодов кодируются верно (ожидание —
    # @does  из tools/uvm_table, источник истины кодов и признака imm64):
    # @does  байт опкода, у мнемоники с imm64 — ещё восемь байтов
    # @does  little-endian значения операнда (7), без imm64 — один байт.
    # @depends feed, MNEMONICS, IMMS
    def test_all_mnemonics(self):
        codes = {rec[1]: rec[0] for rec in TABLE}
        lines = []
        image = bytearray()
        for name in MNEMONICS:
            lines.append(name + (" 7" if IMMS[name] else ""))
            image.append(codes[name])
            if IMMS[name]:
                image += (7).to_bytes(8, "little")
        text = "\n".join(lines) + "\n"
        self.assertEqual(feed(text.encode()),
                         (0, bytes(image)))


class TestValues(unittest.TestCase):
    """Значения констант наблюдаемы аргументом DW (SPEC, разделы 3-4)."""

    # @method test_const_values() -> None
    # @in    нет
    # @out   нет
    # @does  Значения констант всех форм по модулю 2^64: -1 обёрнут
    # @does  в 2^64-1, -2^63 — в 2^63, hex и символьная формы дословно;
    # @does  DW x кодирует значение восемью байтами little-endian.
    # @depends feed
    def test_const_values(self):
        cases = [
            ("x = -1", (2 ** 64 - 1).to_bytes(8, "little")),
            ("x = -9223372036854775808",
             (2 ** 63).to_bytes(8, "little")),
            ("x = 18446744073709551615",
             (2 ** 64 - 1).to_bytes(8, "little")),
            ("x = 0xDeAdBeEf", (0xDEADBEEF).to_bytes(8, "little")),
            ("x = 'A'", (65).to_bytes(8, "little")),
            ("x = 0b101", (5).to_bytes(8, "little")),
        ]
        for defline, image in cases:
            with self.subTest(defline=defline):
                self.assertEqual(
                    feed((defline + "\nDW x\n").encode()),
                    (0, image))


class TestImageLimit(unittest.TestCase):
    """Лимит буфера образа 64 КиБ — контракт инструмента (SPEC, 5А)."""

    # @method test_image_exact_fit() -> None
    # @in    нет
    # @out   нет
    # @does  Образ ровно в 64 КиБ занимает буфер целиком (последний байт
    # @does  пишется в 0x9FFFF, putbyte пропускает адрес imglimit - 1) —
    # @does  успех: 65536 байтов «A», код 0; у эталона лимита нет —
    # @does  ожидание явное; самый медленный тест ветви (два прохода
    # @does  по строке в 64 КиБ).
    # @depends feed
    def test_image_exact_fit(self):
        text = 'DS "' + "A" * 65536 + '"\n'
        self.assertEqual(feed(text.encode()),
                         (0, b"A" * 65536))

    # @method test_image_over_limit() -> None
    # @in    нет
    # @out   нет
    # @does  Девятый байт слова DW за пределом буфера (DS 65529 + DW 1:
    # @does  65529 + 8 > 65536, проверка putword до записи) — «uAsm:
    # @does  строка 2: образ слишком большой» и код 16; образ при ошибке
    # @does  не выводится — только диагностика; у эталона лимита нет —
    # @does  ожидание явное.
    # @depends feed, err
    def test_image_over_limit(self):
        text = 'DS "' + "A" * 65529 + '"\nDW 1\n'
        self.assertEqual(feed(text.encode()),
                         (16, err(2, IMG_TEXT)))


if __name__ == "__main__":
    unittest.main()
