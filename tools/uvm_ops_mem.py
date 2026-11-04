# @uadro
# @file    tools/uvm_ops_mem.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Обработчики опкодов группы «память»: LOAD8, LOAD64, STORE8,
# @desc    STORE64 (SPEC/L0-UVM.txt, раздел 5).

"""Обработчики опкодов памяти UVM v0.1 (ветвь t0.uvm.ops).

Все проверки границ и порядок байт little-endian уже лежат в кирпичах
ядра t0.uvm.core: обработчики только снимают аргументы со стека
и кладут результат. Обработчики PC не трогают.
"""

from tools.uvm_core import (
    ds_pop,
    ds_pop2,
    ds_push,
    load_byte,
    load_word,
    store_byte,
    store_word,
)


# @method op_load8(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  LOAD8 ( addr — u8 ): читает байт ОЗУ и расширяет нулями до
# @does  слова; адрес вне ОЗУ — ловушка 7.
# @depends ds_pop, ds_push, load_byte
def op_load8(m, imm):
    addr = ds_pop(m)
    ds_push(m, load_byte(m, addr))


# @method op_load64(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  LOAD64 ( addr — w64 ): читает 8 байтов little-endian без
# @does  требования выравнивания; адрес вне ОЗУ — ловушка 7.
# @depends ds_pop, ds_push, load_word
def op_load64(m, imm):
    addr = ds_pop(m)
    ds_push(m, load_word(m, addr))


# @method op_store8(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  STORE8 ( val addr — ): пишет младший байт val; addr — вершина
# @does  стека, val — под ним; адрес вне ОЗУ — ловушка 7.
# @depends ds_pop2, store_byte
def op_store8(m, imm):
    val, addr = ds_pop2(m)
    store_byte(m, addr, val)


# @method op_store64(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  STORE64 ( val addr — ): раскладывает слово val в 8 байтов
# @does  little-endian; addr — вершина стека, val — под ним; адрес
# @does  вне ОЗУ — ловушка 7.
# @depends ds_pop2, store_word
def op_store64(m, imm):
    val, addr = ds_pop2(m)
    store_word(m, addr, val)
