# @uadro
# @file    tools/uvm_exec.py
# @layer   T0
# @branch  t0.uvm.exec
# @desc    Шаг исполнения UVM: счётчик шагов CYC, декодирование инструкции
# @desc    по PC и вызов её обработчика (SPEC/L0-UVM.txt; CYC — черновик
# @desc    v0.3, Этап 5).

"""Шаг исполнения UVM (ветвь t0.uvm.exec).

step — один шаг машины: счётчик CYC увеличивается на 1 (до
декодирования — начатый шаг считается, SPEC, раздел 1, v0.3),
декодер ветви t0.uvm.decode читает инструкцию по PC и ставит PC
на байт, следующий за инструкцией целиком, затем запускается
обработчик из таблицы опкодов t0.uvm.table. Обработчики переходов
переписывают PC сами; HALT поднимает UvmHalt, аварии — UvmTrap;
обе ловит цикл запуска — ветвь t0.uvm.run.
"""

from tools.uvm_core import WORD_MASK
from tools.uvm_decode import decode_at


# @method step(m) -> None
# @in    m: Machine — состояние машины; PC указывает на байт опкода
# @out   нет
# @does  Исполняет одну инструкцию: сначала CYC растёт на 1 по модулю
# @does  2^64 — в начале каждого шага, до декодирования (SPEC, раздел 1,
# @does  v0.3: начатый шаг считается, даже если инструкция ловушкой
# @does  завершится); decode_at читает инструкцию по PC, PC переводится
# @does  за неё целиком, обработчик из записи таблицы выполняет эффект
# @does  инструкции (SPEC, раздел 5); UvmHalt и UvmTrap проходят наверх
# @does  к циклу запуска t0.uvm.run. Горячий кирпич интерпретатора:
# @does  двухстрочное тело decode встроено в step — на одну функцию
# @does  меньше на каждую инструкцию; decode остаётся публичным
# @does  кирпичом (тесты t0.uvm.decode, будущий отладчик).
# @depends decode_at
# @uses   m.cyc — счётчик шагов машины
def step(m):
    m.cyc = (m.cyc + 1) & WORD_MASK
    entry, imm, next_addr = decode_at(m, m.pc)
    m.pc = next_addr
    entry[2](m, imm)
