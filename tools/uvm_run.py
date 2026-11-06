# @uadro
# @file    tools/uvm_run.py
# @layer   T0
# @branch  t0.uvm.run
# @desc    Цикл запуска UVM: шаги step до UvmHalt или UvmTrap, приведение
# @desc    к коду завершения; кирпич run_image привязывает стандартный набор
# @desc    устройств и запускает готовый образ (SPEC/L0-UVM.txt, разделы 2
# @desc    и 6А.4).

"""Цикл запуска UVM (ветвь t0.uvm.run).

run гонит машину шагами step ветви t0.uvm.exec, пока не поднимется
UvmHalt (нормальная остановка HALT) или UvmTrap (ловушка); поле code
остановки или ловушки становится кодом завершения (SPEC, разделы 2-3).
Состояние машины после остановки сохраняется — на это обопрётся отладчик
(Этап 11). run_image — кирпич полного запуска: свежая машина, привязка
стандартного набора устройств — консоль и таймер (SPEC, 6А.4: программа
рассчитывает на них всегда; v0.3), загрузка образа с адреса 0 (SPEC,
раздел 2) и цикл run; его потребители — ветвь t0.uvm.cli и
интеграционные программы. Блочное хранилище подключает раннер по
своему решению (флаг командной строки — подшаг 5.5, ROADMAP.txt).
"""

from tools.uvm_core import (DS_SIZE_DEFAULT, RAM_SIZE_DEFAULT,
                            RS_SIZE_DEFAULT, Machine, UvmHalt, UvmTrap,
                            load_image)
from tools.uvm_devices import attach_standard
from tools.uvm_exec import step


# @method run(m) -> int
# @in    m: Machine — состояние машины; образ загружен, PC указывает
# @in    на первую инструкцию
# @out   code: int — код завершения: imm инструкции HALT по модулю 256
# @out   или код ловушки 1-8 (SPEC, раздел 3)
# @does  Исполняет инструкции циклом step до остановки: UvmHalt и UvmTrap
# @does  прекращают цикл, их поле code возвращается как код завершения;
# @does  машина после остановки не сбрасывается (стеки, ОЗУ и PC доступны
# @does  вызывающему). Горячий путь: step привязывается локальной
# @does  переменной — поиск имени в глобалах на каждую инструкцию
# @does  исчезает, поведение то же.
# @depends step
def run(m):
    step_local = step
    try:
        while True:
            step_local(m)
    except (UvmHalt, UvmTrap) as stop:
        return stop.code


# @method run_image(image, ram_size, ds_size, rs_size) -> tuple
# @in    image: bytes — образ программы
# @in    ram_size: int — размер ОЗУ в байтах (по умолчанию 1 МиБ)
# @in    ds_size: int — ёмкость стека данных в словах (по умолчанию 1024)
# @in    rs_size: int — ёмкость стека возвратов в словах (по умолчанию 256)
# @out   m: Machine — остановленная машина; её состояние доступно
# @out   code: int — код завершения запуска
# @does  Полный запуск образа (SPEC, разделы 2 и 6А.4): свежая машина
# @does  заданных размеров, привязка стандартного набора устройств —
# @does  консоль и таймер (v0.3: программа рассчитывает на них всегда;
# @does  точка нуля TMR_WALL — момент привязки), загрузка образа
# @does  с адреса 0, цикл run; кирпич ветви t0.uvm.cli и интеграционных
# @does  программ.
# @depends Machine, attach_standard, load_image, run
def run_image(image, ram_size=RAM_SIZE_DEFAULT, ds_size=DS_SIZE_DEFAULT,
              rs_size=RS_SIZE_DEFAULT):
    m = Machine(ram_size=ram_size, ds_size=ds_size, rs_size=rs_size)
    attach_standard(m)
    load_image(m, image)
    code = run(m)
    return m, code
