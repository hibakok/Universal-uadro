# @uadro
# @file    tests/test_uvm_devices.py
# @layer   T0
# @branch  t0.uvm.bus
# @desc    Тесты устройств стандартного набора: консоль (CON_RX/CON_TX),
# @desc    таймер (TMR_CYC/TMR_WALL), блочное хранилище (BLK_ADDR/
# @desc    BLK_DATA/BLK_SIZE), привязка стандартного набора
# @desc    (SPEC/L0-UVM.txt, 6А.3-6А.4).

"""Тесты устройств стандартного набора шины (ветвь t0.uvm.bus,
tools/uvm_devices.py).

Консоль проверяется с заглушками потоков узла (tk.FakeStream,
tk.patched_stdin) — устройство работает через общие кирпичи
host_read_byte/host_write_byte (SPEC, 6А.4). CYC проверяется
сквозным прогоном: шаг исполнения считает начатые шаги, TMR_CYC
читает счётчик. TMR_WALL недетерминирован — проверяется только
неубывание и маска (SPEC, раздел 1). Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import contextlib
import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc
from tools import uvm_devices as dev
from tools import uvm_run
from tools import uvm_bus as bus


class TestConsole(unittest.TestCase):
    """Консоль: CON_RX — байт ввода, CON_TX — вывод (SPEC, 6А.3)."""

    # @method test_con_rx_reads_bytes_then_eof() -> None
    # @in    нет
    # @out   нет
    # @does  CON_RX читает байты ввода по порядку, за последним — слово
    # @does  из всех единиц (как SYS 0).
    def test_con_rx_reads_bytes_then_eof(self):
        m = tk.small()
        dev.attach_console(m)
        got = []
        tk.patched_stdin(tk.FakeStream(b"AB"),
                         lambda: got.extend([
                             bus.bus_read(m, dev.CON_RX)
                             for _ in range(3)]))
        self.assertEqual(got, [65, 66, uc.WORD_MASK])

    # @method test_con_rx_write_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Запись в регистр чтения CON_RX — ловушка 9.
    def test_con_rx_write_traps(self):
        m = tk.small()
        dev.attach_console(m)
        self.assertEqual(
            tk.trap_code(lambda: bus.bus_write(m, dev.CON_RX, 1)),
            uc.TRAP_BAD_PORT)

    # @method test_con_tx_writes_low_byte() -> None
    # @in    нет
    # @out   нет
    # @does  CON_TX выводит младший байт слова: 321 -> "A" (как SYS 1).
    def test_con_tx_writes_low_byte(self):
        m = tk.small()
        dev.attach_console(m)
        out = tk.FakeStream()
        with contextlib.redirect_stdout(out):
            bus.bus_write(m, dev.CON_TX, 321)
        self.assertEqual(out.buffer.getvalue(), b"A")

    # @method test_con_tx_read_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Чтение регистра записи CON_TX — ловушка 9.
    def test_con_tx_read_traps(self):
        m = tk.small()
        dev.attach_console(m)
        self.assertEqual(
            tk.trap_code(lambda: bus.bus_read(m, dev.CON_TX)),
            uc.TRAP_BAD_PORT)


class TestTimer(unittest.TestCase):
    """Таймер: TMR_CYC — шаги, TMR_WALL — время узла (SPEC, 6А.3)."""

    # @method test_tmr_cyc_reads_machine_counter() -> None
    # @in    нет
    # @out   нет
    # @does  TMR_CYC читает счётчик шагов машины (SPEC, раздел 1).
    def test_tmr_cyc_reads_machine_counter(self):
        m = tk.small()
        dev.attach_timer(m)
        m.cyc = 7
        self.assertEqual(bus.bus_read(m, dev.TMR_CYC), 7)

    # @method test_tmr_cyc_counts_started_steps() -> None
    # @in    нет
    # @out   нет
    # @does  После прогона двух инструкций TMR_CYC равно двум: шаг
    # @does  считается в начале, до декодирования (SPEC, раздел 1).
    def test_tmr_cyc_counts_started_steps(self):
        m = tk.small()
        dev.attach_timer(m)
        tk.load_prog(m, [0x01, tk.imm64(5), 0x45, tk.imm64(0)])
        uvm_run.run(m)
        self.assertEqual(bus.bus_read(m, dev.TMR_CYC), 2)

    # @method test_tmr_wall_monotone_and_masked() -> None
    # @in    нет
    # @out   нет
    # @does  TMR_WALL не убывает от чтения к чтению и остаётся словом
    # @does  0..2^64-1; недетерминированное значение не проверяется.
    def test_tmr_wall_monotone_and_masked(self):
        m = tk.small()
        dev.attach_timer(m)
        first = bus.bus_read(m, dev.TMR_WALL)
        second = bus.bus_read(m, dev.TMR_WALL)
        self.assertLessEqual(first, second)
        self.assertLess(second, 1 << 64)

    # @method test_tmr_write_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Запись в регистры таймера — ловушка 9: оба только читаются.
    def test_tmr_write_traps(self):
        m = tk.small()
        dev.attach_timer(m)
        self.assertEqual(
            tk.trap_code(lambda: bus.bus_write(m, dev.TMR_CYC, 1)),
            uc.TRAP_BAD_PORT)
        self.assertEqual(
            tk.trap_code(lambda: bus.bus_write(m, dev.TMR_WALL, 1)),
            uc.TRAP_BAD_PORT)


class TestBlock(unittest.TestCase):
    """Хранилище: окно над байтами данных (SPEC, 6А.3)."""

    # @method test_blk_size_reports_data_len() -> None
    # @in    нет
    # @out   нет
    # @does  BLK_SIZE возвращает размер данных устройства в байтах.
    def test_blk_size_reports_data_len(self):
        m = tk.small()
        dev.attach_block(m, bytes(10))
        self.assertEqual(bus.bus_read(m, dev.BLK_SIZE), 10)

    # @method test_blk_addr_read_and_write() -> None
    # @in    нет
    # @out   нет
    # @does  BLK_ADDR: запись устанавливает окно (словом), чтение
    # @does  возвращает его.
    def test_blk_addr_read_and_write(self):
        m = tk.small()
        dev.attach_block(m, bytes(16))
        bus.bus_write(m, dev.BLK_ADDR, -2)
        self.assertEqual(bus.bus_read(m, dev.BLK_ADDR),
                         uc.WORD_MASK - 1)
        bus.bus_write(m, dev.BLK_ADDR, 3)
        self.assertEqual(bus.bus_read(m, dev.BLK_ADDR), 3)

    # @method test_blk_data_reads_word_le_and_advances() -> None
    # @in    нет
    # @out   нет
    # @does  BLK_DATA читает слово little-endian в окне и переносит
    # @does  окно на 8: следующее чтение даёт следующее слово.
    def test_blk_data_reads_word_le_and_advances(self):
        m = tk.small()
        data = bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
                      15, 16])
        dev.attach_block(m, data)
        self.assertEqual(bus.bus_read(m, dev.BLK_DATA),
                         0x0807060504030201)
        self.assertEqual(bus.bus_read(m, dev.BLK_DATA),
                         0x100F0E0D0C0B0A09)
        self.assertEqual(bus.bus_read(m, dev.BLK_ADDR), 16)

    # @method test_blk_data_window_jump_and_unaligned() -> None
    # @in    нет
    # @out   нет
    # @does  Окно BLK_ADDR задаёт точку чтения: без выравнивания слово
    # @does  собирается с любого байта.
    def test_blk_data_window_jump_and_unaligned(self):
        m = tk.small()
        data = bytes([9, 1, 2, 3, 4, 5, 6, 7, 8, 0, 0, 0, 0, 0, 0, 0])
        dev.attach_block(m, data)
        bus.bus_write(m, dev.BLK_ADDR, 1)
        self.assertEqual(bus.bus_read(m, dev.BLK_DATA),
                         0x0807060504030201)

    # @method test_blk_data_tail_and_beyond_read_zeros() -> None
    # @in    нет
    # @out   нет
    # @does  За концом данных и в хвосте короче восьми байтов читаются
    # @does  нули (SPEC, 6А.3).
    def test_blk_data_tail_and_beyond_read_zeros(self):
        m = tk.small()
        dev.attach_block(m, bytes([0xAB, 0xCD]))
        self.assertEqual(bus.bus_read(m, dev.BLK_DATA), 0xCDAB)
        bus.bus_write(m, dev.BLK_ADDR, 100)
        self.assertEqual(bus.bus_read(m, dev.BLK_DATA), 0)

    # @method test_blk_addr_window_wraps_mod_word() -> None
    # @in    нет
    # @out   нет
    # @does  Перенос окна на 8 идёт по модулю 2^64: чтение на границе
    # @does  слова переносит окно в начало адресного пространства.
    def test_blk_addr_window_wraps_mod_word(self):
        m = tk.small()
        dev.attach_block(m, bytes([1, 2, 3, 4, 5, 6, 7, 8]))
        bus.bus_write(m, dev.BLK_ADDR, uc.WORD_MASK)
        self.assertEqual(bus.bus_read(m, dev.BLK_DATA),
                         0)  # за концом данных — нули
        self.assertEqual(bus.bus_read(m, dev.BLK_ADDR), 7)

    # @method test_blk_data_and_size_write_trap() -> None
    # @in    нет
    # @out   нет
    # @does  Запись BLK_DATA и BLK_SIZE — ловушка 9: хранилище v0.3
    # @does  только читается (SPEC, 6А.4).
    def test_blk_data_and_size_write_trap(self):
        m = tk.small()
        dev.attach_block(m, bytes(8))
        self.assertEqual(
            tk.trap_code(lambda: bus.bus_write(m, dev.BLK_DATA, 1)),
            uc.TRAP_BAD_PORT)
        self.assertEqual(
            tk.trap_code(lambda: bus.bus_write(m, dev.BLK_SIZE, 1)),
            uc.TRAP_BAD_PORT)

    # @method test_block_data_is_copy() -> None
    # @in    нет
    # @out   нет
    # @does  Устройство хранит копию данных: изменение источника после
    # @does  привязки не видно (SPEC, 6А.4).
    def test_block_data_is_copy(self):
        m = tk.small()
        source = bytearray([1, 2, 3, 4, 5, 6, 7, 8])
        dev.attach_block(m, source)
        source[0] = 0xFF
        self.assertEqual(bus.bus_read(m, dev.BLK_DATA),
                         0x0807060504030201)


class TestStandardSet(unittest.TestCase):
    """Стандартный набор раннера: консоль и таймер (SPEC, 6А.4)."""

    # @method test_standard_set_binds_console_and_timer() -> None
    # @in    нет
    # @out   нет
    # @does  attach_standard привязывает ровно порты консоли и таймера.
    def test_standard_set_binds_console_and_timer(self):
        m = tk.small()
        dev.attach_standard(m)
        self.assertEqual(sorted(m.bus), [dev.CON_RX, dev.CON_TX,
                                         dev.TMR_CYC, dev.TMR_WALL])
        self.assertEqual(bus.bus_read(m, dev.TMR_CYC), 0)

    # @method test_standard_set_leaves_block_to_runner() -> None
    # @in    нет
    # @out   нет
    # @does  Хранилище в стандартный набор не входит: его порты до
    # @does  привязки — ловушка 9 (SPEC, 6А.4).
    def test_standard_set_leaves_block_to_runner(self):
        m = tk.small()
        dev.attach_standard(m)
        self.assertEqual(
            tk.trap_code(lambda: bus.bus_read(m, dev.BLK_SIZE)),
            uc.TRAP_BAD_PORT)


if __name__ == "__main__":
    unittest.main()
