# @uadro
# @file    tools/uasm_cli.py
# @layer   T0
# @branch  t0.uasm.cli
# @desc    Командные режимы uAsm: asm — сборка текста в образ, dis —
# @desc    дизассемблирование образа в файл или stdout (SPEC/L2-UASM.txt,
# @desc    раздел 9).

"""Командный запуск uAsm (ветвь t0.uasm.cli).

Собирает Этап 2 в две команды (из корня репозитория):

    python tools/uasm_cli.py asm ИСТОЧНИК.uasm ОБРАЗ.uvm
    python tools/uasm_cli.py dis ОБРАЗ.uvm [ТЕКСТ.uasm]

Кирпичи: parse_args разбирает аргументы режима (parse_asm_args,
parse_dis_args), read_text/read_image читают исходник и образ,
write_bytes/write_text пишут результат, run_asm/run_dis исполняют
режимы, main диспетчеризует. Сборка — ветвь t0.uasm.assemble (assemble),
разбор — ветвь t0.uasm.disasm (disasm). Ошибки — код выхода 2
и сообщение в stderr; успех — код 0. Останов декодирования в dis —
не ошибка, а хвост данных (SPEC, раздел 8).
"""

import os
import sys

# Запуск сценарием (python tools/uasm_cli.py) требует корня репозитория
# в sys.path для пакета tools; при запуске модулем (-m) он уже есть.
if not __package__:
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.uasm_assemble import assemble
from tools.uasm_disasm import disasm

USAGE_CODE = 2   # код выхода: неверные аргументы или файлы


# @method usage_text() -> str
# @in    нет
# @out   text: str — строка подсказки команды
# @does  Даёт текст обеих форм запуска, который main печатает в stderr
# @does  при ошибке аргументов (SPEC/L2-UASM.txt, раздел 9).
def usage_text():
    return ("использование: python tools/uasm_cli.py asm "
            "ИСТОЧНИК.uasm ОБРАЗ.uvm\n"
            "            python tools/uasm_cli.py dis ОБРАЗ.uvm "
            "[ТЕКСТ.uasm]")


# @method parse_asm_args(rest) -> tuple
# @in    rest: list — аргументы после слова asm
# @out   parsed: tuple — ("asm", источник, образ) либо None
# @does  Режим asm: ровно два пути — исходник и образ.
def parse_asm_args(rest):
    if len(rest) != 2:
        return None
    return ("asm", rest[0], rest[1])


# @method parse_dis_args(rest) -> tuple
# @in    rest: list — аргументы после слова dis
# @out   parsed: tuple — ("dis", образ, текст либо None) либо None
# @does  Режим dis: путь образа и, возможно, путь текста; без текста
# @does  результат печатается в stdout.
def parse_dis_args(rest):
    if len(rest) == 1:
        return ("dis", rest[0], None)
    if len(rest) == 2:
        return ("dis", rest[0], rest[1])
    return None


# @method parse_args(argv) -> tuple
# @in    argv: list — аргументы командной строки без имени программы
# @out   parsed: tuple — ("asm", источник, образ) либо ("dis", образ,
# @out   текст либо None) либо None
# @does  Разбирает аргументы: первое слово — режим asm или dis, дальше
# @does  аргументы режима; пустые аргументы и неизвестный режим — None.
# @depends parse_asm_args, parse_dis_args
def parse_args(argv):
    if not argv:
        return None
    mode = argv[0]
    rest = argv[1:]
    if mode == "asm":
        return parse_asm_args(rest)
    if mode == "dis":
        return parse_dis_args(rest)
    return None


# @method read_text(path) -> str
# @in    path: str — путь к файлу исходника uAsm
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


# @method read_image(path) -> bytes
# @in    path: str — путь к файлу образа
# @out   image: bytes — байты образа либо None
# @does  Читает файл образа целиком; ошибки доступа дают None.
def read_image(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
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


# @method run_asm(parsed) -> int
# @in    parsed: tuple — ("asm", источник, образ) из parse_args
# @out   code: int — 0 — образ собран и записан; 2 — ошибка
# @does  Режим asm: читает исходник (read_text), собирает (assemble),
# @does  пишет образ (write_bytes); ошибка сборки печатается в stderr
# @does  как есть («uAsm: строка N: текст»), ошибки файлов — своим
# @does  сообщением; код ошибки — 2 (SPEC, раздел 9).
# @depends read_text, assemble, write_bytes
# @uses   sys.stderr — стандартный вывод ошибок хоста
def run_asm(parsed):
    _, src, dst = parsed
    text = read_text(src)
    if text is None:
        print(f"ошибка: не читается исходник: {src}", file=sys.stderr)
        return USAGE_CODE
    image, error = assemble(text)
    if error is not None:
        print(error, file=sys.stderr)
        return USAGE_CODE
    write_error = write_bytes(dst, image)
    if write_error is not None:
        print(write_error, file=sys.stderr)
        return USAGE_CODE
    return 0


# @method run_dis(parsed) -> int
# @in    parsed: tuple — ("dis", образ, текст либо None) из parse_args
# @out   code: int — 0 — текст получен; 2 — ошибка чтения или записи
# @does  Режим dis: читает образ (read_image), дизассемблирует (disasm),
# @does  пишет текст в файл (write_text) либо, без файла, в stdout;
# @does  ошибки файлов — код 2 и сообщение в stderr (SPEC, раздел 9).
# @depends read_image, disasm, write_text
# @uses   sys.stderr, sys.stdout — стандартные потоки хоста
def run_dis(parsed):
    _, src, dst = parsed
    image = read_image(src)
    if image is None:
        print(f"ошибка: не читается образ: {src}", file=sys.stderr)
        return USAGE_CODE
    text = disasm(image)
    if dst is None:
        sys.stdout.write(text)
        return 0
    write_error = write_text(dst, text)
    if write_error is not None:
        print(write_error, file=sys.stderr)
        return USAGE_CODE
    return 0


# @method main(argv) -> int
# @in    argv: list — аргументы командной строки без имени программы
# @out   code: int — 0 — успех; 2 — ошибка аргументов или режима
# @does  Полный запуск команды: parse_args, затем режим asm (run_asm)
# @does  или dis (run_dis); ошибка аргументов печатает подсказку
# @does  использования в stderr.
# @depends usage_text, parse_args, run_asm, run_dis
# @uses   sys.stderr — стандартный вывод ошибок хоста
def main(argv):
    parsed = parse_args(argv)
    if parsed is None:
        print(usage_text(), file=sys.stderr)
        return USAGE_CODE
    if parsed[0] == "asm":
        return run_asm(parsed)
    return run_dis(parsed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
