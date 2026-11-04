# @uadro
# @file    tests/test_uasm_assemble.py
# @layer   T0
# @branch  t0.uasm.assemble
# @desc    Тесты сборки текста uAsm в образ: деление на строки, ошибки
# @desc    с номером строки, проходы 1 и 2, ссылки вперёд, метки и
# @desc    константы, пустой текст (SPEC/L2-UASM.txt, раздел 7).

"""Тесты ветви t0.uasm.assemble (tools/uasm_assemble.py).

Сборка текста в образ двумя проходами: адреса записей и таблица
символов прохода 1 (метка — адрес следующей записи, метка в конце
текста — адрес конца образа), кодирование прохода 2, ошибки «uAsm:
строка N: текст», ссылки вперёд, директивы данных, пустой текст —
пустой образ.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.uasm_assemble import (
    assemble, define_symbol, pass1, pass2, split_lines, wrap_error,
)
from tools.uasm_symbols import symbol_get, symbols_new
from tools.uvm_table import entry_by_mnemonic


# @method op(mnemonic) -> bytes
# @in    mnemonic: str — мнемоника опкода UVM
# @out   data: bytes — один байт опкода
# @does  Байт опкода по мнемонике — для золотых байтов тестов.
# @depends entry_by_mnemonic
def op(mnemonic):
    return bytes([entry_by_mnemonic(mnemonic)[0]])


# @method word(value) -> bytes
# @in    value: int — значение (литерал, имя или слово)
# @out   data: bytes — восемь байтов little-endian
# @does  Поле imm64 в золотых байтах тестов: слово с оборачиванием
# @does  отрицательных по модулю 2^64.
def word(value):
    return (value % (1 << 64)).to_bytes(8, "little")


class TestSplitLines(unittest.TestCase):
    """Деление текста на строки (SPEC, раздел 2)."""

    # @method test_empty_text() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой текст — одна пустая строка.
    def test_empty_text(self):
        self.assertEqual(split_lines(""), [""])

    # @method test_one_line_without_lf() -> None
    # @in    нет
    # @out   нет
    # @does  Текст без перевода строки — одна строка целиком.
    def test_one_line_without_lf(self):
        self.assertEqual(split_lines("PUSH 1"), ["PUSH 1"])

    # @method test_split_by_lf() -> None
    # @in    нет
    # @out   нет
    # @does  Деление по LF; концевой LF даёт пустую последнюю строку.
    def test_split_by_lf(self):
        self.assertEqual(split_lines("a\nb\nc"), ["a", "b", "c"])
        self.assertEqual(split_lines("a\n"), ["a", ""])

    # @method test_crlf_stripped() -> None
    # @in    нет
    # @out   нет
    # @does  Концевые CR снимаются: текст CRLF собирается как LF.
    def test_crlf_stripped(self):
        self.assertEqual(split_lines("a\r\nb"), ["a", "b"])


class TestWrapError(unittest.TestCase):
    """Сообщение об ошибке с номером строки (SPEC, раздел 7)."""

    # @method test_message_format() -> None
    # @in    нет
    # @out   нет
    # @does  Формат «uAsm: строка N: текст»; нумерация с 1.
    def test_message_format(self):
        self.assertEqual(wrap_error(7, "плохое имя"),
                         "uAsm: строка 7: плохое имя")
        self.assertEqual(wrap_error(1, "x"), "uAsm: строка 1: x")


class TestDefineSymbol(unittest.TestCase):
    """Определение символов прохода 1 (SPEC, разделы 3 и 7)."""

    # @method test_label_gets_addr() -> None
    # @in    нет
    # @out   нет
    # @does  Метка определяется адресом следующей записи.
    def test_label_gets_addr(self):
        table = symbols_new()
        self.assertIsNone(define_symbol(table, ("label", "a"), 5))
        self.assertEqual(symbol_get(table, "a"), 5)

    # @method test_const_gets_value() -> None
    # @in    нет
    # @out   нет
    # @does  Константа определяется своим значением.
    def test_const_gets_value(self):
        table = symbols_new()
        self.assertIsNone(define_symbol(table, ("const", "c", 9), 0))
        self.assertEqual(symbol_get(table, "c"), 9)

    # @method test_other_records_define_nothing() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция и директива данных символов не определяют.
    def test_other_records_define_nothing(self):
        table = symbols_new()
        self.assertIsNone(define_symbol(table, ("instr", "NOP", None), 0))
        self.assertIsNone(define_symbol(table, ("data", "DB", ("1",)), 0))
        self.assertEqual(table, {})

    # @method test_duplicate_is_error() -> None
    # @in    нет
    # @out   нет
    # @does  Второе определение имени — ошибка, значение сохраняется.
    def test_duplicate_is_error(self):
        table = symbols_new()
        define_symbol(table, ("label", "x"), 1)
        self.assertEqual(define_symbol(table, ("const", "x", 2), 3),
                         "повторное определение имени x")
        self.assertEqual(symbol_get(table, "x"), 1)


class TestPass1(unittest.TestCase):
    """Проход 1: записи, адреса, символы (SPEC, раздел 7)."""

    # @method test_blank_and_comment_lines_skip() -> None
    # @in    нет
    # @out   нет
    # @does  Пустые строки и комментарии не дают записей и символов.
    def test_blank_and_comment_lines_skip(self):
        items, symbols, error = pass1(["", "  ; комментарий", ""])
        self.assertEqual((items, symbols, error), ([], {}, None))

    # @method test_records_keep_line_numbers() -> None
    # @in    нет
    # @out   нет
    # @does  Записи несут номера исходных строк, а не свои позиции.
    def test_records_keep_line_numbers(self):
        items, _, error = pass1(["NOP", "", "PUSH 1"])
        self.assertIsNone(error)
        self.assertEqual(items, [(1, ("instr", "NOP", None)),
                                 (3, ("instr", "PUSH", "1"))])

    # @method test_label_addr_is_next_record_addr() -> None
    # @in    нет
    # @out   нет
    # @does  Метка получает адрес следующей записи: DB 1 2 (2 байта)
    # @does  -> метка 2; размеры даёт record_size.
    def test_label_addr_is_next_record_addr(self):
        _, symbols, error = pass1(["DB 1 2", "lbl:", "DW 3"])
        self.assertIsNone(error)
        self.assertEqual(symbol_get(symbols, "lbl"), 2)

    # @method test_label_at_end_is_image_end() -> None
    # @in    нет
    # @out   нет
    # @does  Метка в конце текста — адрес конца образа: HALT 0
    # @does  занимает 9 байтов.
    def test_label_at_end_is_image_end(self):
        _, symbols, error = pass1(["HALT 0", "fin:"])
        self.assertIsNone(error)
        self.assertEqual(symbol_get(symbols, "fin"), 9)

    # @method test_const_and_label_values() -> None
    # @in    нет
    # @out   нет
    # @does  Константа — значение литерала; метка до записи — 0.
    def test_const_and_label_values(self):
        _, symbols, error = pass1(["x = 5", "start:", "PUSH x"])
        self.assertIsNone(error)
        self.assertEqual(symbol_get(symbols, "x"), 5)
        self.assertEqual(symbol_get(symbols, "start"), 0)

    # @method test_parse_error_stops_pass() -> None
    # @in    нет
    # @out   нет
    # @does  Запись-ошибка прекращает проход с номером своей строки.
    def test_parse_error_stops_pass(self):
        triple = pass1(["NOP", "FOO"])
        self.assertEqual(triple, (None, None,
                         "uAsm: строка 2: неизвестная мнемоника FOO"))

    # @method test_duplicate_symbol_stops_pass() -> None
    # @in    нет
    # @out   нет
    # @does  Повторное определение имени — ошибка с номером строки.
    def test_duplicate_symbol_stops_pass(self):
        triple = pass1(["a:", "a:"])
        self.assertEqual(triple, (None, None,
                         "uAsm: строка 2: повторное определение имени a"))


class TestPass2(unittest.TestCase):
    """Проход 2: кодирование записей с подстановкой имён (SPEC, раздел 7)."""

    # @method test_encodes_with_symbols() -> None
    # @in    нет
    # @out   нет
    # @does  Записи кодируются в байты; метки и константы байтов
    # @does  не дают.
    def test_encodes_with_symbols(self):
        items, symbols, error = pass1(["n = 65", "l:", "PUSH n", "HALT 0"])
        self.assertIsNone(error)
        image, error = pass2(items, symbols)
        self.assertIsNone(error)
        self.assertEqual(image, op("PUSH") + word(65) + op("HALT") + word(0))

    # @method test_unknown_name_error() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестное имя обнаруживается в проходе 2 с номером
    # @does  строки записи.
    def test_unknown_name_error(self):
        items, symbols, _ = pass1(["PUSH q"])
        self.assertEqual(pass2(items, symbols),
                         (None, "uAsm: строка 1: неизвестное имя q"))

    # @method test_db_range_error() -> None
    # @in    нет
    # @out   нет
    # @does  Аргумент DB вне 0..255 — ошибка прохода 2.
    def test_db_range_error(self):
        items, symbols, _ = pass1(["DB 300"])
        self.assertEqual(pass2(items, symbols),
                         (None, "uAsm: строка 1: байт вне диапазона"))


class TestAssembleOk(unittest.TestCase):
    """Сборка текста в образ: программы и данные (SPEC, разделы 4-7)."""

    # @method test_empty_text_gives_empty_image() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой текст и текст без записей — пустой образ.
    def test_empty_text_gives_empty_image(self):
        self.assertEqual(assemble(""), (b"", None))
        self.assertEqual(assemble("\n; нет записей\n\n"), (b"", None))

    # @method test_simple_program() -> None
    # @in    нет
    # @out   нет
    # @does  Вывод символа: PUSH 65, SYS 1, HALT 0 — золотые байты.
    def test_simple_program(self):
        image, error = assemble("PUSH 65\nSYS 1\nHALT 0")
        self.assertIsNone(error)
        self.assertEqual(image,
                         op("PUSH") + word(65) + op("SYS") + word(1)
                         + op("HALT") + word(0))

    # @method test_arith_program() -> None
    # @in    нет
    # @out   нет
    # @does  Арифметика (2+3)*4: инструкции без операнда — по байту.
    def test_arith_program(self):
        image, error = assemble("PUSH 2\nPUSH 3\nADD\nPUSH 4\nMUL\nHALT 0")
        self.assertIsNone(error)
        self.assertEqual(image,
                         op("PUSH") + word(2) + op("PUSH") + word(3)
                         + op("ADD") + op("PUSH") + word(4) + op("MUL")
                         + op("HALT") + word(0))

    # @method test_forward_reference() -> None
    # @in    нет
    # @out   нет
    # @does  Ссылка вперёд: JMP на метку после него (адрес 9).
    def test_forward_reference(self):
        image, error = assemble("JMP end\nend:\nHALT 0")
        self.assertIsNone(error)
        self.assertEqual(image,
                         op("JMP") + word(9) + op("HALT") + word(0))

    # @method test_backward_reference() -> None
    # @in    нет
    # @out   нет
    # @does  Ссылка назад: метка до записи имеет адрес 0.
    def test_backward_reference(self):
        image, error = assemble("start:\nPUSH 1\nJMP start")
        self.assertIsNone(error)
        self.assertEqual(image,
                         op("PUSH") + word(1) + op("JMP") + word(0))

    # @method test_const_in_operands() -> None
    # @in    нет
    # @out   нет
    # @does  Имя константы — операнд PUSH и HALT: значение слова.
    def test_const_in_operands(self):
        image, error = assemble("n = 5\nPUSH n\nHALT n")
        self.assertIsNone(error)
        self.assertEqual(image,
                         op("PUSH") + word(5) + op("HALT") + word(5))

    # @method test_data_directives() -> None
    # @in    нет
    # @out   нет
    # @does  DS — байты UTF-8, DZ — плюс 0x00, DB — по байту, DW —
    # @does  по слову little-endian.
    def test_data_directives(self):
        image, error = assemble("DS \"AB\"\nDZ \"C\"\nDB 1 2\nDW 3")
        self.assertIsNone(error)
        self.assertEqual(image, b"AB" + b"C\x00" + b"\x01\x02" + word(3))

    # @method test_const_in_db_and_dw() -> None
    # @in    нет
    # @out   нет
    # @does  Аргументы DB и DW — имена констант.
    def test_const_in_db_and_dw(self):
        image, error = assemble("b = 65\nDB b\nDW b")
        self.assertIsNone(error)
        self.assertEqual(image, b"\x41" + word(65))

    # @method test_negative_wraps() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH -1 оборачивается в слово 2^64-1.
    def test_negative_wraps(self):
        image, error = assemble("PUSH -1")
        self.assertIsNone(error)
        self.assertEqual(image, op("PUSH") + word((1 << 64) - 1))

    # @method test_literal_forms() -> None
    # @in    нет
    # @out   нет
    # @does  Символьный, шестнадцатеричный и двоичный литералы
    # @does  кодируются своими значениями.
    def test_literal_forms(self):
        image, error = assemble("PUSH 'A'\nPUSH 0x10\nPUSH 0b101")
        self.assertIsNone(error)
        self.assertEqual(image, op("PUSH") + word(65) + op("PUSH") + word(16)
                         + op("PUSH") + word(5))

    # @method test_utf8_string_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  DS кодирует строку в байты UTF-8 (кириллица — два байта
    # @does  на букву).
    def test_utf8_string_bytes(self):
        image, error = assemble("DS \"Ж\"")
        self.assertIsNone(error)
        self.assertEqual(image, "Ж".encode("utf-8"))

    # @method test_comment_and_tail_ignored() -> None
    # @in    нет
    # @out   нет
    # @does  Комментарий «;» и концевой LF не меняют образ.
    def test_comment_and_tail_ignored(self):
        image, error = assemble("; шапка\n\nPUSH 1 ; хвост\n")
        self.assertIsNone(error)
        self.assertEqual(image, op("PUSH") + word(1))

    # @method test_crlf_text_assembles() -> None
    # @in    нет
    # @out   нет
    # @does  Текст с переводами CRLF собирается как с LF.
    def test_crlf_text_assembles(self):
        image, error = assemble("PUSH 1\r\nHALT 0\r\n")
        self.assertIsNone(error)
        self.assertEqual(image, op("PUSH") + word(1) + op("HALT") + word(0))


class TestAssembleErrors(unittest.TestCase):
    """Ошибки сборки: текст и номер строки (SPEC, раздел 7)."""

    # @method check_error(source, expected) -> None
    # @in    source: str — текст uAsm
    # @in    expected: str — ожидаемое сообщение об ошибке
    # @out   нет
    # @does  Сборка текста обязана окончиться первой ошибкой с точным
    # @does  сообщением.
    # @depends assemble
    def check_error(self, source, expected):
        image, error = assemble(source)
        self.assertIsNone(image, source)
        self.assertEqual(error, expected, source)

    # @method test_line_parse_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Тексты ошибок разбора строки: неизвестная мнемоника
    # @does  (в том числе строчная), нет и лишний операнд, плохой
    # @does  литерал, плохое имя метки, плохой строковый литерал,
    # @does  пустая директива.
    # @depends check_error
    def test_line_parse_errors(self):
        self.check_error("FOO", "uAsm: строка 1: неизвестная мнемоника FOO")
        self.check_error("push 1",
                         "uAsm: строка 1: неизвестная мнемоника push")
        self.check_error("PUSH", "uAsm: строка 1: нет операнда у PUSH")
        self.check_error("ADD 5", "uAsm: строка 1: лишний операнд у ADD")
        self.check_error("PUSH 12x", "uAsm: строка 1: плохой литерал 12x")
        self.check_error("1a:", "uAsm: строка 1: плохое имя")
        self.check_error("a: NOP", "uAsm: строка 1: плохое имя")
        self.check_error("DS abc", "uAsm: строка 1: плохой строковый литерал")
        self.check_error("DB", "uAsm: строка 1: пустая директива DB")

    # @method test_range_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Литерал вне -2^63..2^64-1 — и в операнде, и в константе;
    # @does  аргумент DB вне 0..255.
    # @depends check_error
    def test_range_errors(self):
        self.check_error("PUSH 18446744073709551616",
                         "uAsm: строка 1: литерал вне диапазона")
        self.check_error("x = -9223372036854775809",
                         "uAsm: строка 1: литерал вне диапазона")
        self.check_error("DB 256", "uAsm: строка 1: байт вне диапазона")

    # @method test_const_and_name_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Плохой литерал константы; имя использовано, но не
    # @does  определено.
    # @depends check_error
    def test_const_and_name_errors(self):
        self.check_error("x = 1z", "uAsm: строка 1: плохой литерал 1z")
        self.check_error("PUSH q", "uAsm: строка 1: неизвестное имя q")

    # @method test_first_error_stops() -> None
    # @in    нет
    # @out   нет
    # @does  Первая ошибка прекращает сборку: сообщается строка 1,
    # @does  а не строка 2.
    # @depends check_error
    def test_first_error_stops(self):
        self.check_error("FOO\nBAR",
                         "uAsm: строка 1: неизвестная мнемоника FOO")

    # @method test_line_numbers_count_blanks() -> None
    # @in    нет
    # @out   нет
    # @does  Номер строки — позиция в исходном тексте: пустые строки
    # @does  и комментарии считаются.
    # @depends check_error
    def test_line_numbers_count_blanks(self):
        source = "\n; комментарий\nFOO"
        self.check_error(source,
                         "uAsm: строка 3: неизвестная мнемоника FOO")


if __name__ == "__main__":
    unittest.main()
