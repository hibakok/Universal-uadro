# @uadro
# @file    tools/uvm_devices.py
# @layer   T0
# @branch  t0.uvm.bus
# @desc    Устройства стандартного набора шины UVM v0.3: консоль, таймер,
# @desc    блочное хранилище; привязка набора к машине (SPEC/L0-UVM.txt,
# @desc    6А.3-6А.4).

"""Устройства стандартного набора шины UVM v0.3 (ветвь t0.uvm.bus).

Три устройства карты портов v1 (SPEC/L0-UVM.txt, 6А.3): консоль
(CON_RX — байт ввода, CON_TX — вывод), таймер (TMR_CYC — счётчик
шагов машины, TMR_WALL — миллисекунды узла-хоста) и блочное
хранилище (BLK_ADDR/BLK_DATA/BLK_SIZE — окно над байтами данных).
Каждое устройство — пара операций read(m, порт) / write(m, порт, w)
(контракт 6А.4); направления портов нарушать нельзя — ловушка 9.
Механика шины (привязка, перенос слова) — tools/uvm_bus.py.
"""

import time

from tools.uvm_bus import attach_device
from tools.uvm_core import WORD_MASK, TRAP_BAD_PORT, trap
from tools.uvm_ops_sys import host_read_byte, host_write_byte

CON_RX = 0x00   # консоль: байт ввода (все единицы — конец ввода)
CON_TX = 0x01   # консоль: младший байт слова — в вывод
TMR_CYC = 0x10  # таймер: значение CYC (SPEC, раздел 1)
TMR_WALL = 0x11  # таймер: мс монотонных часов узла-хоста
BLK_ADDR = 0x20  # хранилище: окно данных в байтах
BLK_DATA = 0x21  # хранилище: слово в окне, окно += 8
BLK_SIZE = 0x22  # хранилище: размер данных в байтах


# @method ConsoleDev() -> ConsoleDev
# @in    нет
# @out   dev: ConsoleDev — устройство консоли без своего состояния
# @does  Консоль карты портов v1: CON_RX читает байт ввода узла-хоста
# @does  (в конце ввода — все единицы), CON_TX пишет младший байт
# @does  в вывод (SPEC, 6А.3); мост узла-хоста — общие кирпичи
# @does  host_read_byte/host_write_byte (6А.4).
# @depends host_read_byte, host_write_byte, trap
class ConsoleDev:
    """Консоль: ввод-вывод байтов узла-хоста (SPEC, 6А.3)."""

    def read(self, m, port):
        if port == CON_RX:
            return host_read_byte()
        trap(TRAP_BAD_PORT)

    def write(self, m, port, w):
        if port == CON_TX:
            host_write_byte(w)
        else:
            trap(TRAP_BAD_PORT)


# @method TimerDev() -> TimerDev
# @in    нет
# @out   dev: TimerDev — устройство таймера
# @does  Таймер карты портов v1: TMR_CYC читает счётчик шагов машины
# @does  (SPEC, раздел 1), TMR_WALL — миллисекунды монотонных часов
# @does  узла-хоста от точки нуля — момента создания устройства
# @does  (SPEC, 6А.3-6А.4); оба регистра только читаются.
# @uses  time.monotonic — монотонные часы узла-хоста (Python)
class TimerDev:
    """Таймер: шаги машины и время узла-хоста (SPEC, 6А.3)."""

    def __init__(self):
        self.zero = time.monotonic()

    def read(self, m, port):
        if port == TMR_CYC:
            return m.cyc
        if port == TMR_WALL:
            return wall_ms(self)
        trap(TRAP_BAD_PORT)

    def write(self, m, port, w):
        trap(TRAP_BAD_PORT)


# @method wall_ms(dev) -> int
# @in    dev: TimerDev — устройство таймера
# @out   ms: int — миллисекунды от точки нуля устройства, по модулю
# @out   2^64
# @does  Даёт текущее значение TMR_WALL: монотонные часы узла-хоста
# @does  минус точка нуля, в миллисекундах, словом по модулю 2^64
# @does  (SPEC, 6А.3). Недетерминировано — исключение детерминизма
# @does  (раздел 1).
# @uses  time.monotonic — монотонные часы узла-хоста (Python)
def wall_ms(dev):
    return int((time.monotonic() - dev.zero) * 1000) & WORD_MASK


