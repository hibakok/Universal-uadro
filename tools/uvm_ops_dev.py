# @uadro
# @file    tools/uvm_ops_dev.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Обработчики инструкций устройств DEVRD и DEVWR: чтение и запись
# @desc    слова порта через шину (SPEC/L0-UVM.txt, раздел 6А.2).

"""Инструкции устройств UVM v0.3 (ветвь t0.uvm.ops).

DEVRD и DEVWR — обращения к шине устройств (SPEC/L0-UVM.txt, 6А.2):
переносят одно слово между стеком данных и портом; механика шины —
ветвь t0.uvm.bus (tools/uvm_bus.py), устройства стандартного набора —
tools/uvm_devices.py. Обе инструкции без поля imm64: операнды берутся
со стека и снимаются прежде обращения к шине — пустой стек даёт
ловушку 2 до обращения, отказ устройства — ловушку 9 после снятия
операндов. Порядок операндов DEVWR — как у STORE8/STORE64: слово
глубже, порт на вершине. Обработчики PC не трогают.
"""

from tools.uvm_bus import bus_read, bus_write
from tools.uvm_core import ds_pop, ds_pop2, ds_push


# @method op_devrd(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — не используется (у DEVRD нет поля imm64)
# @out   нет
# @does  DEVRD ( порт -- w ): снимает порт со стека, читает слово порта
# @does  шиной и кладёт его на стек; пустой стек — ловушка 2 до
# @does  обращения, отказ устройства — ловушка 9 после снятия порта
# @does  (SPEC, 6А.2).
# @depends ds_pop, ds_push, bus_read
def op_devrd(m, imm):
    port = ds_pop(m)
    ds_push(m, bus_read(m, port))


# @method op_devwr(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — не используется (у DEVWR нет поля imm64)
# @out   нет
# @does  DEVWR ( w порт -- ): снимает слово w (глубже) и порт (вершина),
# @does  как STORE8/STORE64, и пишет слово в порт шиной; пустой стек —
# @does  ловушка 2 до обращения, отказ устройства — ловушка 9 после
# @does  снятия операндов (SPEC, 6А.2).
# @depends ds_pop2, bus_write
def op_devwr(m, imm):
    w, port = ds_pop2(m)
    bus_write(m, port, w)
