# @uadro
# @file    tools/uvm_ops_jump.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Обработчики опкодов группы «переходы и остановка»: JMP, JZ, JNZ,
# @desc    CALL, RET, HALT (SPEC/L0-UVM.txt, разделы 4-5).

"""Обработчики управляющих опкодов UVM v0.1 (ветвь t0.uvm.ops).

КОНТРАКТ PC (для ветви t0.uvm.exec): к моменту вызова обработчика
PC уже установлен на адрес байта, следующего за инструкцией целиком
(включая поле imm64). Обработчики переходов переписывают m.pc сами,
остальные обработчики PC не трогают. Поэтому CALL кладёт на RS
текущий m.pc — это уже готовый адрес возврата (SPEC, раздел 4).

HALT — нормальная остановка: поднимает UvmHalt с кодом imm по модулю
256; ловушки UvmTrap остаются только для аварийных кодов 1-8.
"""

from tools.uvm_core import UvmHalt, ds_pop, rs_pop, rs_push, to_byte


# @method op_jmp(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — абсолютный адрес байта в ОЗУ
# @out   нет
# @does  JMP addr ( — ): PC = addr.
def op_jmp(m, imm):
    m.pc = imm


# @method op_jz(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — абсолютный адрес байта в ОЗУ
# @out   нет
# @does  JZ addr ( c — ): PC = addr, если c = 0; условие снимается
# @does  со стека в любом случае; пустой стек — ловушка 2.
# @depends ds_pop
def op_jz(m, imm):
    if ds_pop(m) == 0:
        m.pc = imm


# @method op_jnz(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — абсолютный адрес байта в ОЗУ
# @out   нет
# @does  JNZ addr ( c — ): PC = addr, если c не равно 0; условие
# @does  снимается со стека в любом случае; пустой стек — ловушка 2.
# @depends ds_pop
def op_jnz(m, imm):
    if ds_pop(m) != 0:
        m.pc = imm


# @method op_call(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — абсолютный адрес байта в ОЗУ
# @out   нет
# @does  CALL addr ( — ): адрес возврата (текущий PC) кладётся на RS,
# @does  PC = addr; переполнение RS — ловушка 5.
# @depends rs_push
def op_call(m, imm):
    rs_push(m, m.pc)
    m.pc = imm


# @method op_ret(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  RET ( — ): PC <- вершина RS; пустой RS — ловушка 4.
# @depends rs_pop
def op_ret(m, imm):
    m.pc = rs_pop(m)


# @method op_halt(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — код завершения (imm по модулю 256)
# @out   нет — всегда поднимает UvmHalt
# @does  HALT imm ( — ): нормальное завершение с кодом imm по модулю
# @does  256 (SPEC, раздел 5).
# @depends UvmHalt, to_byte
def op_halt(m, imm):
    raise UvmHalt(to_byte(imm))
