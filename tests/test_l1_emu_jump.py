# @uadro
# @file    tests/test_l1_emu_jump.py
# @layer   T0
# @branch  l1.uvm.emu
# @desc    Тесты подшага 6 ветви l1.uvm.emu — переходы и SYS-мост
# @desc    (src/l1/opsjump.ubrk, opssys.ubrk, tab.ubrk; SPEC/
# @desc    L4-SELFHOST.txt, раздел 5Б): JMP вперёд и назад (цикл с
# @desc    выводом), JZ/JNZ — переход и пропуск, CALL/RET с вложенными
# @desc    вызовами (снимки RS гостя по раскладке), ловушки 4/5 на RS,
# @desc    JMP/CALL за границу ОЗУ — ловушка 7 (покрытие выхода PC
# @desc    за ОЗУ из золотого набора), SYS 0 — признак конца ввода,
# @desc    SYS 1 — байты вывода (по модулю 256), SYS 2 — код завершения
# @desc    со стека, прочий номер — ловушка 8; ловушка 2 на пустом
# @desc    стеке условий и SYS 1/2; образ инструмента ниже буферов
# @desc    (контракт раскладки); паритет с эталоном на машине гостя.

"""Тесты подшага 6 ветви l1.uvm.emu (SPEC/L4-SELFHOST.txt, раздел 5Б).

Обработчики переходов (src/l1/opsjump.ubrk): JMP, JZ, JNZ, CALL, RET;
SYS-мост (src/l1/opssys.ubrk): SYS 0/1/2, ловушка 8. Снимки RS гостя
читаются по раскладке раздела 5Б: байты [grsbase, grsbase + grsp * 8).
Паритет: ref_state — код, стеки DS/RS (машина эталона строится здесь же
и не отбрасывается при ловушке), ref_out — код и байты вывода (эталон
на машине гостя с подменёнными stdin/stdout, как run_with_io).

Адреса в тестовых программах — абсолютные байты образа: инструкция
с imm64 занимает 9 байтов, без imm — 1 байт (SPEC/L0-UVM.txt, раздел 4).
"""

import contextlib
import os
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools import uvm_core as uc
from tools import uvm_run

GRS_BASE = 0x90800    # стек возвратов гостя в ОЗУ узла (раздел 5Б)
GDSP_ADDR = 0x90A08   # клетка gdsp — слов в DS гостя
GRSP_ADDR = 0x90A10   # клетка grsp — слов в RS гостя
GRAM_SIZE = 0x80000   # ОЗУ гостя — 512 КиБ
DS_WORDS = 256        # ёмкость DS гостя — слов (раздел 5Б)
RS_WORDS = 64         # ёмкость RS гостя — слов (раздел 5Б)
PUSH = 0x01           # опкоды групп «стек», «арифметика», «переходы»
DROP = 0x02           # и «система» (SPEC/L0-UVM.txt, разделы 4-6)
DUP = 0x03
ADD = 0x20
SUB = 0x21
JMP = 0x40
JZ = 0x41
JNZ = 0x42
CALL = 0x43
RET = 0x44
HALT = 0x45
SYS = 0x50
EOF_WORD = 2 ** 64 - 1  # признак конца ввода SYS 0 (SPEC, раздел 6)


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
# @out   triple: tuple — (код эталона, список слов DS, список слов RS)
# @does  Паритет с эталоном (SPEC/L4-SELFHOST.txt, раздел 5Б: машина
# @does  гостя — ОЗУ 512 КиБ, DS 256, RS 64, пустой stdin): машина
# @does  строится здесь же, чтобы при ловушке UvmTrap сохранить её
# @does  состояние — снимки стеков после ловушки сравниваются (CALL
# @does  за границу оставляет адрес возврата на RS, переполнение RS —
# @does  64 слова). Stdin эталона подменён пустым (patched_stdin — как
# @does  в run_with_io: гостевой SYS 0 читает EOF, а не настоящий
# @does  stdin процесса), stdout — заглушка без вывода наружу.
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
    return code, list(m.ds), list(m.rs)


