# @uadro
# @file    tests/test_uasm_encode.py
# @layer   T0
# @branch  t0.uasm.encode
# @desc    Тесты кирпичей кодирования значений: слово с оборачиванием
# @desc    отрицательных, слово little-endian, байт DB, разрешение
# @desc    операнда — литерал или имя (SPEC/L2-UASM.txt, разделы 4-6).

"""Тесты кирпичей кодирования значений (tools/uasm_encode.py).

to_word, word_le, byte_of, resolve_value. Кодирование записей целиком —
tests/test_uasm_encode_rec.py.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.uasm_encode import byte_of, resolve_value, to_word, word_le

WORD_MOD = 1 << 64
MIN_LITERAL = -(1 << 63)
MAX_LITERAL = (1 << 64) - 1


class TestToWord(unittest.TestCase):
    """Слово 0..2^64-1; отрицательные оборачиваются (SPEC, раздел 4)."""

    # @method test_word_in_range() -> None
    # @in    нет
    # @out   нет
    # @does  Значения 0..2^64-1 переходят в слово без изменений.
    def test_word_in_range(self):
        self.assertEqual(to_word(0), 0)
        self.assertEqual(to_word(5), 5)
        self.assertEqual(to_word(MAX_LITERAL), MAX_LITERAL)

    # @method test_word_negative_wraps() -> None
    # @in    нет
    # @out   нет
    # @does  Отрицательные значения оборачиваются по модулю 2^64: -1 —
    # @does  в 2^64-1, -2 — в 2^64-2, нижняя граница литерала -2^63 —
    # @does  в 2^63.
    def test_word_negative_wraps(self):
        self.assertEqual(to_word(-1), WORD_MOD - 1)
        self.assertEqual(to_word(-2), WORD_MOD - 2)
        self.assertEqual(to_word(MIN_LITERAL), 1 << 63)

    # @method test_word_over_module() -> None
    # @in    нет
    # @out   нет
    # @does  Значения от 2^64 и выше сворачиваются по модулю 2^64.
    def test_word_over_module(self):
        self.assertEqual(to_word(WORD_MOD), 0)
        self.assertEqual(to_word(WORD_MOD + 7), 7)


class TestWordLe(unittest.TestCase):
    """Восемь байтов little-endian (SPEC, разделы 5-6)."""

    # @method test_word_le_small() -> None
    # @in    нет
    # @out   нет
    # @does  Младший байт значения — первый; ноль даёт восемь нулевых
    # @does  байтов.
    def test_word_le_small(self):
        self.assertEqual(word_le(0), b"\x00" * 8)
        self.assertEqual(word_le(1), b"\x01" + b"\x00" * 7)
        self.assertEqual(word_le(0x0A), b"\x0a" + b"\x00" * 7)

    # @method test_word_le_known() -> None
    # @in    нет
    # @out   нет
    # @does  Известное слово 0x1234567890ABCDEF даёт байты EFCDAB9078563412
    # @does  (младший байт первым).
    def test_word_le_known(self):
        self.assertEqual(word_le(0x1234567890ABCDEF),
                         bytes.fromhex("EFCDAB9078563412"))

    # @method test_word_le_negative() -> None
    # @in    нет
    # @out   нет
    # @does  Отрицательное значение сначала оборачивается: -1 даёт восемь
    # @does  байтов FF, -2 — FE и семь FF.
    def test_word_le_negative(self):
        self.assertEqual(word_le(-1), b"\xff" * 8)
        self.assertEqual(word_le(-2), b"\xfe" + b"\xff" * 7)


class TestByteOf(unittest.TestCase):
    """Байт директивы DB: диапазон 0..255 (SPEC, раздел 6)."""

    # @method test_byte_in_range() -> None
    # @in    нет
    # @out   нет
    # @does  Значения 0..255 проходят в байт без изменений.
    def test_byte_in_range(self):
        self.assertEqual(byte_of(0), 0)
        self.assertEqual(byte_of(65), 65)
        self.assertEqual(byte_of(255), 255)

    # @method test_byte_out_of_range() -> None
    # @in    нет
    # @out   нет
    # @does  Значения вне 0..255 дают None — сигнал ошибки «байт вне
    # @does  диапазона».
    def test_byte_out_of_range(self):
        self.assertIsNone(byte_of(-1))
        self.assertIsNone(byte_of(256))
        self.assertIsNone(byte_of(MAX_LITERAL))


class TestResolveValue(unittest.TestCase):
    """Операнд: числовой литерал или имя (SPEC, разделы 5-6)."""

    # @method test_resolve_literal_forms() -> None
    # @in    нет
    # @out   нет
    # @does  Все числовые формы раздела 4: десятичная, шестнадцатеричная,
    # @does  двоичная, символьная с escape и минус перед любой формой.
    def test_resolve_literal_forms(self):
        cases = [("5", 5), ("0x10", 16), ("0b101", 5), ("'A'", 65),
                 ("'\\n'", 10), ("-7", -7), ("-0x10", -16), ("-'A'", -65)]
        for text, value in cases:
            with self.subTest(text=text):
                self.assertEqual(resolve_value(text, {}), (value, None))

    # @method test_resolve_literal_bounds() -> None
    # @in    нет
    # @out   нет
    # @does  Границы диапазона литералов -2^63 и 2^64-1 разрешаются.
    def test_resolve_literal_bounds(self):
        self.assertEqual(resolve_value(str(MAX_LITERAL), {}),
                         (MAX_LITERAL, None))
        self.assertEqual(resolve_value(str(MIN_LITERAL), {}),
                         (MIN_LITERAL, None))

    # @method test_resolve_literal_out_of_range() -> None
    # @in    нет
    # @out   нет
    # @does  Числовой литерал вне -2^63..2^64-1 — ошибка «литерал вне
    # @does  диапазона».
    def test_resolve_literal_out_of_range(self):
        self.assertEqual(resolve_value(str(MAX_LITERAL + 1), {}),
                         (None, "литерал вне диапазона"))
        self.assertEqual(resolve_value(str(MIN_LITERAL - 1), {}),
                         (None, "литерал вне диапазона"))

    # @method test_resolve_names() -> None
    # @in    нет
    # @out   нет
    # @does  Имя берёт значение из таблицы символов как есть: ноль —
    # @does  законное значение, отрицательное значение не оборачивается
    # @does  на этом шаге.
    def test_resolve_names(self):
        symbols = {"start": 9, "zero": 0, "neg": -1}
        self.assertEqual(resolve_value("start", symbols), (9, None))
        self.assertEqual(resolve_value("zero", symbols), (0, None))
        self.assertEqual(resolve_value("neg", symbols), (-1, None))

    # @method test_resolve_unknown_name() -> None
    # @in    нет
    # @out   нет
    # @does  Имя, которого нет в таблице символов, — ошибка «неизвестное
    # @does  имя X».
    def test_resolve_unknown_name(self):
        self.assertEqual(resolve_value("zz", {}),
                         (None, "неизвестное имя zz"))

    # @method test_resolve_bad_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Текст — не числовой литерал и не имя: «плохой литерал X»;
    # @does  пустой текст — «плохой литерал» без X.
    def test_resolve_bad_literal(self):
        for text in ["5x", "+5", "'ab'", "0x", "-", ""]:
            with self.subTest(text=text):
                if text:
                    error = "плохой литерал " + text
                else:
                    error = "плохой литерал"
                self.assertEqual(resolve_value(text, {}), (None, error))


if __name__ == "__main__":
    unittest.main()
