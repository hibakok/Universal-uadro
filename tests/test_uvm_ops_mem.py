# @uadro
# @file    tests/test_uvm_ops_mem.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты обработчиков памяти: LOAD8, LOAD64, STORE8, STORE64
# @desc    (SPEC/L0-UVM.txt, раздел 5).

"""Тесты группы «память» ветви t0.uvm.ops (tools/uvm_ops_mem.py).

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_ops_mem as ops


class TestLoad(unittest.TestCase):
    """Чтение из ОЗУ (SPEC, разделы 1 и 5)."""

    # @method test_load8_reads_byte_zero_extended() -> None
    # @in    нет
    # @out   нет
    # @does  LOAD8 возвращает байт 0..255, расширенный нулями до слова.
    def test_load8_reads_byte_zero_extended(self):
        m = tk.small()
        uc.store_byte(m, 5, 0xFF)
        uc.ds_push(m, 5)
        ops.op_load8(m, 0)
        self.assertEqual(tk.stack_of(m), [255])

    # @method test_load8_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  LOAD8 по адресу вне ОЗУ — ловушка 7.
    def test_load8_out_of_ram_traps(self):
        m = tk.small(ram_size=16)
        uc.ds_push(m, 16)
        self.assertEqual(tk.trap_code(lambda: ops.op_load8(m, 0)),
                         uc.TRAP_OOB)

    # @method test_load64_roundtrip_unaligned() -> None
    # @in    нет
    # @out   нет
    # @does  LOAD64 читает слово little-endian без выравнивания.
    def test_load64_roundtrip_unaligned(self):
        m = tk.small()
        uc.store_word(m, 3, 0x1122334455667788)
        uc.ds_push(m, 3)
        ops.op_load64(m, 0)
        self.assertEqual(tk.stack_of(m), [0x1122334455667788])

    # @method test_load64_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  LOAD64 по адресу, где слово не помещается, — ловушка 7.
    def test_load64_out_of_ram_traps(self):
        m = tk.small(ram_size=16)
        uc.ds_push(m, 9)
        self.assertEqual(tk.trap_code(lambda: ops.op_load64(m, 0)),
                         uc.TRAP_OOB)


class TestStore(unittest.TestCase):
    """Запись в ОЗУ (SPEC, разделы 1 и 5)."""

    # @method test_store8_writes_low_byte() -> None
    # @in    нет
    # @out   нет
    # @does  STORE8 пишет младший байт val; на стеке val глубже addr.
    def test_store8_writes_low_byte(self):
        m = tk.small()
        uc.ds_push(m, 300)
        uc.ds_push(m, 4)
        ops.op_store8(m, 0)
        self.assertEqual(uc.load_byte(m, 4), 44)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_store8_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  STORE8 по адресу вне ОЗУ — ловушка 7.
    def test_store8_out_of_ram_traps(self):
        m = tk.small(ram_size=16)
        uc.ds_push(m, 1)
        uc.ds_push(m, 16)
        self.assertEqual(tk.trap_code(lambda: ops.op_store8(m, 0)),
                         uc.TRAP_OOB)

    # @method test_store64_little_endian() -> None
    # @in    нет
    # @out   нет
    # @does  STORE64 раскладывает слово от младшего байта к старшему.
    def test_store64_little_endian(self):
        m = tk.small()
        uc.ds_push(m, 0x0102030405060708)
        uc.ds_push(m, 0)
        ops.op_store64(m, 0)
        self.assertEqual(bytes(m.ram[0:8]),
                         bytes([8, 7, 6, 5, 4, 3, 2, 1]))

    # @method test_store64_roundtrip_unaligned() -> None
    # @in    нет
    # @out   нет
    # @does  STORE64/LOAD64 восстанавливают слово без выравнивания.
    def test_store64_roundtrip_unaligned(self):
        m = tk.small()
        uc.ds_push(m, 0x1122334455667788)
        uc.ds_push(m, 3)
        ops.op_store64(m, 0)
        self.assertEqual(uc.load_word(m, 3), 0x1122334455667788)

    # @method test_store64_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  STORE64 по адресу, где слово не помещается, — ловушка 7.
    def test_store64_out_of_ram_traps(self):
        m = tk.small(ram_size=16)
        uc.ds_push(m, 1)
        uc.ds_push(m, 12)
        self.assertEqual(tk.trap_code(lambda: ops.op_store64(m, 0)),
                         uc.TRAP_OOB)


if __name__ == "__main__":
    unittest.main()
