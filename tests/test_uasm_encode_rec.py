# @uadro
# @file    tests/test_uasm_encode_rec.py
# @layer   T0
# @branch  t0.uasm.encode
# @desc    Тесты кодирования записей uAsm: инструкции (опкод и поле
# @desc    imm64), директивы DB/DW, размер записи для прохода 1 и запись
# @desc    целиком (SPEC/L2-UASM.txt, разделы 5-7).

"""Тесты кодирования записей (tools/uasm_encode.py).

encode_instr, encode_db, encode_dw, record_size, encode_record. Кирпичи
кодирования значений — tests/test_uasm_encode.py.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.uasm_encode import (encode_db, encode_dw, encode_instr,
                               encode_record, record_size, word_le)
from tools.uasm_line import parse_line


class TestEncodeInstr(unittest.TestCase):
    """Инструкция: байт опкода, при imm64 — слово (SPEC, раздел 5)."""

    # @method test_instr_without_imm() -> None
    # @in    нет
    # @out   нет
    # @does  Опкод без поля imm64 кодируется одним байтом; операнда нет.
    def test_instr_without_imm(self):
        self.assertEqual(encode_instr("NOP", None, {}), (b"\x00", None))
        self.assertEqual(encode_instr("ADD", None, {}), (b"\x20", None))
        self.assertEqual(encode_instr("RET", None, {}), (b"\x44", None))

    # @method test_instr_imm_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Опкод с полем imm64 — байт опкода и восемь байтов значения
    # @does  little-endian.
    def test_instr_imm_literals(self):
        self.assertEqual(encode_instr("PUSH", "5", {}),
                         (b"\x01" + word_le(5), None))
        self.assertEqual(encode_instr("PICK", "2", {}),
                         (b"\x07" + word_le(2), None))
        self.assertEqual(encode_instr("HALT", "0", {}),
                         (b"\x45" + word_le(0), None))
        self.assertEqual(encode_instr("SYS", "1", {}),
                         (b"\x50" + word_le(1), None))

    # @method test_instr_imm_forms_and_wrap() -> None
    # @in    нет
    # @out   нет
    # @does  Значение операнда — любая форма литерала; отрицательное
    # @does  значение оборачивается: PUSH -1 даёт восемь байтов FF.
    def test_instr_imm_forms_and_wrap(self):
        self.assertEqual(encode_instr("PUSH", "0x10", {}),
                         (b"\x01" + word_le(16), None))
        self.assertEqual(encode_instr("PUSH", "'A'", {}),
                         (b"\x01" + word_le(65), None))
        self.assertEqual(encode_instr("PUSH", "-1", {}),
                         (b"\x01" + b"\xff" * 8, None))

    # @method test_instr_imm_names() -> None
    # @in    нет
    # @out   нет
    # @does  Операнд-имя берёт значение из таблицы символов; адреса
    # @does  переходов — абсолютные.
    def test_instr_imm_names(self):
        symbols = {"start": 9, "fn": 0x10}
        self.assertEqual(encode_instr("JMP", "start", symbols),
                         (b"\x40" + word_le(9), None))
        self.assertEqual(encode_instr("CALL", "fn", symbols),
                         (b"\x43" + word_le(16), None))

    # @method test_instr_negative_const_like_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Значение имени берётся как есть, оборачивание — при
    # @does  кодировании: PUSH имени со значением -1 и PUSH -1 дают
    # @does  одинаковые байты.
    def test_instr_negative_const_like_literal(self):
        self.assertEqual(encode_instr("PUSH", "neg", {"neg": -1}),
                         encode_instr("PUSH", "-1", {}))

    # @method test_instr_unknown_mnemonic() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестная мнемоника — ошибка «неизвестная мнемоника X»;
    # @does  регистр значим: строчная «push» неизвестна.
    def test_instr_unknown_mnemonic(self):
        self.assertEqual(encode_instr("XYZ", None, {}),
                         (None, "неизвестная мнемоника XYZ"))
        self.assertEqual(encode_instr("push", "5", {}),
                         (None, "неизвестная мнемоника push"))

    # @method test_instr_operand_presence() -> None
    # @in    нет
    # @out   нет
    # @does  У опкода с imm64 отсутствие операнда — «нет операнда у X»;
    # @does  у опкода без imm64 наличие операнда — «лишний операнд у X».
    def test_instr_operand_presence(self):
        self.assertEqual(encode_instr("PUSH", None, {}),
                         (None, "нет операнда у PUSH"))
        self.assertEqual(encode_instr("NOP", "5", {}),
                         (None, "лишний операнд у NOP"))

    # @method test_instr_operand_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Ошибки значения операнда: плохой литерал, неизвестное имя,
    # @does  литерал вне диапазона.
    def test_instr_operand_errors(self):
        self.assertEqual(encode_instr("PUSH", "5x", {}),
                         (None, "плохой литерал 5x"))
        self.assertEqual(encode_instr("JMP", "zz", {}),
                         (None, "неизвестное имя zz"))
        self.assertEqual(encode_instr("PUSH", "18446744073709551616", {}),
                         (None, "литерал вне диапазона"))


class TestEncodeDb(unittest.TestCase):
    """DB: байт на аргумент, диапазон 0..255 (SPEC, раздел 6)."""

    # @method test_db_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Аргументы-литералы (десятичный, символьный, шестнадцатеричный)
    # @does  дают по одному байту в порядке записи.
    def test_db_literals(self):
        self.assertEqual(encode_db(("65", "'B'", "0x43"), {}),
                         (b"ABC", None))
        self.assertEqual(encode_db(("0",), {}), (b"\x00", None))
        self.assertEqual(encode_db(("255",), {}), (b"\xff", None))

    # @method test_db_names() -> None
    # @in    нет
    # @out   нет
    # @does  Аргумент-имя берёт значение из таблицы символов.
    def test_db_names(self):
        self.assertEqual(encode_db(("hi", "lo"), {"hi": 72, "lo": 105}),
                         (b"Hi", None))

    # @method test_db_out_of_range() -> None
    # @in    нет
    # @out   нет
    # @does  Значение аргумента вне 0..255 (в том числе имя) — «байт вне
    # @does  диапазона».
    def test_db_out_of_range(self):
        self.assertEqual(encode_db(("-1",), {}),
                         (None, "байт вне диапазона"))
        self.assertEqual(encode_db(("256",), {}),
                         (None, "байт вне диапазона"))
        self.assertEqual(encode_db(("big",), {"big": 300}),
                         (None, "байт вне диапазона"))

    # @method test_db_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Плохой аргумент — «плохой литерал X»; отсутствие аргументов —
    # @does  «пустая директива DB».
    def test_db_errors(self):
        self.assertEqual(encode_db(("5x",), {}),
                         (None, "плохой литерал 5x"))
        self.assertEqual(encode_db((), {}), (None, "пустая директива DB"))


class TestEncodeDw(unittest.TestCase):
    """DW: восемь байтов little-endian на аргумент (SPEC, раздел 6)."""

    # @method test_dw_literals() -> None
    # @in    нет
    # @out   нет
    # @does  Аргумент кодируется словом little-endian; отрицательное
    # @does  значение оборачивается по модулю 2^64.
    def test_dw_literals(self):
        self.assertEqual(encode_dw(("1",), {}), (word_le(1), None))
        self.assertEqual(encode_dw(("-1",), {}), (b"\xff" * 8, None))
        self.assertEqual(encode_dw(("0x1234567890ABCDEF",), {}),
                         (bytes.fromhex("EFCDAB9078563412"), None))

    # @method test_dw_many_args() -> None
    # @in    нет
    # @out   нет
    # @does  Несколько аргументов кодируются подряд, по слову на аргумент.
    def test_dw_many_args(self):
        self.assertEqual(encode_dw(("1", "2"), {}),
                         (word_le(1) + word_le(2), None))

    # @method test_dw_names() -> None
    # @in    нет
    # @out   нет
    # @does  Аргумент-имя берёт значение из таблицы символов.
    def test_dw_names(self):
        self.assertEqual(encode_dw(("addr",), {"addr": 0x10}),
                         (word_le(16), None))

    # @method test_dw_errors() -> None
    # @in    нет
    # @out   нет
    # @does  Плохой аргумент — «плохой литерал X»; отсутствие аргументов —
    # @does  «пустая директива DW».
    def test_dw_errors(self):
        self.assertEqual(encode_dw(("5x",), {}),
                         (None, "плохой литерал 5x"))
        self.assertEqual(encode_dw((), {}), (None, "пустая директива DW"))


class TestRecordSize(unittest.TestCase):
    """Размер записи для адресов прохода 1 (SPEC, раздел 7)."""

    # @method test_size_instr() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция с полем imm64 занимает 9 байтов, без — 1 байт.
    def test_size_instr(self):
        self.assertEqual(record_size(("instr", "PUSH", "5")), 9)
        self.assertEqual(record_size(("instr", "SYS", "1")), 9)
        self.assertEqual(record_size(("instr", "RET", None)), 1)
        self.assertEqual(record_size(("instr", "ADD", None)), 1)

    # @method test_size_data() -> None
    # @in    нет
    # @out   нет
    # @does  DB — по байту на аргумент; DW — по 8 байтов; DS и DZ — длина
    # @does  готовых байтов (нуль-байт DZ уже включён).
    def test_size_data(self):
        self.assertEqual(record_size(("data", "DB", ("1", "2", "3"))), 3)
        self.assertEqual(record_size(("data", "DW", ("1", "2"))), 16)
        self.assertEqual(record_size(("data", "DS", b"AB")), 2)
        self.assertEqual(record_size(("data", "DZ", b"A\x00")), 2)

    # @method test_size_no_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  Метка, константа, запись-ошибка и неизвестная мнемоника
    # @does  байтов не дают — размер 0.
    def test_size_no_bytes(self):
        self.assertEqual(record_size(("label", "x")), 0)
        self.assertEqual(record_size(("const", "x", 5)), 0)
        self.assertEqual(record_size(("error", "x")), 0)
        self.assertEqual(record_size(("instr", "ZZZ", None)), 0)


class TestEncodeRecord(unittest.TestCase):
    """Запись целиком — вход прохода 2 (SPEC, разделы 5-7)."""

    # @method test_record_from_parse_line() -> None
    # @in    нет
    # @out   нет
    # @does  Записи разбора строки кодируются целиком: инструкции с
    # @does  литералом и именем, DB, DS, DZ (нуль-байт на конце).
    def test_record_from_parse_line(self):
        symbols = {"start": 9}
        record = parse_line("PUSH 5")
        self.assertEqual(encode_record(record, symbols),
                         (b"\x01" + word_le(5), None))
        record = parse_line("JMP start")
        self.assertEqual(encode_record(record, symbols),
                         (b"\x40" + word_le(9), None))
        record = parse_line("RET")
        self.assertEqual(encode_record(record, symbols), (b"\x44", None))
        record = parse_line("DB 72 105")
        self.assertEqual(encode_record(record, symbols), (b"Hi", None))
        record = parse_line('DS "Hi"')
        self.assertEqual(encode_record(record, symbols), (b"Hi", None))
        record = parse_line('DZ "Hi"')
        self.assertEqual(encode_record(record, symbols), (b"Hi\x00", None))

    # @method test_record_label_const() -> None
    # @in    нет
    # @out   нет
    # @does  Метка и константа байтов не дают — пустые байты.
    def test_record_label_const(self):
        self.assertEqual(encode_record(("label", "x"), {}), (b"", None))
        self.assertEqual(encode_record(("const", "x", 5), {}),
                         (b"", None))

    # @method test_record_error_passthrough() -> None
    # @in    нет
    # @out   нет
    # @does  Запись-ошибка возвращает свой текст без изменений.
    def test_record_error_passthrough(self):
        self.assertEqual(encode_record(("error", "плохое имя"), {}),
                         (None, "плохое имя"))

    # @method test_record_bad() -> None
    # @in    нет
    # @out   нет
    # @does  Записи вне контракта — неизвестная директива, DS не с байтами,
    # @does  неизвестный вид — «плохая запись».
    def test_record_bad(self):
        self.assertEqual(encode_record(("data", "DX", ("1",)), {}),
                         (None, "плохая запись"))
        self.assertEqual(encode_record(("data", "DS", "не байты"), {}),
                         (None, "плохая запись"))
        self.assertEqual(encode_record(("nonsense",), {}),
                         (None, "плохая запись"))


if __name__ == "__main__":
    unittest.main()
