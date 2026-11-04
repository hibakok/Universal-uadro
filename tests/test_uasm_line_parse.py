# @uadro
# @file    tests/test_uasm_line_parse.py
# @layer   T0
# @branch  t0.uasm.line
# @desc    Тесты разбора строки uAsm в запись: пустые строки, метки,
# @desc    константы, инструкции, директивы данных, комментарии и все
# @desc    тексты ошибок (SPEC/L2-UASM.txt, разделы 2-7).

"""Тесты parse_line (tools/uasm_line.py).

Каждый вид строки из раздела 2 SPEC и каждый текст ошибки из раздела 7
покрыты отдельным случаем. Кирпичи подготовки строки — в
tests/test_uasm_line.py.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.uasm_line import parse_line


class TestParseEmpty(unittest.TestCase):
    """Пустые строки и комментарии (SPEC, раздел 2)."""

    # @method test_empty_and_comment() -> None
    # @in    нет
    # @out   нет
    # @does  Пустая строка, одни пробелы/табуляции и комментарий
    # @does  дают None.
    def test_empty_and_comment(self):
        for line in ("", "   ", "\t\t", "; comment", "  ; c", "\t;x"):
            self.assertIsNone(parse_line(line), line)


class TestParseLabel(unittest.TestCase):
    """Метки «имя:» — вся строка целиком (SPEC, разделы 3 и 7)."""

    # @method test_label_ok() -> None
    # @in    нет
    # @out   нет
    # @does  Метка занимает всю строку; имя может совпадать с
    # @does  мнемоникой и директивой — роль слова определяет позиция.
    def test_label_ok(self):
        self.assertEqual(parse_line("foo:"), ("label", "foo"))
        self.assertEqual(parse_line("_x1:"), ("label", "_x1"))
        self.assertEqual(parse_line("  PUSH:  "), ("label", "PUSH"))
        self.assertEqual(parse_line("DB:"), ("label", "DB"))

    # @method test_label_bad_name() -> None
    # @in    нет
    # @out   нет
    # @does  Имя не по разделу 3 SPEC — «плохое имя».
    def test_label_bad_name(self):
        for line in (":", "1foo:", "foo::", "метка:", "a-b:", "'q':"):
            self.assertEqual(parse_line(line), ("error", "плохое имя"), line)

    # @method test_label_extra_words() -> None
    # @in    нет
    # @out   нет
    # @does  Слова после метки — «плохое имя»; двоеточие через пробел —
    # @does  не метка, а «неизвестная мнемоника».
    def test_label_extra_words(self):
        self.assertEqual(parse_line("foo: bar"), ("error", "плохое имя"))
        self.assertEqual(parse_line("foo :"),
                         ("error", "неизвестная мнемоника foo"))
        self.assertEqual(parse_line("foo:bar"),
                         ("error", "неизвестная мнемоника foo:bar"))


class TestParseConst(unittest.TestCase):
    """Константы «имя = числовой литерал» (SPEC, разделы 3, 4 и 7)."""

    # @method test_const_values() -> None
    # @in    нет
    # @out   нет
    # @does  Все формы числовых литералов и границы диапазона
    # @does  -2^63..2^64-1.
    def test_const_values(self):
        self.assertEqual(parse_line("x = 5"), ("const", "x", 5))
        self.assertEqual(parse_line("y=-0x10"), ("const", "y", -16))
        self.assertEqual(parse_line("z = 0b101"), ("const", "z", 5))
        self.assertEqual(parse_line("w = 'A'"), ("const", "w", 65))
        self.assertEqual(parse_line("n = -'A'"), ("const", "n", -65))
        self.assertEqual(parse_line("max = 18446744073709551615"),
                         ("const", "max", 18446744073709551615))
        self.assertEqual(parse_line("min = -9223372036854775808"),
                         ("const", "min", -9223372036854775808))

    # @method test_const_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Плохое имя слева; справа — не числовой литерал (имя,
    # @does  строка, мусор, несколько слов, пусто); значение вне
    # @does  диапазона.
    def test_const_errors(self):
        self.assertEqual(parse_line("1x = 5"), ("error", "плохое имя"))
        self.assertEqual(parse_line("x y = 5"), ("error", "плохое имя"))
        self.assertEqual(parse_line("= 5"), ("error", "плохое имя"))
        self.assertEqual(parse_line("метка = 5"), ("error", "плохое имя"))
        self.assertEqual(parse_line("x = abc"),
                         ("error", "плохой литерал abc"))
        self.assertEqual(parse_line('x = "s"'),
                         ("error", "плохой литерал \"s\""))
        self.assertEqual(parse_line("x = 'ab'"),
                         ("error", "плохой литерал 'ab'"))
        self.assertEqual(parse_line("x ="), ("error", "плохой литерал"))
        self.assertEqual(parse_line("x = 5 6"),
                         ("error", "плохой литерал 5 6"))
        self.assertEqual(parse_line("x = - 5"),
                         ("error", "плохой литерал - 5"))
        self.assertEqual(parse_line("x = 18446744073709551616"),
                         ("error", "литерал вне диапазона"))
        self.assertEqual(parse_line("x = -9223372036854775809"),
                         ("error", "литерал вне диапазона"))

    # @method test_const_name_conflicts() -> None
    # @in    нет
    # @out   нет
    # @does  Константа с именем мнемоники или директивы невозможна:
    # @does  строка разбирается как инструкция или директива (SPEC,
    # @does  раздел 3).
    def test_const_name_conflicts(self):
        self.assertEqual(parse_line("PUSH = 5"), ("instr", "PUSH", "= 5"))
        self.assertEqual(parse_line("DB = 5"),
                         ("data", "DB", ("=", "5")))


class TestParseInstr(unittest.TestCase):
    """Инструкции (SPEC, раздел 5)."""

    # @method test_instr_with_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Опкоды с полем imm64: операнд обязателен и остаётся
    # @does  текстом — имя может быть ссылкой вперёд, значение подставит
    # @does  проход 2.
    def test_instr_with_operand(self):
        self.assertEqual(parse_line("PUSH 5"), ("instr", "PUSH", "5"))
        self.assertEqual(parse_line("PUSH -0x10"),
                         ("instr", "PUSH", "-0x10"))
        self.assertEqual(parse_line("PUSH 'A'"), ("instr", "PUSH", "'A'"))
        self.assertEqual(parse_line("JMP loop"), ("instr", "JMP", "loop"))
        self.assertEqual(parse_line("CALL  entry"),
                         ("instr", "CALL", "entry"))
        self.assertEqual(parse_line("HALT 0"), ("instr", "HALT", "0"))
        self.assertEqual(parse_line("SYS 1"), ("instr", "SYS", "1"))
        self.assertEqual(parse_line("PICK 0x1F"), ("instr", "PICK", "0x1F"))
        self.assertEqual(parse_line("PUSH 5 6"),
                         ("instr", "PUSH", "5 6"))

    # @method test_instr_without_operand() -> None
    # @in    нет
    # @out   нет
    # @does  Опкоды без imm64: операнд запрещён, запись с None.
    def test_instr_without_operand(self):
        self.assertEqual(parse_line("NOP"), ("instr", "NOP", None))
        self.assertEqual(parse_line("RET"), ("instr", "RET", None))
        self.assertEqual(parse_line("ADD"), ("instr", "ADD", None))
        self.assertEqual(parse_line("\tSWAP  "), ("instr", "SWAP", None))

    # @method test_instr_operand_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Нет операнда у опкода с imm64; лишний операнд у остальных.
    def test_instr_operand_errors(self):
        self.assertEqual(parse_line("PUSH"),
                         ("error", "нет операнда у PUSH"))
        self.assertEqual(parse_line("HALT"),
                         ("error", "нет операнда у HALT"))
        self.assertEqual(parse_line("SYS"), ("error", "нет операнда у SYS"))
        self.assertEqual(parse_line("NOP 0"),
                         ("error", "лишний операнд у NOP"))
        self.assertEqual(parse_line("RET x"),
                         ("error", "лишний операнд у RET"))
        self.assertEqual(parse_line("ADD 1 2"),
                         ("error", "лишний операнд у ADD"))

    # @method test_instr_unknown_mnemonic() -> None
    # @in    нет
    # @out   нет
    # @does  Строчная и неизвестная мнемоника — «неизвестная мнемоника
    # @does  X» с первым словом строки.
    def test_instr_unknown_mnemonic(self):
        self.assertEqual(parse_line("push 5"),
                         ("error", "неизвестная мнемоника push"))
        self.assertEqual(parse_line("FOO 5"),
                         ("error", "неизвестная мнемоника FOO"))
        self.assertEqual(parse_line("123"),
                         ("error", "неизвестная мнемоника 123"))
        self.assertEqual(parse_line("abc def"),
                         ("error", "неизвестная мнемоника abc"))


class TestParseData(unittest.TestCase):
    """Директивы данных DB, DW, DS, DZ (SPEC, раздел 6)."""

    # @method test_db_dw_args() -> None
    # @in    нет
    # @out   нет
    # @does  DB/DW: аргументы — слова (тексты), значения литералов
    # @does  и имён подставит проход 2; запятая не разделитель.
    def test_db_dw_args(self):
        self.assertEqual(parse_line("DB 1"), ("data", "DB", ("1",)))
        self.assertEqual(parse_line("DB 1 2 3"),
                         ("data", "DB", ("1", "2", "3")))
        self.assertEqual(parse_line("DB x, y"),
                         ("data", "DB", ("x,", "y")))
        self.assertEqual(parse_line("DW 1 0x40 'A'"),
                         ("data", "DW", ("1", "0x40", "'A'")))

    # @method test_db_dw_empty() -> None
    # @in    нет
    # @out   нет
    # @does  DB и DW без аргументов — «пустая директива X».
    def test_db_dw_empty(self):
        self.assertEqual(parse_line("DB"), ("error", "пустая директива DB"))
        self.assertEqual(parse_line("DW"), ("error", "пустая директива DW"))

    # @method test_ds_dz_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  DS/DZ: один строковый литерал в байтах UTF-8, escape и
    # @does  пробелы внутри значимы; DZ добавляет байт 0x00.
    def test_ds_dz_bytes(self):
        self.assertEqual(parse_line('DS "abc"'), ("data", "DS", b"abc"))
        self.assertEqual(parse_line('DS ""'), ("data", "DS", b""))
        self.assertEqual(parse_line('DS "a b"'), ("data", "DS", b"a b"))
        self.assertEqual(parse_line('DS "Привет"'),
                         ("data", "DS", "Привет".encode("utf-8")))
        self.assertEqual(parse_line('DS "a\\nb"'),
                         ("data", "DS", b"a\nb"))
        self.assertEqual(parse_line('DZ "Hi"'),
                         ("data", "DZ", b"Hi\x00"))
        self.assertEqual(parse_line('DZ ""'), ("data", "DZ", b"\x00"))

    # @method test_ds_dz_bad() -> None
    # @in    нет
    # @out   нет
    # @does  DS/DZ без литерала, с лишним текстом или с незакрытой
    # @does  кавычкой — «плохой строковый литерал»; строчная директива —
    # @does  «неизвестная мнемоника».
    def test_ds_dz_bad(self):
        for line in ("DS", "DS abc", 'DS "a" "b"', 'DS "a', 'DS "a;b',
                     "DZ 5"):
            self.assertEqual(parse_line(line),
                             ("error", "плохой строковый литерал"), line)
        self.assertEqual(parse_line("db 1"),
                         ("error", "неизвестная мнемоника db"))


class TestParseComments(unittest.TestCase):
    """Комментарии и значимые пробелы (SPEC, раздел 2)."""

    # @method test_comment_after_code() -> None
    # @in    нет
    # @out   нет
    # @does  Комментарий после оператора отбрасывается; «;» вплотную
    # @does  к операнду и внутри кавычек — не комментарий.
    def test_comment_after_code(self):
        self.assertEqual(parse_line("PUSH 5 ; код"),
                         ("instr", "PUSH", "5"))
        self.assertEqual(parse_line("PUSH 5;код"),
                         ("instr", "PUSH", "5"))
        self.assertEqual(parse_line('DS "a;b"'), ("data", "DS", b"a;b"))
        self.assertEqual(parse_line("DB ';' 65"),
                         ("data", "DB", ("';'", "65")))
        self.assertEqual(parse_line("PUSH ';' ; c"),
                         ("instr", "PUSH", "';'"))
        self.assertEqual(parse_line("x = 5 ; константа"),
                         ("const", "x", 5))
        self.assertEqual(parse_line("foo: ; метка"), ("label", "foo"))
        self.assertEqual(parse_line("  RET ; выйти"),
                         ("instr", "RET", None))

    # @method test_edge_spaces() -> None
    # @in    нет
    # @out   нет
    # @does  Пробелы и табуляции по краям и между словами не мешают
    # @does  всем видам записей.
    def test_edge_spaces(self):
        self.assertEqual(parse_line("  PUSH 5  "), ("instr", "PUSH", "5"))
        self.assertEqual(parse_line("\tPUSH\t5\t"), ("instr", "PUSH", "5"))
        self.assertEqual(parse_line("  x = 5  "), ("const", "x", 5))
        self.assertEqual(parse_line("  foo:  "), ("label", "foo"))
        self.assertEqual(parse_line("  DB 1  "), ("data", "DB", ("1",)))


if __name__ == "__main__":
    unittest.main()