# @method word_at(data, pos) -> int
# @in    data: bytes — байты данных устройства
# @in    pos: int — позиция младшего байта слова (64-битное слово)
# @out   w: int — 8 байтов little-endian с позиции pos
# @does  Собирает слово из байтов данных: за концом данных и в хвосте
# @does  короче восьми байтов читаются нули (SPEC, 6А.3 — BLK_DATA).
def word_at(data, pos):
    chunk = bytes(data[pos:pos + 8])
    if len(chunk) < 8:
        chunk = chunk.ljust(8, b"\x00")
    return int.from_bytes(chunk, "little")


# @method block_word(dev) -> int
# @in    dev: BlockDev — устройство хранилища
# @out   w: int — слово в текущем окне
# @does  Читает BLK_DATA: слово LE в окне устройства, затем окно
# @does  переносится на 8 вперёд по модулю 2^64 (SPEC, 6А.3).
# @depends word_at
def block_word(dev):
    w = word_at(dev.data, dev.pos)
    dev.pos = (dev.pos + 8) & WORD_MASK
    return w


# @method BlockDev(data) -> BlockDev
# @in    data: bytes-like — байты данных устройства; хранится копией
# @out   dev: BlockDev — устройство хранилища, окно в нуле
# @does  Блочное хранилище карты портов v1 (SPEC, 6А.3): BLK_ADDR —
# @does  окно в байтах (чтение и запись), BLK_DATA — чтение слова LE
# @does  в окне с переносом окна на 8, BLK_SIZE — размер данных;
# @does  запись BLK_DATA/BLK_SIZE — ловушка 9 (хранилище v0.3 только
# @does  читается, 6А.4); данные копируются при создании — источник
# @does  дальше не виден.
# @depends block_word, trap
class BlockDev:
    """Блочное хранилище: окно над байтами данных (SPEC, 6А.3)."""

    def __init__(self, data):
        self.data = bytes(data)
        self.pos = 0

    def read(self, m, port):
        if port == BLK_ADDR:
            return self.pos
        if port == BLK_DATA:
            return block_word(self)
        if port == BLK_SIZE:
            return len(self.data)
        trap(TRAP_BAD_PORT)

    def write(self, m, port, w):
        if port == BLK_ADDR:
            self.pos = w & WORD_MASK
        else:
            trap(TRAP_BAD_PORT)


# @method attach_console(m) -> None
# @in    m: Machine — состояние машины
# @out   нет
# @does  Привязывает устройство консоли к портам CON_RX и CON_TX
# @does  (SPEC, 6А.3); кирпич attach_standard.
# @depends attach_device, ConsoleDev
def attach_console(m):
    attach_device(m, ConsoleDev(), (CON_RX, CON_TX))


# @method attach_timer(m) -> None
# @in    m: Machine — состояние машины
# @out   нет
# @does  Привязывает устройство таймера к портам TMR_CYC и TMR_WALL;
# @does  точка нуля TMR_WALL — момент привязки (SPEC, 6А.3-6А.4);
# @does  кирпич attach_standard.
# @depends attach_device, TimerDev
def attach_timer(m):
    attach_device(m, TimerDev(), (TMR_CYC, TMR_WALL))


# @method attach_block(m, data) -> None
# @in    m: Machine — состояние машины
# @in    data: bytes-like — байты данных хранилища
# @out   нет
# @does  Привязывает блочное хранилище к портам BLK_ADDR, BLK_DATA
# @does  и BLK_SIZE (SPEC, 6А.3); раннер вызывает по своему решению
# @does  (6А.4, подшаг 5.5).
# @depends attach_device, BlockDev
def attach_block(m, data):
    attach_device(m, BlockDev(data), (BLK_ADDR, BLK_DATA, BLK_SIZE))


# @method attach_standard(m) -> None
# @in    m: Machine — состояние машины
# @out   нет
# @does  Привязывает стандартный набор раннера — консоль и таймер
# @does  (SPEC, 6А.4): программа рассчитывает на них всегда.
# @depends attach_console, attach_timer
def attach_standard(m):
    attach_console(m)
    attach_timer(m)
