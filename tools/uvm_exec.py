# @uadro
# @file    tools/uvm_exec.py
# @layer   T0
# @branch  t0.uvm.exec
# @desc    Шаг исполнения UVM v0.1: декодировать инструкцию по PC и вызвать
# @desc    её обработчик (SPEC/L0-UVM.txt, Этап 1).

"""Шаг исполнения UVM v0.1 (ветвь t0.uvm.exec).

step — один шаг машины: декодер ветви t0.uvm.decode читает инструкцию
по PC и ставит PC на байт, следующий за инструкцией целиком, затем
запускается обработчик из таблицы опкодов t0.uvm.table. Обработчики
переходов переписывают PC сами; HALT поднимает UvmHalt, аварии —
UvmTrap; обе ловит цикл запуска — ветвь t0.uvm.run, следующий шаг
Этапа 1.
"""

from tools.uvm_decode import decode_at


# @method step(m) -> None
# @in    m: Machine — состояние машины; PC указывает на байт опкода
# @out   нет
# @does  Исполняет одну инструкцию: decode_at читает инструкцию по PC,
# @does  PC переводится за неё целиком, обработчик из записи таблицы
# @does  выполняет эффект инструкции (SPEC, раздел 5); UvmHalt и UvmTrap
# @does  проходят наверх к циклу запуска t0.uvm.run. Горячий кирпич
# @does  интерпретатора: двухстрочное тело decode встроено в step —
# @does  на одну функцию меньше на каждую инструкцию; decode остаётся
# @does  публичным кирпичом (тесты t0.uvm.decode, будущий отладчик).
# @depends decode_at
def step(m):
    entry, imm, next_addr = decode_at(m, m.pc)
    m.pc = next_addr
    entry[2](m, imm)
