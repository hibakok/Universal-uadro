# @uadro
# @file    tests/test_l1_emu_ops.py
# @layer   T0
# @branch  l1.uvm.emu
# @desc    Тесты подшагов 3-4 ветви l1.uvm.emu — стеки и память гостя
# @desc    (src/l1/mem.ubrk, opsstack.ubrk, opsmem.ubrk, tab.ubrk;
# @desc    SPEC/L4-SELFHOST.txt, раздел 5Б): обработчики группы «стек»
# @desc    целиком (PUSH/DROP/DUP/SWAP/OVER/ROT/PICK — снимок DS гостя
# @desc    по раскладке, ловушки 2/3 — пустой стек, глубина PICK вне
# @desc    стека, граница ёмкости 256/257 слов) и группы «память»
# @desc    (LOAD8/LOAD64/STORE8/STORE64 — байты ОЗУ гостя по раскладке,
# @desc    младший байт STORE8, расширение нулями LOAD8, порядок LE,
# @desc    ловушка 7: адрес и пересечение границы последним словом);
# @desc    паритет с эталоном на машине гостя (код, стек DS, байты ОЗУ).
# @desc    rpush/rpop (ловушки 4/5) прогоном не покрываются: guest-код
# @desc    не достигает RS без CALL/RET — покрывают подшаги 6-7.

"""Тесты подшагов 3-4 ветви l1.uvm.emu (SPEC/L4-SELFHOST.txt, раздел 5Б).

Кирпичи стеков гостя (src/l1/mem.ubrk): gpush/gpop/gpick (ловушки 2/3)
и rpush/rpop (ловушки 4/5); стеки гостя лежат в ОЗУ узла по раскладке
раздела 5Б — снимок DS читается байтами [gdsbase, gdsbase + gdsp * 8).
Обработчики группы «стек» (opsstack.ubrk): PUSH/DROP/DUP/SWAP/OVER/ROT/
PICK; группы «память» (opsmem.ubrk): LOAD8/LOAD64/STORE8/STORE64.

Каждая проверка сверяет код завершения и снимок DS собственного
эмулятора (кирпич run: run_saved, stdin — образ гостя) с ожиданием
и с эталоном на машине гостя (кирпич ref_state: uvm_run.run_image,
ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin — код, стек и байты ОЗУ).
"""

import os
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools import uvm_core as uc
from tools import uvm_run

GRAM_BASE = 0x10000   # ОЗУ гостя в ОЗУ узла (раздел 5Б)
GDS_BASE = 0x90000    # стек данных гостя в ОЗУ узла
GDSP_ADDR = 0x90A08   # клетка gdsp — слов в DS гостя
GRAM_SIZE = 0x80000   # ОЗУ гостя — 512 КиБ
PUSH = 0x01           # опкоды группы «стек» (SPEC/L0-UVM.txt, раздел 5)
DROP = 0x02
DUP = 0x03
SWAP = 0x04
OVER = 0x05
ROT = 0x06
PICK = 0x07
LOAD8 = 0x10          # опкоды группы «память»
LOAD64 = 0x11
STORE8 = 0x12
STORE64 = 0x13
HALT = 0x45           # опкод HALT imm
DS_WORDS = 256        # ёмкость DS гостя — слов (раздел 5Б)


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


# @method ref_state(image) -> tuple
# @in    image: bytes — образ гостя
# @out   pair: tuple — (код завершения эталона, список слов DS эталона)
# @does  Паритет с эталоном (SPEC/L4-SELFHOST.txt, раздел 5Б: машина
# @does  гостя — ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin): эталон
# @does  исполняет образ гостя; ловушка при загрузке даёт код ловушки
# @does  и пустой стек.
# @depends uvm_run.run_image, uc.UvmTrap
def ref_state(image):
    try:
        m, code = uvm_run.run_image(image, GRAM_SIZE, DS_WORDS, 64)
        return code, list(m.ds)
    except uc.UvmTrap as exc:
        return exc.code, []


# @method cell(m, addr) -> int
# @in    m: Machine — машина узла (снимок run_saved)
# @in    addr: int — адрес клетки в ОЗУ узла
# @out   value: int — значение клетки (8 байтов little-endian)
# @does  Читает клетку состояния гостя из ОЗУ узла по раскладке
# @does  раздела 5Б; кирпич проверки gdsp.
def cell(m, addr):
    return int.from_bytes(m.ram[addr:addr + 8], "little")


