# @uadro
# @file    tools/ubrick_cli.py
# @layer   T0
# @branch  t0.ubrick.cli
# @desc    Командный режим uBrick: compile — чтение исходника, разбор,
# @desc    сборка образа UVM и запись результата; --asm сохраняет
# @desc    промежуточный текст uAsm (SPEC/L3-UBRICK.txt, раздел 9).

"""Командный запуск uBrick (ветвь t0.ubrick.cli).

Собирает Этап 3 в команду (из корня репозитория):

    python tools/ubrick_cli.py compile ИСТОЧНИК.ubrk ОБРАЗ.uvm
        [--asm ТЕКСТ.uasm]

Кирпичи: parse_args разбирает аргументы режима (parse_compile_args),
read_text читает исходник, write_bytes/write_text пишут результат,
write_asm_text сохраняет промежуточный текст uAsm флага --asm,
run_compile исполняет режим, main диспетчеризует. Разбор — ветвь
t0.ubrick.parse (parse_ubrk), сборка — ветвь t0.ubrick.build
(build_ubrk, build_text). Ошибки — код выхода 2 и сообщение
в stderr; успех — код 0.
"""

import os
import sys

# Запуск сценарием (python tools/ubrick_cli.py) требует корня репозитория
# в sys.path для пакета tools; при запуске модулем (-m) он уже есть.
if not __package__:
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.ubrick_build import build_text, build_ubrk
from tools.ubrick_parse import parse_ubrk

USAGE_CODE = 2        # код выхода: неверные аргументы или файлы
ASM_FLAG = "--asm"    # флаг сохранения промежуточного текста uAsm


# @method usage_text() -> str
# @in    нет
# @out   text: str — строка подсказки команды
# @does  Даёт текст формы запуска, который main печатает в stderr при
# @does  ошибке аргументов (SPEC/L3-UBRICK.txt, раздел 9).
def usage_text():
    return ("использование: python tools/ubrick_cli.py compile "
            "ИСТОЧНИК.ubrk ОБРАЗ.uvm [--asm ТЕКСТ.uasm]")


# @method parse_compile_args(rest) -> tuple
# @in    rest: list — аргументы после слова compile
# @out   parsed: tuple — ("compile", источник, образ, текст либо None)
# @out   либо None
# @does  Режим compile: ровно два пути — исходник и образ — и, возможно,
# @does  флаг --asm с путём текста uAsm; иное число аргументов, флаг без
# @does  значения и другие флаги дают None.
def parse_compile_args(rest):
    if len(rest) == 2:
        return ("compile", rest[0], rest[1], None)
    if len(rest) == 4 and rest[2] == ASM_FLAG:
        return ("compile", rest[0], rest[1], rest[3])
    return None


# @method parse_args(argv) -> tuple
# @in    argv: list — аргументы командной строки без имени программы
# @out   parsed: tuple — ("compile", источник, образ, текст либо None)
# @out   либо None
# @does  Разбирает аргументы: первое слово — режим compile (единственный
# @does  режим ветви), дальше аргументы режима; пустые аргументы
# @does  и неизвестный режим — None.
# @depends parse_compile_args
def parse_args(argv):
    if not argv or argv[0] != "compile":
        return None
    return parse_compile_args(argv[1:])


# @method read_text(path) -> str
# @in    path: str — путь к файлу исходника uBrick
# @out   text: str — текст файла либо None
# @does  Читает исходник целиком в кодировке UTF-8; отсутствие файла,
# @does  каталог и плохая кодировка дают None (сообщение печатает
# @does  вызывающий режим).
def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


# @method write_bytes(path, data) -> str
# @in    path: str — путь к файлу образа
# @in    data: bytes — байты образа
# @out   error: str — текст ошибки записи либо None при успехе
# @does  Пишет байты в файл; ошибки доступа дают текст ошибки для stderr.
def write_bytes(path, data):
    try:
        with open(path, "wb") as handle:
            handle.write(data)
    except OSError:
        return f"ошибка: не пишется файл образа: {path}"
    return None


# @method write_text(path, text) -> str
# @in    path: str — путь к файлу текста
# @in    text: str — текст uAsm
# @out   error: str — текст ошибки записи либо None при успехе
# @does  Пишет текст в файл в кодировке UTF-8; ошибки доступа дают текст
# @does  ошибки для stderr.
def write_text(path, text):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        return f"ошибка: не пишется файл текста: {path}"
    return None


# @method write_asm_text(records, path) -> int
# @in    records: tuple — записи разбора parse_ubrk
# @in    path: str — путь к файлу текста uAsm
# @out   code: int — 0 — текст записан; 2 — ошибка записи
# @does  Сохраняет промежуточный текст uAsm (build_text) в файл флага
# @does  --asm; ошибка записи — код 2 и сообщение в stderr.
# @depends build_text, write_text
# @uses   sys.stderr — стандартный вывод ошибок хоста
def write_asm_text(records, path):
    write_error = write_text(path, build_text(records))
    if write_error is not None:
        print(write_error, file=sys.stderr)
        return USAGE_CODE
    return 0


# @method run_compile(parsed) -> int
# @in    parsed: tuple — ("compile", источник, образ, текст либо None)
# @in    из parse_args
# @out   code: int — 0 — образ собран и записан; 2 — ошибка
# @does  Режим compile: читает исходник (read_text), разбирает
# @does  (parse_ubrk), собирает образ (build_ubrk) и пишет его
# @does  (write_bytes); с флагом --asm дополнительно сохраняет
# @does  промежуточный текст uAsm (write_asm_text); ошибка разбора
# @does  или сборки печатается в stderr как есть («uBrick: строка N:
# @does  текст» / «uAsm: строка N: текст»), ошибки файлов — своим
# @does  сообщением; код ошибки — 2 (SPEC, раздел 9).
# @depends read_text, parse_ubrk, build_ubrk, write_bytes, write_asm_text
# @uses   sys.stderr — стандартный вывод ошибок хоста
def run_compile(parsed):
    _, src, dst, asm = parsed
    text = read_text(src)
    if text is None:
        print(f"ошибка: не читается исходник: {src}", file=sys.stderr)
        return USAGE_CODE
    records, error = parse_ubrk(text)
    if error is not None:
        print(error, file=sys.stderr)
        return USAGE_CODE
    image, build_error = build_ubrk(records)
    if build_error is not None:
        print(build_error, file=sys.stderr)
        return USAGE_CODE
    write_error = write_bytes(dst, image)
    if write_error is not None:
        print(write_error, file=sys.stderr)
        return USAGE_CODE
    if asm is not None:
        return write_asm_text(records, asm)
    return 0


# @method main(argv) -> int
# @in    argv: list — аргументы командной строки без имени программы
# @out   code: int — 0 — успех; 2 — ошибка аргументов или режима
# @does  Полный запуск команды: parse_args, затем режим compile
# @does  (run_compile); ошибка аргументов печатает подсказку
# @does  использования в stderr.
# @depends usage_text, parse_args, run_compile
# @uses   sys.stderr — стандартный вывод ошибок хоста
def main(argv):
    parsed = parse_args(argv)
    if parsed is None:
        print(usage_text(), file=sys.stderr)
        return USAGE_CODE
    return run_compile(parsed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
