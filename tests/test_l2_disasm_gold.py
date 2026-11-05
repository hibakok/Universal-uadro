# @uadro
# @file    tests/test_l2_disasm_gold.py
# @layer   T0
# @branch  l2.uasm.disasm
# @desc    Подшаг 4 ветви l2.uasm.disasm — золотой набор и закрытие ветви:
# @desc    полный золотой набор SPEC/L4-SELFHOST.txt (раздел 6) одним
# @desc    файлом: пустой вход, каждый опкод v0.1 отдельно, обрывы поля
# @desc    imm64, хвосты данных, смешанные программы, образы программ
# @desc    этапов 1-2; для каждого золотого образа — вывод собственного
# @desc    дизассемблера равен эталону disasm байт в байт и раунд-трип
# @desc    assemble(disasm(B)) == B на собственном выводе; TestProcess —
# @desc    сквозной конвейер настоящими процессами.

"""Золотой набор дизассемблера l2.uasm.disasm (SPEC/L4-SELFHOST.txt,
раздел 6; подшаг 4 — закрытие ветви).

Собственное воплощение дизассемблера (src/l2/disasm.ubrk, образ —
кирпич l2_image) прогоняется кирпичом run_with_io на каждом образе
золотого набора. Производители образов — по категории набора (кирпичи
opcode_images, cut_images, tail_images, mixed_images, program_images,
сборка всего набора — golden_images). Для каждого золотого образа B:

- golden — вывод собственного дизассемблера равен выводу эталона disasm
  байт в байт, код завершения 0 (раздел 6: сверка с эталоном);
- roundtrip — assemble(disasm(B)) == B на собственном выводе; собирает
  Python-эталон (собственный ассемблер — ветвь 4 раздела 7 SPEC).

Категории набора (раздел 6): пустой вход; каждый опкод v0.1 отдельно
(30 без imm64 — байт опкода; 8 с imm64 — со значениями 0, 1, 12345,
2^64-1); обрыв imm64 — 0-7 байтов поля каждого imm-опкода; хвост
данных — 0x51 и 0xFF с 0-18 байтами после (длина короче восьми, ровно
восемь, смешанная); смешанные программы — инструкции обоих видов,
данные и дыра таблицы в конце; образы программ этапов 1-2 — собранные
эталонным ассемблером src/hello.uasm, src/arith.uasm,
src/nested_calls.uasm.

TestProcess — сквозной конвейер настоящими процессами: ubrick_cli
compile собирает собственный дизассемблер, uasm_cli asm собирает
src/hello.uasm, uvm_cli исполняет дизассемблер с входным файлом-образом;
stdout — «PUSH 72 / SYS 1 / PUSH 105 / SYS 1 / HALT 0», код 0.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools import uasm_assemble as am
from tools.uasm_disasm import disasm as ref_disasm
from tools.uvm_table import TABLE

NOIMM = [rec for rec in TABLE if not rec[3]]   # опкоды без поля imm64
IMM = [rec for rec in TABLE if rec[3]]         # опкоды с полем imm64
VALUES = (0, 1, 12345, 2 ** 64 - 1)            # золотые значения imm64
TAIL_OPS = (0x51, 0xFF)                        # неизвестные опкоды хвоста
TAIL_COUNTS = range(19)                        # длины хвоста 0-18
CUT_BYTE = 0x39                                # байт-заполнитель обрыва
PROGRAMS = ("hello.uasm", "arith.uasm", "nested_calls.uasm")


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для путей src/l2, src и запуска
# @does  инструментов настоящим процессом в TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method l2_source() -> str
# @in    нет
# @out   path: str — путь к исходнику src/l2/disasm.ubrk
# @does  Строит путь к собственному воплощению дизассемблера (слой L2,
# @does  SPEC/L4-SELFHOST.txt, раздел 3).
def l2_source():
    return os.path.join(repo_root(), "src", "l2", "disasm.ubrk")


# @method l2_image() -> bytes
# @in    нет
# @out   image: bytes — образ дизассемблера, собранный командой compile;
# @out   None — ошибка сборки (сообщение печатает cli в stderr)
# @does  Собирает src/l2/disasm.ubrk настоящей командой ubrick_cli
# @does  (режим compile, временный файл образа); кирпич всех тестов ветви.
# @depends ubrick_cli.main
# @uses   sys.stderr — стандартный вывод ошибок хоста (через cli)
def l2_image():
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "disasm.uvm")
        code = ubrick_cli.main(["compile", l2_source(), image])
        if code != 0:
            return None
        with open(image, "rb") as handle:
            return handle.read()


# @method src_path(name) -> str
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   path: str — путь к программе этапа 1-2
# @does  Строит путь к исходнику .uasm каталога src/.
def src_path(name):
    return os.path.join(repo_root(), "src", name)


# @method src_text(name) -> str
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   text: str — текст исходника в кодировке UTF-8
# @does  Читает исходник программы этапа 1-2 целиком; кирпич
# @does  program_images.
def src_text(name):
    with open(src_path(name), "r", encoding="utf-8") as handle:
        return handle.read()


# @method src_image(name) -> bytes
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   image: bytes — образ, собранный эталонным ассемблером
# @does  Собирает исходник .uasm эталонным ассемблером (t0.uasm.assemble,
# @does  SPEC/L4-SELFHOST.txt, раздел 6: образы программ этапов 1-2 —
# @does  собранные src/*.uasm); ошибка сборки — ошибка теста.
# @depends am.assemble, src_text
def src_image(name):
    image, error = am.assemble(src_text(name))
    assert error is None, (name, error)
    return image


# @method feed(image, data) -> tuple
# @in    image: bytes — образ дизассемблера
# @in    data: bytes — байты входа (дизассемблируемый образ)
# @out   pair: tuple — (код завершения, байты stdout)
# @does  Прогон образа без процесса с подменёнными stdin/stdout; кирпич
# @does  всех проверок ветви.
# @depends tk.run_with_io
def feed(image, data):
    return tk.run_with_io(image, data)


# @method golden(image, label, data) -> bytes
# @in    image: bytes — образ дизассемблера
# @in    label: str — имя золотого образа (сообщение при расхождении)
# @in    data: bytes — золотой образ B
# @out   out: bytes — вывод собственного дизассемблера на образе B
# @does  Сверка с эталоном (SPEC/L4-SELFHOST.txt, раздел 6): код
# @does  завершения 0 и вывод равен эталону disasm байт в байт;
# @does  кирпич check_golden.
# @depends feed, ref_disasm
def golden(image, label, data):
    code, out = feed(image, data)
    assert (code, out) == (0, ref_disasm(data).encode()), (
        label, code, out, ref_disasm(data).encode())
    return out


# @method roundtrip(text, label, data) -> None
# @in    text: str — текст uAsm — собственный вывод на образе B
# @in    label: str — имя золотого образа (сообщение при расхождении)
# @in    data: bytes — золотой образ B
# @out   нет (утверждение теста)
# @does  Раунд-трип на собственном выводе (SPEC, раздел 6):
# @does  assemble(disasm(B)) == B — текст собственного вывода собирается
# @does  эталонным ассемблером обратно в образ B; кирпич check_golden.
# @depends am.assemble
def roundtrip(text, label, data):
    again, error = am.assemble(text)
    assert error is None, (label, error)
    assert again == data, (label, again, data)


# @method check_golden(image, label, data) -> None
# @in    image: bytes — образ дизассемблера
# @in    label: str — имя золотого образа (сообщение при расхождении)
# @in    data: bytes — золотой образ B
# @out   нет (утверждения теста)
# @does  Составная проверка одного золотого образа: golden сверяет вывод
# @does  с эталоном и возвращает его, roundtrip собирает собственный
# @does  вывод обратно в образ; кирпич всех тестов набора.
# @depends golden, roundtrip
def check_golden(image, label, data):
    roundtrip(golden(image, label, data).decode(), label, data)


# @method opcode_images() -> list
# @in    нет
# @out   items: list — пары (имя, образ): каждый опкод v0.1 отдельно —
# @out   30 без imm64 байтом опкода, 8 с imm64 со значениями VALUES
# @does  Производитель образов «каждый опкод v0.1 отдельно» (SPEC,
# @does  раздел 6): без imm — байт опкода; с imm — опкод и поле imm64;
# @does  кирпич golden_images.
# @depends tk.imm64
def opcode_images():
    items = []
    for rec in NOIMM:
        items.append(("опкод " + rec[1], bytes([rec[0]])))
    for rec in IMM:
        for value in VALUES:
            items.append(("%s %d" % (rec[1], value),
                          bytes([rec[0]]) + tk.imm64(value)))
    return items


# @method cut_images() -> list
# @in    нет
# @out   items: list — пары (имя, образ): каждый imm-опкод с 0-7 байтами
# @out   поля imm64 в конце входа
# @does  Производитель образов «обрыв imm64» (SPEC, раздел 6): опкод
# @does  с imm в конце входа и 0-7 байтов поля; кирпич golden_images.
def cut_images():
    items = []
    for rec in IMM:
        for count in range(8):
            items.append(("обрыв %s %d" % (rec[1], count),
                          bytes([rec[0]]) + bytes([CUT_BYTE]) * count))
    return items


# @method tail_images() -> list
# @in    нет
# @out   items: list — пары (имя, образ): неизвестный опкод TAIL_OPS
# @out   с 0-18 байтами данных после
# @does  Производитель образов «хвост данных» (SPEC, раздел 6): длина
# @does  хвоста короче восьми, ровно восемь и смешанная; байты данных —
# @does  (i * 37 + 11) mod 256; кирпич golden_images.
def tail_images():
    items = []
    for opcode in TAIL_OPS:
        for count in TAIL_COUNTS:
            data = bytes([opcode]) + bytes(
                (i * 37 + 11) & 0xFF for i in range(count))
            items.append(("хвост 0x%02X %d" % (opcode, count), data))
    return items


# @method mixed_images() -> list
# @in    нет
# @out   items: list — пары (имя, образ): инструкции обоих видов,
# @out   данные и дыра таблицы в конце
# @does  Производитель образов «смешанные программы» (SPEC, раздел 6):
# @does  инструкции без imm64 и с imm64 потоком, вариант с данными
# @does  после останова и вариант с дырой таблицы (0x0A) в конце.
# @depends tk.imm64
def mixed_images():
    stream = (b"\x00\x01" + tk.imm64(12345) + b"\x13\x45"
              + tk.imm64(1))
    holed = (b"\x02\x03\x20\x2B\x44\x00\x07" + tk.imm64(12345)
             + b"\x30\x31\x0A")
    return [
        ("смешанный поток", stream),
        ("смешанный поток с данными", stream + b"\x51\x07\x08"),
        ("смешанная программа с дырой", holed),
    ]


# @method program_images() -> list
# @in    нет
# @out   items: list — пары (имя, образ): образы программ этапов 1-2,
# @out   собранные эталонным ассемблером из src/*.uasm
# @does  Производитель образов «образы программ этапов 1-2» (SPEC,
# @does  раздел 6): hello, arith, nested_calls; кирпич golden_images.
# @depends src_image
def program_images():
    return [("программа " + name, src_image(name)) for name in PROGRAMS]


# @method golden_images() -> list
# @in    нет
# @out   items: list — пары (имя, образ) — весь золотой набор раздела 6
# @out   SPEC/L4-SELFHOST.txt: пустой вход и все категории набора
# @does  Собирает золотой набор дизассемблера целиком: пустой вход,
# @does  опкоды, обрывы поля, хвосты данных, смешанные программы,
# @does  образы программ этапов 1-2; кирпич тестов золотого набора.
# @depends opcode_images, cut_images, tail_images, mixed_images,
# @depends program_images
def golden_images():
    return ([("пустой вход", b"")]
            + opcode_images() + cut_images() + tail_images()
            + mixed_images() + program_images())


class TestGoldenSet(unittest.TestCase):
    """Золотой набор подшагом 4: сверка с эталоном и раунд-трип."""

    # @method test_empty_input() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой вход — пустой вывод, код 0, раунд-трип пустого
    # @does  текста — пустой образ (SPEC, раздел 6).
    # @depends l2_image, check_golden
    def test_empty_input(self):
        check_golden(l2_image(), "пустой вход", b"")

    # @method test_opcodes_alone() -> None
    # @in    нет
    # @out   нет
    # @does  Каждый опкод v0.1 отдельно (SPEC, раздел 6): 30 без imm64 —
    # @does  байт опкода; 8 с imm64 — со значениями 0, 1, 12345,
    # @does  2^64-1; сверка с эталоном и раунд-трип на каждом.
    # @depends l2_image, check_golden, opcode_images
    def test_opcodes_alone(self):
        image = l2_image()
        for label, data in opcode_images():
            check_golden(image, label, data)

    # @method test_imm_cuts() -> None
    # @in    нет
    # @out   нет
    # @does  Обрыв поля imm64 (SPEC, раздел 6): каждый imm-опкод
    # @does  с 0-7 байтами поля в конце входа — останов декодирования
    # @does  с хвостом DB; сверка с эталоном и раунд-трип на каждом.
    # @depends l2_image, check_golden, cut_images
    def test_imm_cuts(self):
        image = l2_image()
        for label, data in cut_images():
            check_golden(image, label, data)

    # @method test_data_tails() -> None
    # @in    нет
    # @out   нет
    # @does  Хвост данных (SPEC, раздел 6): неизвестные опкоды 0x51,
    # @does  0xFF с 0-18 байтами данных — длина короче восьми, ровно
    # @does  восемь и смешанная; сверка с эталоном и раунд-трип.
    # @depends l2_image, check_golden, tail_images
    def test_data_tails(self):
        image = l2_image()
        for label, data in tail_images():
            check_golden(image, label, data)

    # @method test_mixed_programs() -> None
    # @in    нет
    # @out   нет
    # @does  Смешанные программы (SPEC, раздел 6): инструкции обоих
    # @does  видов, данные после останова и дыра таблицы в конце;
    # @does  сверка с эталоном и раунд-трип на каждой.
    # @depends l2_image, check_golden, mixed_images
    def test_mixed_programs(self):
        image = l2_image()
        for label, data in mixed_images():
            check_golden(image, label, data)

    # @method test_stage12_programs() -> None
    # @in    нет
    # @out   нет
    # @does  Образы программ этапов 1-2 (SPEC, раздел 6): hello.uasm,
    # @does  arith.uasm, nested_calls.uasm, собранные эталонным
    # @does  ассемблером; сверка с эталоном и раунд-трип на каждом.
    # @depends l2_image, check_golden, program_images
    def test_stage12_programs(self):
        image = l2_image()
        for label, data in program_images():
            check_golden(image, label, data)

    # @method test_whole_set_at_once() -> None
    # @in    нет
    # @out   нет
    # @does  Весь золотой набор одной проверкой (SPEC, раздел 6): каждый
    # @does  образ набора — golden_images; страховка полноты набора
    # @does  против потерь категорий при будущих правках.
    # @depends l2_image, check_golden, golden_images
    def test_whole_set_at_once(self):
        image = l2_image()
        items = golden_images()
        self.assertEqual(len(items), 1 + 30 + 32 + 64 + 38 + 3 + 3)
        for label, data in items:
            check_golden(image, label, data)


class TestProcess(unittest.TestCase):
    """Сквозной конвейер настоящими процессами (SPEC, разделы 5-6)."""

    # @method test_process_pipeline() -> None
    # @in    нет
    # @out   нет
    # @does  Полный конвейер документации настоящими процессами:
    # @does  ubrick_cli compile собирает собственный дизассемблер,
    # @does  uasm_cli asm собирает src/hello.uasm в образ, uvm_cli
    # @does  исполняет дизассемблер с входным файлом-образом; stdout —
    # @does  строки «PUSH 72 / SYS 1 / PUSH 105 / SYS 1 / HALT 0»,
    # @does  коды процессов 0.
    # @depends l2_source, src_path
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool = os.path.join(tmp, "disasm.uvm")
            prog = os.path.join(tmp, "hello.uvm")
            compile_code = subprocess.call(
                [sys_python(), tools_path("ubrick_cli.py"), "compile",
                 l2_source(), tool],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(compile_code, 0)
            asm_proc = subprocess.run(
                [sys_python(), tools_path("uasm_cli.py"), "asm",
                 src_path("hello.uasm"), prog],
                capture_output=True, timeout=60)
            self.assertEqual(asm_proc.returncode, 0)
            with open(prog, "rb") as handle:
                run = subprocess.run(
                    [sys_python(), tools_path("uvm_cli.py"), tool],
                    stdin=handle, capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(
            run.stdout,
            b"PUSH 72\nSYS 1\nPUSH 105\nSYS 1\nHALT 0\n")


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
# @depends repo_root
def tools_path(name):
    return os.path.join(repo_root(), "tools", name)


if __name__ == "__main__":
    unittest.main()
