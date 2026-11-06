# @uadro
# @file    tools/uvm_table.py
# @layer   T0
# @branch  t0.uvm.table
# @desc    Таблица опкодов UVM: код, мнемоника, обработчик, признак imm64
# @desc    40 записей — v0.1 + DEVRD/DEVWR v0.3 (SPEC/L0-UVM.txt, раздел 5).

"""Таблица опкодов UVM (ветвь t0.uvm.table).

Вся система команд на одном экране: 40 записей вида
(код, мнемоника, обработчик, признак imm64), сгруппированных по группам
опкодов SPEC: 38 записей v0.1 и пара DEVRD/DEVWR v0.3 (Этап 5, раздел 6А.2).
Таблица — чистые данные: функции поиска не меняют состояние
машины. Неизвестный код или мнемоника дают None; ловушку 6 (неизвестный
опкод) поднимает декодер — ветвь t0.uvm.decode.
"""

from tools import uvm_ops_arith as arith
from tools import uvm_ops_cmp as cmp
from tools import uvm_ops_dev as dev
from tools import uvm_ops_jump as jump
from tools import uvm_ops_mem as mem
from tools import uvm_ops_stack as stack
from tools import uvm_ops_sys as sysops

# Формат записи: (код опкода, мнемоника, обработчик, признак поля imm64).
GROUP_STACK = (
    (0x00, "NOP", stack.op_nop, False),
    (0x01, "PUSH", stack.op_push, True),
    (0x02, "DROP", stack.op_drop, False),
    (0x03, "DUP", stack.op_dup, False),
    (0x04, "SWAP", stack.op_swap, False),
    (0x05, "OVER", stack.op_over, False),
    (0x06, "ROT", stack.op_rot, False),
    (0x07, "PICK", stack.op_pick, True),
)

GROUP_MEM = (
    (0x10, "LOAD8", mem.op_load8, False),
    (0x11, "LOAD64", mem.op_load64, False),
    (0x12, "STORE8", mem.op_store8, False),
    (0x13, "STORE64", mem.op_store64, False),
)

GROUP_ARITH = (
    (0x20, "ADD", arith.op_add, False),
    (0x21, "SUB", arith.op_sub, False),
    (0x22, "MUL", arith.op_mul, False),
    (0x23, "UDIV", arith.op_udiv, False),
    (0x24, "UMOD", arith.op_umod, False),
    (0x25, "NEG", arith.op_neg, False),
    (0x26, "SHL", arith.op_shl, False),
    (0x27, "SHR", arith.op_shr, False),
    (0x28, "SAR", arith.op_sar, False),
    (0x29, "AND", arith.op_and, False),
    (0x2A, "OR", arith.op_or, False),
    (0x2B, "XOR", arith.op_xor, False),
    (0x2C, "INV", arith.op_inv, False),
)

GROUP_CMP = (
    (0x30, "EQ", cmp.op_eq, False),
    (0x31, "NEQ", cmp.op_neq, False),
    (0x32, "LTU", cmp.op_ltu, False),
    (0x33, "GTU", cmp.op_gtu, False),
    (0x34, "LEU", cmp.op_leu, False),
    (0x35, "GEU", cmp.op_geu, False),
)

GROUP_JUMP = (
    (0x40, "JMP", jump.op_jmp, True),
    (0x41, "JZ", jump.op_jz, True),
    (0x42, "JNZ", jump.op_jnz, True),
    (0x43, "CALL", jump.op_call, True),
    (0x44, "RET", jump.op_ret, False),
    (0x45, "HALT", jump.op_halt, True),
)

GROUP_SYS = (
    (0x50, "SYS", sysops.op_sys, True),
)

GROUP_DEV = (
    (0x52, "DEVRD", dev.op_devrd, False),
    (0x53, "DEVWR", dev.op_devwr, False),
)

TABLE = (
    GROUP_STACK + GROUP_MEM + GROUP_ARITH + GROUP_CMP
    + GROUP_JUMP + GROUP_SYS + GROUP_DEV
)
BY_CODE = {rec[0]: rec for rec in TABLE}
BY_MNEMONIC = {rec[1]: rec for rec in TABLE}
# Диспетчеризация по опкоду списком на 256 записей: байт опкода 0..255
# индексирует список напрямую, запись — тот же кортеж таблицы (или None
# для свободного кода — ловушку 6 поднимает декодер). Горячий кирпич
# интерпретатора: индекс списка быстрее поиска по словарю; данные те же,
# второй источник истины не появляется.
BY_LIST = [BY_CODE.get(code) for code in range(256)]


# @method entry_by_code(code) -> tuple
# @in    code: int — опкод 0..255
# @out   entry: tuple — (код, мнемоника, обработчик, imm64) или None
# @does  Находит запись опкода в таблице; неизвестный код — None.
def entry_by_code(code):
    return BY_CODE.get(code)


# @method entry_by_mnemonic(mnemonic) -> tuple
# @in    mnemonic: str — мнемоника опкода (например, "PUSH")
# @out   entry: tuple — (код, мнемоника, обработчик, imm64) или None
# @does  Находит запись по мнемонике; неизвестная мнемоника — None.
# @does  Кирпич ассемблера и дизассемблера (Этап 2).
def entry_by_mnemonic(mnemonic):
    return BY_MNEMONIC.get(mnemonic)


# @method mnemonic_of(code) -> str
# @in    code: int — опкод 0..255
# @out   name: str — мнемоника опкода или None для неизвестного кода
# @does  Даёт мнемонику опкода; кирпич дизассемблера (Этап 2).
# @depends entry_by_code
def mnemonic_of(code):
    entry = entry_by_code(code)
    return entry[1] if entry else None


# @method handler_of(code) -> callable
# @in    code: int — опкод 0..255
# @out   handler: callable — обработчик handler(m, imm) или None
# @does  Даёт обработчик опкода; кирпич ветвей t0.uvm.decode и t0.uvm.exec.
# @depends entry_by_code
def handler_of(code):
    entry = entry_by_code(code)
    return entry[2] if entry else None


# @method has_imm(code) -> bool
# @in    code: int — опкод 0..255
# @out   flag: bool — True, если за опкодом следует поле imm64
# @does  Показывает формат инструкции: 1 байт опкода либо 1 байт + 8 байтов
# @does  imm64; для неизвестного кода — False (сам код проверяет
# @does  entry_by_code).
# @depends entry_by_code
def has_imm(code):
    entry = entry_by_code(code)
    return entry[3] if entry else False


# @method code_of(mnemonic) -> int
# @in    mnemonic: str — мнемоника опкода
# @out   code: int — опкод 0..255 или None для неизвестной мнемоники
# @does  Даёт код опкода по мнемонике; кирпич ассемблера (Этап 2).
# @depends entry_by_mnemonic
def code_of(mnemonic):
    entry = entry_by_mnemonic(mnemonic)
    return entry[0] if entry else None
