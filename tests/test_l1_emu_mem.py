# @uadro
# @file    tests/test_l1_emu_mem.py
# @layer   T0
# @branch  l1.uvm.emu
# @desc    Тесты подшага 1 ветви l1.uvm.emu — каркас и память эмулятора
# @desc    (src/l1/emu.ubrk, SPEC/L4-SELFHOST.txt, раздел 5Б): раскладка
# @desc    ОЗУ инструмента — образ гостя из stdin ложится в ОЗУ узла байт
# @desc    в байт с адреса 0x10000, клетки машины гостя gpc/gdsp/grsp по
# @desc    раскладке, лимит 512 КиБ — вход ровно в лимит читается целиком,
# @desc    вход длиннее — ловушка 7 гостя до начала исполнения: код 7,
# @desc    вывод пуст (паритет кода с эталоном load_image); прогон —
# @desc    тест-кирпич run_saved с сохранением машины (t0.infra.tests).

"""Тесты подшага 1 ветви l1.uvm.emu (SPEC/L4-SELFHOST.txt, раздел 5Б).

Эмулятор (src/l1/emu.ubrk с use-включениями mem/dec/tab/opsstack/opsjump,
образ — кирпич l1_image) прогоняется кирпичем run_saved: stdin — образ
гостя, машина узла сохраняется, снимки читаются по раскладке раздела 5Б
(ОЗУ гостя с 0x10000, клетки gpc/gdsp/grsp с 0x90A00).

Границы лимита 512 КиБ гоняют полный буфер через UVM — около минуты
на пару тестов, как границы буферов ассемблера (DOC/JOURNAL.txt,
подшаг 1 ветви l2.uasm.assemble). Пустой вход прогоном не тестируется:
НОП-горка до конца ОЗУ — исключение золотого набора (SPEC, раздел 6).
"""

import os
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools import uvm_core as uc
from tools import uvm_run

GRAM_BASE = 0x10000   # ОЗУ гостя в ОЗУ узла (раздел 5Б)
GPC_ADDR = 0x90A00    # клетка gpc — PC гостя
GDSP_ADDR = 0x90A08   # клетка gdsp — слов в DS гостя
GRSP_ADDR = 0x90A10   # клетка grsp — слов в RS гостя
GRAM_SIZE = 0x80000   # ОЗУ гостя — 512 КиБ
HALT = 0x45           # опкод HALT imm (SPEC/L0-UVM.txt, раздел 5)


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для пути src/l1.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method l1_source() -> str
# @in    нет
# @out   path: str — путь к исходнику src/l1/emu.ubrk
# @does  Строит путь к собственному воплощению эмулятора (слой L1,
# @does  SPEC/L4-SELFHOST.txt, раздел 5Б); use-включения mem, dec, tab,
# @does  opsstack и opsjump склеивает загрузчик.
def l1_source():
    return os.path.join(repo_root(), "src", "l1", "emu.ubrk")


# @method l1_image() -> bytes
# @in    нет
# @out   image: bytes — образ эмулятора, собранный командой compile;
# @out   None — ошибка сборки (сообщение печатает cli в stderr)
# @does  Собирает src/l1/emu.ubrk настоящей командой ubrick_cli
# @does  (режим compile, временный файл образа); кирпич всех тестов ветви.
# @depends ubrick_cli.main
# @uses   sys.stderr — стандартный вывод ошибок хоста (через cli)
def l1_image():
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "emu.uvm")
        code = ubrick_cli.main(["compile", l1_source(), image])
        if code != 0:
            return None
        with open(image, "rb") as handle:
            return handle.read()


# @method halt_image(value) -> bytes
# @in    value: int — imm инструкции HALT
# @out   image: bytes — образ гостя из одной инструкции HALT value
# @does  Собирает образ гостя для тестов подшагов 1-2 (обработчик halt —
# @does  opsjump.ubrk); кирпич всех тестов файлов test_l1_emu_*.
# @depends tk.image_of, tk.imm64
def halt_image(value):
    return tk.image_of([HALT, tk.imm64(value)])


# @method cell(m, addr) -> int
# @in    m: Machine — машина узла (снимок run_saved)
# @in    addr: int — адрес клетки в ОЗУ узла
# @out   value: int — значение клетки (8 байтов little-endian)
# @does  Читает клетку состояния гостя из ОЗУ узла по раскладке раздела
# @does  5Б; кирпич тестов клеток и будущих снимков стеков гостя.
def cell(m, addr):
    return int.from_bytes(m.ram[addr:addr + 8], "little")


