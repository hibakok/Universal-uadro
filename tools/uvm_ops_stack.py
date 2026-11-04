# @uadro
# @file    tools/uvm_ops_stack.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Обработчики опкодов группы «стек»: NOP, PUSH, DROP, DUP, SWAP,
# @desc    OVER, ROT, PICK (SPEC/L0-UVM.txt, раздел 5).

"""Обработчики стековых опкодов UVM v0.1 (ветвь t0.uvm.ops).

Обработчик — функция handler(m, imm): m — состояние Machine, imm —
поле imm64 инструкции (0, если у опкода поля нет). Обработчики собраны
только из кирпичей ядра t0.uvm.core и PC не трогают (контракт ветви
t0.uvm.exec — см. tools/uvm_ops_jump.py).
"""

from tools.uvm_core import ds_pick, ds_pop, ds_push


# @method op_nop(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  NOP ( — ): ничего не делает (SPEC, таблица опкодов).
def op_nop(m, imm):
    pass


# @method op_push(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — слово imm64
# @out   нет
# @does  PUSH imm ( — imm ): кладёт константу на стек данных.
# @depends ds_push
def op_push(m, imm):
    ds_push(m, imm)


# @method op_drop(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  DROP ( a — ): снимает вершину стека данных; пустой стек —
# @does  ловушка 2.
# @depends ds_pop
def op_drop(m, imm):
    ds_pop(m)


# @method op_dup(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  DUP ( a — a a ): дублирует вершину; собран из PICK 0
# @does  (SPEC, замечание о минимальности).
# @depends op_pick
def op_dup(m, imm):
    op_pick(m, 0)


# @method op_swap(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  SWAP ( a b — b a ): меняет местами два верхних элемента.
# @depends ds_pop, ds_push
def op_swap(m, imm):
    b = ds_pop(m)
    a = ds_pop(m)
    ds_push(m, b)
    ds_push(m, a)


# @method op_over(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  OVER ( a b — a b a ): копия второго сверху; собран из PICK 1.
# @depends op_pick
def op_over(m, imm):
    op_pick(m, 1)


# @method op_rot(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  ROT ( a b c — b c a ): циклический сдвиг тройки верхних
# @does  элементов.
# @depends ds_pop, ds_push
def op_rot(m, imm):
    c = ds_pop(m)
    b = ds_pop(m)
    a = ds_pop(m)
    ds_push(m, b)
    ds_push(m, c)
    ds_push(m, a)


# @method op_pick(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — глубина элемента (0 — вершина)
# @out   нет
# @does  PICK imm ( xN..x0 — xN..x0 xN ): копия элемента глубины imm
# @does  (0 = DUP, 1 = OVER); глубина вне стека — ловушка 2.
# @depends ds_push, ds_pick
def op_pick(m, imm):
    ds_push(m, ds_pick(m, imm))
