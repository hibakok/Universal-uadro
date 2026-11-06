# @uadro
# @file    tests/test_l1_emu_arith.py
# @layer   T0
# @branch  l1.uvm.emu
# @desc    Тесты подшага 5 ветви l1.uvm.emu — арифметика и сравнения
# @desc    (src/l1/opsarith.ubrk, opscmp.ubrk, tab.ubrk; SPEC/
# @desc    L4-SELFHOST.txt, раздел 5Б): обработчики группы «арифметика»
# @desc    целиком (ADD..INV — снимок DS гостя по раскладке, оборачивание
# @desc    по модулю 2^64, маска счётчика сдвигов 0..63, деление на ноль —
# @desc    ловушка 1: оба операнда уже сняты, как у эталона) и группы
# @desc    «сравнения» (EQ..GEU — флаги 1/0, беззнаковый порядок,
# @desc    граничные значения 0, 2^63, 2^64-1); ловушка 2 на пустом
# @desc    стеке; паритет с эталоном на машине гостя (код, стек DS —
# @desc    в том числе на ловушках: ref_state строит машину сам и не
# @desc    отбрасывает её состояние при UvmTrap).

"""Тесты подшага 5 ветви l1.uvm.emu (SPEC/L4-SELFHOST.txt, раздел 5Б).

Обработчики арифметики (src/l1/opsarith.ubrk): ADD, SUB, MUL, UDIV, UMOD,
NEG, SHL, SHR, SAR, AND, OR, XOR, INV; сравнения (src/l1/opscmp.ubrk):
EQ, NEQ, LTU, GTU, LEU, GEU. Каждая проверка сверяет код завершения
и снимок DS собственного эмулятора (кирпич run: run_saved, stdin — образ
гостя) с ожиданием и с эталоном на машине гостя (ref_state: машина
ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin; при ловушке состояние машины
сохраняется — снимок DS доступен и сравнивается).
"""

import contextlib
import os
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools import uvm_core as uc
from tools import uvm_run

GDS_BASE = 0x90000    # стек данных гостя в ОЗУ узла (раздел 5Б)
GDSP_ADDR = 0x90A08   # клетка gdsp — слов в DS гостя
GRAM_SIZE = 0x80000   # ОЗУ гостя — 512 КиБ
DS_WORDS = 256        # ёмкость DS гостя — слов (раздел 5Б)
RS_WORDS = 64         # ёмкость RS гостя — слов (раздел 5Б)
PUSH = 0x01           # опкоды групп «стек», «арифметика», «сравнения»
ADD = 0x20            # (SPEC/L0-UVM.txt, раздел 5)
SUB = 0x21
MUL = 0x22
UDIV = 0x23
UMOD = 0x24
NEG = 0x25
SHL = 0x26
SHR = 0x27
SAR = 0x28
AND = 0x29
OR = 0x2A
XOR = 0x2B
INV = 0x2C
EQ = 0x30
NEQ = 0x31
LTU = 0x32
GTU = 0x33
LEU = 0x34
GEU = 0x35
HALT = 0x45           # опкод HALT imm
WORD_MASK = 2 ** 64 - 1


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
# @does  гостя — ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin): машина
# @does  строится здесь же, чтобы при ловушке UvmTrap сохранить её
# @does  состояние — снимок DS после ловушки сравнивается, а не
# @does  отбрасывается (усиление кирпича ref_state test_l1_emu_ops.py:
# @does  у UDIV/UMOD оба операнда сняты до ловушки 1, как у эталона).
# @does  Stdin эталона подменён пустым (как run_with_io) — безопасно
# @does  по умолчанию для гостей с SYS 0: настоящий stdin процесса
# @does  иначе блокирует прогон на незакрытом терминале.
# @depends tk.FakeStream, tk.patched_stdin, uc.Machine, uc.load_image,
# @depends uvm_run.run, uc.UvmTrap
# @uses   sys.stdin, sys.stdout — потоки хоста (подмена на время прогона)
def ref_state(image):
    out = tk.FakeStream()
    with contextlib.redirect_stdout(out):
        m = uc.Machine(ram_size=GRAM_SIZE, ds_size=DS_WORDS,
                       rs_size=RS_WORDS)
        uc.load_image(m, image)
        src = tk.FakeStream(b"")
        try:
            code = tk.patched_stdin(src, lambda: uvm_run.run(m))
        except uc.UvmTrap as exc:
            code = exc.code
    return code, list(m.ds)


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
# @does  кирпич всех проверок подшага 5.
# @depends cell
def ds_of(m):
    count = cell(m, GDSP_ADDR)
    return [int.from_bytes(m.ram[GDS_BASE + i * 8:GDS_BASE + i * 8 + 8],
                           "little") for i in range(count)]


