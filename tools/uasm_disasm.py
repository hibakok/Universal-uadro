# @uadro
# @file    tools/uasm_disasm.py
# @layer   T0
# @branch  t0.uasm.disasm
# @desc    Дизассемблер образа UVM: линейное чтение с адреса 0, по одной
# @desc    инструкции на строку, хвост данных — директивами DB до восьми
# @desc    аргументов на строку (SPEC/L2-UASM.txt, раздел 8).

"""Дизассемблер образа UVM (ветвь t0.uasm.disasm).

Кирпичи: imm64_at (слово little-endian по адресу либо None, если поле
не помещается в образ), instr_line (строка «МНЕМОНИКА» или «МНЕМОНИКА
значение» — значения десятичные), decode_step (одна инструкция: строка
и адрес следующей либо сигнал останова), db_lines (хвост данных
директивами DB — до восьми аргументов на строку), join_lines (строки
в текст с концевым переводом) и disasm (образ -> текст).

Таблица опкодов — ветвь t0.uvm.table (кирпичи mnemonic_of и has_imm).
Признак останова декодирования: неизвестный опкод или поле imm64, не
помещающееся в образ; с этого байта до конца образа данные печатаются
директивами DB. Если образ закончился на границе инструкции, директив
DB нет. Пустой образ дизассемблируется в пустой текст. Раунд-трип
assemble(disasm(B)) == B — критерий готовности Этапа 2 (ветвь
t0.uasm.integration).
"""

from tools.uvm_table import has_imm, mnemonic_of

IMM_SIZE = 8      # байтов в поле imm64 (SPEC/L0-UVM.txt, раздел 4)
DB_PER_LINE = 8   # аргументов директивы DB на строку (SPEC, раздел 8)


# @method imm64_at(image, pos) -> int
# @in    image: bytes — двоичный образ UVM
# @in    pos: int — адрес первого байта поля imm64
# @out   value: int — слово 0..2^64-1 little-endian либо None, если поле
# @out   не помещается в образ
# @does  Читает восемь байтов little-endian с адреса pos; кирпич,
# @does  обратный word_le ветви t0.uasm.encode.
def imm64_at(image, pos):
    if pos + IMM_SIZE > len(image):
        return None
    return int.from_bytes(image[pos:pos + IMM_SIZE], "little")


# @method instr_line(mnemonic, value) -> str
# @in    mnemonic: str — мнемоника опкода
# @in    value: int — значение поля imm64 либо None, если поля нет
# @out   line: str — «МНЕМОНИКА» или «МНЕМОНИКА значение»
# @does  Печатает инструкцию одной строкой (SPEC, раздел 8): значение —
# @does  десятичный литерал слова 0..2^64-1; имена не восстанавливаются.
def instr_line(mnemonic, value):
    if value is None:
        return mnemonic
    return mnemonic + " " + str(value)


# @method decode_step(image, pos) -> tuple
# @in    image: bytes — двоичный образ UVM
# @in    pos: int — адрес байта опкода
# @out   pair: tuple — (строка инструкции, адрес следующей) либо
# @out   (None, pos) — сигнал останова декодирования
# @does  Декодирует одну инструкцию с адреса pos (SPEC, раздел 8):
# @does  неизвестный опкод или поле imm64, не помещающееся в образ,
# @does  останавливают декодирование — с этого байта хвост печатается
# @does  директивами DB.
# @depends mnemonic_of, has_imm, imm64_at, instr_line
def decode_step(image, pos):
    mnemonic = mnemonic_of(image[pos])
    if mnemonic is None:
        return None, pos
    if not has_imm(image[pos]):
        return instr_line(mnemonic, None), pos + 1
    value = imm64_at(image, pos + 1)
    if value is None:
        return None, pos
    return instr_line(mnemonic, value), pos + 1 + IMM_SIZE


# @method db_lines(data) -> list
# @in    data: bytes — хвост образа с байта останова декодирования
# @out   lines: list — строки «DB b1 [b2 ...]» до восьми аргументов
# @out   на строку; пустой хвост — пустой список
# @does  Печатает данные директивами DB (SPEC, раздел 8): байты —
# @does  десятичные литералы 0..255.
def db_lines(data):
    lines = []
    for start in range(0, len(data), DB_PER_LINE):
        chunk = data[start:start + DB_PER_LINE]
        lines.append("DB " + " ".join(str(b) for b in chunk))
    return lines


# @method join_lines(lines) -> str
# @in    lines: list — строки текста без переводов
# @out   text: str — строки, разделённые LF; непустой текст оканчивается
# @out   переводом строки, пустой список — пустой текст
# @does  Собирает строки в текстовый файл uAsm; кирпич ветвей
# @does  t0.uasm.disasm и t0.uasm.cli.
def join_lines(lines):
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


# @method disasm(image) -> str
# @in    image: bytes — двоичный образ UVM
# @out   text: str — текст uAsm: по одной инструкции на строку, хвост
# @out   данных — директивы DB; пустой образ — пустой текст
# @does  Дизассемблирует образ линейно с адреса 0 (SPEC, раздел 8):
# @does  decode_step до останова декодирования, затем хвост директивами
# @does  db_lines; раунд-трип assemble(disasm(B)) == B — критерий
# @does  готовности Этапа 2 (ветвь t0.uasm.integration).
# @depends decode_step, db_lines, join_lines
def disasm(image):
    lines = []
    pos = 0
    while pos < len(image):
        line, next_pos = decode_step(image, pos)
        if line is None:
            lines += db_lines(image[pos:])
            break
        lines.append(line)
        pos = next_pos
    return join_lines(lines)
