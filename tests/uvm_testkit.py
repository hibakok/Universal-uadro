# @uadro
# @file    tests/uvm_testkit.py
# @layer   T0
# @branch  t0.infra.tests
# @desc    Общий тест-набор UVM: компактные машины, снимки стека, сборка
# @desc    образов программ и чтение кодов ловушек и остановки для тестов
# @desc    ветвей t0.uvm.*.

"""Тест-набор UVM (ветвь t0.infra.tests).

Переиспользуется всеми тестами ветвей t0.uvm.*: компактные машины
для проверок границ, чтение кодов ловушек и остановки HALT, сборка
маленьких программных образов для декодера и шага исполнения.
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


# @method imm64(v) -> bytes
# @in    v: int — слово (оборачивается по модулю 2^64)
# @out   raw: bytes — 8 байтов little-endian
# @does  Кодирует поле imm64 инструкции (SPEC, раздел 4); кирпич сборки
# @does  тестовых образов для ветвей t0.uvm.decode/exec/run.
# @depends uc.to_word
def imm64(v):
    return uc.to_word(v).to_bytes(8, "little")


# @method load_prog(m, parts) -> None
# @in    m: Machine — состояние машины
# @in    parts: list — элементы образа: int 0..255 (байт) или bytes
# @out   нет
# @does  Собирает элементы в образ, загружает его с адреса 0 и сбрасывает
# @does  состояние запуска: PC = 0, стеки пусты; кирпич тестов ветвей
# @does  t0.uvm.decode/exec/run.
# @depends uc.load_image
def load_prog(m, parts):
    image = bytearray()
    for part in parts:
        if isinstance(part, int):
            image.append(part & 0xFF)
        else:
            image.extend(part)
    uc.load_image(m, bytes(image))