# @method prog(parts) -> bytes
# @in    parts: list — элементы образа до HALT 0
# @out   image: bytes — образ гостя с завершением HALT 0
# @does  Дописывает HALT 0 к элементам (image_of) — нормальная
# @does  остановка большинства проверок подшага 5; кирпич табличных
# @does  проверок.
# @depends tk.image_of
def prog(parts):
    return tk.image_of(list(parts) + [HALT, tk.imm64(0)])


# @method binop(opcode, a, b) -> bytes
# @in    opcode: int — опкод бинарной операции
# @in    a: int — первый операнд (кладётся глубже)
# @in    b: int — второй операнд (вершина)
# @out   image: bytes — образ гостя: PUSH a, PUSH b, opcode, HALT 0
# @does  Собирает программу одной бинарной операции с данными
# @does  операндами; кирпич табличных проверок арифметики и сравнений.
# @depends prog, tk.imm64
def binop(opcode, a, b):
    return prog([PUSH, tk.imm64(a), PUSH, tk.imm64(b), opcode])


class TestEmuArith(unittest.TestCase):
    """Подшаг 5: обработчики группы «арифметика», ловушки 1/2."""

    # @method test_binary_table() -> None
    # @in    нет
    # @out   нет
    # @does  Бинарные обработчики дают эффект таблицы опкодов (SPEC/
    # @does  L0-UVM.txt, раздел 5): ADD, SUB, MUL, UDIV, UMOD, SHL, SHR,
    # @does  SAR, AND, OR, XOR — снимок DS равен ожиданию и эталону
    # @does  (порядок операндов ( a b -- a?b ): a глубже, b вершина).
    # @depends run, ref_state, ds_of, binop
    def test_binary_table(self):
        cases = [
            (ADD, 7, 5, 12),
            (SUB, 7, 5, 2),
            (MUL, 6, 7, 42),
            (UDIV, 100, 7, 14),
            (UMOD, 100, 7, 2),
            (SHL, 1, 4, 16),
            (SHL, 3, 62, 3 << 62),
            (SHR, WORD_MASK, 1, 2 ** 63 - 1),
            (SAR, uc.to_word(-8), 1, uc.to_word(-4)),
            (AND, 0xF0F0, 0xFF00, 0xF000),
            (OR, 0xF0F0, 0x0F00, 0xFFF0),
            (XOR, 0xF0F0, 0xFF00, 0x0FF0),
        ]
        for opcode, a, b, want in cases:
            with self.subTest(opcode=hex(opcode)):
                image = binop(opcode, a, b)
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ds_of(m), [want])
                self.assertEqual(ref_state(image), (0, [want]))

    # @method test_wraparound() -> None
    # @in    нет
    # @out   нет
    # @does  Переполнения оборачиваются по модулю 2^64 (SPEC/L0-UVM.txt,
    # @does  раздел 1): ADD 2^64-1 + 1 -> 0, SUB 0 - 1 -> 2^64-1,
    # @does  SUB 5 - 7 -> 2^64-2, MUL 2^32 * 2^32 -> 0, NEG 5 -> 2^64-5,
    # @does  NEG 0 -> 0, INV 0 -> 2^64-1, INV 2^64-1 -> 0; снимки DS
    # @does  равны ожиданию и эталону.
    # @depends run, ref_state, ds_of, binop, prog
    def test_wraparound(self):
        binary = [
            (ADD, WORD_MASK, 1, 0),
            (SUB, 0, 1, WORD_MASK),
            (SUB, 5, 7, WORD_MASK - 1),
            (MUL, 2 ** 32, 2 ** 32, 0),
        ]
        unary = [
            (NEG, 5, WORD_MASK - 4),
            (NEG, 0, 0),
            (INV, 0, WORD_MASK),
            (INV, WORD_MASK, 0),
        ]
        for opcode, a, b, want in binary:
            with self.subTest(opcode=hex(opcode), a=a):
                image = binop(opcode, a, b)
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ds_of(m), [want])
                self.assertEqual(ref_state(image), (0, [want]))
        for opcode, a, want in unary:
            with self.subTest(opcode=hex(opcode), a=a):
                image = prog([PUSH, tk.imm64(a), opcode])
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ds_of(m), [want])
                self.assertEqual(ref_state(image), (0, [want]))

    # @method test_shift_count_mask() -> None
    # @in    нет
    # @out   нет
    # @does  Счётчик сдвига усекается до 0..63 (SPEC/L0-UVM.txt, раздел
    # @does  5): SHL 1 << 64 -> 1 (сдвиг на 0), SHL 1 << 65 -> 2,
    # @does  SHR 2^64-1 >> 64 -> 2^64-1, SAR -8 >> 65 -> -4 (сдвиг
    # @does  на 1); снимки DS равны ожиданию и эталону.
    # @depends run, ref_state, ds_of, binop
    def test_shift_count_mask(self):
        cases = [
            (SHL, 1, 64, 1),
            (SHL, 1, 65, 2),
            (SHR, WORD_MASK, 64, WORD_MASK),
            (SAR, uc.to_word(-8), 65, uc.to_word(-4)),
        ]
        for opcode, a, n, want in cases:
            with self.subTest(opcode=hex(opcode), n=n):
                image = binop(opcode, a, n)
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ds_of(m), [want])
                self.assertEqual(ref_state(image), (0, [want]))

    # @method test_div_by_zero_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Делитель 0 — ловушка 1 (SPEC/L0-UVM.txt, раздел 3): UDIV
    # @does  и UMOD с нулевым делителем (imm и вычисленным: 5 - 5) дают
    # @does  код 1, вывод пуст; оба операнда уже сняты со стека гостя —
    # @does  снимок DS пуст, как у эталона (ds_pop2 прежде trap).
    # @depends run, ref_state, ds_of, prog, binop
    def test_div_by_zero_traps(self):
        cases = [
            binop(UDIV, 5, 0),
            binop(UMOD, 5, 0),
            prog([PUSH, tk.imm64(9), PUSH, tk.imm64(5),
                  PUSH, tk.imm64(5), SUB, UDIV]),
        ]
        for image in cases:
            with self.subTest(image=image[:20]):
                code, out, m = run(image)
                self.assertEqual((code, out), (1, b""))
                self.assertEqual(ds_of(m), [])
                self.assertEqual(ref_state(image), (1, []))

    # @method test_arith_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Ловушка 2 — опустошение DS гостя: бинарные операции на пустом
    # @does  стеке и с одним словом (ADD, SUB, SHL, LTU-класс — порядок
    # @does  снятия тот же), унарные NEG и INV на пустом стеке дают код 2;
    # @does  коды равны кодам эталона.
    # @depends run, ref_state, prog
    def test_arith_empty_traps(self):
        cases = [
            [ADD],
            [SUB],
            [PUSH, tk.imm64(1), SUB],
            [SHL],
            [PUSH, tk.imm64(1), SHR],
            [NEG],
            [INV],
            [XOR],
            [PUSH, tk.imm64(1), AND],
        ]
        for parts in cases:
            with self.subTest(parts=parts):
                image = prog(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (2, b""))
                self.assertEqual(ref_state(image)[0], 2)