# @method ref_out(image) -> tuple
# @in    image: bytes — образ гостя
# @out   pair: tuple — (код эталона, байты вывода эталона)
# @does  Паритет вывода: эталон исполняет образ гостя на машине гостя
# @does  с пустым stdin и подменённым stdout (как run_with_io
# @does  t0.infra.tests, но с размерами машины гостя из раздела 5Б);
# @does  пустой stdin обязателен — гостевой SYS 0 иначе читает
# @does  настоящий stdin процесса; кирпич проверок SYS 1 и циклов
# @does  с выводом.
# @depends tk.FakeStream, tk.patched_stdin, uc.Machine, uc.load_image,
# @depends uvm_run.run, uc.UvmTrap
# @uses   sys.stdin, sys.stdout — потоки хоста (подмена на время прогона)
def ref_out(image):
    out = tk.FakeStream()
    src = tk.FakeStream(b"")
    with contextlib.redirect_stdout(out):
        m = uc.Machine(ram_size=GRAM_SIZE, ds_size=DS_WORDS,
                       rs_size=RS_WORDS)
        uc.load_image(m, image)
        try:
            code = tk.patched_stdin(src, lambda: uvm_run.run(m))
        except uc.UvmTrap as exc:
            code = exc.code
    return code, out.buffer.getvalue()


# @method cell(m, addr) -> int
# @in    m: Machine — машина узла (снимок run_saved)
# @in    addr: int — адрес клетки в ОЗУ узла
# @out   value: int — значение клетки (8 байтов little-endian)
# @does  Читает клетку состояния гостя из ОЗУ узла по раскладке
# @does  раздела 5Б; кирпич проверок gdsp/grsp.
def cell(m, addr):
    return int.from_bytes(m.ram[addr:addr + 8], "little")


# @method rs_of(m) -> list
# @in    m: Machine — машина узла (снимок run_saved)
# @out   items: list — снимок RS гостя, нижнее слово первым
# @does  Читает снимок стека возвратов гостя по раскладке раздела 5Б:
# @does  байты [grsbase, grsbase + grsp * 8) словами little-endian;
# @does  кирпич проверок CALL/RET и ловушек 4/5.
# @depends cell
def rs_of(m):
    count = cell(m, GRSP_ADDR)
    return [int.from_bytes(m.ram[GRS_BASE + i * 8:GRS_BASE + i * 8 + 8],
                           "little") for i in range(count)]


# @method ds_of(m) -> list
# @in    m: Machine — машина узла (снимок run_saved)
# @out   items: list — снимок DS гостя, нижнее слово первым
# @does  Читает снимок стека данных гостя по раскладке раздела 5Б;
# @does  кирпич проверок значений после CALL/RET и SYS 0.
# @depends cell
def ds_of(m):
    base = 0x90000
    count = cell(m, GDSP_ADDR)
    return [int.from_bytes(m.ram[base + i * 8:base + i * 8 + 8],
                           "little") for i in range(count)]


