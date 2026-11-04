# @uadro
# @file    tools/uvm_ops_arith.py
# @layer   T0
# @branch  t0.uvm.ops
# @desc    Обработчики опкодов группы «арифметика и биты»: ADD, SUB, MUL,
# @desc    UDIV, UMOD, NEG, SHL, SHR, SAR, AND, OR, XOR, INV
# @desc    (SPEC/L0-UVM.txt, раздел 5).

"""Обработчики арифметических и побитовых опкодов UVM v0.1 (t0.uvm.ops).

Бинарные опкоды имеют вид ( a b — a?b ): a — глубже (первый операнд),
b — вершина (второй). Всё делается по модулю 2^64 (кирпич ds_push),
деление — беззнаковое; знаковое соберётся на слое uBrick из этих
кирпичей (SPEC, замечание о минимальности). Обработчики PC не трогают.
"""

from tools.uvm_core import (
    TRAP_DIV0,
    ds_pop,
    ds_pop2,
    ds_push,
    to_signed,
    to_word,
    trap,
)


# @method shift_count(n) -> int
# @in    n: int — снятое со стека число бит сдвига
# @out   c: int — счётчик 0..63
# @does  Усекает счётчик сдвига до 0..63 (SPEC: «n усекается до 0..63»).
def shift_count(n):
    return n & 63


# @method op_add(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  ADD ( a b — a+b ): сложение по модулю 2^64.
# @depends ds_pop2, ds_push
def op_add(m, imm):
    a, b = ds_pop2(m)
    ds_push(m, a + b)


# @method op_sub(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  SUB ( a b — a-b ): вычитание по модулю 2^64.
# @depends ds_pop2, ds_push
def op_sub(m, imm):
    a, b = ds_pop2(m)
    ds_push(m, a - b)


# @method op_mul(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  MUL ( a b — a*b ): младшие 64 бита произведения.
# @depends ds_pop2, ds_push
def op_mul(m, imm):
    a, b = ds_pop2(m)
    ds_push(m, a * b)


# @method op_udiv(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  UDIV ( a b — a/b ): целое частное без знака; b = 0 — ловушка 1.
# @depends ds_pop2, ds_push, trap
def op_udiv(m, imm):
    a, b = ds_pop2(m)
    if b == 0:
        trap(TRAP_DIV0)
    ds_push(m, a // b)


# @method op_umod(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  UMOD ( a b — a%b ): остаток без знака; b = 0 — ловушка 1.
# @depends ds_pop2, ds_push, trap
def op_umod(m, imm):
    a, b = ds_pop2(m)
    if b == 0:
        trap(TRAP_DIV0)
    ds_push(m, a % b)


# @method op_neg(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  NEG ( a — 0-a ): арифметическое отрицание по модулю 2^64.
# @depends ds_pop, ds_push
def op_neg(m, imm):
    a = ds_pop(m)
    ds_push(m, 0 - a)


# @method op_shl(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  SHL ( a n — a<<n ): сдвиг влево; n усекается до 0..63.
# @depends ds_pop, ds_push, shift_count
def op_shl(m, imm):
    n = shift_count(ds_pop(m))
    a = ds_pop(m)
    ds_push(m, a << n)


# @method op_shr(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  SHR ( a n — a>>n ): логический сдвиг вправо (без знака);
# @does  n усекается до 0..63.
# @depends ds_pop, ds_push, shift_count
def op_shr(m, imm):
    n = shift_count(ds_pop(m))
    a = ds_pop(m)
    ds_push(m, a >> n)


# @method op_sar(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  SAR ( a n — a>>n ): арифметический сдвиг вправо по знаку;
# @does  n усекается до 0..63.
# @depends ds_pop, ds_push, shift_count, to_signed, to_word
def op_sar(m, imm):
    n = shift_count(ds_pop(m))
    a = ds_pop(m)
    ds_push(m, to_word(to_signed(a) >> n))


# @method op_and(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  AND ( a b — a&b ): побитовое И.
# @depends ds_pop2, ds_push
def op_and(m, imm):
    a, b = ds_pop2(m)
    ds_push(m, a & b)


# @method op_or(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  OR ( a b — a|b ): побитовое ИЛИ.
# @depends ds_pop2, ds_push
def op_or(m, imm):
    a, b = ds_pop2(m)
    ds_push(m, a | b)


# @method op_xor(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  XOR ( a b — a^b ): побитовое исключающее ИЛИ.
# @depends ds_pop2, ds_push
def op_xor(m, imm):
    a, b = ds_pop2(m)
    ds_push(m, a ^ b)


# @method op_inv(m, imm) -> None
# @in    m: Machine — состояние машины
# @in    imm: int — поле imm64 (игнорируется)
# @out   нет
# @does  INV ( a — ~a ): побитовая инверсия слова.
# @depends ds_pop, ds_push
def op_inv(m, imm):
    a = ds_pop(m)
    ds_push(m, ~a)
