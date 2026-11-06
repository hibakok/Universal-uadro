# @uadro
# @file    tools/uvm_bus.py
# @layer   T0
# @branch  t0.uvm.bus
# @desc    Шина устройств UVM v0.3: привязка устройств к портам, чтение
# @desc    и запись слова по порту, ловушка 9 (SPEC/L0-UVM.txt, 6А.1).

"""Шина устройств UVM v0.3 (ветвь t0.uvm.bus).

Шина — таблица «порт -> устройство», живущая в Machine.bus (None, пока
раннер не привязал устройства). Кирпичи файла — механика шины:
attach_device привязывает устройство к портам, bus_read и bus_write
переносят слово между машиной и устройством, отказ — ловушка 9
(SPEC/L0-UVM.txt, 6А.1). Устройства стандартного набора (консоль,
таймер, блочное хранилище) — tools/uvm_devices.py той же ветви;
слой эталона не знает конкретных устройств. Инструкции DEVRD/DEVWR
(раздел 6А.2) войдут в таблицу опкодов подшагом 5.2 — до этого шину
читают и пишут раннер и тесты.
"""

from tools.uvm_core import WORD_MASK, TRAP_BAD_PORT, trap


# @method attach_device(m, dev, ports) -> None
# @in    m: Machine — состояние машины; шины может не быть
# @in    dev: object — устройство: read(m, порт) и write(m, порт, w)
# @in    ports: iterable — порты устройства (64-битные слова)
# @out   нет
# @does  Привязывает устройство к шине машины на указанные порты;
# @does  шины нет — создаётся пустая; повторная привязка занятого
# @does  порта заменяет прежнее устройство на нём (SPEC, 6А.1).
# @uses  m.bus — таблица «порт -> устройство» машины
def attach_device(m, dev, ports):
    if m.bus is None:
        m.bus = {}
    for port in ports:
        m.bus[port] = dev


# @method bus_read(m, port) -> int
# @in    m: Machine — состояние машины
# @in    port: int — порт устройства
# @out   w: int — 64-битное слово, прочитанное устройством по порту
# @does  Читает слово порта (SPEC, 6А.1): машина без шины или порт
# @does  не привязан — ловушка 9; ответ устройства берётся по модулю
# @does  2^64 — слово шины всегда слово (раздел 1).
# @depends trap
# @uses  m.bus — таблица «порт -> устройство» машины
def bus_read(m, port):
    bus = m.bus
    if bus is None or port not in bus:
        trap(TRAP_BAD_PORT)
    return bus[port].read(m, port) & WORD_MASK


# @method bus_write(m, port, w) -> None
# @in    m: Machine — состояние машины
# @in    port: int — порт устройства
# @in    w: int — записываемое слово; берётся по модулю 2^64
# @out   нет
# @does  Пишет слово в порт (SPEC, 6А.1): машина без шины или порт
# @does  не привязан — ловушка 9; устройству передаётся слово
# @does  по модулю 2^64 — слово шины всегда слово (раздел 1).
# @depends trap
# @uses  m.bus — таблица «порт -> устройство» машины
def bus_write(m, port, w):
    bus = m.bus
    if bus is None or port not in bus:
        trap(TRAP_BAD_PORT)
    bus[port].write(m, port, w & WORD_MASK)