class TestEmuJump(unittest.TestCase):
    """Подшаг 6: обработчики группы «переходы», ловушки 2/4/5/7."""

    # @method test_jmp_forward() -> None
    # @in    нет
    # @out   нет
    # @does  JMP вперёд пропускает HALT 7 (адрес 27 = 9 + 9 + 9: два
    # @does  PUSH/JMP по 9 байтов и пропускаемый HALT): код 0, DS = [42];
    # @does  код, снимок DS и снимок RS равны эталону.
    # @depends run, ref_state, ds_of, rs_of, tk.image_of, tk.imm64
    def test_jmp_forward(self):
        image = tk.image_of([PUSH, tk.imm64(42),
                             JMP, tk.imm64(27),
                             HALT, tk.imm64(7),
                             HALT, tk.imm64(0)])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [42])
        self.assertEqual(rs_of(m), [])
        self.assertEqual(ref_state(image), (0, [42], []))

    # @method test_jmp_back_loop() -> None
    # @in    нет
    # @out   нет
    # @does  JMP назад в цикле: счётчик 3, каждая итерация печатает 'A'
    # @does  (SYS 1) и уменьшает счётчик (PUSH 1, SUB), JNZ на метку 9
    # @does  (адрес после PUSH 3) повторяет, DROP и HALT 0 завершают —
    # @does  вывод b"AAA" доказывает ровно три итерации; вывод и код
    # @does  равны эталону (ref_out), стеки пусты.
    # @depends run, ref_state, ref_out, ds_of, rs_of, tk.image_of,
    # @depends tk.imm64
    def test_jmp_back_loop(self):
        image = tk.image_of([PUSH, tk.imm64(3),
                             PUSH, tk.imm64(65), SYS, tk.imm64(1),
                             PUSH, tk.imm64(1), SUB, DUP,
                             JNZ, tk.imm64(9),
                             DROP, HALT, tk.imm64(0)])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b"AAA"))
        self.assertEqual(ds_of(m), [])
        self.assertEqual(rs_of(m), [])
        self.assertEqual(ref_out(image), (0, b"AAA"))

    # @method test_jz_jnz() -> None
    # @in    нет
    # @out   нет
    # @does  JZ переходит при нулевом условии (код 0, HALT 7 пропущен),
    # @does  JNZ — при ненулевом; пропуск перехода ведёт на следующий
    # @does  HALT 3; условие снимается со стека в любом случае (DS пуст);
    # @does  коды и снимки равны эталону.
    # @depends run, ref_state, ds_of, tk.image_of, tk.imm64
    def test_jz_jnz(self):
        skip = 27  # адрес HALT 0: 9 + 9 + 9
        cases = [
            ([PUSH, tk.imm64(0), JZ, tk.imm64(skip),
              HALT, tk.imm64(7), HALT, tk.imm64(0)], 0),
            ([PUSH, tk.imm64(5), JZ, tk.imm64(skip),
              HALT, tk.imm64(3), HALT, tk.imm64(0)], 3),
            ([PUSH, tk.imm64(5), JNZ, tk.imm64(skip),
              HALT, tk.imm64(7), HALT, tk.imm64(0)], 0),
            ([PUSH, tk.imm64(0), JNZ, tk.imm64(skip),
              HALT, tk.imm64(3), HALT, tk.imm64(0)], 3),
        ]
        for parts, want in cases:
            with self.subTest(want=want):
                image = tk.image_of(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (want, b""))
                self.assertEqual(ds_of(m), [])
                self.assertEqual(ref_state(image), (want, [], []))

    # @method test_cond_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  JZ и JNZ на пустом стеке гостя — ловушка 2 (условие
    # @does  снимается прежде перехода, как op_jz/op_jnz эталона);
    # @does  коды равны кодам эталона.
    # @depends run, ref_state, tk.image_of, tk.imm64
    def test_cond_empty_traps(self):
        for opcode in (JZ, JNZ):
            with self.subTest(opcode=hex(opcode)):
                image = tk.image_of([opcode, tk.imm64(27),
                                     HALT, tk.imm64(0)])
                code, out, m = run(image)
                self.assertEqual((code, out), (2, b""))
                self.assertEqual(ref_state(image)[0], 2)

    # @method test_call_ret() -> None
    # @in    нет
    # @out   нет
    # @does  CALL 27 вызывает подпрограмму DUP ADD (адрес 27 = 9 + 9 + 9:
    # @does  PUSH, CALL, HALT), RET возвращается на HALT 0: удвоение 21
    # @does  -> 42, DS = [42], RS пуст (адрес возврата снят); код и стеки
    # @does  равны эталону.
    # @depends run, ref_state, ds_of, rs_of, tk.image_of, tk.imm64
    def test_call_ret(self):
        image = tk.image_of([PUSH, tk.imm64(21),
                             CALL, tk.imm64(27),
                             HALT, tk.imm64(0),
                             DUP, ADD, RET])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [42])
        self.assertEqual(rs_of(m), [])
        self.assertEqual(ref_state(image), (0, [42], []))

    # @method test_nested_calls() -> None
    # @in    нет
    # @out   нет
    # @does  Вложенные вызовы: main -> f (адрес 18) -> g (адрес 28),
    # @does  g кладёт 7 и возвращается, f возвращает, HALT 0: DS = [7],
    # @does  RS пуст — rpush/rpop сбалансированы на глубине 2; код
    # @does  и стеки равны эталону.
    # @depends run, ref_state, ds_of, rs_of, tk.image_of, tk.imm64
    def test_nested_calls(self):
        image = tk.image_of([CALL, tk.imm64(18),
                             HALT, tk.imm64(0),
                             CALL, tk.imm64(28), RET,
                             PUSH, tk.imm64(7), RET])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [7])
        self.assertEqual(rs_of(m), [])
        self.assertEqual(ref_state(image), (0, [7], []))

    # @method test_ret_empty_traps() -> None
    # @in    нет
    # @out   нет
    # @does  RET на пустом RS гостя — ловушка 4 (как rs_pop эталона
    # @does  в op_ret): код 4, вывод пуст; код равен коду эталона.
    # @depends run, ref_state, tk.image_of
    def test_ret_empty_traps(self):
        image = tk.image_of([RET])
        code, out, m = run(image)
        self.assertEqual((code, out), (4, b""))
        self.assertEqual(ref_state(image), (4, [], []))

    # @method test_rs_overflow_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Переполнение RS — ловушка 5: CALL 0 рекурсивно вызывает
    # @does  себя (адрес возврата 9 каждый раз), 65-й вызов при 64
    # @does  словах RS — код 5; снимок RS хранит ровно 64 слова [9],
    # @does  как у эталона (rs_push прежде PC).
    # @depends run, ref_state, rs_of, tk.image_of, tk.imm64
    def test_rs_overflow_traps(self):
        image = tk.image_of([CALL, tk.imm64(0)])
        code, out, m = run(image)
        self.assertEqual((code, out), (5, b""))
        self.assertEqual(rs_of(m), [9] * RS_WORDS)
        self.assertEqual(ref_state(image), (5, [], [9] * RS_WORDS))

    # @method test_jump_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Выход PC за ОЗУ — ловушка 7 (золотой набор, SPEC/
    # @does  L4-SELFHOST.txt, раздел 6): JMP на границу ОЗУ (0x80000)
    # @does  и на огромное слово (2^64-1) — следующий decode читает
    # @does  опкод вне ОЗУ гостя; коды равны кодам эталона.
    # @depends run, ref_state, tk.image_of, tk.imm64
    def test_jump_out_of_ram_traps(self):
        for addr in (GRAM_SIZE, 2 ** 64 - 1):
            with self.subTest(addr=addr):
                image = tk.image_of([JMP, tk.imm64(addr)])
                code, out, m = run(image)
                self.assertEqual((code, out), (7, b""))
                self.assertEqual(ref_state(image)[0], 7)

    # @method test_call_out_of_ram_traps() -> None
    # @in    нет
    # @out   нет
    # @does  CALL за границу ОЗУ: адрес возврата (9) уже на RS гостя,
    # @does  переход ловится следующим decode — ловушка 7; снимок RS
    # @does  хранит [9], как у эталона (rs_push прежде PC).
    # @depends run, ref_state, rs_of, tk.image_of, tk.imm64
    def test_call_out_of_ram_traps(self):
        image = tk.image_of([CALL, tk.imm64(GRAM_SIZE)])
        code, out, m = run(image)
        self.assertEqual((code, out), (7, b""))
        self.assertEqual(rs_of(m), [9])
        self.assertEqual(ref_state(image), (7, [], [9]))


