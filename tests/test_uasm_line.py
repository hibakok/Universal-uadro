# @uadro
# @file    tests/test_uasm_line.py
# @layer   T0
# @branch  t0.uasm.line
# @desc    Тесты кирпичей подготовки строки uAsm: поиск символа вне
# @desc    кавычек, комментарий, очистка краёв, знак «=», первое слово,
# @desc    разбиение на слова (SPEC/L2-UASM.txt, разделы 2 и 7).

"""Тесты кирпичей подготовки строки (tools/uasm_line.py).

find_outside_quotes, strip_comment, clean_line, find_eq, split_first,
split_words. Разбор целой строки parse_line — tests/test_uasm_line_parse.py.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.uasm_line import (clean_line, find_eq, find_outside_quotes,
                             split_first, split_words, strip_comment)


class TestFindOutsideQuotes(unittest.TestCase):
    """Поиск символа вне литералов в кавычках (SPEC, раздел 2)."""

    # @method test_find_plain() -> None
    # @in    нет
    # @out   нет
    # @does  Символ без кавычек; находится первое вхождение; отсутствие
    # @does  вхождения даёт -1.
    def test_find_plain(self):
        self.assertEqual(find_outside_quotes("PUSH 5", " "), 4)
        self.assertEqual(find_outside_quotes("a=b=c", "="), 1)
        self.assertEqual(find_outside_quotes("abc", ";"), -1)

    # @method test_find_skips_quotes() -> None
    # @in    нет
    # @out   нет
    # @does  Символ внутри двойных и одинарных кавычек пропускается;
    # @does  находится первое вхождение вне кавычек.
    def test_find_skips_quotes(self):
        self.assertEqual(find_outside_quotes('DS "a=b"', "="), -1)
        self.assertEqual(find_outside_quotes("DB ';'", ";"), -1)
        self.assertEqual(find_outside_quotes("x '=' = 5", "="), 6)

    # @method test_find_escape_aware() -> None
    # @in    нет
    # @out   нет
    # @does  Escape-кавычка не закрывает литерал: символ после неё —
    # @does  внутри литерала и пропускается.
    def test_find_escape_aware(self):
        self.assertEqual(find_outside_quotes('"a\\"b"', ";"), -1)
        self.assertEqual(find_outside_quotes("'\\''", "'"), -1)


class TestStripComment(unittest.TestCase):
    """Комментарий «;» вне кавычек (SPEC, раздел 2)."""

    # @method test_strip_cuts_comment() -> None
    # @in    нет
    # @out   нет
    # @does  Хвост от «;» до конца строки отбрасывается, крайние пробелы
    # @does  до «;» остаются.
    def test_strip_cuts_comment(self):
        self.assertEqual(strip_comment("PUSH 5 ; код"), "PUSH 5 ")
        self.assertEqual(strip_comment("PUSH 5;код"), "PUSH 5")
        self.assertEqual(strip_comment("A ; B ; C"), "A ")
        self.assertEqual(strip_comment("; c"), "")

    # @method test_strip_keeps_quoted() -> None
    # @in    нет
    # @out   нет
    # @does  «;» внутри "..." и '...' не начинается комментарий.
    def test_strip_keeps_quoted(self):
        self.assertEqual(strip_comment('DS "a;b"'), 'DS "a;b"')
        self.assertEqual(strip_comment("DB ';' 65"), "DB ';' 65")
        self.assertEqual(strip_comment('DS "a\\"b" ; x'),
                         'DS "a\\"b" ')

    # @method test_strip_no_comment() -> None
    # @in    нет
    # @out   нет
    # @does  Строка без «;» вне кавычек возвращается как есть.
    def test_strip_no_comment(self):
        self.assertEqual(strip_comment("RET"), "RET")
        self.assertEqual(strip_comment('"semi ; inside"'), '"semi ; inside"')


class TestCleanLine(unittest.TestCase):
    """Комментарий плюс крайние пробелы и табуляции (SPEC, раздел 2)."""

    # @method test_clean_variants() -> None
    # @in    нет
    # @out   нет
    # @does  Комментарий и крайние пробелы/табуляции удаляются; строка
    # @does  из одних пробелов и комментарий дают пустую строку;
    # @does  пробелы внутри литералов сохраняются.
    def test_clean_variants(self):
        self.assertEqual(clean_line("  PUSH 5 ; c "), "PUSH 5")
        self.assertEqual(clean_line("\t; c\t"), "")
        self.assertEqual(clean_line("   "), "")
        self.assertEqual(clean_line('DS "a b"'), 'DS "a b"')
        self.assertEqual(clean_line("no comment"), "no comment")


class TestFindEq(unittest.TestCase):
    """Знак «=» константы вне кавычек (SPEC, раздел 7, шаг 3)."""

    # @method test_eq_positions() -> None
    # @in    нет
    # @out   нет
    # @does  Первый «=» без пробелов и с ними; отсутствие «=» даёт -1;
    # @does  «=» внутри кавычек не считается.
    def test_eq_positions(self):
        self.assertEqual(find_eq("x = 5"), 2)
        self.assertEqual(find_eq("x=5"), 1)
        self.assertEqual(find_eq("a=b=c"), 1)
        self.assertEqual(find_eq("abc"), -1)
        self.assertEqual(find_eq('DS "a=b"'), -1)


class TestSplitFirst(unittest.TestCase):
    """Первое слово и остаток строки (SPEC, раздел 2)."""

    # @method test_split_first_variants() -> None
    # @in    нет
    # @out   нет
    # @does  Слово до пробела или табуляции; остаток без крайних
    # @does  пробелов слева, пробелы внутри остатка значимы.
    def test_split_first_variants(self):
        self.assertEqual(split_first("PUSH 5"), ("PUSH", "5"))
        self.assertEqual(split_first("PUSH\t5"), ("PUSH", "5"))
        self.assertEqual(split_first("PUSH    5 6"), ("PUSH", "5 6"))
        self.assertEqual(split_first("NOP"), ("NOP", ""))
        self.assertEqual(split_first('DS "a b"'), ("DS", '"a b"'))
        self.assertEqual(split_first("x = 5"), ("x", "= 5"))


class TestSplitWords(unittest.TestCase):
    """Разбиение на слова по пробелам и табуляциям (SPEC, раздел 2)."""

    # @method test_split_words_variants() -> None
    # @in    нет
    # @out   нет
    # @does  Слова разделяются последовательностями пробелов и
    # @does  табуляций; пустой текст и одни пробелы дают пустой список.
    def test_split_words_variants(self):
        self.assertEqual(split_words(""), [])
        self.assertEqual(split_words("   "), [])
        self.assertEqual(split_words("1 2 3"), ["1", "2", "3"])
        self.assertEqual(split_words("  1\t\t2 "), ["1", "2"])
        self.assertEqual(split_words("'a' x -0x10"), ["'a'", "x", "-0x10"])


if __name__ == "__main__":
    unittest.main()
