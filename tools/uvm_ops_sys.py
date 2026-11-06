# @uadro
# @file    tools/uvm_ops_sys.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Обработчик опкода SYS и мост к узлу-хосту: SYS 0 — чтение байта,
# @desc    SYS 1 — вывод байта, SYS 2 — завершение с кодом со стека
# @desc    (SPEC/L0-UVM.txt, раздел 6).

"""Системные вызовы UVM v0.2 (ветвь t0.uvm.ops).

SYS — временный мост к узлу-хосту до появления шины устройств
(Этап 5). Хостовые кирпичи host_read_byte и host_write_byte изолируют
stdin/stdout: когда появится шина устройств, заменятся только эти два
кирпича, а не обработчики. SYS 2 — завершение с кодом со стека:
нормальная остановка, как HALT imm, но код — данные со стека; нужна
собственным инструментам Этапа 4 — эмулятор передаёт код завершения
гостя (SPEC/L4-SELFHOST.txt, раздел 5Б). Обработчик PC не трогает.
"""

import sys

from tools.uvm_core import (WORD_MASK, TRAP_BAD_SYS, UvmHalt, ds_pop,
                            ds_push, to_byte, trap)

EOF_WORD = WORD_MASK  # признак конца ввода для SYS 0 (SPEC, раздел 6)


# @method host_read_byte() -> int
# @in    нет
# @out   c: int — байт 0..255 или EOF_WORD при конце ввода
# @does  Читает один байт из stdin узла-хоста (кирпич SYS 0).
# @uses  sys.stdin — стандартный ввод хоста
def host_read_byte():
    data = sys.stdin.buffer.read(1)
    if not data:
        return EOF_WORD
    return data[0]


# @method host_write_byte(c) -> None
# @in    c: int — значение; выводится младший байт
# @out   нет
# @does  Пишет один байт (c по модулю 256) в stdout узла-хоста (кирпич
# @does  SYS 1).
# @uses  sys.stdout — стандартный вывод хоста
def host_write_byte(c):
    sys.stdout.buffer.write(bytes([c & 0xFF]))


# @method op_sys(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — номер системного вызова n
# @out   нет
# @does  SYS n (SPEC, раздел 6): n = 0 — прочитать байт ( — c ),
# @does  c = 0..255 или EOF_WORD в конце ввода; n = 1 — вывести байт
# @does  ( c — ); n = 2 — завершить исполнение с кодом c со стека
# @does  по модулю 256 — нормальная остановка, как HALT imm; код
# @does  снимается со стека прежде остановки, пустой стек — ловушка 2;
# @does  неизвестный n — ловушка 8.
# @depends ds_push, ds_pop, host_read_byte, host_write_byte, to_byte,
# @depends UvmHalt, trap
def op_sys(m, imm):
    if imm == 0:
        ds_push(m, host_read_byte())
    elif imm == 1:
        host_write_byte(ds_pop(m))
    elif imm == 2:
        raise UvmHalt(to_byte(ds_pop(m)))
    else:
        trap(TRAP_BAD_SYS)
