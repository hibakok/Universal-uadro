# @uadro
# @file    tests/test_uvm_bus.py
# @layer   T0
# @branch  t0.uvm.bus
# @desc    Тесты механики шины устройств: привязка устройств к портам,
# @desc    замена устройства на занятом порту, ловушка 9 без шины
# @desc    и на непривязанном порту, маска слова шины
# @desc    (SPEC/L0-UVM.txt, 6А.1).

"""Тесты механики шины устройств (ветвь t0.uvm.bus, tools/uvm_bus.py).

Механика проверяется на поддельном устройстве FakeDev: оно записывает
обращения и отвечает заданным словом. Устройства стандартного набора
(консоль, таймер, хранилище) и привязка набора — tests/test_uvm_
devices.py. Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_bus as bus
from tools import uvm_core as uc


# @method FakeDev(answer) -> FakeDev
# @in    answer: int — слово, возвращаемое чтением (по умолчанию 0)
# @out   dev: FakeDev — поддельное устройство шины
# @does  Поддельное устройство для тестов механики шины: записывает
# @does  прочитанные порты в reads, записанные пары (порт, слово)
# @does  в writes и отвечает словом answer.
class FakeDev:
    """Поддельное устройство: пишет обращения, отвечает словом."""

    def __init__(self, answer=0):
        self.answer = answer
        self.reads = []
        self.writes = []

    def read(self, m, port):
        self.reads.append(port)
        return self.answer

    def write(self, m, port, w):
        self.writes.append((port, w))


class TestAttach(unittest.TestCase):
    """Привязка устройств к портам (SPEC, 6А.1)."""

    # @method test_attach_creates_bus_and_binds_ports() -> None
    # @in    нет
    # @out   нет
    # @does  Привязка создаёт шину на машине без шины и занимает порты.
    def test_attach_creates_bus_and_binds_ports(self):
        m = tk.small()
        dev = FakeDev()
        bus.attach_device(m, dev, (7, 9))
        self.assertIs(m.bus[7], dev)
        self.assertIs(m.bus[9], dev)

    # @method test_attach_keeps_other_ports() -> None
    # @in    нет
    # @out   нет
    # @does  Повторная привязка добавляет порты, не стирая прежние.
    def test_attach_keeps_other_ports(self):
        m = tk.small()
        first = FakeDev()
        second = FakeDev()
        bus.attach_device(m, first, (1,))
        bus.attach_device(m, second, (2,))
        self.assertIs(m.bus[1], first)
        self.assertIs(m.bus[2], second)

    # @method test_attach_rebind_replaces_device() -> None
    # @in    нет
    # @out   нет
    # @does  Привязка к занятому порту заменяет прежнее устройство
    # @does  (SPEC, 6А.1).
    def test_attach_rebind_replaces_device(self):
        m = tk.small()
        first = FakeDev()
        second = FakeDev()
        bus.attach_device(m, first, (5,))
        bus.attach_device(m, second, (5,))
        self.assertIs(m.bus[5], second)


class TestRefusal(unittest.TestCase):
    """Отказ устройства — ловушка 9 (SPEC, 6А.1)."""

    # @method test_read_without_bus_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Чтение порта на машине без шины — ловушка 9.
    def test_read_without_bus_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: bus.bus_read(m, 0)),
                         uc.TRAP_BAD_PORT)

    # @method test_write_without_bus_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Запись порта на машине без шины — ловушка 9.
    def test_write_without_bus_traps(self):
        m = tk.small()
        self.assertEqual(tk.trap_code(lambda: bus.bus_write(m, 0, 1)),
                         uc.TRAP_BAD_PORT)

    # @method test_read_unbound_port_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Чтение непривязанного порта на привязанной шине — ловушка 9.
    def test_read_unbound_port_traps(self):
        m = tk.small()
        bus.attach_device(m, FakeDev(), (1,))
        self.assertEqual(tk.trap_code(lambda: bus.bus_read(m, 2)),
                         uc.TRAP_BAD_PORT)

    # @method test_write_unbound_port_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Запись непривязанного порта на привязанной шине — ловушка 9.
    def test_write_unbound_port_traps(self):
        m = tk.small()
        bus.attach_device(m, FakeDev(), (1,))
        self.assertEqual(tk.trap_code(lambda: bus.bus_write(m, 2, 1)),
                         uc.TRAP_BAD_PORT)


class TestWordTransfer(unittest.TestCase):
    """Перенос слова между машиной и устройством (SPEC, 6А.1)."""

    # @method test_read_passes_port_and_masks_answer() -> None
    # @in    нет
    # @out   нет
    # @does  Чтение передаёт устройству машину и порт; ответ берётся
    # @does  по модулю 2^64 — слово шины всегда слово.
    def test_read_passes_port_and_masks_answer(self):
        m = tk.small()
        dev = FakeDev(answer=(1 << 64) + 5)
        bus.attach_device(m, dev, (3,))
        self.assertEqual(bus.bus_read(m, 3), 5)
        self.assertEqual(dev.reads, [3])

    # @method test_write_passes_port_and_masks_word() -> None
    # @in    нет
    # @out   нет
    # @does  Запись передаёт устройству порт и слово по модулю 2^64 —
    # @does  отрицательное становится словом.
    def test_write_passes_port_and_masks_word(self):
        m = tk.small()
        dev = FakeDev()
        bus.attach_device(m, dev, (3,))
        bus.bus_write(m, 3, -2)
        self.assertEqual(dev.writes, [(3, uc.WORD_MASK - 1)])

    # @method test_read_and_write_do_not_touch_stack() -> None
    # @in    нет
    # @out   нет
    # @does  Кирпичи шины не трогают стеки машины: перенос слова — дело
    # @does  инструкций DEV (SPEC, 6А.2), не механики шины.
    def test_read_and_write_do_not_touch_stack(self):
        m = tk.small()
        uc.ds_push(m, 111)
        dev = FakeDev(answer=77)
        bus.attach_device(m, dev, (0,))
        bus.bus_write(m, 0, 5)
        self.assertEqual(bus.bus_read(m, 0), 77)
        self.assertEqual(tk.stack_of(m), [111])


if __name__ == "__main__":
    unittest.main()
