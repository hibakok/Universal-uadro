# @uadro
# @file    tests/test_l1_emu_gold.py
# @layer   T0
# @branch  l1.uvm.emu
# @desc    Подшаг 7 ветви l1.uvm.emu — золотой набор и закрытие ветви
# @desc    (SPEC/L4-SELFHOST.txt, разделы 5Б и 6): каждый опкод v0.1
# @desc    отдельной программой с известным эффектом — вывод байтами,
# @desc    стек — снимком DS/RS по раскладке раздела 5Б — и паритетом
# @desc    с эталоном (код, стеки, вывод); ловушки 1-8 — по короткой
# @desc    программе на каждую (выход PC за ОЗУ — JMP за границу);
# @desc    программы этапов 1-2 src/*.uasm на машине гостя — вывод,
# @desc    код завершения и стеки как у эталона; страховка полноты —
# @desc    счётные проверки набора (38 опкодов, 8 ловушек); TestProcess —
# @desc    сквозной прогон настоящим процессом: собственный эмулятор
# @desc    исполняет hello.uasm и печатает «Hi». Прогоном не покрыты
# @desc    (SPEC v0.9, раздел 6): пустой вход и NOP-горки до конца ОЗУ
# @desc    (сотни тысяч гостевых инструкций) и вход длиннее 512 КиБ —
# @desc    покрыт тестами подшага 1 (tests/test_l1_emu_mem.py, TestEmuMem).