class TestEmuCmp(unittest.TestCase):
    """Подшаг 5: обработчики группы «сравнения», флаги 1/0."""

    # @method test_cmp_table() -> None
    # @in    нет
    # @out   нет
    # @does  Сравнения дают флаг 1/0 по таблице опкодов (SPEC/L0-UVM.txt,
    # @does  раздел 5): EQ/NEQ на равных и неравных, LTU/GTU/LEU/GEU
    # @does  на (3, 5), (5, 3) и (5, 5) — снимок DS равен ожиданию
    # @does  и эталону.
    # @depends run, ref_state, ds_of, binop
    def test_cmp_table(self):
        cases = [
            (EQ, 3, 5, 0),
            (EQ, 5, 5, 1),
            (NEQ, 3, 5, 1),
            (NEQ, 5, 5, 0),
            (LTU, 3, 5, 1),
            (LTU, 5, 3, 0),
            (LTU, 5, 5, 0),
            (GTU, 5, 3, 1),
            (GTU, 3, 5, 0),
            (LEU, 5, 5, 1),
            (LEU, 6, 5, 0),
            (GEU, 5, 5, 1),
            (GEU, 3, 5, 0),
        ]
        for opcode, a, b, want in cases:
            with self.subTest(opcode=hex(opcode), a=a, b=b):
                image = binop(opcode, a, b)
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ds_of(m), [want])
                self.assertEqual(ref_state(image), (0, [want]))

    # @method test_cmp_boundaries() -> None
    # @in    нет
    # @out   нет
    # @does  Граничные значения беззнакового порядка: 0 < 2^64-1,
    # @does  2^64-1 > 0, 2^63-1 < 2^63, 2^63 >= 2^63-1, 0 = 0 — флаги
    # @does  на краях диапазона слов; снимки DS равны ожиданию и эталону.
    # @depends run, ref_state, ds_of, binop
    def test_cmp_boundaries(self):
        cases = [
            (LTU, 0, WORD_MASK, 1),
            (LTU, WORD_MASK, 0, 0),
            (GTU, WORD_MASK, 0, 1),
            (LEU, 2 ** 63 - 1, 2 ** 63, 1),
            (GEU, 2 ** 63, 2 ** 63 - 1, 1),
            (EQ, 0, 0, 1),
        ]
        for opcode, a, b, want in cases:
            with self.subTest(opcode=hex(opcode), a=a, b=b):
                image = binop(opcode, a, b)
                code, out, m = run(image)
                self.assertEqual((code, out), (0, b""))
                self.assertEqual(ds_of(m), [want])
                self.assertEqual(ref_state(image), (0, [want]))


if __name__ == "__main__":
    unittest.main()