# @method ds_of(m) -> list
# @in    m: Machine — машина узла (снимок run_saved)
# @out   items: list — снимок DS гостя, нижнее слово первым
# @does  Читает снимок стека данных гостя по раскладке раздела 5Б:
# @does  байты [gdsbase, gdsbase + gdsp * 8) словами little-endian;
# @does  кирпич всех проверок подшага 3.
# @depends cell
def ds_of(m):
    count = cell(m, GDSP_ADDR)
    return [int.from_bytes(m.ram[GDS_BASE + i * 8:GDS_BASE + i * 8 + 8],
                           "little") for i in range(count)]


# @method prog(parts) -> bytes
# @in    parts: list — элементы образа до HALT 0
# @out   image: bytes — образ гостя с завершением HALT 0
# @does  Дописывает HALT 0 к элементам (image_of) — подавляющее
# @does  число проверок подшагов 3-4 оканчивается нормальной
# @does  остановкой; кирпич табличных проверок.
# @depends tk.image_of
def prog(parts):
    return tk.image_of(list(parts) + [HALT, tk.imm64(0)])


class TestEmuOpsStack(unittest.TestCase):
    """Подшаг 3: обработчики группы «стек», снимок DS, ловушки 2/3."""

    # @method test_push_snapshot() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH кладёт imm на DS гостя (SPEC/L0-UVM.txt, раздел 5):
    # @does  снимок после PUSH 11, PUSH 22, HALT 0 — [11, 22], клетка
    # @does  gdsp = 2, gpc за инструкцией HALT (2 * 9 + 9 = 27); вывод
    # @does  пуст; код и снимок DS равны эталону.
    # @depends run, ref_state, ds_of, cell, tk.image_of
    def test_push_snapshot(self):
        image = tk.image_of([PUSH, tk.imm64(11), PUSH, tk.imm64(22),
                             HALT, tk.imm64(0)])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [11, 22])
        self.assertEqual(cell(m, 0x90A00), 27)
        self.assertEqual(cell(m, GDSP_ADDR), 2)
        self.assertEqual(ref_state(image), (0, [11, 22]))

    # @method test_stack_words() -> None
    # @in    нет
    # @out   нет
    # @does  Обработчики группы «стек» дают эффект таблицы опкодов
    # @does  (SPEC/L0-UVM.txt, раздел 5): SWAP, ROT, DUP, OVER, DROP
    # @does  и PICK (0 = DUP, 1 = OVER, глубина imm) — снимок DS равен
    # @does  ожиданию и эталону.
    # @depends run, ref_state, ds_of, prog
    def test_stack_words(self):
        cases = [
            ([PUSH, tk.imm64(1), PUSH, tk.imm64(2), SWAP], [2, 1]),
            ([PUSH, tk.imm64(1), PUSH, tk.imm64(2), PUSH, tk.imm64(3),
              ROT], [2, 3, 1]),
            ([PUSH, tk.imm64(5), DUP], [5, 5]),
            ([PUSH, tk.imm64(1), PUSH, tk.imm64(2), OVER], [1, 2, 1]),
            ([PUSH, tk.imm64(1), PUSH, tk.imm64(2), PUSH, tk.imm64(3),
              DROP], [1, 2]),
            ([PUSH, tk.imm64(10), PUSH, tk.imm64(20), PUSH, tk.imm64(30),
              PICK, tk.imm64(1)], [10, 20, 30, 20]),
            ([PUSH, tk.imm64(10), PUSH, tk.imm64(20), PUSH, tk.imm64(30),
              PICK, tk.imm64(2)], [10, 20, 30, 10]),
        ]
        for parts, want in cases:
            with self.subTest(want=want):
                image = prog(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ds_of(m), want)
                self.assertEqual(ref_state(image), (0, want))

    # @method test_stack_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Ловушка 2 — опустошение DS гостя (SPEC/L0-UVM.txt, раздел
    # @does  3): DROP, DUP, OVER, ROT, SWAP и PICK на недостаточной
    # @does  глубине (0, 1, 2 слов) дают код 2, вывод пуст; коды равны
    # @does  кодам эталона.
    # @depends run, ref_state, prog, tk.image_of
    def test_stack_empty_traps(self):
        cases = [
            [DROP],
            [DUP],
            [PUSH, tk.imm64(1), SWAP],
            [PUSH, tk.imm64(1), OVER],
            [PUSH, tk.imm64(1), PUSH, tk.imm64(2), ROT],
            [PUSH, tk.imm64(1), PICK, tk.imm64(1)],
        ]
        for parts in cases:
            with self.subTest(parts=parts):
                image = prog(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (2, b""))
                self.assertEqual(ref_state(image)[0], 2)

    # @method test_pick_depth_out_of_stack() -> None
    # @in    нет
    # @out   нет
    # @does  Глубина PICK вне стека — ловушка 2 (ds_pick эталона):
    # @does  глубина 3 при двух словах и глубина 2^64-1 (сравнение
    # @does  беззнаковое, imm64 может быть любым словом) дают код 2;
    # @does  коды равны кодам эталона.
    # @depends run, ref_state, prog
    def test_pick_depth_out_of_stack(self):
        for depth in (3, 2 ** 64 - 1):
            with self.subTest(depth=depth):
                image = prog([PUSH, tk.imm64(1), PUSH, tk.imm64(2),
                              PICK, tk.imm64(depth)])
                code, out, m = run(image)
                self.assertEqual((code, out), (2, b""))
                self.assertEqual(ref_state(image)[0], 2)

    # @method test_ds_capacity_boundary() -> None
    # @in    нет
    # @out   нет
    # @does  Граница ёмкости DS гостя (раздел 5Б: 256 слов из раскладки
    # @does  gdsbase/gdslimit): 256 PUSH укладываются в стек целиком
    # @does  (снимок — 256 слов), 257-й — ловушка 3, снимок хранит
    # @does  ровно 256; коды и снимки равны эталону.
    # @depends run, ref_state, ds_of
    def test_ds_capacity_boundary(self):
        for count, want_code in ((DS_WORDS, 0), (DS_WORDS + 1, 3)):
            with self.subTest(count=count):
                image = tk.image_of([PUSH, tk.imm64(7)] * count
                                    + [HALT, tk.imm64(0)])
                code, out, m = run(image)
                self.assertEqual((code, out), (want_code, b""))
                self.assertEqual(ds_of(m), [7] * min(count, DS_WORDS))
                ref_code, ref_ds = ref_state(image)
                self.assertEqual(ref_code, want_code)
                self.assertEqual(ref_ds, [7] * min(count, DS_WORDS))


