# @uadro
# @file    tools/uvm_ops_cmp.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Обработчики опкодов группы «сравнения»: EQ, NEQ, LTU, GTU,
# @desc    LEU, GEU (SPEC/L0-UVM.txt, раздел 5).

"""Обработчики сравнений UVM v0.1 (ветвь t0.uvm.ops).

Все сравнения беззнаковые (слова — целые без знака); результат —
слово-флаг 1 (истина) или 0 (ложь). Знаковые сравнения соберутся на
слое uBrick из беззнаковых кирпичей (SPEC, замечание о минимальности).
Обработчики PC не трогают.
"""

from tools.uvm_core import ds_pop2, ds_push


# @method push_flag(m, flag) -> None
# @in    m: Machine — состояние машины
# @in    flag: bool — результат сравнения
# @out   нет
# @does  Кладёт слово 1 (истина) или 0 (ложь) на стек данных — общий
# @does  кирпич сравнений.
# @depends ds_push
def push_flag(m, flag):
    ds_push(m, 1 if flag else 0)


# @method op_eq(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  EQ ( a b — ф ): ф = 1, если a = b, иначе 0.
# @depends ds_pop2, push_flag
def op_eq(m, imm):
    a, b = ds_pop2(m)
    push_flag(m, a == b)


# @method op_neq(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  NEQ ( a b — ф ): ф = 1, если a не равно b, иначе 0.
# @depends ds_pop2, push_flag
def op_neq(m, imm):
    a, b = ds_pop2(m)
    push_flag(m, a != b)


# @method op_ltu(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  LTU ( a b — ф ): ф = 1, если a < b (без знака).
# @depends ds_pop2, push_flag
def op_ltu(m, imm):
    a, b = ds_pop2(m)
    push_flag(m, a < b)


# @method op_gtu(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  GTU ( a b — ф ): ф = 1, если a > b (без знака).
# @depends ds_pop2, push_flag
def op_gtu(m, imm):
    a, b = ds_pop2(m)
    push_flag(m, a > b)


# @method op_leu(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  LEU ( a b — ф ): ф = 1, если a <= b (без знака).
# @depends ds_pop2, push_flag
def op_leu(m, imm):
    a, b = ds_pop2(m)
    push_flag(m, a <= b)


# @method op_geu(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  GEU ( a b — ф ): ф = 1, если a >= b (без знака).
# @depends ds_pop2, push_flag
def op_geu(m, imm):
    a, b = ds_pop2(m)
    push_flag(m, a >= b)
