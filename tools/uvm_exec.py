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

from tools.uvm_decode import decode


# @method step(m) -> None
# @in    m: Machine — состояние машины; PC указывает на байт опкода
# @out   нет
# @does  Исполняет одну инструкцию: decode(m) даёт обработчик и значение
# @does  imm, обработчик выполняет эффект инструкции (SPEC, раздел 5);
# @does  UvmHalt и UvmTrap проходят наверх к циклу запуска t0.uvm.run.
# @depends decode
def step(m):
    handler, imm = decode(m)
    handler(m, imm)
