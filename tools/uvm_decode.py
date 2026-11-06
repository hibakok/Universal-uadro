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

Горячий путь интерпретатора: выборка опкода и поля imm64 встроены
в тело decode_at (одна проверка границы на каждое чтение, срез байтов
для imm64) — поведение то же, вызовов меньше; внеграничные обращения
идут через load_byte с той же ловушкой 7.
"""

from tools.uvm_core import TRAP_BAD_OPCODE, TRAP_OOB, load_byte, trap
from tools.uvm_table import BY_CODE

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
# @does  (Этап 2) и отладчика (Этап 11). Горячий путь интерпретатора:
# @does  опкод и imm64 читаются встроенными срезами, поле на границе
# @does  ОЗУ — побайтово через load_byte (ловушка 7 на первом байте
# @does  вне ОЗУ, как раньше).
# @depends load_byte, trap, BY_CODE
def decode_at(m, addr):
    ram = m.ram
    if not 0 <= addr < len(ram):
        trap(TRAP_OOB)
    entry = BY_CODE.get(ram[addr])
    if entry is None:
        trap(TRAP_BAD_OPCODE)
    if not entry[3]:
        return entry, 0, addr + OPCODE_SIZE
    end = addr + OPCODE_SIZE + IMM_SIZE
    if end <= len(ram):
        imm = int.from_bytes(ram[addr + OPCODE_SIZE:end], "little")
        return entry, imm, end
    imm = 0
    for i in range(IMM_SIZE):
        imm |= load_byte(m, addr + OPCODE_SIZE + i) << (8 * i)
    return entry, imm, end


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
