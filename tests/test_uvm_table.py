# @uadro
# @file    tests/test_uvm_table.py
# @layer   T0
# @branch  t0.uvm.table
# @desc    Тесты таблицы опкодов: 40 записей (38 SPEC v0.1 + DEVRD/DEVWR
# @desc    v0.3), уникальность кодов и мнемоник, золотое соответствие
# @desc    код-мнемоника-imm64, проводка обработчиков, поиск неизвестных
# @desc    кодов и мнемоник.

"""Тесты ветви t0.uvm.table (tools/uvm_table.py).

Золотая таблица GOLDEN повторяет SPEC/L0-UVM.txt, раздел 5: любое
расхождение таблицы со спецификацией ловится здесь. 38 записей v0.1
и пара DEVRD/DEVWR v0.3 (Этап 5, раздел 6А.2) — 40 записей.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools import uvm_ops_arith as arith
from tools import uvm_ops_cmp as cmp
from tools import uvm_ops_dev as dev
from tools import uvm_ops_jump as jump
from tools import uvm_ops_mem as mem
from tools import uvm_ops_stack as stack
from tools import uvm_ops_sys as sysops
from tools import uvm_table as tbl

GOLDEN = (
    (0x00, "NOP", False),
    (0x01, "PUSH", True),
    (0x02, "DROP", False),
    (0x03, "DUP", False),
    (0x04, "SWAP", False),
    (0x05, "OVER", False),
    (0x06, "ROT", False),
    (0x07, "PICK", True),
    (0x10, "LOAD8", False),
    (0x11, "LOAD64", False),
    (0x12, "STORE8", False),
    (0x13, "STORE64", False),
    (0x20, "ADD", False),
    (0x21, "SUB", False),
    (0x22, "MUL", False),
    (0x23, "UDIV", False),
    (0x24, "UMOD", False),
    (0x25, "NEG", False),
    (0x26, "SHL", False),
    (0x27, "SHR", False),
    (0x28, "SAR", False),
    (0x29, "AND", False),
    (0x2A, "OR", False),
    (0x2B, "XOR", False),
    (0x2C, "INV", False),
    (0x30, "EQ", False),
    (0x31, "NEQ", False),
    (0x32, "LTU", False),
    (0x33, "GTU", False),
    (0x34, "LEU", False),
    (0x35, "GEU", False),
    (0x40, "JMP", True),
    (0x41, "JZ", True),
    (0x42, "JNZ", True),
    (0x43, "CALL", True),
    (0x44, "RET", False),
    (0x45, "HALT", True),
    (0x50, "SYS", True),
    (0x52, "DEVRD", False),
    (0x53, "DEVWR", False),
)


class TestOpcodeTable(unittest.TestCase):
    """Таблица опкодов UVM (SPEC, раздел 5; DEV — 6А.2)."""

    # @method test_table_has_40_opcodes() -> None
    # @in    нет
    # @out   нет
    # @does  В таблице ровно 40 опкодов: 38 v0.1 и пара DEVRD/DEVWR
    # @does  v0.3 (SPEC, раздел 5 и 6А.2).
    def test_table_has_40_opcodes(self):
        self.assertEqual(len(tbl.TABLE), 40)

    # @method test_codes_are_unique_and_in_byte_range() -> None
    # @in    нет
    # @out   нет
    # @does  Коды опкодов уникальны и лежат в 0..255 (байтовый опкод).
    def test_codes_are_unique_and_in_byte_range(self):
        codes = [rec[0] for rec in tbl.TABLE]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(tbl.BY_CODE), 40)
        for code in codes:
            self.assertTrue(0 <= code <= 255)

    # @method test_mnemonics_are_unique_and_nonempty() -> None
    # @in    нет
    # @out   нет
    # @does  Мнемоники уникальны и непусты: обратный поиск однозначен
    # @does  (кирпич ассемблера, Этап 2).
    def test_mnemonics_are_unique_and_nonempty(self):
        names = [rec[1] for rec in tbl.TABLE]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(tbl.BY_MNEMONIC), 40)
        for name in names:
            self.assertTrue(name)

    # @method test_entries_are_well_formed() -> None
    # @in    нет
    # @out   нет
    # @does  Каждая запись — четвёрка (код, мнемоника, обработчик, флаг
    # @does  imm64) с корректными типами.
    def test_entries_are_well_formed(self):
        for rec in tbl.TABLE:
            self.assertEqual(len(rec), 4)
            self.assertIsInstance(rec[1], str)
            self.assertTrue(callable(rec[2]))
            self.assertIsInstance(rec[3], bool)

    # @method test_golden_spec_mapping() -> None
    # @in    нет
    # @out   нет
    # @does  Золотая таблица из 40 строк совпадает с TABLE: код -> мнемоника
    # @does  и imm64, а также обратный путь мнемоника -> код.
    def test_golden_spec_mapping(self):
        self.assertEqual(len(tbl.TABLE), len(GOLDEN))
        for code, name, has in GOLDEN:
            entry = tbl.entry_by_code(code)
            self.assertIsNotNone(entry)
            self.assertEqual(entry[1], name)
            self.assertEqual(entry[3], has)
            back = tbl.entry_by_mnemonic(name)
            self.assertIsNotNone(back)
            self.assertEqual(back[0], code)
        self.assertEqual(tbl.mnemonic_of(0x01), "PUSH")
        self.assertEqual(tbl.code_of("PUSH"), 0x01)
        self.assertEqual(tbl.mnemonic_of(0x2A), "OR")
        self.assertEqual(tbl.code_of("HALT"), 0x45)
        self.assertEqual(tbl.mnemonic_of(0x52), "DEVRD")
        self.assertEqual(tbl.code_of("DEVWR"), 0x53)

    # @method test_imm_flag_matches_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Поле imm64 имеют ровно 8 опкодов: PUSH, PICK, JMP, JZ, JNZ,
    # @does  CALL, HALT, SYS (SPEC, раздел 4).
    def test_imm_flag_matches_spec(self):
        imm_codes = {rec[0] for rec in tbl.TABLE if rec[3]}
        expected = {0x01, 0x07, 0x40, 0x41, 0x42, 0x43, 0x45, 0x50}
        self.assertEqual(imm_codes, expected)
        self.assertFalse(tbl.has_imm(0x00))
        self.assertFalse(tbl.has_imm(0x44))
        self.assertTrue(tbl.has_imm(0x50))

    # @method test_group_sizes_match_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Группы опкодов содержат 8, 4, 13, 6, 6, 1 и 2 записи (SPEC,
    # @does  разделы 5 и 6А.2: DEV-группа — v0.3).
    def test_group_sizes_match_spec(self):
        self.assertEqual(len(tbl.GROUP_STACK), 8)
        self.assertEqual(len(tbl.GROUP_MEM), 4)
        self.assertEqual(len(tbl.GROUP_ARITH), 13)
        self.assertEqual(len(tbl.GROUP_CMP), 6)
        self.assertEqual(len(tbl.GROUP_JUMP), 6)
        self.assertEqual(len(tbl.GROUP_SYS), 1)
        self.assertEqual(len(tbl.GROUP_DEV), 2)

    # @method test_handlers_are_wired_to_groups() -> None
    # @in    нет
    # @out   нет
    # @does  Каждый код ведёт к обработчику своей группы опкодов
    # @does  (tools/uvm_ops_*.py).
    def test_handlers_are_wired_to_groups(self):
        self.assertIs(tbl.handler_of(0x01), stack.op_push)
        self.assertIs(tbl.handler_of(0x07), stack.op_pick)
        self.assertIs(tbl.handler_of(0x10), mem.op_load8)
        self.assertIs(tbl.handler_of(0x13), mem.op_store64)
        self.assertIs(tbl.handler_of(0x20), arith.op_add)
        self.assertIs(tbl.handler_of(0x2C), arith.op_inv)
        self.assertIs(tbl.handler_of(0x30), cmp.op_eq)
        self.assertIs(tbl.handler_of(0x35), cmp.op_geu)
        self.assertIs(tbl.handler_of(0x40), jump.op_jmp)
        self.assertIs(tbl.handler_of(0x44), jump.op_ret)
        self.assertIs(tbl.handler_of(0x45), jump.op_halt)
        self.assertIs(tbl.handler_of(0x50), sysops.op_sys)
        self.assertIs(tbl.handler_of(0x52), dev.op_devrd)
        self.assertIs(tbl.handler_of(0x53), dev.op_devwr)

    # @method test_unknown_code_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Неиспользуемые коды (промежутки и свободные диапазоны SPEC)
    # @does  не находятся: None и False, без исключений.
    def test_unknown_code_is_none(self):
        for code in (0x08, 0x0F, 0x14, 0x1F, 0x2D, 0x36, 0x46, 0x51, 0xFF):
            self.assertIsNone(tbl.entry_by_code(code))
            self.assertIsNone(tbl.handler_of(code))
            self.assertIsNone(tbl.mnemonic_of(code))
            self.assertFalse(tbl.has_imm(code))

    # @method test_unknown_mnemonic_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестная и пустая мнемоника не находится: None, без
    # @does  исключений.
    def test_unknown_mnemonic_is_none(self):
        self.assertIsNone(tbl.entry_by_mnemonic("XX"))
        self.assertIsNone(tbl.code_of("PUSHH"))
        self.assertIsNone(tbl.code_of(""))


if __name__ == "__main__":
    unittest.main()
