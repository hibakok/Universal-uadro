# @uadro
# @file    tests/test_uvm_decode.py
# @layer   T0
# @branch  t0.uvm.decode
# @desc    Тесты декодера инструкций: опкод, поле imm64 little-endian,
# @desc    адрес следующей инструкции, чистота decode_at, ловушки 6 и 7
# @desc    (SPEC/L0-UVM.txt, разделы 3-5).

"""Тесты ветви t0.uvm.decode (tools/uvm_decode.py).

decode_at проверяется как чистый кирпич (PC и стеки не меняются),
decode — как продвижение PC на байт за инструкцией целиком и выдача
обработчика из таблицы. Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_decode as dec
from tools import uvm_table as tab


class TestDecodeAt(unittest.TestCase):
    """Чистое декодирование инструкции по адресу (SPEC, раздел 4)."""

    # @method test_opcode_without_imm() -> None
    # @in    нет
    # @out   нет
    # @does  Опкод без поля imm64: запись таблицы, imm = 0, следующий
    # @does  адрес = адрес + 1.
    def test_opcode_without_imm(self):
        m = tk.small()
        m.ram[5] = 0x02  # DROP
        entry, imm, next_addr = dec.decode_at(m, 5)
        self.assertEqual(entry, tab.entry_by_code(0x02))
        self.assertEqual(imm, 0)
        self.assertEqual(next_addr, 6)

    # @method test_opcode_with_imm() -> None
    # @in    нет
    # @out   нет
    # @does  Опкод с полем imm64: слово читается little-endian, следующий
    # @does  адрес = адрес + 9.
    def test_opcode_with_imm(self):
        m = tk.small()
        m.ram[3] = 0x01  # PUSH
        uc.store_word(m, 4, 0x1122334455667788)
        entry, imm, next_addr = dec.decode_at(m, 3)
        self.assertEqual(entry, tab.entry_by_code(0x01))
        self.assertEqual(imm, 0x1122334455667788)
        self.assertEqual(next_addr, 12)

    # @method test_decode_at_is_pure() -> None
    # @in    нет
    # @out   нет
    # @does  decode_at не меняет PC и стеки машины.
    def test_decode_at_is_pure(self):
        m = tk.small()
        m.ram[0] = 0x01  # PUSH
        uc.store_word(m, 1, 7)
        uc.ds_push(m, 5)
        dec.decode_at(m, 0)
        self.assertEqual(m.pc, 0)
        self.assertEqual(tk.stack_of(m), [5])
        self.assertEqual(m.rs, [])

    # @method test_unknown_opcode_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Неиспользуемые коды 0x0F и 0xFF — ловушка 6.
    def test_unknown_opcode_traps(self):
        for code in (0x0F, 0xFF):
            with self.subTest(code=code):
                m = tk.small()
                m.ram[0] = code
                self.assertEqual(tk.trap_code(lambda: dec.decode_at(m, 0)),
                                 uc.TRAP_BAD_OPCODE)

    # @method test_fetch_outside_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Выбор опкода вне ОЗУ — ловушка 7.
    def test_fetch_outside_ram_traps(self):
        m = tk.small(ram_size=8)
        self.assertEqual(tk.trap_code(lambda: dec.decode_at(m, 8)),
                         uc.TRAP_OOB)
        self.assertEqual(tk.trap_code(lambda: dec.decode_at(m, -1)),
                         uc.TRAP_OOB)

    # @method test_imm_outside_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Поле imm64, не помещающееся в ОЗУ, — ловушка 7.
    def test_imm_outside_ram_traps(self):
        m = tk.small(ram_size=12)
        m.ram[4] = 0x01  # PUSH: полю imm64 нужны байты 5..12
        self.assertEqual(tk.trap_code(lambda: dec.decode_at(m, 4)),
                         uc.TRAP_OOB)


class TestDecode(unittest.TestCase):
    """Декодирование по PC с продвижением (контракт t0.uvm.exec)."""

    # @method test_decode_returns_handler_and_imm() -> None
    # @in    нет
    # @out   нет
    # @does  decode даёт обработчик из таблицы и значение imm64.
    def test_decode_returns_handler_and_imm(self):
        m = tk.small()
        m.ram[0] = 0x01  # PUSH
        uc.store_word(m, 1, 77)
        handler, imm = dec.decode(m)
        self.assertEqual(imm, 77)
        self.assertEqual(handler, tab.handler_of(0x01))

    # @method test_decode_advances_pc_without_imm() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция без imm64: PC = PC + 1.
    def test_decode_advances_pc_without_imm(self):
        m = tk.small()
        m.ram[0] = 0x00  # NOP
        dec.decode(m)
        self.assertEqual(m.pc, 1)

    # @method test_decode_advances_pc_with_imm() -> None
    # @in    нет
    # @out   нет
    # @does  Инструкция с imm64: PC = PC + 9.
    def test_decode_advances_pc_with_imm(self):
        m = tk.small()
        m.ram[0] = 0x01  # PUSH
        uc.store_word(m, 1, 7)
        dec.decode(m)
        self.assertEqual(m.pc, 9)

    # @method test_decode_at_arbitrary_pc() -> None
    # @in    нет
    # @out   нет
    # @does  Декодируется инструкция по текущему PC, а не только с нуля.
    def test_decode_at_arbitrary_pc(self):
        m = tk.small()
        m.ram[20] = 0x03  # DUP
        m.pc = 20
        dec.decode(m)
        self.assertEqual(m.pc, 21)

    # @method test_decode_unknown_keeps_pc() -> None
    # @in    нет
    # @out   нет
    # @does  Ловушка 6 на неизвестном опкоде: PC остаётся прежним.
    def test_decode_unknown_keeps_pc(self):
        m = tk.small()
        m.ram[0] = 0x99
        m.pc = 0
        self.assertEqual(tk.trap_code(lambda: dec.decode(m)),
                         uc.TRAP_BAD_OPCODE)
        self.assertEqual(m.pc, 0)


if __name__ == "__main__":
    unittest.main()
