# @uadro
# @file    tests/uvm_testkit.py
# @layer   T0
# @branch  t0.infra.tests
# @desc    Общий тест-набор UVM: компактные машины, снимки стека, чтение
# @desc    кодов ловушек и остановки для тестов ветвей t0.uvm.*.

"""Тест-набор UVM (ветвь t0.infra.tests).

Переиспользуется всеми тестами ветвей t0.uvm.*: компактные машины
для проверок границ и чтение кодов ловушек и остановки HALT.
"""

from tools import uvm_core as uc


# @method small(ram_size, ds_size, rs_size) -> Machine
# @in    ram_size: int — размер ОЗУ в байтах (по умолчанию 64)
# @in    ds_size: int — ёмкость стека данных в словах (по умолчанию 8)
# @in    rs_size: int — ёмкость стека возвратов в словах (по умолчанию 4)
# @out   m: Machine — машина с малым ОЗУ и малыми стеками
# @does  Компактная машина для быстрых тестов границ и переполнений;
# @does  размеры переопределяются точечно.
# @depends uc.Machine
def small(ram_size=64, ds_size=8, rs_size=4):
    return uc.Machine(ram_size=ram_size, ds_size=ds_size, rs_size=rs_size)


# @method stack_of(m) -> list
# @in    m: Machine — состояние машины
# @out   items: list — снимок стека данных (нижний элемент первым)
# @does  Копия содержимого DS для сравнения в тестах.
def stack_of(m):
    return list(m.ds)


# @method trap_code(action) -> int
# @in    action: callable — действие, обязанное поднять ловушку
# @out   code: int — код поднятой ловушки
# @does  Исполняет действие и возвращает код ловушки; без ловушки —
# @does  ошибка теста.
# @depends uc.UvmTrap
def trap_code(action):
    try:
        action()
    except uc.UvmTrap as exc:
        return exc.code
    raise AssertionError("ловушка не поднята")


# @method halt_code(action) -> int
# @in    action: callable — действие, обязанное поднять UvmHalt
# @out   code: int — код нормальной остановки
# @does  Исполняет действие и возвращает код остановки HALT; без
# @does  остановки — ошибка теста.
# @depends uc.UvmHalt
def halt_code(action):
    try:
        action()
    except uc.UvmHalt as exc:
        return exc.code
    raise AssertionError("остановка не поднята")
