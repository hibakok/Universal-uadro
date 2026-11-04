# @uadro
# @file    tests/test_uvm_core.py
# @layer   T0
# @branch  t0.uvm.core
# @desc    Тесты ядра UVM: слова, ловушки, остановка, ОЗУ, стеки DS/RS
# @desc    и загрузка образа.

"""Тесты ветви t0.uvm.core (tools/uvm_core.py) по SPEC/L0-UVM.txt.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc


class TestWordBricks(unittest.TestCase):
    """Слова и байты (SPEC, раздел 1)."""

    # @method test_to_word_wraps() -> None
    # @in    нет
    # @out   нет
    # @does  Переполнения оборачиваются по модулю 2^64.
    def test_to_word_wraps(self):
        self.assertEqual(uc.to_word(123), 123)
        self.assertEqual(uc.to_word(1 << 64), 0)
        self.assertEqual(uc.to_word(-1), uc.WORD_MASK)

    # @method test_to_byte_masks() -> None
    # @in    нет
    # @out   нет
    # @does  Остаются младшие 8 бит значения.
    def test_to_byte_masks(self):
        self.assertEqual(uc.to_byte(0x1FF), 0xFF)
        self.assertEqual(uc.to_byte(256), 0)
        self.assertEqual(uc.to_byte(-2), 0xFE)

    # @method test_to_signed_reads_twos_complement() -> None
    # @in    нет
    # @out   нет
    # @does  Слова читаются как знаковые в дополнительном коде: 5 — 5,
    # @does  WORD_MASK — -1, 2^63 — -2^63, 2^63+5 — -2^63+5.
    def test_to_signed_reads_twos_complement(self):
        self.assertEqual(uc.to_signed(5), 5)
        self.assertEqual(uc.to_signed(uc.WORD_MASK), -1)
        self.assertEqual(uc.to_signed(1 << 63), -(1 << 63))
        self.assertEqual(uc.to_signed((1 << 63) + 5), -(1 << 63) + 5)

    # @method test_to_signed_wraps_input_first() -> None
    # @in    нет
    # @out   нет
    # @does  to_signed сначала оборачивает вход в слово по модулю 2^64.
    def test_to_signed_wraps_input_first(self):
        self.assertEqual(uc.to_signed((1 << 64) + 5), 5)
        self.assertEqual(uc.to_signed(-1), -1)


class TestTraps(unittest.TestCase):
    """Ловушки и их коды (SPEC, раздел 3)."""

    # @method test_trap_raises_with_code() -> None
    # @in    нет
    # @out   нет
    # @does  trap поднимает UvmTrap с переданным кодом.
    def test_trap_raises_with_code(self):
        with self.assertRaises(uc.UvmTrap) as ctx:
            uc.trap(7)
        self.assertEqual(ctx.exception.code, 7)

    # @method test_trap_codes_match_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Коды ловушек 1..8 соответствуют таблице раздела 3 SPEC.
    def test_trap_codes_match_spec(self):
        codes = [
            uc.TRAP_DIV0, uc.TRAP_DS_EMPTY, uc.TRAP_DS_FULL,
            uc.TRAP_RS_EMPTY, uc.TRAP_RS_FULL, uc.TRAP_BAD_OPCODE,
            uc.TRAP_OOB, uc.TRAP_BAD_SYS,
        ]
        self.assertEqual(codes, list(range(1, 9)))


class TestHalt(unittest.TestCase):
    """Нормальная остановка HALT (SPEC, раздел 5)."""

    # @method test_halt_carries_code() -> None
    # @in    нет
    # @out   нет
    # @does  UvmHalt несёт код завершения.
    def test_halt_carries_code(self):
        exc = uc.UvmHalt(44)
        self.assertEqual(exc.code, 44)

    # @method test_halt_is_not_trap() -> None
    # @in    нет
    # @out   нет
    # @does  UvmHalt — не UvmTrap: цикл запуска отличит нормальную
    # @does  остановку от аварийной ловушки.
    def test_halt_is_not_trap(self):
        self.assertNotIsInstance(uc.UvmHalt(0), uc.UvmTrap)


class TestMachineState(unittest.TestCase):
    """Свежее состояние машины (SPEC, разделы 1-2)."""

    # @method test_default_sizes() -> None
    # @in    нет
    # @out   нет
    # @does  По умолчанию: ОЗУ 1 МиБ, DS 1024 слова, RS 256 слов.
    def test_default_sizes(self):
        m = uc.Machine()
        self.assertEqual(len(m.ram), 1048576)
        self.assertEqual(m.ds_size, 1024)
        self.assertEqual(m.rs_size, 256)

    # @method test_fresh_state() -> None
    # @in    нет
    # @out   нет
    # @does  Свежая машина: PC = 0, стеки пусты, ОЗУ из нулей.
    def test_fresh_state(self):
        m = uc.Machine(ram_size=10)
        self.assertEqual(m.pc, 0)
        self.assertEqual(m.ds, [])
        self.assertEqual(m.rs, [])
        self.assertEqual(bytes(m.ram), bytes(10))


class TestRam(unittest.TestCase):
    """ОЗУ: байты, слова little-endian, границы (SPEC, раздел 1)."""

    # @method test_byte_roundtrip() -> None
    # @in    нет
    # @out   нет
    # @does  store_byte пишет, load_byte читает тот же байт.
    def test_byte_roundtrip(self):
        m = tk.small(16)
        uc.store_byte(m, 0, 255)
        uc.store_byte(m, 15, 1)
        self.assertEqual(uc.load_byte(m, 0), 255)
        self.assertEqual(uc.load_byte(m, 15), 1)

    # @method test_store_byte_keeps_low_bits() -> None
    # @in    нет
    # @out   нет
    # @does  Примитив записи хранит младший байт значения.
    def test_store_byte_keeps_low_bits(self):
        m = tk.small(16)
        uc.store_byte(m, 3, 300)
        self.assertEqual(uc.load_byte(m, 3), 44)

    # @method test_byte_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Обращение вне ОЗУ — ловушка 7 и на чтение, и на запись.
    def test_byte_out_of_ram_traps(self):
        m = tk.small(16)
        self.assertEqual(tk.trap_code(lambda: uc.load_byte(m, 16)),
                         uc.TRAP_OOB)
        self.assertEqual(tk.trap_code(lambda: uc.load_byte(m, -1)),
                         uc.TRAP_OOB)
        self.assertEqual(tk.trap_code(lambda: uc.store_byte(m, 16, 1)),
                         uc.TRAP_OOB)

    # @method test_word_little_endian() -> None
    # @in    нет
    # @out   нет
    # @does  store_word раскладывает слово от младшего байта к старшему.
    def test_word_little_endian(self):
        m = tk.small(16)
        uc.store_word(m, 0, 0x0102030405060708)
        self.assertEqual(bytes(m.ram[0:8]), bytes([8, 7, 6, 5, 4, 3, 2, 1]))

    # @method test_word_roundtrip_unaligned() -> None
    # @in    нет
    # @out   нет
    # @does  store_word/load_word восстанавливают слово без выравнивания.
    def test_word_roundtrip_unaligned(self):
        m = tk.small(16)
        for addr in (0, 3, 8):
            uc.store_word(m, addr, 0x1122334455667788)
            self.assertEqual(uc.load_word(m, addr), 0x1122334455667788)
        uc.store_word(m, 0, uc.WORD_MASK)
        self.assertEqual(uc.load_word(m, 0), uc.WORD_MASK)

    # @method test_word_beyond_64_bits_wraps() -> None
    # @in    нет
    # @out   нет
    # @does  Значение старше 64 бит усекается до младших 64 бит.
    def test_word_beyond_64_bits_wraps(self):
        m = tk.small(16)
        uc.store_word(m, 0, 1 << 70)
        self.assertEqual(uc.load_word(m, 0), 0)

    # @method test_word_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Слово, не поместившееся в ОЗУ, — ловушка 7 (границу
    # @does  проверяет каждый байт-кирпич).
    def test_word_out_of_ram_traps(self):
        m = tk.small(8)
        self.assertEqual(tk.trap_code(lambda: uc.load_word(m, 1)),
                         uc.TRAP_OOB)
        self.assertEqual(tk.trap_code(lambda: uc.store_word(m, 2, 5)),
                         uc.TRAP_OOB)


class TestImage(unittest.TestCase):
    """Загрузка образа (SPEC, раздел 2)."""

    # @method test_load_image_copies_and_resets() -> None
    # @in    нет
    # @out   нет
    # @does  Образ копируется с адреса 0; PC = 0; DS и RS пусты.
    def test_load_image_copies_and_resets(self):
        m = tk.small(16)
        m.pc = 9
        m.ds.append(1)
        m.rs.append(2)
        uc.load_image(m, b"\x01\x02\xff")
        self.assertEqual(bytes(m.ram[0:3]), b"\x01\x02\xff")
        self.assertEqual(m.pc, 0)
        self.assertEqual(m.ds, [])
        self.assertEqual(m.rs, [])

    # @method test_load_image_too_big_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Образ больше ОЗУ — ловушка 7.
    def test_load_image_too_big_traps(self):
        m = tk.small(4)
        self.assertEqual(
            tk.trap_code(lambda: uc.load_image(m, b"12345")),
            uc.TRAP_OOB)


class TestDataStack(unittest.TestCase):
    """Стек данных DS (SPEC, разделы 1 и 3)."""

    # @method test_push_pop_lifo() -> None
    # @in    нет
    # @out   нет
    # @does  DS работает как LIFO.
    def test_push_pop_lifo(self):
        m = tk.small()
        uc.ds_push(m, 1)
        uc.ds_push(m, 2)
        uc.ds_push(m, 3)
        self.assertEqual(uc.ds_pop(m), 3)
        self.assertEqual(uc.ds_pop(m), 2)
        self.assertEqual(uc.ds_pop(m), 1)

    # @method test_push_wraps_to_64_bits() -> None
    # @in    нет
    # @out   нет
    # @does  На DS кладётся слово по модулю 2^64.
    def test_push_wraps_to_64_bits(self):
        m = tk.small()
        uc.ds_push(m, (1 << 64) + 5)
        self.assertEqual(uc.ds_pop(m), 5)
        uc.ds_push(m, -1)
        self.assertEqual(uc.ds_pop(m), uc.WORD_MASK)

    # @method test_pop_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Снятие с пустого DS — ловушка 2.
    def test_pop_empty_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: uc.ds_pop(m)),
                         uc.TRAP_DS_EMPTY)

    # @method test_push_overflow_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Клад сверх ёмкости DS — ловушка 3.
    def test_push_overflow_traps(self):
        m = tk.small(ds_size=3)
        uc.ds_push(m, 1)
        uc.ds_push(m, 2)
        uc.ds_push(m, 3)
        self.assertEqual(tk.trap_code(lambda: uc.ds_push(m, 4)),
                         uc.TRAP_DS_FULL)

    # @method test_pop2_returns_operands_in_order() -> None
    # @in    нет
    # @out   нет
    # @does  ds_pop2 даёт (a, b): a — глубже (первый операнд), b —
    # @does  вершина (второй операнд).
    def test_pop2_returns_operands_in_order(self):
        m = tk.small()
        uc.ds_push(m, 1)
        uc.ds_push(m, 2)
        self.assertEqual(uc.ds_pop2(m), (1, 2))

    # @method test_pop2_needs_two_words() -> None
    # @in    нет
    # @out   нет
    # @does  Меньше двух слов на DS — ловушка 2.
    def test_pop2_needs_two_words(self):
        m = tk.small()
        uc.ds_push(m, 1)
        self.assertEqual(tk.trap_code(lambda: uc.ds_pop2(m)),
                         uc.TRAP_DS_EMPTY)

    # @method test_pick_returns_depth_copy() -> None
    # @in    нет
    # @out   нет
    # @does  PICK-примитив: глубина 0 — вершина, глубже — старее; копия
    # @does  не снимается (0 = DUP, 1 = OVER).
    def test_pick_returns_depth_copy(self):
        m = tk.small()
        uc.ds_push(m, 10)
        uc.ds_push(m, 20)
        uc.ds_push(m, 30)
        self.assertEqual(uc.ds_pick(m, 0), 30)
        self.assertEqual(uc.ds_pick(m, 1), 20)
        self.assertEqual(uc.ds_pick(m, 2), 10)
        self.assertEqual(len(m.ds), 3)

    # @method test_pick_out_of_stack_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Глубина вне стека — ловушка 2.
    def test_pick_out_of_stack_traps(self):
        m = tk.small()
        uc.ds_push(m, 10)
        self.assertEqual(tk.trap_code(lambda: uc.ds_pick(m, 1)),
                         uc.TRAP_DS_EMPTY)
        self.assertEqual(tk.trap_code(lambda: uc.ds_pick(m, -1)),
                         uc.TRAP_DS_EMPTY)


class TestReturnStack(unittest.TestCase):
    """Стек возвратов RS (SPEC, разделы 1 и 3)."""

    # @method test_push_pop_lifo() -> None
    # @in    нет
    # @out   нет
    # @does  RS работает как LIFO и держит 64-битные слова.
    def test_push_pop_lifo(self):
        m = tk.small()
        uc.rs_push(m, 7)
        uc.rs_push(m, (1 << 64) + 1)
        self.assertEqual(uc.rs_pop(m), 1)
        self.assertEqual(uc.rs_pop(m), 7)

    # @method test_pop_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Снятие с пустого RS — ловушка 4.
    def test_pop_empty_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: uc.rs_pop(m)),
                         uc.TRAP_RS_EMPTY)

    # @method test_push_overflow_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Клад сверх ёмкости RS — ловушка 5.
    def test_push_overflow_traps(self):
        m = tk.small(rs_size=2)
        uc.rs_push(m, 1)
        uc.rs_push(m, 2)
        self.assertEqual(tk.trap_code(lambda: uc.rs_push(m, 3)),
                         uc.TRAP_RS_FULL)


if __name__ == "__main__":
    unittest.main()