class TestEmuOpsMem(unittest.TestCase):
    """Подшаг 4: обработчики группы «память», байты ОЗУ, ловушка 7."""

    # @method test_store8_load8() -> None
    # @in    нет
    # @out   нет
    # @does  STORE8 пишет младший байт val (0x1FF -> 0xFF) в ОЗУ гостя
    # @does  по адресу addr, LOAD8 читает байт и расширяет нулями
    # @does  (0x80 -> 0x80, не знак): байты ОЗУ по раскладке равны
    # @does  ожиданию, снимки DS и коды равны эталону.
    # @depends run, ref_state, ds_of, prog
    def test_store8_load8(self):
        image = prog([PUSH, tk.imm64(0x1FF), PUSH, tk.imm64(100), STORE8,
                      PUSH, tk.imm64(0x80), PUSH, tk.imm64(101), STORE8,
                      PUSH, tk.imm64(100), LOAD8,
                      PUSH, tk.imm64(101), LOAD8])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [0xFF, 0x80])
        self.assertEqual(m.ram[GRAM_BASE + 100], 0xFF)
        self.assertEqual(m.ram[GRAM_BASE + 101], 0x80)
        ref_code, ref_ds = ref_state(image)
        self.assertEqual((ref_code, ref_ds), (0, [0xFF, 0x80]))

    # @method test_store64_load64() -> None
    # @in    нет
    # @out   нет
    # @does  STORE64 раскладывает слово в восемь байтов little-endian
    # @does  без требования выравнивания (адрес 0x123), LOAD64 собирает
    # @does  слово обратно: байты ОЗУ по раскладке равны LE-разложению,
    # @does  снимок DS и код равны эталону.
    # @depends run, ref_state, ds_of, prog
    def test_store64_load64(self):
        value = 0x1122334455667788
        image = prog([PUSH, tk.imm64(value), PUSH, tk.imm64(0x123),
                      STORE64, PUSH, tk.imm64(0x123), LOAD64])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [value])
        self.assertEqual(m.ram[GRAM_BASE + 0x123:GRAM_BASE + 0x123 + 8],
                         value.to_bytes(8, "little"))
        self.assertEqual(ref_state(image), (0, [value]))

    # @method test_memory_boundary_ok() -> None
    # @in    нет
    # @out   нет
    # @does  Последний байт ОЗУ гостя (0x7FFFF) читается LOAD8 и пишется
    # @does  STORE8, последнее полное слово (0x7FFF8) — LOAD64/STORE64:
    # @does  коды 0, ловушки нет (граница — «строго больше», как эталон);
    # @does  коды равны кодам эталона.
    # @depends run, ref_state, prog
    def test_memory_boundary_ok(self):
        cases = [
            [PUSH, tk.imm64(0x7FFFF), LOAD8],
            [PUSH, tk.imm64(0x7FFF8), LOAD64],
            [PUSH, tk.imm64(1), PUSH, tk.imm64(0x7FFFF), STORE8],
            [PUSH, tk.imm64(1), PUSH, tk.imm64(0x7FFF8), STORE64],
        ]
        for parts in cases:
            with self.subTest(parts=parts):
                image = prog(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ref_state(image)[0], 0)

    # @method test_memory_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Ловушка 7 — обращение вне ОЗУ гостя (SPEC/L0-UVM.txt,
    # @does  раздел 3): LOAD8/STORE8 по адресу 0x80000 и по огромному
    # @does  адресу 2^64-1 (проверка беззнаковая прежде сложения с базой),
    # @does  LOAD64/STORE64 с пересечением границы последним байтом
    # @does  (адрес 0x7FFFD/0x7FFFC) — код 7, вывод пуст; коды равны
    # @does  кодам эталона.
    # @depends run, ref_state, prog
    def test_memory_traps(self):
        cases = [
            [PUSH, tk.imm64(0x80000), LOAD8],
            [PUSH, tk.imm64(2 ** 64 - 1), LOAD8],
            [PUSH, tk.imm64(1), PUSH, tk.imm64(0x80000), STORE8],
            [PUSH, tk.imm64(1), PUSH, tk.imm64(2 ** 64 - 1), STORE8],
            [PUSH, tk.imm64(0x7FFFD), LOAD64],
            [PUSH, tk.imm64(1), PUSH, tk.imm64(0x7FFFC), STORE64],
        ]
        for parts in cases:
            with self.subTest(parts=parts):
                image = prog(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (7, b""))
                self.assertEqual(ref_state(image)[0], 7)

    # @method test_memory_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Ловушка 2 у обработчиков памяти: LOAD8 и STORE64 на пустом
    # @does  стеке гостя (STORE64 — одно слово вместо двух) дают код 2;
    # @does  коды равны кодам эталона.
    # @depends run, ref_state, prog
    def test_memory_empty_traps(self):
        for parts in ([LOAD8], [PUSH, tk.imm64(1), STORE64]):
            with self.subTest(parts=parts):
                image = prog(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (2, b""))
                self.assertEqual(ref_state(image)[0], 2)

    # @method test_mixed_program() -> None
    # @in    нет
    # @out   нет
    # @does  Смешанная программа стека и памяти: значение сохраняется
    # @does  в ОЗУ гостя, DUP и OVER комбинируются, слово читается
    # @does  обратно и снимается — снимок DS, байты ОЗУ и код равны
    # @does  эталону (полный паритет состояния).
    # @depends run, ref_state, ds_of, prog
    def test_mixed_program(self):
        image = prog([PUSH, tk.imm64(0xAA), PUSH, tk.imm64(0x200), STORE8,
                      PUSH, tk.imm64(0xBB), PUSH, tk.imm64(0x201), STORE8,
                      PUSH, tk.imm64(0x200), LOAD8, DUP,
                      PUSH, tk.imm64(0x201), LOAD8, OVER, ROT, DROP])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [0xAA, 0xBB, 0xAA])
        self.assertEqual(m.ram[GRAM_BASE + 0x200:GRAM_BASE + 0x202],
                         b"\xaa\xbb")
        self.assertEqual(ref_state(image), (0, [0xAA, 0xBB, 0xAA]))


if __name__ == "__main__":
    unittest.main()
