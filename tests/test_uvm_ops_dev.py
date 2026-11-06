# @uadro
# @file    tests/test_uvm_ops_dev.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Тесты инструкций устройств DEVRD/DEVWR: чтение и запись слова
# @desc    порта, порядок операндов, ловушки 2 и 9, маска слова шины,
# @desc    проводка опкодов 0x52/0x53 через декодер и цикл запуска
# @desc    (SPEC/L0-UVM.txt, 6А.2).

"""Тесты инструкций устройств (ветвь t0.uvm.ops, tools/uvm_ops_dev.py).

Обработчики проверяются на блочном хранилище (BlockDev — детерминированное
устройство стандартного набора) и поддельном устройстве FakeDev: слова,
порядок операндов (порт — вершина), ловушки — пустой стек 2 до обращения,
отказ устройства 9 после снятия операндов; маска слова шины — по модулю
2^64. Проводка опкодов 0x52/0x53 — через декодер и цикл запуска
(t0.uvm.decode, t0.uvm.run); привязка стандартного набора в run_image —
таймером TMR_CYC (детерминированный порт) и портом CON_TX консоли
(интеграционные программы — tests/test_uasm_integration.py). Запуск
из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tests import uvm_testkit as tk
from tools import uvm_bus as bus
from tools import uvm_core as uc
from tools import uvm_devices as devs
from tools import uvm_ops_dev as ops
from tools import uvm_run as rn


# @method FakeDev(answer) -> FakeDev
# @in    answer: int — слово, возвращаемое чтением (по умолчанию 0)
# @out   dev: FakeDev — поддельное устройство шины
# @does  Поддельное устройство для тестов инструкций DEV: записывает
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


class TestDevrd(unittest.TestCase):
    """DEVRD ( порт -- w ): чтение слова порта (SPEC, 6А.2)."""

    # @method test_devrd_reads_port_word() -> None
    # @in    нет
    # @out   нет
    # @does  DEVRD снимает порт и кладёт слово устройства: поддельное
    # @does  устройство ответило словом, порт снят, обращение записано.
    def test_devrd_reads_port_word(self):
        m = tk.small()
        dev = FakeDev(answer=0xAB)
        bus.attach_device(m, dev, (7,))
        m.ds.extend([7])
        ops.op_devrd(m, 0)
        self.assertEqual(tk.stack_of(m), [0xAB])
        self.assertEqual(dev.reads, [7])

    # @method test_devrd_reads_block_size() -> None
    # @in    нет
    # @out   нет
    # @does  DEVRD на реальном устройстве: BLK_SIZE блочного хранилища
    # @does  возвращает размер данных в байтах.
    def test_devrd_reads_block_size(self):
        m = tk.small()
        devs.attach_block(m, b"12345678")
        m.ds.extend([devs.BLK_SIZE])
        ops.op_devrd(m, 0)
        self.assertEqual(tk.stack_of(m), [8])

    # @method test_devrd_without_bus_traps_9() -> None
    # @in    нет
    # @out   нет
    # @does  Машина без шины: DEVRD снимает порт и даёт ловушку 9 —
    # @does  стек после снятия пуст.
    def test_devrd_without_bus_traps_9(self):
        m = tk.small()
        m.ds.extend([devs.BLK_SIZE])
        code = tk.trap_code(lambda: ops.op_devrd(m, 0))
        self.assertEqual(code, uc.TRAP_BAD_PORT)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_devrd_unbound_port_traps_9() -> None
    # @in    нет
    # @out   нет
    # @does  Порт не привязан к шине: ловушка 9 после снятия порта.
    def test_devrd_unbound_port_traps_9(self):
        m = tk.small()
        devs.attach_block(m, b"data")
        m.ds.extend([0x2F])          # CSR-порт не привязан в v0.3
        code = tk.trap_code(lambda: ops.op_devrd(m, 0))
        self.assertEqual(code, uc.TRAP_BAD_PORT)

    # @method test_devrd_empty_stack_traps_2() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой стек: ловушка 2 до обращения к шине — устройство
    # @does  не тронуто (обращений нет).
    def test_devrd_empty_stack_traps_2(self):
        m = tk.small()
        dev = FakeDev()
        bus.attach_device(m, dev, (7,))
        code = tk.trap_code(lambda: ops.op_devrd(m, 0))
        self.assertEqual(code, uc.TRAP_DS_EMPTY)
        self.assertEqual(dev.reads, [])

    # @method test_devrd_writeonly_port_traps_9() -> None
    # @in    нет
    # @out   нет
    # @does  Чтение регистра записи запрещено направлением: DEVRD порта
    # @does  CON_TX (только запись) — ловушка 9.
    def test_devrd_writeonly_port_traps_9(self):
        m = tk.small()
        bus.attach_device(m, devs.ConsoleDev(), (devs.CON_TX,))
        m.ds.extend([devs.CON_TX])
        code = tk.trap_code(lambda: ops.op_devrd(m, 0))
        self.assertEqual(code, uc.TRAP_BAD_PORT)

    # @method test_devrd_keeps_pc() -> None
    # @in    нет
    # @out   нет
    # @does  Обработчик DEVRD не трогает PC — как все обработчики без
    # @does  переходов.
    def test_devrd_keeps_pc(self):
        m = tk.small()
        dev = FakeDev()
        bus.attach_device(m, dev, (7,))
        m.ds.extend([7])
        m.pc = 12
        ops.op_devrd(m, 0)
        self.assertEqual(m.pc, 12)


class TestDevwr(unittest.TestCase):
    """DEVWR ( w порт -- ): запись слова в порт (SPEC, 6А.2)."""

    # @method test_devwr_writes_port_word() -> None
    # @in    нет
    # @out   нет
    # @does  DEVWR снимает слово (глубже) и порт (вершина), передаёт
    # @does  слово устройству; стек пуст.
    def test_devwr_writes_port_word(self):
        m = tk.small()
        dev = FakeDev()
        bus.attach_device(m, dev, (7,))
        m.ds.extend([0xAB, 7])       # слово глубже, порт на вершине
        ops.op_devwr(m, 0)
        self.assertEqual(tk.stack_of(m), [])
        self.assertEqual(dev.writes, [(7, 0xAB)])

    # @method test_devwr_sets_block_window() -> None
    # @in    нет
    # @out   нет
    # @does  DEVWR на реальном устройстве: запись BLK_ADDR переносит окно
    # @does  хранилища, следующее чтение BLK_DATA читает слово с нового
    # @does  места.
    def test_devwr_sets_block_window(self):
        m = tk.small()
        devs.attach_block(m, b"ABCDEFGH" + b"IJKLMNOP")
        m.ds.extend([8, devs.BLK_ADDR])
        ops.op_devwr(m, 0)
        m.ds.extend([devs.BLK_DATA])
        ops.op_devrd(m, 0)
        self.assertEqual(tk.stack_of(m), [int.from_bytes(b"IJKLMNOP",
                                                         "little")])

    # @method test_devwr_word_is_masked() -> None
    # @in    нет
    # @out   нет
    # @does  Слово шины — по модулю 2^64: запись 2^64 + 5 в BLK_ADDR
    # @does  ставит окно в 5.
    def test_devwr_word_is_masked(self):
        m = tk.small()
        block = devs.BlockDev(b"12345678")
        bus.attach_device(m, block, (devs.BLK_ADDR, devs.BLK_DATA))
        m.ds.extend([(1 << 64) + 5, devs.BLK_ADDR])
        ops.op_devwr(m, 0)
        self.assertEqual(block.pos, 5)

    # @method test_devwr_without_bus_traps_9() -> None
    # @in    нет
    # @out   нет
    # @does  Машина без шины: DEVWR снимает оба операнда и даёт
    # @does  ловушку 9 — стек после снятия пуст.
    def test_devwr_without_bus_traps_9(self):
        m = tk.small()
        m.ds.extend([1, devs.BLK_ADDR])
        code = tk.trap_code(lambda: ops.op_devwr(m, 0))
        self.assertEqual(code, uc.TRAP_BAD_PORT)
        self.assertEqual(tk.stack_of(m), [])

    # @method test_devwr_empty_stacks_trap_2() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой стек и один операнд: ловушка 2 до обращения к шине —
    # @does  устройство не тронуто.
    def test_devwr_empty_stacks_trap_2(self):
        m = tk.small()
        dev = FakeDev()
        bus.attach_device(m, dev, (7,))
        self.assertEqual(tk.trap_code(lambda: ops.op_devwr(m, 0)),
                         uc.TRAP_DS_EMPTY)
        m.ds.extend([7])
        self.assertEqual(tk.trap_code(lambda: ops.op_devwr(m, 0)),
                         uc.TRAP_DS_EMPTY)
        self.assertEqual(dev.writes, [])

    # @method test_devwr_readonly_port_traps_9() -> None
    # @in    нет
    # @out   нет
    # @does  Запись регистра чтения запрещена направлением: DEVWR в порт
    # @does  BLK_DATA (только чтение) — ловушка 9 после снятия операндов.
    def test_devwr_readonly_port_traps_9(self):
        m = tk.small()
        devs.attach_block(m, b"data")
        m.ds.extend([1, devs.BLK_DATA])
        code = tk.trap_code(lambda: ops.op_devwr(m, 0))
        self.assertEqual(code, uc.TRAP_BAD_PORT)

    # @method test_devwr_keeps_pc() -> None
    # @in    нет
    # @out   нет
    # @does  Обработчик DEVWR не трогает PC.
    def test_devwr_keeps_pc(self):
        m = tk.small()
        dev = FakeDev()
        bus.attach_device(m, dev, (7,))
        m.ds.extend([1, 7])
        m.pc = 12
        ops.op_devwr(m, 0)
        self.assertEqual(m.pc, 12)


class TestDevWiring(unittest.TestCase):
    """Опкоды 0x52/0x53 через декодер и цикл запуска (SPEC, 6А.2)."""

    # @method test_devrd_opcode_runs_in_cycle() -> None
    # @in    нет
    # @out   нет
    # @does  Байт 0x52 исполняется как DEVRD: на машине без шины цикл
    # @does  run завершается ловушкой 9.
    def test_devrd_opcode_runs_in_cycle(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(devs.BLK_SIZE),
                         0x52,                # DEVRD — машины без шины
                         0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), uc.TRAP_BAD_PORT)

    # @method test_devwr_opcode_runs_in_cycle() -> None
    # @in    нет
    # @out   нет
    # @does  Байт 0x53 исполняется как DEVWR: на машине без шины цикл
    # @does  run завершается ловушкой 9.
    def test_devwr_opcode_runs_in_cycle(self):
        m = tk.small()
        tk.load_prog(m, [0x01, tk.imm64(1),
                         0x01, tk.imm64(devs.BLK_ADDR),
                         0x53,                # DEVWR — машины без шины
                         0x45, tk.imm64(0)])
        self.assertEqual(rn.run(m), uc.TRAP_BAD_PORT)

    # @method test_run_image_reads_timer_cycle() -> None
    # @in    нет
    # @out   нет
    # @does  run_image привязывает стандартный набор (SPEC, 6А.4):
    # @does  DEVRD порта TMR_CYC возвращает CYC на момент чтения — PUSH
    # @does  (шаг 1), DEVRD (шаг 2) — на стеке слово 2.
    def test_run_image_reads_timer_cycle(self):
        image = bytes([0x01]) + tk.imm64(devs.TMR_CYC) \
            + bytes([0x52, 0x45]) + tk.imm64(0)
        m, code = rn.run_image(image)
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [2])


if __name__ == "__main__":
    unittest.main()
