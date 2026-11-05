# @uadro
# @file    tests/test_ubrick_parse.py
# @layer   T0
# @branch  t0.ubrick.parse
# @desc    Тесты разбора uBrick: кирпичи строк, имён и строковых
# @desc    литералов; записи успешного разбора — определения, var,
# @desc    text, элементы тел (SPEC/L3-UBRICK.txt v0.2, разделы 3 и 6).

"""Тесты записей ветви t0.ubrick.parse (tools/ubrick_parse.py).

Записи: ("word", имя, тело), ("var", имя), ("text", имя, байты);
элементы тела: ("word", слово), ("lit", значение), ("construct",
слово). Тексты ошибок раздела 8 — в tests/test_ubrick_parse_errors.py.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.ubrick_parse import (
    is_word_name,
    parse_ubrk,
    split_lines,
    take_string,
    wrap_error,
)


class TestLines(unittest.TestCase):
    """Деление текста на строки, формат ошибок, правило имён."""

    # @method test_split_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой текст — одна пустая строка; LF делит; концевые CR
    # @does  снимаются; концевой LF даёт пустую последнюю строку.
    def test_split_lines(self):
        self.assertEqual(split_lines(""), [""])
        self.assertEqual(split_lines("a\nb"), ["a", "b"])
        self.assertEqual(split_lines("a\r\nb"), ["a", "b"])
        self.assertEqual(split_lines("a\n"), ["a", ""])

    # @method test_wrap_error() -> None
    # @in    нет
    # @out   нет
    # @does  Формат «uBrick: строка N: текст»; нумерация с 1.
    def test_wrap_error(self):
        self.assertEqual(wrap_error(7, "x"), "uBrick: строка 7: x")
        self.assertEqual(wrap_error(1, "слово main обязательно"),
                         "uBrick: строка 1: слово main обязательно")

    # @method test_is_word_name() -> None
    # @in    нет
    # @out   нет
    # @does  Имя — строчная латиница и цифры; заглавные, дефисы,
    # @does  подчёркивания, не-латиница и цифра в начале запрещены;
    # @does  точное имя var занято, но префикс var — законное имя.
    def test_is_word_name(self):
        for name in ("a", "main", "x1", "abc123", "lts", "var2x"):
            self.assertTrue(is_word_name(name), name)
        for name in ("", "1a", "Foo", "bad-name", "_x", "a_b", "нот",
                     "A", "var!"):
            self.assertFalse(is_word_name(name), name)


class TestTakeString(unittest.TestCase):
    """Один строковый литерал в начале текста (SPEC/L2-UASM.txt, 4)."""

    # @method test_valid_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Байты UTF-8, escape, пробелы внутри, хвост после кавычки;
    # @does  пустой литерал и пробелы после кавычки дают пустой хвост.
    def test_valid_literals(self):
        self.assertEqual(take_string('"ab" c'), (b"ab", "c"))
        self.assertEqual(take_string('"a b"'), (b"a b", ""))
        self.assertEqual(take_string('"a\\nb"'), (b"a\nb", ""))
        self.assertEqual(take_string('"a\\\\"'), (b"a\\", ""))
        self.assertEqual(take_string('"Ж"'), ("Ж".encode("utf-8"), ""))
        self.assertEqual(take_string('""'), (b"", ""))
        self.assertEqual(take_string('"a"   '), (b"a", ""))

    # @method test_invalid_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Без кавычки в начале, незакрытая кавычка и неизвестный
    # @does  escape дают None.
    def test_invalid_literals(self):
        self.assertIsNone(take_string("abc"))
        self.assertIsNone(take_string('"abc'))
        self.assertIsNone(take_string('"a\\q"'))
        self.assertIsNone(take_string(""))


class TestRecordsOk(unittest.TestCase):
    """Записи успешного разбора (SPEC, разделы 3 и 6)."""

    # @method test_full_program() -> None
    # @in    нет
    # @out   нет
    # @does  var, text и слово с элементами всех видов: ссылки на text
    # @does  и var, производное слово, литерал, примитив, псевдоним.
    def test_full_program(self):
        records, error = parse_ubrk(
            'var x\n'
            'text msg "Hello, world!"\n'
            ': main msg prints 42 x STORE64 BYE ;\n')
        self.assertIsNone(error)
        self.assertEqual(records, [
            ("var", "x"),
            ("text", "msg", b"Hello, world!"),
            ("word", "main", (("word", "msg"), ("word", "prints"),
                              ("lit", 42), ("word", "x"),
                              ("word", "STORE64"), ("word", "BYE"))),
        ])

    # @method test_multiline_definition() -> None
    # @in    нет
    # @out   нет
    # @does  Тело на нескольких строках; «;» в хвосте строки
    # @does  закрывает определение, комментарий после него игнорируется.
    def test_multiline_definition(self):
        records, error = parse_ubrk(
            ": main\n"
            "DUP 0 EQ\n"
            "IF DROP EXIT THEN\n"
            "BYE ; хвост\n")
        self.assertIsNone(error)
        self.assertEqual(records, [
            ("word", "main", (("word", "DUP"), ("lit", 0),
                              ("word", "EQ"), ("construct", "IF"),
                              ("word", "DROP"), ("word", "EXIT"),
                              ("construct", "THEN"), ("word", "BYE"))),
        ])

    # @method test_nested_constructs() -> None
    # @in    нет
    # @out   нет
    # @does  Вложенные IF/ELSE/THEN: закрывающие слова связываются
    # @does  с ближайшей незакрытой конструкцией.
    def test_nested_constructs(self):
        records, error = parse_ubrk(
            ": main IF 1 ELSE IF 2 ELSE 3 THEN THEN ;")
        self.assertIsNone(error)
        self.assertEqual(records, [
            ("word", "main", (
                ("construct", "IF"), ("lit", 1), ("construct", "ELSE"),
                ("construct", "IF"), ("lit", 2), ("construct", "ELSE"),
                ("lit", 3), ("construct", "THEN"),
                ("construct", "THEN"))),
        ])

    # @method test_forward_references() -> None
    # @in    нет
    # @out   нет
    # @does  Ссылки вперёд разрешены: имя читается до проверки ссылок,
    # @does  которая идёт после разбора всего исходника.
    def test_forward_references(self):
        records, error = parse_ubrk(
            ": main later 65 EMIT ;\n"
            ": later 1 SUB ;\n")
        self.assertIsNone(error)
        self.assertEqual(records, [
            ("word", "main", (("word", "later"), ("lit", 65),
                              ("word", "EMIT"))),
            ("word", "later", (("lit", 1), ("word", "SUB"))),
        ])

    # @method test_literal_forms() -> None
    # @in    нет
    # @out   нет
    # @does  Десятичная, шестнадцатеричная, двоичная, символьная
    # @does  формы и минус (SPEC/L2-UASM.txt, раздел 4).
    def test_literal_forms(self):
        records, error = parse_ubrk(
            ": main 123 0x1F 0b101 'A' -123 ;")
        self.assertIsNone(error)
        self.assertEqual(records, [
            ("word", "main", (("lit", 123), ("lit", 31), ("lit", 5),
                              ("lit", 65), ("lit", -123))),
        ])

    # @method test_name_on_next_line() -> None
    # @in    нет
    # @out   нет
    # @does  Перенос строки — разделитель слов: имя определения может
    # @does  стоять на строке после «:», между ними — комментарии.
    def test_name_on_next_line(self):
        records, error = parse_ubrk(":\n; ждём имя\nmain 1 ;")
        self.assertIsNone(error)
        self.assertEqual(records, [("word", "main", (("lit", 1),))])

    # @method test_empty_body() -> None
    # @in    нет
    # @out   нет
    # @does  Пустое тело допустимо: «: имя ;» — слово без элементов.
    def test_empty_body(self):
        records, error = parse_ubrk(": main ;")
        self.assertIsNone(error)
        self.assertEqual(records, [("word", "main", ())])

    # @method test_comment_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Строка с «;» в начале — комментарий на любом уровне:
    # @does  верхний уровень, между операторами и внутри тела.
    def test_comment_lines(self):
        records, error = parse_ubrk(
            "; шапка\n"
            "\n"
            "var x\n"
            "; между операторами\n"
            ": main\n"
            "; внутри тела\n"
            "x LOAD64\n"
            "DROP ; закрывающий хвост\n")
        self.assertIsNone(error)
        self.assertEqual(records, [
            ("var", "x"),
            ("word", "main", (("word", "x"), ("word", "LOAD64"),
                              ("word", "DROP"))),
        ])

    # @method test_crlf_and_semicolon_in_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Текст CRLF разбирается как LF; «;» в литералах в кавычках
    # @does  (символьный и строковый) не обрезает строку.
    def test_crlf_and_semicolon_in_literal(self):
        records, error = parse_ubrk(
            'text m "a;b"\r\n: main \';\' EMIT ;\r\n')
        self.assertIsNone(error)
        self.assertEqual(records, [
            ("text", "m", b"a;b"),
            ("word", "main", (("lit", 59), ("word", "EMIT"))),
        ])


if __name__ == "__main__":
    unittest.main()
