# @uadro
# @file    tests/test_uasm_disasm.py
# @layer   T0
# @branch  t0.uasm.disasm
# @desc    Тесты дизассемблера образа: чтение imm64, строка инструкции,
# @desc    шаг декодирования, хвост данных директивами DB, пустой образ,
# @desc    раунд-трип assemble(disasm(B)) == B (SPEC/L2-UASM.txt,
# @desc    раздел 8).

"""Тесты ветви t0.uasm.disasm (tools/uasm_disasm.py).

Дизассемблер образа UVM: линейное чтение с адреса 0, по одной
инструкции на строку («МНЕМОНИКА» или «МНЕМОНИКА значение», значения —
десятичные литералы), останов декодирования по неизвестному опкоду или
обрыву поля imm64, хвост данных — директивы DB до восьми аргументов
на строку, пустой образ — пустой текст. Раунд-трип
assemble(disasm(B)) == B — критерий готовности Этапа 2.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.uasm_assemble import assemble
from tools.uasm_disasm import (
    db_lines, decode_step, disasm, imm64_at, instr_line, join_lines,
)
from tools.uvm_table import entry_by_mnemonic

WORD_MAX = (1 << 64) - 1


# @method op(mnemonic) -> bytes
# @in    mnemonic: str — мнемоника опкода UVM
# @out   data: bytes — один байт опкода
# @does  Байт опкода по мнемонике — для золотых байтов тестов.
# @depends entry_by_mnemonic
def op(mnemonic):
    return bytes([entry_by_mnemonic(mnemonic)[0]])


# @method word(value) -> bytes
# @in    value: int — значение слова
# @out   data: bytes — восемь байтов little-endian
# @does  Поле imm64 в золотых байтах тестов.
def word(value):
    return (value % (1 << 64)).to_bytes(8, "little")


class TestImm64At(unittest.TestCase):
    """Чтение слова little-endian по адресу (SPEC, раздел 8)."""

    # @method test_reads_word() -> None
    # @in    нет
    # @out   нет
    # @does  Восемь байтов little-endian дают слово: обычное
    # @does  и максимальное 2^64-1.
    def test_reads_word(self):
        self.assertEqual(imm64_at(word(65), 0), 65)
        self.assertEqual(imm64_at(word(WORD_MAX), 0), WORD_MAX)
        self.assertEqual(imm64_at(word(0), 0), 0)

    # @method test_reads_at_offset() -> None
    # @in    нет
    # @out   нет
    # @does  Поле читается с любого адреса: за байтом опкода и внутри
    # @does  образа.
    def test_reads_at_offset(self):
        self.assertEqual(imm64_at(op("PUSH") + word(5), 1), 5)
        self.assertEqual(imm64_at(b"\x00" * 10, 2), 0)

    # @method test_none_when_does_not_fit() -> None
    # @in    нет
    # @out   нет
    # @does  Поле, не помещающееся в образ, даёт None: не хватает
    # @does  байтов до конца или образ пуст.
    def test_none_when_does_not_fit(self):
        self.assertIsNone(imm64_at(b"\x00" * 10, 3))
        self.assertIsNone(imm64_at(b"\x00" * 7, 0))
        self.assertIsNone(imm64_at(b"", 0))

    # @method test_fits_exactly_at_end() -> None
    # @in    нет
    # @out   нет
    # @does  Поле, заканчивающееся ровно на границе образа, читается.
    def test_fits_exactly_at_end(self):
        self.assertEqual(imm64_at(b"\x01" + word(7), 1), 7)


class TestInstrLine(unittest.TestCase):
    """Строка инструкции (SPEC, раздел 8)."""

    # @method test_without_value() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция без поля imm64 — одна мнемоника.
    def test_without_value(self):
        self.assertEqual(instr_line("NOP", None), "NOP")
        self.assertEqual(instr_line("ADD", None), "ADD")

    # @method test_with_value() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция с полем imm64 — «МНЕМОНИКА значение», значение —
    # @does  десятичный литерал, в том числе ноль.
    def test_with_value(self):
        self.assertEqual(instr_line("PUSH", 65), "PUSH 65")
        self.assertEqual(instr_line("HALT", 0), "HALT 0")

    # @method test_max_word_value() -> None
    # @in    нет
    # @out   нет
    # @does  Максимальное слово 2^64-1 печатается десятичным литералом
    # @does  без знака.
    def test_max_word_value(self):
        self.assertEqual(instr_line("PUSH", WORD_MAX),
                         "PUSH 18446744073709551615")


class TestDecodeStep(unittest.TestCase):
    """Шаг декодирования: инструкция или сигнал останова (SPEC, раздел 8)."""

    # @method test_plain_opcode() -> None
    # @in    нет
    # @out   нет
    # @does  Опкод без imm64: строка-мнемоника и адрес следующий байт.
    def test_plain_opcode(self):
        self.assertEqual(decode_step(op("NOP"), 0), ("NOP", 1))
        self.assertEqual(decode_step(op("ADD") + op("NOP"), 0), ("ADD", 1))

    # @method test_imm_opcode() -> None
    # @in    нет
    # @out   нет
    # @does  Опкод с imm64: строка со значением и адрес за полем.
    def test_imm_opcode(self):
        image = op("PUSH") + word(65)
        self.assertEqual(decode_step(image, 0), ("PUSH 65", 9))

    # @method test_imm_exactly_at_end() -> None
    # @in    нет
    # @out   нет
    # @does  Поле imm64, заканчивающееся на границе образа, декодируется.
    def test_imm_exactly_at_end(self):
        image = op("PUSH") + word(5)
        self.assertEqual(decode_step(image, 0), ("PUSH 5", 9))

    # @method test_unknown_opcode_stops() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный опкод — сигнал останова на своём адресе.
    def test_unknown_opcode_stops(self):
        self.assertEqual(decode_step(b"\x7f", 0), (None, 0))
        self.assertEqual(decode_step(op("NOP") + b"\x0a", 1), (None, 1))

    # @method test_truncated_imm_stops() -> None
    # @in    нет
    # @out   нет
    # @does  Поле imm64, не помещающееся в образ, — сигнал останова
    # @does  на адресе опкода.
    def test_truncated_imm_stops(self):
        self.assertEqual(decode_step(op("PUSH") + b"\x01\x02", 0),
                         (None, 0))


class TestDbLines(unittest.TestCase):
    """Хвост данных директивами DB (SPEC, раздел 8)."""

    # @method test_empty_data() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой хвост — ни одной строки.
    def test_empty_data(self):
        self.assertEqual(db_lines(b""), [])

    # @method test_short_data() -> None
    # @in    нет
    # @out   нет
    # @does  До восьми байтов — одна строка «DB b1 [...]» с десятичными
    # @does  аргументами.
    def test_short_data(self):
        self.assertEqual(db_lines(b"\x01"), ["DB 1"])
        self.assertEqual(db_lines(b"\xff\x00"), ["DB 255 0"])

    # @method test_eight_per_line() -> None
    # @in    нет
    # @out   нет
    # @does  Ровно восемь аргументов — одна строка; девятый начинает
    # @does  вторую.
    def test_eight_per_line(self):
        self.assertEqual(db_lines(bytes(range(1, 9))),
                         ["DB 1 2 3 4 5 6 7 8"])
        self.assertEqual(db_lines(bytes(range(1, 10))),
                         ["DB 1 2 3 4 5 6 7 8", "DB 9"])

    # @method test_long_tail_chunks() -> None
    # @in    нет
    # @out   нет
    # @does  Двенадцать байтов — строки по восемь и четыре аргумента.
    def test_long_tail_chunks(self):
        self.assertEqual(db_lines(bytes(range(0, 12))),
                         ["DB 0 1 2 3 4 5 6 7", "DB 8 9 10 11"])


class TestJoinLines(unittest.TestCase):
    """Строки в текст (SPEC, раздел 8)."""

    # @method test_empty() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой список строк — пустой текст.
    def test_empty(self):
        self.assertEqual(join_lines([]), "")

    # @method test_lines_get_lf() -> None
    # @in    нет
    # @out   нет
    # @does  Строки разделяются LF, непустой текст оканчивается
    # @does  переводом строки.
    def test_lines_get_lf(self):
        self.assertEqual(join_lines(["NOP"]), "NOP\n")
        self.assertEqual(join_lines(["NOP", "PUSH 1"]), "NOP\nPUSH 1\n")


class TestDisasm(unittest.TestCase):
    """Дизассемблирование образа целиком (SPEC, раздел 8)."""

    # @method test_empty_image() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой образ — пустой текст.
    def test_empty_image(self):
        self.assertEqual(disasm(b""), "")

    # @method test_single_instructions() -> None
    # @in    нет
    # @out   нет
    # @does  Одна инструкция с imm64 и одна без — по строке на каждую.
    def test_single_instructions(self):
        self.assertEqual(disasm(op("NOP")), "NOP\n")
        self.assertEqual(disasm(op("PUSH") + word(65)), "PUSH 65\n")

    # @method test_program() -> None
    # @in    нет
    # @out   нет
    # @does  Программа (2+3)*4: инструкции подряд, значения — десятичные
    # @does  литералы, имена не восстанавливаются.
    def test_program(self):
        image = (op("PUSH") + word(2) + op("PUSH") + word(3) + op("ADD")
                 + op("PUSH") + word(4) + op("MUL") + op("HALT") + word(0))
        self.assertEqual(
            disasm(image),
            "PUSH 2\nPUSH 3\nADD\nPUSH 4\nMUL\nHALT 0\n",
        )

    # @method test_unknown_opcode_tail() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный опкод останавливает декодирование: с него
    # @does  до конца образа данные печатаются директивами DB.
    def test_unknown_opcode_tail(self):
        self.assertEqual(disasm(op("NOP") + b"\x07\x0a"),
                         "NOP\nDB 7 10\n")

    # @method test_truncated_imm_tail() -> None
    # @in    нет
    # @out   нет
    # @does  Обрыв поля imm64 останавливает декодирование: весь остаток
    # @does  с опкода — директивы DB.
    def test_truncated_imm_tail(self):
        self.assertEqual(disasm(op("PUSH") + b"\x01\x02"),
                         "DB 1 1 2\n")

    # @method test_end_on_boundary_no_db() -> None
    # @in    нет
    # @out   нет
    # @does  Образ, закончившийся на границе инструкции, директив DB
    # @does  не даёт.
    def test_end_on_boundary_no_db(self):
        self.assertEqual(disasm(op("ADD")), "ADD\n")
        self.assertEqual(disasm(op("PUSH") + word(1)), "PUSH 1\n")

    # @method test_data_tail_chunking() -> None
    # @in    нет
    # @out   нет
    # @does  Хвост данных длиннее восьми байтов делится на строки DB
    # @does  по восемь аргументов.
    def test_data_tail_chunking(self):
        self.assertEqual(disasm(op("NOP") + bytes(range(0x60, 0x6C))),
                         "NOP\nDB 96 97 98 99 100 101 102 103\n"
                         "DB 104 105 106 107\n")

    # @method test_all_data_image() -> None
    # @in    нет
    # @out   нет
    # @does  Образ, не начинающийся с опкода, весь печатается
    # @does  директивами DB.
    def test_all_data_image(self):
        self.assertEqual(disasm(b"\xab\xcd"), "DB 171 205\n")


class TestRoundTrip(unittest.TestCase):
    """Раунд-трип assemble(disasm(B)) == B (SPEC, раздел 8)."""

    # @method roundtrip(image) -> None
    # @in    image: bytes — двоичный образ UVM
    # @out   нет
    # @does  Проверяет критерий готовности Этапа 2: образ, собранный
    # @does  обратно из дизассемблированного текста, равен исходному.
    # @depends disasm, assemble
    def roundtrip(self, image):
        text = disasm(image)
        again, error = assemble(text)
        self.assertIsNone(error, text)
        self.assertEqual(again, image, text)

    # @method test_empty() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой образ проходит раунд-трип через пустой текст.
    # @depends roundtrip
    def test_empty(self):
        self.roundtrip(b"")

    # @method test_instruction_program() -> None
    # @in    нет
    # @out   нет
    # @does  Программа из инструкций собирается обратно байт в байт.
    # @depends roundtrip
    def test_instruction_program(self):
        image, error = assemble("PUSH 2\nPUSH 3\nADD\nHALT 0")
        self.assertIsNone(error)
        self.roundtrip(image)

    # @method test_jump_and_call_program() -> None
    # @in    нет
    # @out   нет
    # @does  Адресные операнды JMP/CALL сохраняются десятичными
    # @does  литералами и собираются обратно.
    # @depends roundtrip
    def test_jump_and_call_program(self):
        image, error = assemble(
            "start:\nPUSH 1\nJMP start\nCALL fin\nfin:\nHALT 0")
        self.assertIsNone(error)
        self.roundtrip(image)

    # @method test_max_imm() -> None
    # @in    нет
    # @out   нет
    # @does  Максимальное слово 2^64-1 в поле imm64 проходит раунд-трип
    # @does  десятичным литералом.
    # @depends roundtrip
    def test_max_imm(self):
        self.roundtrip(op("PUSH") + word(WORD_MAX))

    # @method test_data_tail() -> None
    # @in    нет
    # @out   нет
    # @does  Хвост данных за инструкциями возвращается директивами DB
    # @does  байт в байт.
    # @depends roundtrip
    def test_data_tail(self):
        self.roundtrip(op("HALT") + word(0) + bytes(range(20)))

    # @method test_mixed_arbitrary_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  Смесь известных опкодов, перехода и данных проходит
    # @does  раунд-трип.
    # @depends roundtrip
    def test_mixed_arbitrary_bytes(self):
        self.roundtrip(b"\x29\x2a\x07\xff")

    # @method test_image_from_data_directives() -> None
    # @in    нет
    # @out   нет
    # @does  Образ директив данных DS/DZ/DB/DW дизассемблируется (как
    # @does  инструкции или DB-хвост) и собирается обратно байт в байт.
    # @depends roundtrip
    def test_image_from_data_directives(self):
        image, error = assemble('DS "AB"\nDZ "C"\nDB 1 2\nDW 3')
        self.assertIsNone(error)
        self.roundtrip(image)


if __name__ == "__main__":
    unittest.main()
