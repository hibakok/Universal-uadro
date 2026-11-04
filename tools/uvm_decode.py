# @uadro
# @file    tools/uvm_decode.py
# @layer   T0
# @branch  t0.uvm.decode
# @desc    Декодер инструкции UVM v0.1 по адресу: опкод, поле imm64
# @desc    little-endian, адрес следующей инструкции (SPEC/L0-UVM.txt,
# @desc    раздел 4).

"""Декодер инструкций UVM v0.1 (ветвь t0.uvm.decode).

decode_at — чистый кирпич: читает по адресу байт опкода и (если у опкода
есть поле imm64) восемь байтов little-endian за ним; возвращает запись
таблицы опкодов, значение imm и адрес следующей инструкции; состояние
машины не меняет. decode — декодирует инструкцию по PC и переводит PC
на байт, следующий за инструкцией целиком: это контракт обработчиков
ветви t0.uvm.exec (CALL кладёт на RS уже готовый адрес возврата).

Неизвестный опкод — ловушка 6 (SPEC, разделы 3 и 5); чтение вне ОЗУ —
ловушка 7 (кирпичи load_byte/load_word ядра t0.uvm.core).
"""

from tools.uvm_core import TRAP_BAD_OPCODE, load_byte, load_word, trap
from tools.uvm_table import entry_by_code

OPCODE_SIZE = 1  # байт опкода (SPEC, раздел 4)
IMM_SIZE = 8     # байтов в поле imm64 (SPEC, раздел 4)


# @method decode_at(m, addr) -> tuple
# @in    m: Machine — состояние машины (не меняется)
# @in    addr: int — адрес байта опкода в ОЗУ
# @out   entry: tuple — запись таблицы (код, мнемоника, обработчик, imm64)
# @out   imm: int — значение поля imm64 или 0, если поля нет
# @out   next_addr: int — адрес байта, следующего за инструкцией целиком
# @does  Читает инструкцию по адресу: опкод из ОЗУ, при наличии поля imm64
# @does  — восемь байтов little-endian за ним; неизвестный опкод —
# @does  ловушка 6, выход за границы ОЗУ — ловушка 7; кирпич дизассемблера
# @does  (Этап 2) и отладчика (Этап 11).
# @depends load_byte, load_word, trap, entry_by_code
def decode_at(m, addr):
    opcode = load_byte(m, addr)
    entry = entry_by_code(opcode)
    if entry is None:
        trap(TRAP_BAD_OPCODE)
    if entry[3]:
        imm = load_word(m, addr + OPCODE_SIZE)
        return entry, imm, addr + OPCODE_SIZE + IMM_SIZE
    return entry, 0, addr + OPCODE_SIZE


# @method decode(m) -> tuple
# @in    m: Machine — состояние машины; PC указывает на байт опкода
# @out   handler: callable — обработчик handler(m, imm) из таблицы опкодов
# @out   imm: int — значение поля imm64 или 0, если поля нет
# @does  Декодирует инструкцию по PC и переводит PC на байт, следующий
# @does  за инструкцией целиком (включая поле imm64) — контракт
# @does  обработчиков ветви t0.uvm.exec; при ловушке PC остаётся прежним;
# @does  ловушки — как у decode_at.
# @depends decode_at
def decode(m):
    entry, imm, next_addr = decode_at(m, m.pc)
    m.pc = next_addr
    return entry[2], imm
