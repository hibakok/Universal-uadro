# @uadro
# @file    tests/test_uasm_lex.py
# @layer   T0
# @branch  t0.uasm.lex
# @desc    Тесты лексических кирпичей uAsm: числовые литералы всех форм
# @desc    и минус, диапазон литералов, имена, строковые литералы и
# @desc    escape (SPEC/L2-UASM.txt, разделы 3-4).

"""Тесты ветви t0.uasm.lex (tools/uasm_lex.py).

Каждая форма литерала и каждая граница распознавания покрыты отдельным
случаем; все некорректные формы обязаны давать None.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools import uasm_lex as lex


class TestParseDec(unittest.TestCase):
    """Десятичные литералы (SPEC, раздел 4)."""

    # @method test_dec_values() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль, обычные числа, ведущие нули.
    def test_dec_values(self):
        self.assertEqual(lex.parse_dec("0"), 0)
        self.assertEqual(lex.parse_dec("123"), 123)
        self.assertEqual(lex.parse_dec("007"), 7)

    # @method test_dec_rejects() -> None
    # @in    нет
    # @out   нет
    # @does  Не-цифры, пустая строка, знак и другие формы дают None.
    def test_dec_rejects(self):
        for text in ("", "12a", "a1", "-1", "1_0", "0x1"):
            self.assertIsNone(lex.parse_dec(text), text)


class TestParseHex(unittest.TestCase):
    """Шестнадцатеричные литералы (SPEC, раздел 4)."""

    # @method test_hex_values() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль, малые и большие значения, регистр цифр.
    def test_hex_values(self):
        self.assertEqual(lex.parse_hex("0x0"), 0)
        self.assertEqual(lex.parse_hex("0x1F"), 31)
        self.assertEqual(lex.parse_hex("0xff"), 255)
        self.assertEqual(lex.parse_hex("0xAbCdEf"), 11259375)

    # @method test_hex_rejects() -> None
    # @in    нет
    # @out   нет
    # @does  Нет префикса или цифр, заглавный префикс, чужие цифры.
    def test_hex_rejects(self):
        for text in ("", "0x", "0X1F", "1F", "ff", "0xG", "0b11"):
            self.assertIsNone(lex.parse_hex(text), text)


class TestParseBin(unittest.TestCase):
    """Двоичные литералы (SPEC, раздел 4)."""

    # @method test_bin_values() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль, единица, многобитовые значения.
    def test_bin_values(self):
        self.assertEqual(lex.parse_bin("0b0"), 0)
        self.assertEqual(lex.parse_bin("0b1"), 1)
        self.assertEqual(lex.parse_bin("0b101"), 5)
        self.assertEqual(lex.parse_bin("0b11111111"), 255)

    # @method test_bin_rejects() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой префикс, заглавный префикс, чужие цифры.
    def test_bin_rejects(self):
        for text in ("", "0b", "0B1", "101", "0b12"):
            self.assertIsNone(lex.parse_bin(text), text)


class TestParseChar(unittest.TestCase):
    """Символьные литералы (SPEC, раздел 4)."""

    # @method test_char_values() -> None
    # @in    нет
    # @out   нет
    # @does  Обычные символы, пробел, цифра, кавычка и все escape.
    def test_char_values(self):
        self.assertEqual(lex.parse_char("'A'"), 65)
        self.assertEqual(lex.parse_char("'z'"), 122)
        self.assertEqual(lex.parse_char("' '"), 32)
        self.assertEqual(lex.parse_char("'0'"), 48)
        self.assertEqual(lex.parse_char("'\"'"), 34)
        self.assertEqual(lex.parse_char("'\\n'"), 10)
        self.assertEqual(lex.parse_char("'\\r'"), 13)
        self.assertEqual(lex.parse_char("'\\t'"), 9)
        self.assertEqual(lex.parse_char("'\\\\'"), 92)
        self.assertEqual(lex.parse_char("'\\''"), 39)
        self.assertEqual(lex.parse_char("'\\0'"), 0)

    # @method test_char_rejects() -> None
    # @in    нет
    # @out   нет
    # @does  Пустые, длинные, незакрытые, неизвестный escape.
    def test_char_rejects(self):
        for text in ("", "A", "''", "'ab'", "'a", "a'", "'\\q'", "'\\"):
            self.assertIsNone(lex.parse_char(text), text)


class TestParseNumber(unittest.TestCase):
    """Полный числовой литерал с минусом (SPEC, раздел 4)."""

    # @method test_number_values() -> None
    # @in    нет
    # @out   нет
    # @does  Все формы без знака и с минусом, минус-ноль.
    def test_number_values(self):
        self.assertEqual(lex.parse_number("42"), 42)
        self.assertEqual(lex.parse_number("-42"), -42)
        self.assertEqual(lex.parse_number("0x10"), 16)
        self.assertEqual(lex.parse_number("-0x10"), -16)
        self.assertEqual(lex.parse_number("0b11"), 3)
        self.assertEqual(lex.parse_number("-0b11"), -3)
        self.assertEqual(lex.parse_number("'A'"), 65)
        self.assertEqual(lex.parse_number("-'A'"), -65)
        self.assertEqual(lex.parse_number("-0"), 0)

    # @method test_number_rejects() -> None
    # @in    нет
    # @out   нет
    # @does  Одинокий и двойной минус, мусор, пустые префиксы.
    def test_number_rejects(self):
        for text in ("", "-", "--1", "1+2", "- 1", "0x", "-0b", "abc"):
            self.assertIsNone(lex.parse_number(text), text)


class TestLiteralRange(unittest.TestCase):
    """Диапазон числовых литералов -2^63 .. 2^64-1 (SPEC, раздел 4)."""

    # @method test_range_inside() -> None
    # @in    нет
    # @out   нет
    # @does  Границы и окрестность нуля внутри диапазона.
    def test_range_inside(self):
        for value in (0, 1, -1, -(1 << 63), (1 << 64) - 1):
            self.assertTrue(lex.in_literal_range(value), value)

    # @method test_range_outside() -> None
    # @in    нет
    # @out   нет
    # @does  Значения за обеими границами вне диапазона.
    def test_range_outside(self):
        for value in (-(1 << 63) - 1, 1 << 64, 1 << 70):
            self.assertFalse(lex.in_literal_range(value), value)


class TestIsName(unittest.TestCase):
    """Имена [A-Za-z_][A-Za-z0-9_]* (SPEC, раздел 3)."""

    # @method test_name_accepts() -> None
    # @in    нет
    # @out   нет
    # @does  Буква, подчёркивание, цифры внутри; строчные мнемоники —
    # @does  тоже допустимые имена.
    def test_name_accepts(self):
        for text in ("a", "A", "_", "_x", "x_1", "Loop1", "push"):
            self.assertTrue(lex.is_name(text), text)

    # @method test_name_rejects() -> None
    # @in    нет
    # @out   нет
    # @does  Пустое, цифра в начале, знак, пробел, не-ASCII.
    def test_name_rejects(self):
        for text in ("", "1a", "a-b", "a b", "метка", "a.b"):
            self.assertFalse(lex.is_name(text), text)


class TestParseString(unittest.TestCase):
    """Строковые литералы "..." с escape (SPEC, раздел 4)."""

    # @method test_string_values() -> None
    # @in    нет
    # @out   нет
    # @does  Пустая строка, символы, UTF-8, все escape, пробел внутри.
    def test_string_values(self):
        self.assertEqual(lex.parse_string('""'), b"")
        self.assertEqual(lex.parse_string('"a"'), b"a")
        self.assertEqual(lex.parse_string('"Привет"'),
                         "Привет".encode("utf-8"))
        self.assertEqual(lex.parse_string('"a b"'), b"a b")
        self.assertEqual(lex.parse_string('"a\\nb"'), b"a\nb")
        self.assertEqual(lex.parse_string('"\\t\\r"'), b"\t\r")
        self.assertEqual(lex.parse_string('"\\\\"'), b"\\")
        self.assertEqual(lex.parse_string('"\\""'), b'"')
        self.assertEqual(lex.parse_string('"\\0"'), b"\x00")
        self.assertEqual(lex.parse_string("\"'\""), b"'")

    # @method test_string_rejects() -> None
    # @in    нет
    # @out   нет
    # @does  Нет кавычек, незакрытая, лишнее после закрывающей,
    # @does  неизвестный escape.
    def test_string_rejects(self):
        for text in ("", '"', "abc", 'a"b"', '"a"b"', '"abc',
                     '"abc\\', '"a\\qb"', '"a" '):
            self.assertIsNone(lex.parse_string(text), text)


if __name__ == "__main__":
    unittest.main()