"""Золотой набор эмулятора l1.uvm.emu (SPEC/L4-SELFHOST.txt, раздел 6;
подшаг 7 раздела 5Б — закрытие ветви).

Собственное воплощение эмулятора (src/l1/emu.ubrk с use-включениями,
образ — кирпич l1_image ветви tests/test_l1_emu_jump.py) исполняет каждый
вход золотого набора на машине гостя (ОЗУ 512 КиБ, DS 256, RS 64, пустой
stdin — раздел 5Б); снимки стеков гостя читаются по раскладке раздела 5Б
(кирпичи ds_of/rs_of той же ветви). Каждая программа имеет известный
эффект: код завершения, байты вывода и снимки DS/RS проверяются явно
и паритетом с эталоном (ref_state/ref_out — машина эталона тех же
размеров, stdin пустой, состояние при ловушке не отбрасывается).

Категории набора (раздел 6): 38 опкодов v0.1 — по программе на опкод
(OPCODE_CASES); ловушки 1-8 — по программе на ловушку (TRAP_CASES,
выход PC за ОЗУ — JMP на границу 0x80000); программы этапов 1-2 —
hello.uasm печатает «Hi», arith.uasm оставляет 20 на DS,
nested_calls.uasm печатает «!» и оставляет 111 и 222. Прогоном не
покрыты (SPEC v0.9, раздел 6): пустой вход и NOP-горки до конца ОЗУ
и вход длиннее 512 КиБ (код 7, вывод пуст) — покрыты тестами подшага 1
(tests/test_l1_emu_mem.py, TestEmuMem).

TestProcess — сквозной прогон настоящим процессом (разделы 5Б и 6):
ubrick_cli compile собирает собственный эмулятор, uvm_cli исполняет его
с входным файлом-образом hello (эталонная сборка src/hello.uasm) —
stdout «Hi», код процесса 0.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import test_l1_emu_jump as ej
from tests import uvm_testkit as tk
from tools.uasm_assemble import assemble
# Собственный эмулятор пишется под ISA v0.2 (SPEC/L4-SELFHOST.txt,
# раздел 2): опкоды — из кирпича isa_v02_table, а не из полной таблицы
# эталона (уже с DEVRD/DEVWR v0.3); собственному эмулятору они
# приходят подшагом 5.4 (ROADMAP.txt, Этап 5).
V02 = tk.isa_v02_table()                     # ISA v0.2 — 38 опкодов
OPCODE = {rec[1]: rec[0] for rec in V02}  # мнемоника -> код (раздел 5)
EOF_WORD = 2 ** 64 - 1                      # признак конца ввода SYS 0
GRAM_SIZE = 0x80000                         # ОЗУ гостя — 512 КиБ
DS_WORDS = 256                              # ёмкость DS гостя (раздел 5Б)
RS_WORDS = 64                               # ёмкость RS гостя (раздел 5Б)

# Каждый опкод v0.1 отдельно (SPEC, раздел 6): программа с известным
# эффектом — (мнемоника, части образа, код, снимок DS, байты вывода);
# адреса переходов — абсолютные байты образа (imm64 занимает 9 байтов).
SKIP = 27                                   # адрес HALT 0: 9 + 9 + 9
OPCODE_CASES = [
    ("NOP", [OPCODE["NOP"], OPCODE["HALT"], tk.imm64(0)], 0, [], b""),
    ("PUSH", [OPCODE["PUSH"], tk.imm64(7), OPCODE["HALT"], tk.imm64(0)],
     0, [7], b""),
    ("DROP", [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(2),
              OPCODE["DROP"], OPCODE["HALT"], tk.imm64(0)], 0, [1], b""),
    ("DUP", [OPCODE["PUSH"], tk.imm64(5), OPCODE["DUP"],
             OPCODE["HALT"], tk.imm64(0)], 0, [5, 5], b""),
    ("SWAP", [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(2),
              OPCODE["SWAP"], OPCODE["HALT"], tk.imm64(0)], 0, [2, 1], b""),
    ("OVER", [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(2),
              OPCODE["OVER"], OPCODE["HALT"], tk.imm64(0)],
     0, [1, 2, 1], b""),
    ("ROT", [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(2),
             OPCODE["PUSH"], tk.imm64(3), OPCODE["ROT"],
             OPCODE["HALT"], tk.imm64(0)], 0, [2, 3, 1], b""),
    ("PICK", [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(2),
              OPCODE["PICK"], tk.imm64(1), OPCODE["HALT"], tk.imm64(0)],
     0, [1, 2, 1], b""),
    ("LOAD8", [OPCODE["PUSH"], tk.imm64(65), OPCODE["PUSH"], tk.imm64(100),
               OPCODE["STORE8"], OPCODE["PUSH"], tk.imm64(100),
               OPCODE["LOAD8"], OPCODE["HALT"], tk.imm64(0)], 0, [65], b""),
    ("LOAD64", [OPCODE["PUSH"], tk.imm64(0x1122334455667788),
                OPCODE["PUSH"], tk.imm64(200), OPCODE["STORE64"],
                OPCODE["PUSH"], tk.imm64(200), OPCODE["LOAD64"],
                OPCODE["HALT"], tk.imm64(0)], 0, [0x1122334455667788], b""),
    ("STORE8", [OPCODE["PUSH"], tk.imm64(66), OPCODE["PUSH"], tk.imm64(101),
                OPCODE["STORE8"], OPCODE["PUSH"], tk.imm64(101),
                OPCODE["LOAD8"], OPCODE["HALT"], tk.imm64(0)], 0, [66], b""),
    ("STORE64", [OPCODE["PUSH"], tk.imm64(9), OPCODE["PUSH"], tk.imm64(202),
                 OPCODE["STORE64"], OPCODE["PUSH"], tk.imm64(202),
                 OPCODE["LOAD64"], OPCODE["HALT"], tk.imm64(0)], 0, [9], b""),
    ("ADD", [OPCODE["PUSH"], tk.imm64(20), OPCODE["PUSH"], tk.imm64(22),
             OPCODE["ADD"], OPCODE["HALT"], tk.imm64(0)], 0, [42], b""),
    ("SUB", [OPCODE["PUSH"], tk.imm64(42), OPCODE["PUSH"], tk.imm64(20),
             OPCODE["SUB"], OPCODE["HALT"], tk.imm64(0)], 0, [22], b""),
    ("MUL", [OPCODE["PUSH"], tk.imm64(6), OPCODE["PUSH"], tk.imm64(7),
             OPCODE["MUL"], OPCODE["HALT"], tk.imm64(0)], 0, [42], b""),
    ("UDIV", [OPCODE["PUSH"], tk.imm64(43), OPCODE["PUSH"], tk.imm64(5),
              OPCODE["UDIV"], OPCODE["HALT"], tk.imm64(0)], 0, [8], b""),
    ("UMOD", [OPCODE["PUSH"], tk.imm64(43), OPCODE["PUSH"], tk.imm64(5),
              OPCODE["UMOD"], OPCODE["HALT"], tk.imm64(0)], 0, [3], b""),
    ("NEG", [OPCODE["PUSH"], tk.imm64(5), OPCODE["NEG"],
             OPCODE["HALT"], tk.imm64(0)], 0, [2 ** 64 - 5], b""),
    ("SHL", [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(4),
             OPCODE["SHL"], OPCODE["HALT"], tk.imm64(0)], 0, [16], b""),
    ("SHR", [OPCODE["PUSH"], tk.imm64(0xF0), OPCODE["PUSH"], tk.imm64(4),
             OPCODE["SHR"], OPCODE["HALT"], tk.imm64(0)], 0, [0xF], b""),
    ("SAR", [OPCODE["PUSH"], tk.imm64(-16), OPCODE["PUSH"], tk.imm64(2),
             OPCODE["SAR"], OPCODE["HALT"], tk.imm64(0)],
     0, [2 ** 64 - 4], b""),
    ("AND", [OPCODE["PUSH"], tk.imm64(0b1100), OPCODE["PUSH"], tk.imm64(0b1010),
             OPCODE["AND"], OPCODE["HALT"], tk.imm64(0)], 0, [0b1000], b""),
    ("OR", [OPCODE["PUSH"], tk.imm64(0b1100), OPCODE["PUSH"], tk.imm64(0b1010),
            OPCODE["OR"], OPCODE["HALT"], tk.imm64(0)], 0, [0b1110], b""),
    ("XOR", [OPCODE["PUSH"], tk.imm64(0b1100), OPCODE["PUSH"], tk.imm64(0b1010),
             OPCODE["XOR"], OPCODE["HALT"], tk.imm64(0)], 0, [0b0110], b""),
    ("INV", [OPCODE["PUSH"], tk.imm64(0), OPCODE["INV"],
             OPCODE["HALT"], tk.imm64(0)], 0, [EOF_WORD], b""),
    ("EQ", [OPCODE["PUSH"], tk.imm64(5), OPCODE["PUSH"], tk.imm64(5),
            OPCODE["EQ"], OPCODE["HALT"], tk.imm64(0)], 0, [1], b""),
    ("NEQ", [OPCODE["PUSH"], tk.imm64(5), OPCODE["PUSH"], tk.imm64(6),
             OPCODE["NEQ"], OPCODE["HALT"], tk.imm64(0)], 0, [1], b""),
    ("LTU", [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(2),
             OPCODE["LTU"], OPCODE["HALT"], tk.imm64(0)], 0, [1], b""),
    ("GTU", [OPCODE["PUSH"], tk.imm64(2), OPCODE["PUSH"], tk.imm64(1),
             OPCODE["GTU"], OPCODE["HALT"], tk.imm64(0)], 0, [1], b""),
    ("LEU", [OPCODE["PUSH"], tk.imm64(2), OPCODE["PUSH"], tk.imm64(2),
             OPCODE["LEU"], OPCODE["HALT"], tk.imm64(0)], 0, [1], b""),
    ("GEU", [OPCODE["PUSH"], tk.imm64(2), OPCODE["PUSH"], tk.imm64(2),
             OPCODE["GEU"], OPCODE["HALT"], tk.imm64(0)], 0, [1], b""),
    ("JMP", [OPCODE["PUSH"], tk.imm64(42), OPCODE["JMP"], tk.imm64(SKIP),
             OPCODE["HALT"], tk.imm64(7), OPCODE["HALT"], tk.imm64(0)],
     0, [42], b""),
    ("JZ", [OPCODE["PUSH"], tk.imm64(0), OPCODE["JZ"], tk.imm64(SKIP),
            OPCODE["HALT"], tk.imm64(7), OPCODE["HALT"], tk.imm64(0)],
     0, [], b""),
    ("JNZ", [OPCODE["PUSH"], tk.imm64(5), OPCODE["JNZ"], tk.imm64(SKIP),
             OPCODE["HALT"], tk.imm64(7), OPCODE["HALT"], tk.imm64(0)],
     0, [], b""),
    ("CALL", [OPCODE["PUSH"], tk.imm64(21), OPCODE["CALL"], tk.imm64(SKIP),
              OPCODE["HALT"], tk.imm64(0), OPCODE["DUP"], OPCODE["ADD"],
              OPCODE["RET"]], 0, [42], b""),
    ("RET", [OPCODE["CALL"], tk.imm64(18), OPCODE["HALT"], tk.imm64(0),
             OPCODE["PUSH"], tk.imm64(7), OPCODE["RET"],
             OPCODE["HALT"], tk.imm64(3)], 0, [7], b""),
    ("HALT", [OPCODE["HALT"], tk.imm64(5)], 5, [], b""),
    ("SYS", [OPCODE["PUSH"], tk.imm64(65), OPCODE["SYS"], tk.imm64(1),
             OPCODE["HALT"], tk.imm64(0)], 0, [], b"A"),
]

# Ловушки 1-8 (SPEC, разделы 3 и 6): по короткой программе на каждую;
# выход PC за ОЗУ — JMP на границу ОЗУ, а не NOP-горка.
TRAP_CASES = [
    (1, [OPCODE["PUSH"], tk.imm64(1), OPCODE["PUSH"], tk.imm64(0),
         OPCODE["UDIV"], OPCODE["HALT"], tk.imm64(0)]),
    (2, [OPCODE["DROP"], OPCODE["HALT"], tk.imm64(0)]),
    (3, [OPCODE["PUSH"], tk.imm64(1)] * (DS_WORDS + 1)
         + [OPCODE["HALT"], tk.imm64(0)]),
    (4, [OPCODE["RET"], OPCODE["HALT"], tk.imm64(0)]),
    (5, [OPCODE["CALL"], tk.imm64(0)]),
    (6, [0x51, OPCODE["HALT"], tk.imm64(0)]),
    (7, [OPCODE["JMP"], tk.imm64(GRAM_SIZE)]),
    (8, [OPCODE["SYS"], tk.imm64(9), OPCODE["HALT"], tk.imm64(0)]),
]

# Программы этапов 1-2 (SPEC, раздел 6): имя, снимок DS, байты вывода.
STAGE12 = [
    ("hello.uasm", [], b"Hi"),
    ("arith.uasm", [20], b""),
    ("nested_calls.uasm", [111, 222], b"!"),
]


# @method src_path(name) -> str
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   path: str — путь к программе этапа 1-2
# @does  Строит путь к исходнику .uasm каталога src/; кирпич ref_image
# @does  и TestProcess.
def src_path(name):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "src", name)


# @method ref_image(name) -> bytes
# @in    name: str — имя программы этапа 1-2 в src/
# @out   image: bytes — образ программы, собранный эталонным ассемблером
# @does  Собирает src/<name> эталоном (tools/uasm_assemble.py, источник
# @does  истины поведения); ошибка сборки — ошибка теста.
# @depends assemble
def ref_image(name):
    with open(src_path(name), "r", encoding="utf-8") as handle:
        image, error = assemble(handle.read())
    assert error is None, (name, error)
    return image


# @method sys_python() -> str
# @in    нет
# @out   python: str — интерпретатор для запуска инструментов процессом
# @does  Даёт исполняемый файл Python, запустивший тесты.
# @uses   sys.executable — интерпретатор текущего процесса
def sys_python():
    return sys.executable


# @method tools_path(name) -> str
# @in    name: str — имя сценария в каталоге tools
# @out   path: str — путь к инструменту репозитория
# @does  Строит путь к сценарию инструментов для запуска процессом.
def tools_path(name):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "tools", name)


class TestGoldenSet(unittest.TestCase):
    """Золотой набор подшагом 7: известный эффект и паритет."""

    # @method test_each_opcode() -> None
    # @in    нет
    # @out   нет
    # @does  Каждый опкод v0.1 отдельной программой (SPEC, раздел 6):
    # @does  собственный эмулятор даёт известный эффект — код, байты
    # @does  вывода, снимки DS/RS — и паритет с эталоном (ref_state —
    # @does  код и стеки, ref_out — код и вывод).
    # @depends ej.run, ej.ref_state, ej.ref_out, ej.ds_of, ej.rs_of,
    # @depends tk.image_of, OPCODE_CASES
    def test_each_opcode(self):
        for name, parts, want_code, want_ds, want_out in OPCODE_CASES:
            with self.subTest(opcode=name):
                image = tk.image_of(parts)
                code, out, m = ej.run(image)
                self.assertEqual((code, out), (want_code, want_out))
                self.assertEqual(ej.ds_of(m), want_ds)
                self.assertEqual(ej.rs_of(m), [])
                self.assertEqual(ej.ref_state(image),
                                 (want_code, want_ds, []))
                self.assertEqual(ej.ref_out(image), (want_code, want_out))

    # @method test_trap_sweep() -> None
    # @in    нет
    # @out   нет
    # @does  Ловушки 1-8 (SPEC, разделы 3 и 6): по короткой программе
    # @does  на каждую — код ловушки, вывод пуст; коды равны кодам
    # @does  эталона (ref_state).
    # @depends ej.run, ej.ref_state, tk.image_of, TRAP_CASES
    def test_trap_sweep(self):
        for want, parts in TRAP_CASES:
            with self.subTest(trap=want):
                image = tk.image_of(parts)
                code, out, m = ej.run(image)
                self.assertEqual((code, out), (want, b""))
                self.assertEqual(ej.ref_state(image)[0], want)

    # @method test_stage12_programs() -> None
    # @in    нет
    # @out   нет
    # @does  Программы этапов 1-2 (SPEC, раздел 6): образы эталонной
    # @does  сборки исполняются собственным эмулятором — вывод, код
    # @does  завершения и стеки как у эталона (hello — «Hi», arith — 20
    # @does  на DS, nested_calls — «!» и 111/222 на DS).
    # @depends ej.run, ej.ref_state, ej.ref_out, ej.ds_of, ej.rs_of,
    # @depends ref_image, STAGE12
    def test_stage12_programs(self):
        for name, want_ds, want_out in STAGE12:
            with self.subTest(program=name):
                image = ref_image(name)
                code, out, m = ej.run(image)
                self.assertEqual((code, out), (0, want_out))
                self.assertEqual(ej.ds_of(m), want_ds)
                self.assertEqual(ej.rs_of(m), [])
                self.assertEqual(ej.ref_state(image), (0, want_ds, []))
                self.assertEqual(ej.ref_out(image), (0, want_out))

    # @method test_set_completeness() -> None
    # @in    нет
    # @out   нет
    # @does  Страховка полноты набора (SPEC, раздел 6): программы покрывают
    # @does  все 38 мнемоник ISA v0.2 без пропусков и повторов
    # @does  (кирпич isa_v02_table), ловушки — все коды 1-8.
    # @depends OPCODE_CASES, TRAP_CASES, V02
    def test_set_completeness(self):
        self.assertEqual(len(OPCODE_CASES), len(V02))
        self.assertEqual({row[0] for row in OPCODE_CASES},
                         {rec[1] for rec in V02})
        self.assertEqual([row[0] for row in TRAP_CASES], list(range(1, 9)))


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом (SPEC, разделы 5Б и 6)."""

    # @method test_process_pipeline() -> None
    # @in    нет
    # @out   нет
    # @does  Команды контракта настоящими процессами: ubrick_cli compile
    # @does  собирает собственный эмулятор, uvm_cli исполняет его с входным
    # @does  файлом-образом hello (эталонная сборка src/hello.uasm) —
    # @does  stdout «Hi», код процесса 0.
    # @depends ej.l1_source, ref_image, tools_path, sys_python
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool = os.path.join(tmp, "emu.uvm")
            guest = os.path.join(tmp, "hello.uvm")
            with open(guest, "wb") as handle:
                handle.write(ref_image("hello.uasm"))
            compile_code = subprocess.call(
                [sys_python(), tools_path("ubrick_cli.py"), "compile",
                 ej.l1_source(), tool],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(compile_code, 0)
            with open(guest, "rb") as handle:
                run = subprocess.run(
                    [sys_python(), tools_path("uvm_cli.py"), tool],
                    stdin=handle, capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(run.stdout, b"Hi")


if __name__ == "__main__":
    unittest.main()