class TestEmuSys(unittest.TestCase):
    """Подшаг 6: SYS-мост 0/1/2, ловушки 2/8, раскладка инструмента."""

    # @method test_sys0_eof() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 0 гостя всегда даёт признак конца ввода (SPEC/
    # @does  L4-SELFHOST.txt, раздел 5Б: stdin инструмента израсходован
    # @does  образом): слово 0xFFFFFFFFFFFFFFFF на DS гостя; снимок DS
    # @does  и код равны эталону с пустым stdin.
    # @depends run, ref_state, ds_of, tk.image_of, tk.imm64
    def test_sys0_eof(self):
        image = tk.image_of([SYS, tk.imm64(0), HALT, tk.imm64(0)])
        code, out, m = run(image)
        self.assertEqual((code, out), (0, b""))
        self.assertEqual(ds_of(m), [EOF_WORD])
        self.assertEqual(ref_state(image), (0, [EOF_WORD], []))

    # @method test_sys1_output() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 1 выводит байт по модулю 256 (SPEC/L0-UVM.txt, раздел
    # @does  6): 65 -> b"A", 0x141 -> b"A" (младший байт); слово снимается
    # @does  со стека (DS пуст); вывод и код равны эталону (ref_out).
    # @depends run, ref_state, ref_out, ds_of, tk.image_of, tk.imm64
    def test_sys1_output(self):
        for value, want in ((65, b"A"), (0x141, b"A")):
            with self.subTest(value=value):
                image = tk.image_of([PUSH, tk.imm64(value),
                                     SYS, tk.imm64(1),
                                     HALT, tk.imm64(0)])
                code, out, m = run(image)
                self.assertEqual((code, out), (0, want))
                self.assertEqual(ds_of(m), [])
                self.assertEqual(ref_out(image), (0, want))

    # @method test_sys2_exit_code() -> None
    # @in    нет
    # @out   нет
    # @does  SYS 2 завершает гостя кодом со стека по модулю 256 (SPEC/
    # @does  L0-UVM.txt, раздел 6): 42 -> код 42, 300 -> код 44; код
    # @does  снимается прежде остановки (DS пуст); коды и снимки равны
    # @does  эталону.
    # @depends run, ref_state, ds_of, tk.image_of, tk.imm64
    def test_sys2_exit_code(self):
        for value, want in ((42, 42), (300, 44)):
            with self.subTest(value=value):
                image = tk.image_of([PUSH, tk.imm64(value),
                                     SYS, tk.imm64(2)])
                code, out, m = run(image)
                self.assertEqual((code, out), (want, b""))
                self.assertEqual(ds_of(m), [])
                self.assertEqual(ref_state(image), (want, [], []))

    # @method test_sys_traps() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный номер SYS — ловушка 8 (SYS 9); SYS 1 и SYS 2
    # @does  на пустом стеке гостя — ловушка 2 (слово снимается прежде
    # @does  вывода/остановки, как op_sys эталона); коды равны кодам
    # @does  эталона.
    # @depends run, ref_state, tk.image_of, tk.imm64
    def test_sys_traps(self):
        cases = [
            ([SYS, tk.imm64(9), HALT, tk.imm64(0)], 8),
            ([SYS, tk.imm64(1), HALT, tk.imm64(0)], 2),
            ([SYS, tk.imm64(2), HALT, tk.imm64(0)], 2),
        ]
        for parts, want in cases:
            with self.subTest(want=want):
                image = tk.image_of(parts)
                code, out, m = run(image)
                self.assertEqual((code, out), (want, b""))
                self.assertEqual(ref_state(image)[0], want)

    # @method test_tool_image_below_buffers() -> None
    # @in    нет
    # @out   нет
    # @does  Контракт раскладки (SPEC/L4-SELFHOST.txt, раздел 5Б):
    # @does  собственный образ инструмента загружается с адреса 0
    # @does  и лежит ниже буферов — не длиннее 0x10000 байтов (иначе
    # @does  он наложился бы на ОЗУ гостя); рост эмулятора новыми
    # @does  группами обработчиков не должен нарушить раскладку.
    # @depends l1_image
    def test_tool_image_below_buffers(self):
        image = l1_image()
        self.assertIsNotNone(image)
        self.assertLessEqual(len(image), 0x10000)


if __name__ == "__main__":
    unittest.main()
