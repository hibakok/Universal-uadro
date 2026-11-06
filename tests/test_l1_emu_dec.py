# @uadro
# @file    tests/test_l1_emu_dec.py
# @layer   T0
# @branch  l1.uvm.emu
# @desc    Тесты подшага 2 ветви l1.uvm.emu — декодер и остановка
# @desc    (src/l1/dec.ubrk, tab.ubrk, opsstack.ubrk, opsjump.ubrk;
# @desc    SPEC/L4-SELFHOST.txt, раздел 5Б): обработчики NOP и HALT imm —
# @desc    несколько NOP и HALT imm дают код imm по модулю 256 (значения
# @desc    0, 1, 42, 255, 256, 300, 0x0102, 2^64-1; 0x0102 проверяет
# @desc    порядок байтов little-endian поля imm64), gpc переведён за
# @desc    инструкцию, ловушка 6 — коды вне шести диапазонов (дыры между
# @desc    диапазонами и за таблицей); паритет кодов завершения с эталоном
# @desc    на машине гостя (ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin).
# @desc    Ловушка 7 декодера (чтение за границей ОЗУ гостя) прогоном
# @desc    не покрывается: без переходов (подшаг 6) до конца ОЗУ гостя
# @desc    ведёт НОП-горка — исключение золотого набора (SPEC, раздел 6);
# @desc    выход PC за ОЗУ покроет JMP за границу (подшаги 6-7).

"""Тесты подшага 2 ветви l1.uvm.emu (SPEC/L4-SELFHOST.txt, раздел 5Б).

Декодер (src/l1/dec.ubrk) читает инструкцию гостя по gpc: код — байт
(вне ОЗУ гостя — ловушка 7), принадлежность — шесть диапазонов SPEC/
L0-UVM.txt (неизвестный код — ловушка 6), поле imm64 — восемь байтов
little-endian по gpc + 1; gpc переводится за инструкцию целиком —
контракт обработчиков (как decode эталона t0.uvm.decode). Дерево
диапазонов (src/l1/tab.ubrk) вызывает обработчики NOP (opsstack.ubrk)
и HALT (opsjump.ubrk); коды остальных групп — ловушка 6 (заготовка
подшагов 3-6) и прогоном не проверяются: поведение промежуточное.

Каждая проверка сверяет код завершения собственного эмулятора
(кирпич run: run_saved, stdin — образ гостя) с ожиданием и с кодом
эталона на машине гостя (кирпич ref_code: uvm_run.run_image,
ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin — SPEC, раздел 5Б).
"""

import os
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools import uvm_core as uc
from tools import uvm_run

GRAM_SIZE = 0x80000   # ОЗУ гостя — 512 КиБ (раздел 5Б)
GPC_ADDR = 0x90A00    # клетка gpc — PC гостя
NOP = 0x00            # опкод NOP
HALT = 0x45           # опкод HALT imm (SPEC/L0-UVM.txt, раздел 5)

# Дыры таблицы опкодов: коды между диапазонами и за таблицей —
# навсегда ловушка 6 (SPEC/L0-UVM.txt, раздел 5).
HOLES = (0x08, 0x0F, 0x14, 0x1F, 0x2D, 0x2F,
         0x36, 0x3F, 0x46, 0x4F, 0x51, 0xFF)

# Золотые значения imm64 (как наборы дизассемблера и ассемблера,
# SPEC/L4-SELFHOST.txt, раздел 6) и проверки модуля 256 и порядка
# байтов: 256 -> 0, 300 -> 44, 0x0102 -> 2 (big-endian дал бы 0).
HALT_VALUES = (0, 1, 42, 255, 256, 300, 0x0102, 2 ** 64 - 1)


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
# @does  SPEC/L4-SELFHOST.txt, раздел 5Б).
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
# @does  исполняет образ гостя; ловушка при загрузке даёт код ловушки.
# @depends uvm_run.run_image, uc.UvmTrap
def ref_code(image):
    try:
        _, code = uvm_run.run_image(image, GRAM_SIZE, 256, 64)
        return code
    except uc.UvmTrap as exc:
        return exc.code


# @method cell(m, addr) -> int
# @in    m: Machine — машина узла (снимок run_saved)
# @in    addr: int — адрес клетки в ОЗУ узла
# @out   value: int — значение клетки (8 байтов little-endian)
# @does  Читает клетку состояния гостя из ОЗУ узла по раскладке
# @does  раздела 5Б; кирпич проверки gpc.
def cell(m, addr):
    return int.from_bytes(m.ram[addr:addr + 8], "little")


class TestEmuDec(unittest.TestCase):
    """Подшаг 2: декодер, NOP и HALT, ловушка 6, паритет с эталоном."""

    # @method test_nops_then_halt() -> None
    # @in    нет
    # @out   нет
    # @does  Несколько NOP и HALT imm (SPEC/L4-SELFHOST.txt, раздел 5Б,
    # @does  подшаг 2): три NOP исполняются, HALT 42 останавливает — код
    # @does  42, вывод пуст; клетка gpc переведена за инструкцию HALT
    # @does  (3 * 1 + 9 = 12); код равен коду эталона.
    # @depends run, ref_code, cell, tk.image_of
    def test_nops_then_halt(self):
        image = tk.image_of([NOP, NOP, NOP, HALT, tk.imm64(42)])
        code, out, m = run(image)
        self.assertEqual((code, out), (42, b""))
        self.assertEqual(cell(m, GPC_ADDR), 12)
        self.assertEqual(ref_code(image), 42)

    # @method test_halt_values() -> None
    # @in    нет
    # @out   нет
    # @does  Код HALT — imm по модулю 256 (SPEC/L0-UVM.txt, разделы 3
    # @does  и 5): золотые значения imm64, 256 -> 0, 300 -> 44,
    # @does  2^64-1 -> 255; вывод пуст; коды равны кодам эталона.
    # @depends run, ref_code, tk.image_of
    def test_halt_values(self):
        for value in HALT_VALUES:
            with self.subTest(value=value):
                image = tk.image_of([HALT, tk.imm64(value)])
                code, out, m = run(image)
                self.assertEqual((code, out), (value % 256, b""))
                self.assertEqual(ref_code(image), value % 256)

    # @method test_halt_imm_byte_order() -> None
    # @in    нет
    # @out   нет
    # @does  Поле imm64 читается little-endian (SPEC/L0-UVM.txt, раздел
    # @does  4): HALT 0x0102 — байты 02 01 00 ... — даёт код 2;
    # @does  перепутанный порядок дал бы 0.
    # @depends run, tk.image_of
    def test_halt_imm_byte_order(self):
        image = tk.image_of([HALT, tk.imm64(0x0102)])
        code, out, m = run(image)
        self.assertEqual((code, out), (2, b""))

    # @method test_trap6_holes() -> None
    # @in    нет
    # @out   нет
    # @does  Коды вне шести диапазонов — навсегда ловушка 6 (SPEC/
    # @does  L0-UVM.txt, раздел 5): дыры между диапазонами и за таблицей
    # @does  дают код 6, вывод пуст; коды равны кодам эталона.
    # @depends run, ref_code, tk.image_of
    def test_trap6_holes(self):
        for opcode in HOLES:
            with self.subTest(opcode=hex(opcode)):
                image = tk.image_of([opcode])
                code, out, m = run(image)
                self.assertEqual((code, out), (6, b""))
                self.assertEqual(ref_code(image), 6)


if __name__ == "__main__":
    unittest.main()