# @method run(image) -> tuple
# @in    image: bytes — образ гостя (stdin инструмента)
# @out   triple: tuple — (код завершения, байты stdout, машина узла)
# @does  Прогон образа эмулятора без процесса с сохранением машины
# @does  (run_saved, t0.infra.tests); кирпич всех проверок ветви.
# @depends tk.run_saved, l1_image
def run(image):
    return tk.run_saved(l1_image(), image)


# @method ref_code(image) -> int
# @in    image: bytes — образ гостя
# @out   code: int — код завершения эталона на машине гостя
# @does  Паритет с эталоном (SPEC/L4-SELFHOST.txt, раздел 5Б: машина
# @does  гостя — ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin): эталон
# @does  исполняет образ гостя; ловушка при загрузке (образ больше ОЗУ)
# @does  даёт код ловушки.
# @depends uvm_run.run_image, uc.UvmTrap
def ref_code(image):
    try:
        _, code = uvm_run.run_image(image, GRAM_SIZE, 256, 64)
        return code
    except uc.UvmTrap as exc:
        return exc.code


class TestEmuMem(unittest.TestCase):
    """Подшаг 1: раскладка, образ в ОЗУ узла, клетки, лимит 512 КиБ."""

    # @method test_image_in_host_ram() -> None
    # @in    нет
    # @out   нет
    # @does  Образ гостя ложится в ОЗУ узла байт в байт с адреса
    # @does  0x10000 (раздел 5Б): программа NOP NOP HALT 7 исполняется
    # @does  (код 7, вывод пуст), снятые байты равны образу, за образом
    # @does  ОЗУ гостя нулевая.
    # @depends run, tk.image_of
    def test_image_in_host_ram(self):
        image = tk.image_of([0x00, 0x00, HALT, tk.imm64(7)])
        code, out, m = run(image)
        self.assertEqual((code, out), (7, b""))
        self.assertEqual(m.ram[GRAM_BASE:GRAM_BASE + len(image)], image)
        tail = m.ram[GRAM_BASE + len(image):GRAM_BASE + len(image) + 8]
        self.assertEqual(tail, b"\x00" * 8)

    # @method test_guest_state_cells() -> None
    # @in    нет
    # @out   нет
    # @does  Клетки машины гостя по раскладке (раздел 5Б): после HALT 0
    # @does  клетка gpc переведена декодером за инструкцию (адрес 9),
    # @does  gdsp и grsp нулевые — стеки пусты (greset, SPEC/L0-UVM.txt,
    # @does  раздел 2).
    # @depends run, halt_image, cell
    def test_guest_state_cells(self):
        image = halt_image(0)
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(cell(m, GPC_ADDR), len(image))
        self.assertEqual(cell(m, GDSP_ADDR), 0)
        self.assertEqual(cell(m, GRSP_ADDR), 0)

    # @method test_input_exactly_at_limit() -> None
    # @in    нет
    # @out   нет
    # @does  Вход ровно 512 КиБ читается целиком (лимит — «строго
    # @does  больше», как load_image эталона): последний байт образа
    # @does  ложится в последний байт ОЗУ гостя, HALT 0 в начале
    # @does  останавливает исполнение сразу — код 0.
    # @depends run, halt_image
    def test_input_exactly_at_limit(self):
        image = halt_image(0) + b"\x00" * (GRAM_SIZE - 9)
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(m.ram[GRAM_BASE + GRAM_SIZE - 1], 0)

    # @method test_input_over_limit() -> None
    # @in    нет
    # @out   нет
    # @does  Вход длиннее 512 КиБ — ловушка 7 гостя до начала исполнения
    # @does  (раздел 5Б, как load_image эталона): код 7, вывод пуст;
    # @does  код равен коду эталона на машине гостя.
    # @depends run, ref_code
    def test_input_over_limit(self):
        image = b"\x00" * (GRAM_SIZE + 1)
        code, out, m = run(image)
        self.assertEqual((code, out), (7, b""))
        self.assertEqual(ref_code(image), 7)


if __name__ == "__main__":
    unittest.main()
