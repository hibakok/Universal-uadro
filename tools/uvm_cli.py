# @uadro
# @file    tools/uvm_cli.py
# @layer   T0
# @branch  t0.uvm.cli
# @desc    Запуск образа UVM из файла: разбор аргументов, чтение образа,
# @desc    исполнение run_image, код завершения UVM — в код выхода
# @desc    процесса (SPEC/L0-UVM.txt, Этап 1).

"""Командный запуск UVM v0.1 (ветвь t0.uvm.cli).

Собирает Этап 1 в одну команду (из корня репозитория):

    python tools/uvm_cli.py ОБРАЗ.uvm [--ram N] [--ds N] [--rs N]

Кирпичи: parse_size разбирает число-размер, parse_args — аргументы,
read_image читает файл образа, run_image (ветвь t0.uvm.run) исполняет.
Код завершения UVM — imm инструкции HALT по модулю 256 или код
ловушки 1-8 (SPEC, раздел 3) — становится кодом выхода процесса;
ловушка 7 загрузки (образ больше ОЗУ) ловится здесь же. Ошибки
запуска (аргументы, нечитаемый файл) — код 2 и сообщение в stderr.
Размеры ОЗУ и стеков ограничены 1..2^31-1, чтобы запуск не валил
узел-хост запросами гигантских машин.
"""

import os
import sys

# Запуск сценарием (python tools/uvm_cli.py) требует корня репозитория
# в sys.path для пакета tools; при запуске модулем (-m) он уже есть.
if not __package__:
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.uvm_core import (DS_SIZE_DEFAULT, RAM_SIZE_DEFAULT,
                            RS_SIZE_DEFAULT, UvmTrap)
from tools.uvm_run import run_image

USAGE_CODE = 2           # код выхода: неверные аргументы или файл
MAX_SIZE = 2 ** 31 - 1   # потолок размеров ОЗУ/стеков (защита хоста)


# @method usage_text() -> str
# @in    нет
# @out   text: str — строка использования команды
# @does  Даёт текст подсказки, которую main печатает в stderr при
# @does  ошибке аргументов.
def usage_text():
    return ("использование: python tools/uvm_cli.py ОБРАЗ.uvm "
            "[--ram N] [--ds N] [--rs N]")


# @method parse_size(text) -> int
# @in    text: str — аргумент-размер из командной строки
# @out   n: int — размер 1..2^31-1 или None
# @does  Разбирает размер машины: только цифры, без знака; пустая
# @does  строка, не-цифры, ноль и значения выше потолка дают None.
def parse_size(text):
    if not text.isdigit():
        return None
    value = int(text)
    if value <= 0 or value > MAX_SIZE:
        return None
    return value


# @method parse_args(argv) -> tuple
# @in    argv: list — аргументы командной строки без имени программы
# @out   parsed: tuple — (путь к образу, ram, ds, rs) или None
# @does  Разбирает аргументы: первый аргумент — путь к файлу образа
# @does  (обязателен), флаги --ram/--ds/--rs задают размеры ОЗУ и
# @does  стеков (по умолчанию — из ядра t0.uvm.core); повторный флаг
# @does  берёт последнее значение; неизвестный флаг, флаг без значения
# @does  или плохой размер дают None.
# @depends parse_size
def parse_args(argv):
    if not argv or argv[0].startswith("--"):
        return None
    sizes = {
        "--ram": RAM_SIZE_DEFAULT,
        "--ds": DS_SIZE_DEFAULT,
        "--rs": RS_SIZE_DEFAULT,
    }
    i = 1
    while i < len(argv):
        flag = argv[i]
        if flag not in sizes or i + 1 >= len(argv):
            return None
        value = parse_size(argv[i + 1])
        if value is None:
            return None
        sizes[flag] = value
        i += 2
    return argv[0], sizes["--ram"], sizes["--ds"], sizes["--rs"]


# @method read_image(path) -> bytes
# @in    path: str — путь к файлу образа
# @out   image: bytes — байты образа или None, если файл не читается
# @does  Читает файл образа целиком; отсутствие файла, каталог
# @does  и другие ошибки доступа дают None (сообщение печатает main).
def read_image(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


# @method main(argv) -> int
# @in    argv: list — аргументы командной строки без имени программы
# @out   code: int — код выхода процесса: код UVM 0..255 либо 2
# @does  Полный запуск из командной строки: parse_args, read_image,
# @does  run_image; код завершения UVM (HALT или ловушка) становится
# @does  кодом выхода, ловушка 7 загрузки (образ больше ОЗУ) — тоже;
# @does  ошибки аргументов и файла печатаются в stderr с кодом 2.
# @depends usage_text, parse_args, read_image, run_image
# @uses  sys.stderr — стандартный вывод ошибок хоста
def main(argv):
    parsed = parse_args(argv)
    if parsed is None:
        print(usage_text(), file=sys.stderr)
        return USAGE_CODE
    path, ram_size, ds_size, rs_size = parsed
    image = read_image(path)
    if image is None:
        print(f"ошибка: не читается файл образа: {path}", file=sys.stderr)
        return USAGE_CODE
    try:
        _, code = run_image(image, ram_size=ram_size, ds_size=ds_size,
                            rs_size=rs_size)
    except UvmTrap as exc:
        return exc.code
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
