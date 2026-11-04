# @uadro
# @file    tools/uvm_run.py
# @layer   T0
# @branch  t0.uvm.run
# @desc    Цикл запуска UVM v0.1: шаги step до UvmHalt или UvmTrap,
# @desc    приведение к коду завершения; кирпич run_image запускает
# @desc    готовый образ (SPEC/L0-UVM.txt, Этап 1).

"""Цикл запуска UVM v0.1 (ветвь t0.uvm.run).

run гонит машину шагами step ветви t0.uvm.exec, пока не поднимется
UvmHalt (нормальная остановка HALT) или UvmTrap (ловушка); поле code
остановки или ловушки становится кодом завершения (SPEC, разделы 2-3).
Состояние машины после остановки сохраняется — на это обопрётся отладчик
(Этап 11). run_image — кирпич полного запуска: свежая машина, загрузка
образа с адреса 0 (SPEC, раздел 2) и цикл run; его потребители — ветвь
t0.uvm.cli и интеграционные программы Этапа 1.
"""

from tools.uvm_core import (DS_SIZE_DEFAULT, RAM_SIZE_DEFAULT,
                            RS_SIZE_DEFAULT, Machine, UvmHalt, UvmTrap,
                            load_image)
from tools.uvm_exec import step


# @method run(m) -> int
# @in    m: Machine — состояние машины; образ загружен, PC указывает
# @in    на первую инструкцию
# @out   code: int — код завершения: imm инструкции HALT по модулю 256
# @out   или код ловушки 1-8 (SPEC, раздел 3)
# @does  Исполняет инструкции циклом step до остановки: UvmHalt и UvmTrap
# @does  прекращают цикл, их поле code возвращается как код завершения;
# @does  машина после остановки не сбрасывается (стеки, ОЗУ и PC доступны
# @does  вызывающему).
# @depends step
def run(m):
    try:
        while True:
            step(m)
    except (UvmHalt, UvmTrap) as stop:
        return stop.code


# @method run_image(image, ram_size, ds_size, rs_size) -> tuple
# @in    image: bytes — образ программы
# @in    ram_size: int — размер ОЗУ в байтах (по умолчанию 1 МиБ)
# @in    ds_size: int — ёмкость стека данных в словах (по умолчанию 1024)
# @in    rs_size: int — ёмкость стека возвратов в словах (по умолчанию 256)
# @out   m: Machine — остановленная машина; её состояние доступно
# @out   code: int — код завершения запуска
# @does  Полный запуск образа (SPEC, раздел 2): свежая машина заданных
# @does  размеров, загрузка образа с адреса 0, цикл run; кирпич ветви
# @does  t0.uvm.cli и интеграционных программ Этапа 1.
# @depends Machine, load_image, run
def run_image(image, ram_size=RAM_SIZE_DEFAULT, ds_size=DS_SIZE_DEFAULT,
              rs_size=RS_SIZE_DEFAULT):
    m = Machine(ram_size=ram_size, ds_size=ds_size, rs_size=rs_size)
    load_image(m, image)
    code = run(m)
    return m, code
